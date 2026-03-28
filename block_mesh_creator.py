#!/usr/bin/env python3
"""
blockMeshDict Creator
PySide6 GUI for building OpenFOAM blockMeshDict files.

Features:
  - 3-D viewport with rotation / zoom / pan
  - Add / edit / delete vertices
  - Define hex blocks by clicking 8 vertices in sequence
  - Auto-detect boundary faces and generate patches
  - Manually assign / reassign faces between patches
  - Export blockMeshDict
  - Save / load project as JSON
"""
from __future__ import annotations

import sys
import math
import json
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QPushButton, QLineEdit, QSpinBox,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QComboBox, QCheckBox,
    QGroupBox, QFormLayout, QDialog, QDialogButtonBox, QTextEdit,
    QFileDialog, QMessageBox, QToolBar, QStatusBar, QScrollArea,
    QFrame, QSizePolicy, QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QTimer
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPolygon, QPolygonF, QFont,
    QPainterPath, QAction, QFontMetrics
)

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# OpenFOAM hex-block vertex layout:
#
#       7───────6
#      /│      /│
#     4─┼─────5 │
#     │ 3─────┼─2
#     │/      │/
#     0───────1
#
# Face vertex indices (local, 0-7) in right-hand-outward normal order
HEX_FACE_LOCAL = [
    (0, 4, 7, 3),   # 0  x-min
    (1, 2, 6, 5),   # 1  x-max
    (0, 1, 5, 4),   # 2  y-min
    (3, 7, 6, 2),   # 3  y-max
    (0, 3, 2, 1),   # 4  z-min
    (4, 5, 6, 7),   # 5  z-max
]
HEX_FACE_NAMES = ["x-min", "x-max", "y-min", "y-max", "z-min", "z-max"]

HEX_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),   # bottom ring
    (4, 5), (5, 6), (6, 7), (7, 4),   # top ring
    (0, 4), (1, 5), (2, 6), (3, 7),   # pillars
]

PATCH_TYPES = [
    "wall", "inlet", "outlet", "symmetry", "symmetryPlane",
    "empty", "cyclic", "patch", "wedge",
]

FACE_PALETTE = [
    "#e05252", "#52c0e0", "#52e07a", "#e0c052",
    "#c052e0", "#52e0c0", "#e08052", "#7a52e0",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  HEX VERTEX REORDERING  (any-click-order → OpenFOAM right-hand convention)
# ═══════════════════════════════════════════════════════════════════════════════
#
# OpenFOAM hex layout after reordering:
#
#       7───────6
#      /│      /│
#     4─┼─────5 │
#     │ 3─────┼─2
#     │/      │/
#     0───────1
#
# Requirements:
#   • 0-1-2-3  bottom face, RHR normal points INTO block (toward 4-5-6-7)
#   • 4-5-6-7  top face, same angular sense as bottom
#   • Pillar pairs: 0↔4, 1↔5, 2↔6, 3↔7
#
# Why PCA fails here:
#   A unit cube has covariance = 2·I, so power iteration converges to the body
#   diagonal [1/√3, 1/√3, 1/√3].  Projecting the 8 cube vertices onto that
#   diagonal gives groups {0,1,2,4} vs {3,5,6,7} — a tetrahedral split, not
#   two opposite faces.  The same degeneracy plagues any near-cubic hex.
#
# Correct strategy:
#   1. Try every C(8,4)=35 partition into candidate bottom/top groups.
#   2. Score each by how coplanar its two quads are (sum of squared distances
#      from best-fit plane).  The minimum-score split gives the two real faces.
#   3. Sort each face CCW so its RHR normal points from bottom toward top.
#   4. Cyclically rotate the top face so v4 is angularly closest to v0
#      (ensures correct 0↔4, 1↔5, 2↔6, 3↔7 pillar pairing).
# ─────────────────────────────────────────────────────────────────────────────

def _v3_sub(a: tuple, b: tuple) -> tuple:
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _v3_dot(a: tuple, b: tuple) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _v3_cross(a: tuple, b: tuple) -> tuple:
    return (a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])

def _v3_norm(a: tuple) -> tuple:
    mag = math.sqrt(_v3_dot(a, a))
    if mag < 1e-12:
        return (1.0, 0.0, 0.0)
    return (a[0]/mag, a[1]/mag, a[2]/mag)


def _face_planarity(pts4: list) -> float:
    """
    Planarity residual for 4 points: sum of squared distances from the
    best-fit plane.  Lower = more coplanar.  0 = perfectly planar.
    The plane normal is found via the cross product pair with the largest
    magnitude (most numerically stable for nearly-planar quads).
    """
    gc = tuple(sum(p[d] for p in pts4) / 4 for d in range(3))
    offs = [_v3_sub(p, gc) for p in pts4]
    best_mag2, best_n = 0.0, (1.0, 0.0, 0.0)
    for a in range(4):
        for b in range(a + 1, 4):
            c = _v3_cross(offs[a], offs[b])
            m = _v3_dot(c, c)
            if m > best_mag2:
                best_mag2, best_n = m, c
    if best_mag2 < 1e-24:
        return 0.0
    n = _v3_norm(best_n)
    return sum(_v3_dot(o, n) ** 2 for o in offs)


def _sort_quad_ccw(face_pts: list, face_idx: list,
                   cen: tuple, inward_normal: tuple):
    """
    Sort 4 face points/indices so their right-hand-rule normal aligns with
    inward_normal (i.e. points into the block for the bottom face).

    Returns (sorted_pts, sorted_idx) — both lists of length 4.

    Frame construction:
      right   = normalize(cross(inward_normal, arb))
      forward = normalize(cross(inward_normal, right))   # note: NOT cross(right, normal)
    With this choice cross(right, forward) = +inward_normal, so the frame
    (right, forward, inward_normal) is RIGHT-HANDED, and ascending atan2
    gives CCW order when viewed from the +inward_normal side — which is
    exactly what we want.
    """
    arb = (0.0, 0.0, 1.0) if abs(_v3_dot(inward_normal, (0, 0, 1))) < 0.9 \
          else (1.0, 0.0, 0.0)
    right   = _v3_norm(_v3_cross(inward_normal, arb))
    # cross(inward_normal, right) is perpendicular to both, completing RH frame
    forward = _v3_norm(_v3_cross(inward_normal, right))

    def angle(pt: tuple) -> float:
        lp = _v3_sub(pt, cen)
        return math.atan2(_v3_dot(lp, forward), _v3_dot(lp, right))

    order = sorted(range(4), key=lambda k: angle(face_pts[k]))
    sp = [face_pts[order[k]] for k in range(4)]
    si = [face_idx[order[k]] for k in range(4)]

    # Verify the winding is correct: cross(p1-p0, p2-p0) must align with
    # inward_normal.  If not, reverse vertices 1-3 to flip the winding while
    # keeping v0 fixed.
    v1 = _v3_sub(sp[1], sp[0])
    v2 = _v3_sub(sp[2], sp[0])
    if _v3_dot(_v3_cross(v1, v2), inward_normal) < 0:
        sp = [sp[0], sp[3], sp[2], sp[1]]
        si = [si[0], si[3], si[2], si[1]]

    return sp, si


def reorder_hex_vertices(indices: list, vertices: list) -> list:
    """
    Given 8 global vertex indices in any click order, return them reordered
    to the OpenFOAM hex right-hand-rule convention (positive volume).
    """
    pts = tuple((vertices[i].x, vertices[i].y, vertices[i].z)
                for i in indices)

    # ── Step 1: find the most coplanar bottom/top split ───────────────────────
    # Enumerate all C(8,4)=70 combinations; each unordered pair {A,B} appears
    # twice, so restrict to combinations whose first element is 0 → 35 unique.
    #
    # Sort key is a 2-tuple: (planarity_residual, -centroid_separation²).
    # This correctly handles the degenerate case of a perfect cube where BOTH
    # face-aligned cuts AND diagonal cuts of the cube are perfectly coplanar
    # (planarity=0).  Diagonal cuts have both face centroids at the body centre
    # (sep²=0), while axis-aligned cuts have sep²=edge_length²>0.  The
    # (-sep²) term ensures we always prefer the split with the largest gap
    # between the two opposing face centroids, which is the intended extrusion
    # direction.
    best_key  = (float("inf"), 0.0)
    best_bot: list = [0, 1, 2, 3]
    best_top: list = [4, 5, 6, 7]

    for bot in itertools.combinations(range(8), 4):
        if bot[0] != 0:          # skip duplicates
            continue
        top      = [k for k in range(8) if k not in bot]
        bot_pts4 = [pts[k] for k in bot]
        top_pts4 = [pts[k] for k in top]
        plan     = (_face_planarity(bot_pts4) + _face_planarity(top_pts4))
        bc4      = tuple(sum(p[d] for p in bot_pts4) / 4 for d in range(3))
        tc4      = tuple(sum(p[d] for p in top_pts4) / 4 for d in range(3))
        diff     = _v3_sub(tc4, bc4)
        sep2     = _v3_dot(diff, diff)
        key      = (plan, -sep2)          # minimise: low planarity, high sep
        if key < best_key:
            best_key = key
            best_bot = list(bot)
            best_top = top

    bot_pts = [pts[k]     for k in best_bot]
    top_pts = [pts[k]     for k in best_top]
    bot_idx = [indices[k] for k in best_bot]
    top_idx = [indices[k] for k in best_top]

    # ── Step 2: "up" = bottom-face centroid → top-face centroid ──────────────
    bc  = tuple(sum(p[d] for p in bot_pts) / 4 for d in range(3))
    tc  = tuple(sum(p[d] for p in top_pts) / 4 for d in range(3))
    up  = _v3_norm(_v3_sub(tc, bc))

    # ── Step 3: sort each face CCW (RHR normal = up = into block) ─────────────
    sorted_bot_pts, sorted_bot_idx = _sort_quad_ccw(bot_pts, bot_idx, bc, up)
    sorted_top_pts, sorted_top_idx = _sort_quad_ccw(top_pts, top_idx, tc, up)

    # ── Step 4: cyclically rotate top so v4 is angularly closest to v0 ────────
    # (ensures pillar pairing 0↔4, 1↔5, 2↔6, 3↔7 is geometrically correct)
    #
    # Re-use the same frame as _sort_quad_ccw so angles are consistent.
    arb2    = (0.0, 0.0, 1.0) if abs(_v3_dot(up, (0, 0, 1))) < 0.9 \
              else (1.0, 0.0, 0.0)
    right2  = _v3_norm(_v3_cross(up, arb2))
    fwd2    = _v3_norm(_v3_cross(up, right2))

    def fa(pt: tuple, cen: tuple) -> float:
        lp = _v3_sub(pt, cen)
        return math.atan2(_v3_dot(lp, fwd2), _v3_dot(lp, right2))

    def adiff(a: float, b: float) -> float:
        d = abs(a - b) % (2 * math.pi)
        return min(d, 2 * math.pi - d)

    b0_angle = fa(sorted_bot_pts[0], bc)
    t_angles = [fa(sorted_top_pts[k], tc) for k in range(4)]
    start    = min(range(4), key=lambda k: adiff(t_angles[k], b0_angle))

    final_top_idx = [sorted_top_idx[(start + k) % 4] for k in range(4)]

    return sorted_bot_idx + final_top_idx


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Vertex:
    x: float
    y: float
    z: float
    label: str = ""


@dataclass
class HexBlock:
    verts: List[int]                            # 8 global vertex indices
    cells: List[int] = field(default_factory=lambda: [10, 10, 10])
    grading: str = "simpleGrading (1 1 1)"
    label: str = ""


@dataclass
class BlockFaceRef:
    block_idx: int
    face_idx: int   # 0-5


@dataclass
class ArcEdge:
    """A circular arc edge defined by two endpoint vertex indices and a midpoint."""
    v0: int
    v1: int
    mid: Tuple[float, float, float]  # 3-D point on the arc


@dataclass
class SplineEdge:
    """A polySpline edge defined by two endpoint vertex indices and intermediate waypoints."""
    v0: int
    v1: int
    points: List[Tuple[float, float, float]]  # intermediate points along the spline


@dataclass
class Patch:
    name: str
    ptype: str = "wall"
    faces: List[BlockFaceRef] = field(default_factory=list)
    color: str = "#e05252"


class MeshModel:
    def __init__(self) -> None:
        self.vertices:         List[Vertex] = []
        self.blocks:           List[HexBlock] = []
        self.patches:          List[Patch] = []
        self.arc_edges:        List[ArcEdge] = []
        self.spline_edges:     List[SplineEdge] = []
        self.merge_pairs:      List[Tuple[str, str]] = []
        self.scale:            float = 1.0

    # ── serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "scale": self.scale,
            "vertices": [
                {"x": v.x, "y": v.y, "z": v.z, "label": v.label}
                for v in self.vertices
            ],
            "blocks": [
                {"verts": b.verts, "cells": b.cells,
                 "grading": b.grading, "label": b.label}
                for b in self.blocks
            ],
            "arc_edges": [
                {"v0": e.v0, "v1": e.v1, "mid": list(e.mid)}
                for e in self.arc_edges
            ],
            "spline_edges": [
                {"v0": e.v0, "v1": e.v1,
                 "points": [list(pt) for pt in e.points]}
                for e in self.spline_edges
            ],
            "patches": [
                {"name": p.name, "ptype": p.ptype, "color": p.color,
                 "faces": [{"block_idx": f.block_idx, "face_idx": f.face_idx}
                           for f in p.faces]}
                for p in self.patches
            ],
            "merge_pairs": [list(mp) for mp in self.merge_pairs],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MeshModel":
        m = cls()
        m.scale = d.get("scale", 1.0)
        m.vertices = [Vertex(**v) for v in d.get("vertices", [])]
        for b in d.get("blocks", []):
            m.blocks.append(HexBlock(**b))
        for e in d.get("arc_edges", []):
            m.arc_edges.append(ArcEdge(e["v0"], e["v1"], tuple(e["mid"])))
        for e in d.get("spline_edges", []):
            m.spline_edges.append(
                SplineEdge(e["v0"], e["v1"],
                           [tuple(pt) for pt in e["points"]]))
        for p in d.get("patches", []):
            patch = Patch(p["name"], p.get("ptype", "wall"),
                          [], p.get("color", "#e05252"))
            patch.faces = [BlockFaceRef(**f) for f in p.get("faces", [])]
            m.patches.append(patch)
        m.merge_pairs = [tuple(mp) for mp in d.get("merge_pairs", [])]
        return m

    # ── validation ───────────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Return a list of warning strings. Empty list = mesh looks OK."""
        warnings: List[str] = []

        if not self.vertices:
            warnings.append("No vertices defined.")
        if not self.blocks:
            warnings.append("No blocks defined.")
            return warnings

        # Duplicate vertex positions
        seen_pos: dict = {}
        for i, v in enumerate(self.vertices):
            key = (round(v.x, 9), round(v.y, 9), round(v.z, 9))
            if key in seen_pos:
                warnings.append(
                    f"Vertices {seen_pos[key]} and {i} share the same position {key}.")
            else:
                seen_pos[key] = i

        # Blocks referencing out-of-range vertices
        for bi, b in enumerate(self.blocks):
            for lv, gv in enumerate(b.verts):
                if gv >= len(self.vertices):
                    warnings.append(
                        f"Block {bi}: local vertex {lv} references non-existent "
                        f"global vertex {gv}.")

        # Unassigned boundary faces
        unassigned = self.unassigned_boundary_faces()
        if unassigned:
            warnings.append(
                f"{len(unassigned)} boundary face(s) are not assigned to any patch. "
                "OpenFOAM requires all boundary faces to be named.")

        # Patches with no faces
        for p in self.patches:
            if not p.faces:
                warnings.append(f'Patch "{p.name}" has no faces assigned.')

        # Arc edges referencing out-of-range vertices
        nv = len(self.vertices)
        for i, e in enumerate(self.arc_edges):
            if e.v0 >= nv or e.v1 >= nv:
                warnings.append(f"Arc edge {i}: vertex index out of range.")
        for i, e in enumerate(self.spline_edges):
            if e.v0 >= nv or e.v1 >= nv:
                warnings.append(f"Spline edge {i}: vertex index out of range.")
            if len(e.points) < 1:
                warnings.append(f"Spline edge {i}: needs at least 1 intermediate point.")

        return warnings

    # ── topology helpers ─────────────────────────────────────────────────────

    def _face_key(self, block_idx: int, face_idx: int) -> frozenset:
        b = self.blocks[block_idx]
        local = HEX_FACE_LOCAL[face_idx]
        return frozenset(b.verts[v] for v in local)

    def boundary_faces(self) -> List[Tuple[int, int]]:
        """Return (block_idx, face_idx) for every unshared face."""
        count: Dict[frozenset, List[Tuple[int, int]]] = {}
        for bi, block in enumerate(self.blocks):
            for fi in range(6):
                key = self._face_key(bi, fi)
                count.setdefault(key, []).append((bi, fi))
        return [lst[0] for lst in count.values() if len(lst) == 1]

    def assigned_face_keys(self) -> set:
        return {self._face_key(f.block_idx, f.face_idx)
                for p in self.patches for f in p.faces}

    def unassigned_boundary_faces(self) -> List[Tuple[int, int]]:
        assigned = self.assigned_face_keys()
        return [(bi, fi) for bi, fi in self.boundary_faces()
                if self._face_key(bi, fi) not in assigned]

    def auto_generate_patches(self) -> None:
        """Group boundary faces by face-index direction (0-5) → ≤6 patches."""
        groups: Dict[int, List[Tuple[int, int]]] = {}
        assigned = self.assigned_face_keys()
        for bi, fi in self.boundary_faces():
            if self._face_key(bi, fi) not in assigned:
                groups.setdefault(fi, []).append((bi, fi))

        used_names = {p.name for p in self.patches}
        color_idx = len(self.patches)
        for fi in sorted(groups):
            base = HEX_FACE_NAMES[fi].replace("-", "_")
            name = base
            suffix = 1
            while name in used_names:
                name = f"{base}_{suffix}"; suffix += 1
            patch = Patch(name, "wall", [],
                          FACE_PALETTE[color_idx % len(FACE_PALETTE)])
            for bi, _ in groups[fi]:
                patch.faces.append(BlockFaceRef(bi, fi))
            self.patches.append(patch)
            used_names.add(name)
            color_idx += 1

    # ── blockMeshDict export ─────────────────────────────────────────────────

    def to_blockMeshDict(self) -> str:
        lines: List[str] = []
        W = lines.append

        W("FoamFile"); W("{")
        W("    version     2.0;")
        W("    format      ascii;")
        W("    class       dictionary;")
        W("    object      blockMeshDict;")
        W("}"); W("")
        W("// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //")
        W(""); W(f"scale {self.scale};"); W("")

        W("vertices"); W("(")
        for i, v in enumerate(self.vertices):
            cmt = f"  // {i}" + (f" ({v.label})" if v.label else "")
            W(f"    ( {v.x}  {v.y}  {v.z} ){cmt}")
        W(");"); W("")

        W("blocks"); W("(")
        for i, b in enumerate(self.blocks):
            vs = " ".join(str(x) for x in b.verts)
            cs = " ".join(str(c) for c in b.cells)
            cmt = f"  // block {i}" + (f" {b.label}" if b.label else "")
            W(f"    hex ( {vs} ) ( {cs} ) {b.grading}{cmt}")
        W(");"); W("")

        W("edges"); W("(")
        for e in self.arc_edges:
            mx, my, mz = e.mid
            W(f"    arc {e.v0} {e.v1} ({mx} {my} {mz})")
        for e in self.spline_edges:
            W(f"    polyLine {e.v0} {e.v1}")
            W("    (")
            for px, py, pz in e.points:
                W(f"        ({px} {py} {pz})")
            W("    )")
        W(");"); W("")

        W("boundary"); W("(")
        for p in self.patches:
            W(f"    {p.name}"); W("    {")
            W(f"        type {p.ptype};")
            W("        faces"); W("        (")
            for ref in p.faces:
                b = self.blocks[ref.block_idx]
                local = HEX_FACE_LOCAL[ref.face_idx]
                gids = " ".join(str(b.verts[v]) for v in local)
                W(f"            ( {gids} )")
            W("        );"); W("    }"); W("")
        W(");"); W("")

        W("mergePatchPairs"); W("(")
        for a, b in self.merge_pairs:
            W(f"    ( {a}  {b} )")
        W(");"); W("")
        W("// *************************************************************** //")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOGS
# ═══════════════════════════════════════════════════════════════════════════════

class VertexDialog(QDialog):
    """Add or edit a single vertex."""

    def __init__(self, parent=None, vertex: Optional[Vertex] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Vertex" if vertex is None else "Edit Vertex")
        self.setFixedWidth(300)

        form = QFormLayout(self)

        # Use plain text fields so the "add" case starts completely blank.
        # On edit, pre-fill with the current values.
        self._x = QLineEdit("" if vertex is None else str(vertex.x))
        self._y = QLineEdit("" if vertex is None else str(vertex.y))
        self._z = QLineEdit("" if vertex is None else str(vertex.z))
        self._label = QLineEdit(vertex.label if vertex else "")

        for w in (self._x, self._y, self._z):
            w.setPlaceholderText("0.0")

        form.addRow("X:", self._x)
        form.addRow("Y:", self._y)
        form.addRow("Z:", self._z)
        form.addRow("Label:", self._label)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._try_accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _try_accept(self) -> None:
        for w in (self._x, self._y, self._z):
            text = w.text().strip()
            try:
                float(text) if text else 0.0
            except ValueError:
                w.setStyleSheet("border: 1px solid #e05252;")
                w.setFocus()
                return
            w.setStyleSheet("")
        self.accept()

    def get_vertex(self) -> Vertex:
        def _f(w: QLineEdit) -> float:
            t = w.text().strip()
            return float(t) if t else 0.0
        return Vertex(_f(self._x), _f(self._y), _f(self._z),
                      self._label.text().strip())


class BlockDialog(QDialog):
    """Edit block cell counts, grading, and label."""

    def __init__(self, parent=None, block: Optional[HexBlock] = None):
        super().__init__(parent)
        self.setWindowTitle("Block Properties")
        self.setFixedWidth(360)

        form = QFormLayout(self)
        cells = block.cells if block else [10, 10, 10]
        self._nx = QSpinBox(minimum=1, maximum=10000, value=cells[0])
        self._ny = QSpinBox(minimum=1, maximum=10000, value=cells[1])
        self._nz = QSpinBox(minimum=1, maximum=10000, value=cells[2])
        self._grading = QLineEdit(block.grading if block else "simpleGrading (1 1 1)")
        self._label = QLineEdit(block.label if block else "")

        form.addRow("Cells X:", self._nx)
        form.addRow("Cells Y:", self._ny)
        form.addRow("Cells Z:", self._nz)
        form.addRow("Grading:", self._grading)
        form.addRow("Label:", self._label)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def apply_to(self, block: HexBlock) -> None:
        block.cells = [self._nx.value(), self._ny.value(), self._nz.value()]
        block.grading = self._grading.text().strip() or "simpleGrading (1 1 1)"
        block.label   = self._label.text().strip()


class PatchDialog(QDialog):
    """Add or edit a patch."""

    def __init__(self, parent=None, patch: Optional[Patch] = None):
        super().__init__(parent)
        self.setWindowTitle("Patch" if patch is None else "Edit Patch")
        self.setFixedWidth(300)

        form = QFormLayout(self)
        self._name  = QLineEdit(patch.name if patch else "patch1")
        self._ptype = QComboBox()
        self._ptype.addItems(PATCH_TYPES)
        if patch:
            idx = self._ptype.findText(patch.ptype)
            if idx >= 0:
                self._ptype.setCurrentIndex(idx)

        form.addRow("Name:", self._name)
        form.addRow("Type:", self._ptype)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def get_values(self) -> Tuple[str, str]:
        return self._name.text().strip(), self._ptype.currentText()


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_SELECT   = "select"
TOOL_VERTEX   = "add_vertex"
TOOL_BLOCK    = "add_block"
TOOL_EDGE     = "add_edge"
TOOL_PATCH    = "paint_patch"


# ═══════════════════════════════════════════════════════════════════════════════
#  3-D VIEWPORT
# ═══════════════════════════════════════════════════════════════════════════════

class Viewport3D(QWidget):
    """
    Orthographic 3-D viewport.

    Tools
    ─────
    select      : hover + click vertex or face; emits vertex_clicked / face_clicked
    add_vertex  : no click interaction (inspector handles the form)
    add_block   : sequentially click 8 vertices → emits vertex_clicked
    add_edge    : click 2 vertices → emits vertex_clicked
    paint_patch : click boundary face → emits face_clicked

    Navigation (always active):
      Rotate     left-drag
      Pan        middle-drag | Ctrl+left-drag
      Zoom       scroll wheel
    """

    vertex_clicked = Signal(int)          # global vertex index
    face_clicked   = Signal(int, int)     # block_idx, face_idx
    hover_changed  = Signal(str)          # status bar message

    def __init__(self, mesh: MeshModel, parent=None):
        super().__init__(parent)
        self.mesh = mesh
        self.setMinimumSize(500, 450)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Camera
        self._az    = 35.0
        self._el    = 25.0
        self._zoom  = 80.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        # Interaction
        self._last_pos: Optional[QPoint] = None
        self._panning   = False

        # Tool state
        self.tool = TOOL_SELECT
        self.block_pending: List[int] = []   # vertices collected for add_block
        self.edge_v0: int = -1               # first vertex for add_edge

        # Selection / highlight
        self.selected_vertex: int = -1
        self.selected_face:   Optional[Tuple[int, int]] = None
        self.selected_patch_idx: int = -1   # patch brush (paint_patch tool)
        self.highlight_verts: List[int] = []      # gold highlight (from outliner)
        self.highlight_faces: List[Tuple[int, int]] = []  # gold faces (from list)

        self.hovered_vert:  int = -1
        self.hovered_face:  Optional[Tuple[int, int]] = None

        # Display toggles
        self.show_axes             = True
        self.show_labels           = True
        self.show_block_labels     = True
        self.show_face_patch_labels = False
        self.show_internal_edges   = True
        self.show_normals          = False

    # ── projection ───────────────────────────────────────────────────────────

    def _project(self, x, y, z):
        az = math.radians(self._az); el = math.radians(self._el)
        caz, saz = math.cos(az), math.sin(az)
        cel, sel = math.cos(el), math.sin(el)
        rx = x*caz - y*saz; ry = x*saz + y*caz
        sx = rx; sy = ry*cel - z*sel; sz = ry*sel + z*cel
        px = self.width()/2 + self._pan_x + sx*self._zoom
        py = self.height()/2 + self._pan_y - sz*self._zoom
        return px, py, sy

    def _project_vertex(self, idx):
        v = self.mesh.vertices[idx]
        return self._project(v.x, v.y, v.z)

    def _face_screen_poly(self, bi, fi):
        b = self.mesh.blocks[bi]; pts = []
        for lv in HEX_FACE_LOCAL[fi]:
            gv = b.verts[lv]
            if gv >= len(self.mesh.vertices): return []
            px, py, _ = self._project_vertex(gv)
            pts.append((px, py))
        return pts

    @staticmethod
    def _pip(px, py, poly):
        n = len(poly); inside = False; j = n-1
        for i in range(n):
            xi, yi = poly[i]; xj, yj = poly[j]
            if ((yi>py) != (yj>py)) and (px < (xj-xi)*(py-yi)/(yj-yi+1e-12)+xi):
                inside = not inside
            j = i
        return inside

    def _nearest_vertex(self, pos, max_d=16):
        best, bd2 = -1, max_d*max_d
        for i in range(len(self.mesh.vertices)):
            px, py, _ = self._project_vertex(i)
            d2 = (px-pos.x())**2 + (py-pos.y())**2
            if d2 < bd2: bd2=d2; best=i
        return best

    def _nearest_boundary_face(self, pos):
        hits = []
        for bi, fi in self.mesh.boundary_faces():
            poly = self._face_screen_poly(bi, fi)
            if poly and self._pip(pos.x(), pos.y(), poly):
                depth = sum(pt[1] for pt in poly)/len(poly)
                hits.append((depth, bi, fi))
        if hits:
            hits.sort(); return hits[0][1], hits[0][2]
        return None

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0, 0, self.width(), self.height(), QColor(18, 22, 35))
        if self.show_axes:         self._draw_axes(p)
        self._draw_grid(p)
        self._draw_patch_faces(p)
        self._draw_block_edges(p)
        self._draw_curved_edges(p)
        if self.show_internal_edges: self._draw_internal_edges(p)
        self._draw_vertices(p)
        if self.show_block_labels:     self._draw_block_labels(p)
        if self.show_face_patch_labels: self._draw_face_patch_labels(p)
        if self.show_normals:          self._draw_face_normals(p)
        self._draw_tool_overlay(p)

    def _draw_axes(self, p):
        ox, oy, _ = self._project(0,0,0)
        for ax,ay,az,col,lbl in [(1,0,0,QColor(220,80,80),"X"),
                                  (0,1,0,QColor(80,200,100),"Y"),
                                  (0,0,1,QColor(80,140,220),"Z")]:
            ex,ey,_ = self._project(ax*.6, ay*.6, az*.6)
            p.setPen(QPen(col,2)); p.drawLine(int(ox),int(oy),int(ex),int(ey))
            p.setPen(col); p.setFont(QFont("Consolas",9,QFont.Bold))
            p.drawText(int(ex)+4, int(ey)+4, lbl)

    def _draw_grid(self, p):
        p.setPen(QPen(QColor(50,55,70),1,Qt.DotLine))
        for i in range(-5, 6):
            x1,y1,_ = self._project(-5,i,0); x2,y2,_ = self._project(5,i,0)
            p.drawLine(int(x1),int(y1),int(x2),int(y2))
            x1,y1,_ = self._project(i,-5,0); x2,y2,_ = self._project(i,5,0)
            p.drawLine(int(x1),int(y1),int(x2),int(y2))

    def _draw_block_edges(self, p):
        HEX_EDGES = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                     (0,4),(1,5),(2,6),(3,7)]
        for block in self.mesh.blocks:
            if len(block.verts) != 8: continue
            pts2d = []; valid = True
            for gv in block.verts:
                if gv >= len(self.mesh.vertices): valid=False; break
                pts2d.append(self._project_vertex(gv))
            if not valid: continue
            p.setPen(QPen(QColor(100,180,255),1.5))
            for i,j in HEX_EDGES:
                p.drawLine(int(pts2d[i][0]),int(pts2d[i][1]),
                           int(pts2d[j][0]),int(pts2d[j][1]))

    def _draw_curved_edges(self, p):
        nv = len(self.mesh.vertices)
        p.setPen(QPen(QColor(255,200,80,220),2.0))
        for e in self.mesh.arc_edges:
            if e.v0>=nv or e.v1>=nv: continue
            x0,y0,_ = self._project_vertex(e.v0)
            x1,y1,_ = self._project_vertex(e.v1)
            mx,my,_ = self._project(*e.mid)
            pcx = 2*mx - .5*(x0+x1); pcy = 2*my - .5*(y0+y1)
            path = QPainterPath(); path.moveTo(x0,y0)
            for k in range(1,21):
                t=k/20
                bx=(1-t)**2*x0+2*(1-t)*t*pcx+t**2*x1
                by=(1-t)**2*y0+2*(1-t)*t*pcy+t**2*y1
                path.lineTo(bx,by)
            p.drawPath(path)
        p.setPen(QPen(QColor(100,220,255,220),2.0,Qt.DashLine))
        for e in self.mesh.spline_edges:
            if e.v0>=nv or e.v1>=nv or not e.points: continue
            x0,y0,_ = self._project_vertex(e.v0)
            chain=[(x0,y0)]
            for px,py,pz in e.points:
                sx,sy,_ = self._project(px,py,pz); chain.append((sx,sy))
            x1,y1,_ = self._project_vertex(e.v1); chain.append((x1,y1))
            for i in range(len(chain)-1):
                p.drawLine(int(chain[i][0]),int(chain[i][1]),
                           int(chain[i+1][0]),int(chain[i+1][1]))

    def _draw_internal_edges(self, p):
        if len(self.mesh.blocks) < 2: return
        face_count: Dict[frozenset,int] = {}
        for block in self.mesh.blocks:
            for fi in range(6):
                key = frozenset(block.verts[lv] for lv in HEX_FACE_LOCAL[fi])
                face_count[key] = face_count.get(key,0)+1
        internal = {k for k,c in face_count.items() if c>1}
        edges: set = set()
        for block in self.mesh.blocks:
            for fi in range(6):
                fkey = frozenset(block.verts[lv] for lv in HEX_FACE_LOCAL[fi])
                if fkey in internal:
                    fv = [block.verts[lv] for lv in HEX_FACE_LOCAL[fi]]
                    for k in range(4):
                        a,b = fv[k],fv[(k+1)%4]
                        edges.add((min(a,b),max(a,b)))
        p.setPen(QPen(QColor(180,130,255,140),1.5,Qt.DashLine))
        for a,b in edges:
            if a>=len(self.mesh.vertices) or b>=len(self.mesh.vertices): continue
            ax,ay,_ = self._project_vertex(a); bx,by,_ = self._project_vertex(b)
            p.drawLine(int(ax),int(ay),int(bx),int(by))

    def _draw_patch_faces(self, p):
        sel = self.selected_patch_idx
        hl_face_set = set(self.highlight_faces)

        # Unassigned boundary faces – always show faint
        if self.mesh.blocks:
            assigned = self.mesh.assigned_face_keys()
            for bi,fi in self.mesh.boundary_faces():
                if self.mesh._face_key(bi,fi) in assigned: continue
                poly = self._face_screen_poly(bi,fi)
                if not poly: continue
                qp = QPolygon([QPoint(int(x),int(y)) for x,y in poly])
                p.setBrush(QBrush(QColor(60,80,110,18)))
                p.setPen(QPen(QColor(90,110,150,65),1,Qt.DotLine))
                p.drawPolygon(qp)

        # Assigned patch faces sorted back-to-front
        draws = []
        for pi, patch in enumerate(self.mesh.patches):
            is_active = (pi == sel)
            base = QColor(patch.color)
            if is_active:
                fill = QColor(base.red(),base.green(),base.blue(),190)
                edge = base.lighter(170); ew = 2.5
            else:
                a = 55 if sel>=0 else 85
                fill = QColor(base.red(),base.green(),base.blue(),a)
                edge = QColor(base.red(),base.green(),base.blue(),100 if sel>=0 else 160)
                ew = 1.0
            for ref in patch.faces:
                if ref.block_idx>=len(self.mesh.blocks): continue
                poly = self._face_screen_poly(ref.block_idx,ref.face_idx)
                if not poly: continue
                depth = sum(pt[1] for pt in poly)/len(poly)
                draws.append((depth,poly,fill,edge,ew,is_active,ref.block_idx,ref.face_idx))
        draws.sort(key=lambda x:x[0])
        for _,poly,fill,edge,ew,is_active,bi,fi in draws:
            qp = QPolygon([QPoint(int(x),int(y)) for x,y in poly])
            p.setBrush(QBrush(fill)); p.setPen(QPen(edge,ew)); p.drawPolygon(qp)
            if is_active:
                p.setBrush(Qt.NoBrush); p.setPen(QPen(edge.lighter(140),1.0))
                p.drawPolygon(qp)

        # Highlighted faces (from list selection) – gold overlay
        for bi,fi in self.highlight_faces:
            if bi>=len(self.mesh.blocks): continue
            poly = self._face_screen_poly(bi,fi)
            if not poly: continue
            qp = QPolygon([QPoint(int(x),int(y)) for x,y in poly])
            p.setBrush(QBrush(QColor(255,230,80,130)))
            p.setPen(QPen(QColor(255,245,120,255),2.5)); p.drawPolygon(qp)

        # Selected face – bright white outline
        if self.selected_face:
            bi,fi = self.selected_face
            if bi<len(self.mesh.blocks):
                poly = self._face_screen_poly(bi,fi)
                if poly:
                    qp = QPolygon([QPoint(int(x),int(y)) for x,y in poly])
                    p.setBrush(QBrush(QColor(255,255,255,40)))
                    p.setPen(QPen(QColor(255,255,255,220),2.5)); p.drawPolygon(qp)

        # Hovered face (in paint or select mode)
        if self.hovered_face and (self.tool in (TOOL_SELECT, TOOL_PATCH)):
            bi,fi = self.hovered_face
            if bi<len(self.mesh.blocks):
                poly = self._face_screen_poly(bi,fi)
                if poly:
                    # colour by intent
                    if self.tool == TOOL_PATCH and sel>=0:
                        patch = self.mesh.patches[sel]
                        in_p = any(f.block_idx==bi and f.face_idx==fi for f in patch.faces)
                        fc = QColor(255,80,80,160) if in_p else QColor(80,255,160,140)
                        ec = QColor(255,120,120,255) if in_p else QColor(120,255,200,255)
                    else:
                        fc = QColor(200,220,255,100); ec = QColor(200,220,255,220)
                    qp = QPolygon([QPoint(int(x),int(y)) for x,y in poly])
                    p.setBrush(QBrush(fc)); p.setPen(QPen(ec,2.5)); p.drawPolygon(qp)

    def _draw_vertices(self, p):
        font = QFont("Consolas",8); p.setFont(font)
        hl_set = set(self.highlight_verts)
        pending_set = set(self.block_pending)
        for i,v in enumerate(self.mesh.vertices):
            px,py,_ = self._project(v.x,v.y,v.z)
            if i == self.selected_vertex:
                col = QColor(255,255,255); r = 7
            elif i in pending_set:
                col = QColor(255,210,0); r = 7
            elif i in hl_set:
                col = QColor(255,200,60); r = 6
            elif i == self.hovered_vert:
                col = QColor(255,160,60); r = 6
            else:
                col = QColor(190,200,255); r = 4
            p.setBrush(QBrush(col)); p.setPen(QPen(col.lighter(160),1))
            p.drawEllipse(QPoint(int(px),int(py)),r,r)
            if self.show_labels or i in pending_set or i == self.selected_vertex:
                lbl = str(i)+(f":{v.label}" if v.label else "")
                if i in pending_set:
                    seq = self.block_pending.index(i)
                    p.setPen(QColor(255,220,80)); p.setFont(QFont("Consolas",8,QFont.Bold))
                    p.drawText(int(px)+9,int(py)-3,f"[{seq}]{lbl}")
                    p.setFont(font)
                else:
                    p.setPen(QColor(180,190,220))
                    p.drawText(int(px)+9,int(py)-3,lbl)

        if i == self.edge_v0 and self.edge_v0 >= 0:
            px,py,_ = self._project_vertex(self.edge_v0)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(100,220,255),2))
            p.drawEllipse(QPoint(int(px),int(py)),10,10)

    def _draw_block_labels(self, p):
        p.setFont(QFont("Consolas",8,QFont.Bold))
        for bi,block in enumerate(self.mesh.blocks):
            if len(block.verts)!=8: continue
            cx=cy=cz=0.0; valid=True
            for gv in block.verts:
                if gv>=len(self.mesh.vertices): valid=False; break
                v=self.mesh.vertices[gv]; cx+=v.x; cy+=v.y; cz+=v.z
            if not valid: continue
            sx,sy,_ = self._project(cx/8,cy/8,cz/8)
            lbl = f"B{bi}"+(f":{block.label}" if block.label else "")
            p.setPen(QColor(200,200,100,200))
            p.drawText(int(sx)-len(lbl)*3,int(sy)+4,lbl)

    def _draw_face_patch_labels(self, p):
        p.setFont(QFont("Consolas",8))
        key_to_info: Dict[frozenset,Tuple[str,QColor]] = {}
        for patch in self.mesh.patches:
            col = QColor(patch.color).lighter(160)
            for ref in patch.faces:
                key = self.mesh._face_key(ref.block_idx,ref.face_idx)
                key_to_info[key] = (patch.name,col)
        fm = QFontMetrics(p.font())
        for bi,block in enumerate(self.mesh.blocks):
            for fi in range(6):
                key = self.mesh._face_key(bi,fi)
                if key not in key_to_info: continue
                name,col = key_to_info[key]
                poly = self._face_screen_poly(bi,fi)
                if not poly: continue
                cx = sum(pt[0] for pt in poly)/len(poly)
                cy = sum(pt[1] for pt in poly)/len(poly)
                p.setPen(col)
                p.drawText(int(cx-fm.horizontalAdvance(name)/2),int(cy+4),name)

    def _draw_face_normals(self, p):
        for patch in self.mesh.patches:
            base = QColor(patch.color).lighter(140)
            p.setPen(QPen(base,1.8))
            for ref in patch.faces:
                if ref.block_idx>=len(self.mesh.blocks): continue
                b = self.mesh.blocks[ref.block_idx]
                local = HEX_FACE_LOCAL[ref.face_idx]
                pts3=[];  valid=True
                for lv in local:
                    gv=b.verts[lv]
                    if gv>=len(self.mesh.vertices): valid=False; break
                    v=self.mesh.vertices[gv]; pts3.append((v.x,v.y,v.z))
                if not valid or len(pts3)<3: continue
                fc = tuple(sum(q[d] for q in pts3)/len(pts3) for d in range(3))
                v01=_v3_sub(pts3[1],pts3[0]); v02=_v3_sub(pts3[2],pts3[0])
                n=_v3_norm(_v3_cross(v01,v02))
                tip=(fc[0]+n[0]*.15,fc[1]+n[1]*.15,fc[2]+n[2]*.15)
                sx,sy,_ = self._project(*fc); ex,ey,_ = self._project(*tip)
                p.drawLine(int(sx),int(sy),int(ex),int(ey))
                dx,dy = ex-sx,ey-sy; mag=math.sqrt(dx*dx+dy*dy) or 1
                ux,uy = dx/mag,dy/mag; px2,py2 = -uy*4,ux*4
                tri=QPolygon([QPoint(int(ex),int(ey)),
                              QPoint(int(ex-ux*8+px2),int(ey-uy*8+py2)),
                              QPoint(int(ex-ux*8-px2),int(ey-uy*8-py2))])
                p.setBrush(QBrush(base)); p.setPen(Qt.NoPen); p.drawPolygon(tri)

    def _draw_tool_overlay(self, p):
        """Banner at top of viewport showing current tool and hints."""
        TOOL_INFO = {
            TOOL_SELECT:  ("↖ Select",      "#6090c0", "Click vertex or face to inspect"),
            TOOL_VERTEX:  ("+ Vertex",      "#50c080", "Fill in coordinates in inspector → Add"),
            TOOL_BLOCK:   ("⬡ Block",        "#c0a030", f"Click vertices ({len(self.block_pending)}/8 selected)"),
            TOOL_EDGE:    ("~ Edge",         "#c060c0", "Click v0 then v1" if self.edge_v0<0 else f"v0={self.edge_v0} — click v1"),
            TOOL_PATCH:   ("🎨 Patch",       "#c05050", "Click face to assign/remove"),
        }
        label, hue, hint = TOOL_INFO.get(self.tool, ("", "#444", ""))
        bar_col = QColor(hue)
        p.fillRect(0,0,self.width(),26, QColor(0,0,0,160))
        p.fillRect(0,0,5,26, bar_col)
        p.setFont(QFont("Consolas",9,QFont.Bold))
        p.setPen(bar_col.lighter(160))
        p.drawText(12,17,label)
        p.setPen(QColor(180,195,215))
        p.setFont(QFont("Consolas",9))
        p.drawText(100,17,hint)

    # ── mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        self._last_pos = ev.position().toPoint()
        self._panning = (ev.button()==Qt.MiddleButton or
                         (ev.button()==Qt.LeftButton and ev.modifiers()&Qt.ControlModifier))
        if ev.button()==Qt.LeftButton and not self._panning:
            self._handle_click(ev.position())

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        if self._last_pos and ev.buttons() & (Qt.LeftButton|Qt.MiddleButton):
            dx=pos.x()-self._last_pos.x(); dy=pos.y()-self._last_pos.y()
            if self._panning:
                self._pan_x+=dx; self._pan_y+=dy
            else:
                self._az=(self._az+dx*.5)%360
                self._el=max(-89,min(89,self._el-dy*.4))
            self.update()
        self._last_pos = pos
        self._update_hover(ev.position())

    def mouseReleaseEvent(self, _): self._last_pos = None

    def wheelEvent(self, ev):
        self._zoom *= (1.1 if ev.angleDelta().y()>0 else 0.9)
        self._zoom = max(5,min(2000,self._zoom))
        self.update()

    def _handle_click(self, pos):
        if self.tool in (TOOL_SELECT, TOOL_BLOCK, TOOL_EDGE, TOOL_VERTEX):
            # Prefer vertex click
            idx = self._nearest_vertex(pos)
            if idx >= 0:
                if self.tool == TOOL_SELECT:
                    self.selected_vertex = idx
                    self.selected_face = None
                self.vertex_clicked.emit(idx)
                self.update(); return

        if self.tool in (TOOL_SELECT, TOOL_PATCH):
            hit = self._nearest_boundary_face(pos)
            if hit:
                bi,fi = hit
                if self.tool == TOOL_SELECT:
                    self.selected_face = (bi,fi)
                    self.selected_vertex = -1
                self.face_clicked.emit(bi,fi)
                self.update()

    def _update_hover(self, pos):
        changed = False
        # Vertex hover
        new_v = self._nearest_vertex(pos) if self.tool != TOOL_PATCH else -1
        if new_v != self.hovered_vert:
            self.hovered_vert = new_v; changed=True
            if new_v>=0:
                v=self.mesh.vertices[new_v]
                self.hover_changed.emit(f"Vertex {new_v}  ({v.x:.4g}, {v.y:.4g}, {v.z:.4g})"
                                        +(f"  \"{v.label}\"" if v.label else ""))

        # Face hover for select / patch tools
        if self.tool in (TOOL_SELECT, TOOL_PATCH) and new_v < 0:
            hit = self._nearest_boundary_face(pos)
            new_f = (hit[0],hit[1]) if hit else None
        else:
            new_f = None
        if new_f != self.hovered_face:
            self.hovered_face = new_f; changed=True
            if new_f:
                bi,fi = new_f
                b=self.mesh.blocks[bi]; gvs=[b.verts[lv] for lv in HEX_FACE_LOCAL[fi]]
                key=self.mesh._face_key(bi,fi)
                owner = next((pt.name for pt in self.mesh.patches if
                              key in {self.mesh._face_key(f.block_idx,f.face_idx)
                                      for f in pt.faces}), "unassigned")
                self.hover_changed.emit(f"Block {bi} · {HEX_FACE_NAMES[fi]}  {gvs}  [{owner}]")

        if not new_f and new_v < 0:
            if self.hovered_vert != -1 or self.hovered_face is not None:
                self.hover_changed.emit("")
        if changed: self.update()

    # ── camera ────────────────────────────────────────────────────────────────

    def reset_view(self):
        self._az=35; self._el=25; self._zoom=80; self._pan_x=0; self._pan_y=0
        self.update()

    def frame_all(self):
        if not self.mesh.vertices: return
        xs=[v.x for v in self.mesh.vertices]
        ys=[v.y for v in self.mesh.vertices]
        zs=[v.z for v in self.mesh.vertices]
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
        px,py,_ = self._project(cx,cy,cz)
        self._pan_x += self.width()/2-px; self._pan_y += self.height()/2-py
        span=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs),1)
        self._zoom=min(self.width(),self.height())*.55/span
        self.update()


# ═══════════════════════════════════════════════════════════════════════════════
#  INSPECTOR PAGES
# ═══════════════════════════════════════════════════════════════════════════════

def _sep():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color:#2a3040;"); return f

def _lbl(txt, style="color:#6a8faf;font-size:10px;"):
    l = QLabel(txt); l.setStyleSheet(style); l.setWordWrap(True); return l


class InspectorEmpty(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.addStretch()
        icon = QLabel("◎")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:36px;color:#2a3a50;")
        lay.addWidget(icon)
        lay.addWidget(_lbl("Click a vertex, face, block\nor patch in the outliner\nto inspect it.",
                           "color:#3a5060;font-size:12px;text-align:center;"))
        lay.addStretch()


class InspectorAddVertex(QWidget):
    """Inspector page shown when the Add Vertex tool is active."""
    committed = Signal(object)   # emits Vertex

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("New Vertex"))
        lay.addWidget(_sep())
        form = QFormLayout()
        self._x = QLineEdit(); self._x.setPlaceholderText("0.0")
        self._y = QLineEdit(); self._y.setPlaceholderText("0.0")
        self._z = QLineEdit(); self._z.setPlaceholderText("0.0")
        self._label = QLineEdit()
        form.addRow("X:", self._x); form.addRow("Y:", self._y)
        form.addRow("Z:", self._z); form.addRow("Label:", self._label)
        lay.addLayout(form)
        btn = QPushButton("Add Vertex")
        btn.clicked.connect(self._commit)
        lay.addWidget(btn); lay.addStretch()

    def clear(self):
        for w in (self._x, self._y, self._z, self._label):
            w.clear(); w.setStyleSheet("")

    def _commit(self):
        vals = []
        for w in (self._x, self._y, self._z):
            try: vals.append(float(w.text()) if w.text().strip() else 0.0)
            except ValueError: w.setStyleSheet("border:1px solid #e05252;"); return
            w.setStyleSheet("")
        self.committed.emit(Vertex(vals[0], vals[1], vals[2],
                                   self._label.text().strip()))
        self.clear()


class InspectorVertex(QWidget):
    """Inspector for an existing vertex."""
    changed = Signal()
    deleted = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self._title = QLabel("Vertex 0")
        self._title.setStyleSheet("font-size:13px;font-weight:bold;color:#c8d8f0;")
        lay.addWidget(self._title); lay.addWidget(_sep())
        form = QFormLayout()
        self._x = QLineEdit(); self._y = QLineEdit(); self._z = QLineEdit()
        self._lbl = QLineEdit()
        for w in (self._x,self._y,self._z): w.setPlaceholderText("0.0")
        form.addRow("X:",self._x); form.addRow("Y:",self._y)
        form.addRow("Z:",self._z); form.addRow("Label:",self._lbl)
        lay.addLayout(form)
        self._used = QLabel(""); self._used.setStyleSheet("color:#6a8faf;font-size:10px;")
        lay.addWidget(self._used)
        row = QHBoxLayout()
        self._btn_apply  = QPushButton("Apply"); self._btn_apply.clicked.connect(self._apply)
        self._btn_delete = QPushButton("Delete"); self._btn_delete.clicked.connect(self.deleted)
        row.addWidget(self._btn_apply); row.addWidget(self._btn_delete)
        lay.addLayout(row); lay.addStretch()
        self._idx = -1

    def load(self, idx: int, mesh: MeshModel):
        self._idx = idx
        v = mesh.vertices[idx]
        self._title.setText(f"Vertex {idx}")
        for w,val in zip((self._x,self._y,self._z),(v.x,v.y,v.z)):
            w.setText(str(val)); w.setStyleSheet("")
        self._lbl.setText(v.label)
        n = sum(1 for b in mesh.blocks if idx in b.verts)
        self._used.setText(f"Used by {n} block(s)")

    def _apply(self):
        vals = []
        for w in (self._x,self._y,self._z):
            try: vals.append(float(w.text()) if w.text().strip() else 0.0)
            except ValueError: w.setStyleSheet("border:1px solid #e05252;"); return
            w.setStyleSheet("")
        self._pending = (self._idx, vals[0], vals[1], vals[2], self._lbl.text().strip())
        self.changed.emit()

    def get_pending(self): return self._pending


class InspectorBlock(QWidget):
    """Inspector for a hex block — cells, grading, label, and per-face patch assignment."""
    changed = Signal()
    deleted = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self._title = QLabel("Block 0")
        self._title.setStyleSheet("font-size:13px;font-weight:bold;color:#c8d8f0;")
        lay.addWidget(self._title); lay.addWidget(_sep())

        form = QFormLayout()
        self._nx = QSpinBox(minimum=1,maximum=10000,value=10)
        self._ny = QSpinBox(minimum=1,maximum=10000,value=10)
        self._nz = QSpinBox(minimum=1,maximum=10000,value=10)
        self._grading = QLineEdit("simpleGrading (1 1 1)")
        self._label_e = QLineEdit()
        form.addRow("Cells X:",self._nx); form.addRow("Y:",self._ny); form.addRow("Z:",self._nz)
        form.addRow("Grading:",self._grading); form.addRow("Label:",self._label_e)
        lay.addLayout(form)
        lay.addWidget(_sep())

        lay.addWidget(QLabel("Face → Patch:"))
        self._face_combos: List[QComboBox] = []
        for fi,fname in enumerate(HEX_FACE_NAMES):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"  {fname}:"))
            cb = QComboBox(); cb.setProperty("face_idx", fi)
            cb.currentIndexChanged.connect(self._on_face_combo_changed)
            self._face_combos.append(cb); row.addWidget(cb,1)
            lay.addLayout(row)
        lay.addWidget(_sep())

        btn_row = QHBoxLayout()
        self._btn_apply  = QPushButton("Apply"); self._btn_apply.clicked.connect(self._apply)
        self._btn_delete = QPushButton("Delete"); self._btn_delete.clicked.connect(self.deleted)
        btn_row.addWidget(self._btn_apply); btn_row.addWidget(self._btn_delete)
        lay.addLayout(btn_row); lay.addStretch()
        self._idx = -1; self._mesh: Optional[MeshModel] = None

    def load(self, idx: int, mesh: MeshModel):
        self._idx = idx; self._mesh = mesh
        b = mesh.blocks[idx]
        self._title.setText(f"Block {idx}"+(f" [{b.label}]" if b.label else ""))
        self._nx.setValue(b.cells[0]); self._ny.setValue(b.cells[1]); self._nz.setValue(b.cells[2])
        self._grading.setText(b.grading); self._label_e.setText(b.label)

        # Populate face combos
        key_to_patch: Dict[frozenset,int] = {}
        for pi,p in enumerate(mesh.patches):
            for ref in p.faces:
                key_to_patch[mesh._face_key(ref.block_idx,ref.face_idx)] = pi

        patch_names = ["(none)"]+[p.name for p in mesh.patches]
        for fi,cb in enumerate(self._face_combos):
            cb.blockSignals(True); cb.clear(); cb.addItems(patch_names)
            key = mesh._face_key(idx,fi)
            pi = key_to_patch.get(key,-1)
            cb.setCurrentIndex(pi+1)
            cb.blockSignals(False)

    def _on_face_combo_changed(self, _):
        if self._idx < 0 or self._mesh is None: return
        self._apply_faces()

    def _apply(self):
        if self._idx < 0 or self._mesh is None: return
        b = self._mesh.blocks[self._idx]
        b.cells = [self._nx.value(),self._ny.value(),self._nz.value()]
        b.grading = self._grading.text().strip() or "simpleGrading (1 1 1)"
        b.label   = self._label_e.text().strip()
        self._title.setText(f"Block {self._idx}"+(f" [{b.label}]" if b.label else ""))
        self._apply_faces(); self.changed.emit()

    def _apply_faces(self):
        if self._mesh is None: return
        m = self._mesh; bi = self._idx
        for fi,cb in enumerate(self._face_combos):
            pi = cb.currentIndex()-1   # -1 = none
            key = m._face_key(bi,fi)
            # Remove from all patches
            for p in m.patches:
                p.faces = [f for f in p.faces
                           if m._face_key(f.block_idx,f.face_idx)!=key]
            if pi >= 0 and pi < len(m.patches):
                if not any(f.block_idx==bi and f.face_idx==fi
                           for f in m.patches[pi].faces):
                    m.patches[pi].faces.append(BlockFaceRef(bi,fi))
        self.changed.emit()


class InspectorFace(QWidget):
    """Inspector for a clicked boundary face — shows patch assignment."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self._title = QLabel("Face")
        self._title.setStyleSheet("font-size:13px;font-weight:bold;color:#c8d8f0;")
        lay.addWidget(self._title); lay.addWidget(_sep())
        self._info = QLabel(""); self._info.setStyleSheet("color:#7a9ab0;font-size:10px;")
        lay.addWidget(self._info)
        lay.addWidget(QLabel("Assign to patch:"))
        self._combo = QComboBox()
        lay.addWidget(self._combo)
        self._btn_assign = QPushButton("Assign / Move to patch")
        self._btn_assign.clicked.connect(self._assign)
        lay.addWidget(self._btn_assign)
        self._btn_remove = QPushButton("Remove from patch")
        self._btn_remove.clicked.connect(self._remove)
        lay.addWidget(self._btn_remove)
        lay.addStretch()
        self._bi = self._fi = -1; self._mesh: Optional[MeshModel] = None

    def load(self, bi: int, fi: int, mesh: MeshModel):
        self._bi=bi; self._fi=fi; self._mesh=mesh
        b=mesh.blocks[bi]; gvs=[b.verts[lv] for lv in HEX_FACE_LOCAL[fi]]
        self._title.setText(f"Block {bi}  ·  {HEX_FACE_NAMES[fi]}")
        key=mesh._face_key(bi,fi)
        owner = next((p.name for p in mesh.patches if
                      key in {mesh._face_key(f.block_idx,f.face_idx) for f in p.faces}),
                     None)
        self._info.setText(f"Vertices: {gvs}\n"
                           f"Current patch: {owner or '(unassigned)'}")
        self._combo.clear(); self._combo.addItems([p.name for p in mesh.patches])
        if owner:
            idx = next((i for i,p in enumerate(mesh.patches) if p.name==owner),-1)
            if idx>=0: self._combo.setCurrentIndex(idx)

    def _assign(self):
        if self._bi<0 or self._mesh is None: return
        pi = self._combo.currentIndex()
        if pi<0 or pi>=len(self._mesh.patches): return
        key=self._mesh._face_key(self._bi,self._fi)
        for p in self._mesh.patches:
            p.faces=[f for f in p.faces
                     if self._mesh._face_key(f.block_idx,f.face_idx)!=key]
        self._mesh.patches[pi].faces.append(BlockFaceRef(self._bi,self._fi))
        self.load(self._bi,self._fi,self._mesh); self.changed.emit()

    def _remove(self):
        if self._bi<0 or self._mesh is None: return
        key=self._mesh._face_key(self._bi,self._fi)
        for p in self._mesh.patches:
            p.faces=[f for f in p.faces
                     if self._mesh._face_key(f.block_idx,f.face_idx)!=key]
        self.load(self._bi,self._fi,self._mesh); self.changed.emit()


class InspectorPatch(QWidget):
    """Inspector for a patch — name, type, faces list, bulk-import from face list."""
    changed = Signal()
    deleted = Signal()
    faces_highlighted = Signal(list)  # list of (bi,fi) to highlight in viewport

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setSpacing(4)
        self._swatch = QLabel("  ")
        self._swatch.setFixedSize(18,18)
        self._title = QLabel("Patch")
        self._title.setStyleSheet("font-size:13px;font-weight:bold;color:#c8d8f0;")
        hdr=QHBoxLayout(); hdr.addWidget(self._swatch); hdr.addWidget(self._title,1)
        lay.addLayout(hdr); lay.addWidget(_sep())

        form = QFormLayout()
        self._name_e = QLineEdit()
        self._type_c = QComboBox(); self._type_c.addItems(PATCH_TYPES)
        form.addRow("Name:",self._name_e); form.addRow("Type:",self._type_c)
        lay.addLayout(form)
        row=QHBoxLayout()
        btn_apply=QPushButton("Apply"); btn_apply.clicked.connect(self._apply)
        btn_del=QPushButton("Delete"); btn_del.clicked.connect(self.deleted)
        row.addWidget(btn_apply); row.addWidget(btn_del)
        lay.addLayout(row); lay.addWidget(_sep())

        lay.addWidget(QLabel("Assigned faces:"))
        self._face_list=QListWidget()
        self._face_list.setMaximumHeight(130)
        self._face_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._face_list.itemSelectionChanged.connect(self._on_face_select)
        lay.addWidget(self._face_list)

        row2=QHBoxLayout()
        btn_rem=QPushButton("Remove selected faces"); btn_rem.clicked.connect(self._remove_faces)
        btn_clear=QPushButton("Clear all"); btn_clear.clicked.connect(self._clear)
        row2.addWidget(btn_rem); row2.addWidget(btn_clear)
        lay.addLayout(row2)
        lay.addStretch()
        self._idx=-1; self._mesh:Optional[MeshModel]=None

    def load(self, idx:int, mesh:MeshModel):
        self._idx=idx; self._mesh=mesh; p=mesh.patches[idx]
        col=QColor(p.color)
        self._swatch.setStyleSheet(f"background:{p.color};border:1px solid {p.color};border-radius:2px;")
        self._title.setText(p.name)
        self._name_e.setText(p.name)
        ti=self._type_c.findText(p.ptype)
        if ti>=0: self._type_c.setCurrentIndex(ti)
        self._face_list.clear()
        for ref in p.faces:
            self._face_list.addItem(f"  Block {ref.block_idx}  ·  {HEX_FACE_NAMES[ref.face_idx]}")

    def _apply(self):
        if self._idx<0 or self._mesh is None: return
        p=self._mesh.patches[self._idx]
        p.name=self._name_e.text().strip() or p.name
        p.ptype=self._type_c.currentText()
        self._title.setText(p.name); self.changed.emit()

    def _on_face_select(self):
        if self._idx<0 or self._mesh is None: return
        p=self._mesh.patches[self._idx]
        sel=[p.faces[self._face_list.row(it)] for it in self._face_list.selectedItems()
             if self._face_list.row(it)<len(p.faces)]
        self.faces_highlighted.emit([(r.block_idx,r.face_idx) for r in sel])

    def _remove_faces(self):
        if self._idx<0 or self._mesh is None: return
        rows=sorted({self._face_list.row(it) for it in self._face_list.selectedItems()},reverse=True)
        p=self._mesh.patches[self._idx]
        for r in rows:
            if r<len(p.faces): del p.faces[r]
        self.load(self._idx,self._mesh); self.changed.emit()

    def _clear(self):
        if self._idx<0 or self._mesh is None: return
        self._mesh.patches[self._idx].faces.clear()
        self.load(self._idx,self._mesh); self.changed.emit()


class InspectorExport(QWidget):
    """Validation + export panel."""
    def __init__(self, mesh: MeshModel):
        super().__init__()
        self._mesh=mesh
        lay=QVBoxLayout(self); lay.setSpacing(4)
        lay.addWidget(QLabel("Validation"))
        self._val_status=QLabel("—")
        self._val_status.setStyleSheet("font-weight:bold;font-size:11px;padding:3px 6px;border-radius:4px;")
        lay.addWidget(self._val_status)
        self._val_list=QListWidget(); self._val_list.setMaximumHeight(90)
        lay.addWidget(self._val_list)
        lay.addWidget(_sep())

        scale_row=QHBoxLayout(); scale_row.addWidget(QLabel("Scale:"))
        self._scale=QDoubleSpinBox(decimals=6,minimum=1e-9,maximum=1e9,value=1.0)
        self._scale.setSingleStep(0.1)
        self._scale.valueChanged.connect(lambda v:setattr(mesh,"scale",v))
        scale_row.addWidget(self._scale); scale_row.addStretch()
        lay.addLayout(scale_row)

        # mergePatchPairs
        lay.addWidget(QLabel("mergePatchPairs:"))
        self._mp_list=QListWidget(); self._mp_list.setMaximumHeight(60)
        lay.addWidget(self._mp_list)
        mp_row=QHBoxLayout()
        self._mp_a=QLineEdit(); self._mp_a.setPlaceholderText("patch A")
        self._mp_b=QLineEdit(); self._mp_b.setPlaceholderText("patch B")
        mp_row.addWidget(self._mp_a); mp_row.addWidget(QLabel("↔")); mp_row.addWidget(self._mp_b)
        lay.addLayout(mp_row)
        mp_btns=QHBoxLayout()
        btn_mp_add=QPushButton("Add"); btn_mp_add.clicked.connect(self._mp_add)
        btn_mp_del=QPushButton("Remove"); btn_mp_del.clicked.connect(self._mp_remove)
        mp_btns.addWidget(btn_mp_add); mp_btns.addWidget(btn_mp_del)
        lay.addLayout(mp_btns)
        lay.addWidget(_sep())

        lay.addWidget(QLabel("blockMeshDict preview:"))
        self._preview=QTextEdit(readOnly=True,font=QFont("Consolas",9))
        self._preview.setStyleSheet("background:#0d1117;color:#c9d1d9;border:1px solid #30363d;")
        lay.addWidget(self._preview,1)

        btn_row=QHBoxLayout()
        for lbl,slot in [("↻ Refresh",self.refresh),("⎘ Copy",self._copy),("💾 Save…",self._save)]:
            b=QPushButton(lbl); b.clicked.connect(slot); btn_row.addWidget(b)
        lay.addLayout(btn_row)
        self.refresh()

    def refresh(self):
        self._scale.setValue(self._mesh.scale)
        self._refresh_mp()
        self._preview.setPlainText(self._mesh.to_blockMeshDict())
        self._run_validate()

    def _refresh_mp(self):
        self._mp_list.clear()
        for a,b in self._mesh.merge_pairs:
            self._mp_list.addItem(f"  {a}  ↔  {b}")

    def _mp_add(self):
        a=self._mp_a.text().strip(); b=self._mp_b.text().strip()
        if not a or not b: return
        self._mesh.merge_pairs.append((a,b))
        self._mp_a.clear(); self._mp_b.clear()
        self.refresh()

    def _mp_remove(self):
        r=self._mp_list.currentRow()
        if r<0: return
        del self._mesh.merge_pairs[r]; self.refresh()

    def _run_validate(self):
        warnings=self._mesh.validate(); self._val_list.clear()
        if not warnings:
            self._val_status.setText("✔  Valid")
            self._val_status.setStyleSheet("font-weight:bold;font-size:11px;padding:3px 6px;"
                                           "border-radius:4px;background:#1a3a20;color:#60d080;")
        else:
            self._val_status.setText(f"⚠  {len(warnings)} issue(s)")
            self._val_status.setStyleSheet("font-weight:bold;font-size:11px;padding:3px 6px;"
                                           "border-radius:4px;background:#3a2010;color:#e09040;")
            for w in warnings:
                item=QListWidgetItem(f"  • {w}"); item.setForeground(QColor(220,150,80))
                self._val_list.addItem(item)

    def _copy(self): QApplication.clipboard().setText(self._preview.toPlainText())

    def _save(self):
        issues=self._mesh.validate()
        if issues:
            if QMessageBox.question(self,"Warnings",f"{len(issues)} issue(s). Save anyway?",
                                    QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
                return
        path,_=QFileDialog.getSaveFileName(self,"Save blockMeshDict","blockMeshDict","All Files (*)")
        if path:
            with open(path,"w") as fh: fh.write(self._preview.toPlainText())


# ═══════════════════════════════════════════════════════════════════════════════
#  INSPECTOR SHELL  (stacked widget)
# ═══════════════════════════════════════════════════════════════════════════════

class Inspector(QWidget):
    changed = Signal()

    PAGE_EMPTY      = 0
    PAGE_ADD_VERTEX = 1
    PAGE_VERTEX     = 2
    PAGE_BLOCK      = 3
    PAGE_FACE       = 4
    PAGE_PATCH      = 5
    PAGE_EXPORT     = 6

    def __init__(self, mesh: MeshModel, vp: Viewport3D):
        super().__init__()
        self.mesh=mesh; self.vp=vp
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)

        self._stack=QStackedWidget()
        self.p_empty      = InspectorEmpty()
        self.p_addvert    = InspectorAddVertex()
        self.p_vertex     = InspectorVertex()
        self.p_block      = InspectorBlock()
        self.p_face       = InspectorFace()
        self.p_patch      = InspectorPatch()
        self.p_export     = InspectorExport(mesh)

        for page in (self.p_empty, self.p_addvert, self.p_vertex, self.p_block,
                     self.p_face, self.p_patch, self.p_export):
            self._stack.addWidget(page)

        lay.addWidget(self._stack)

        # Wire signals
        self.p_addvert.committed.connect(self._on_add_vertex)
        self.p_vertex.changed.connect(self._on_vertex_changed)
        self.p_vertex.deleted.connect(self._on_vertex_deleted)
        self.p_block.changed.connect(self.changed)
        self.p_block.deleted.connect(self._on_block_deleted)
        self.p_face.changed.connect(self.changed)
        self.p_patch.changed.connect(self.changed)
        self.p_patch.deleted.connect(self._on_patch_deleted)
        self.p_patch.faces_highlighted.connect(
            lambda faces: setattr(vp, "highlight_faces", faces) or vp.update())

    def show_empty(self):       self._stack.setCurrentIndex(self.PAGE_EMPTY)
    def show_add_vertex(self):  self._stack.setCurrentIndex(self.PAGE_ADD_VERTEX)
    def show_export(self):
        self.p_export.refresh(); self._stack.setCurrentIndex(self.PAGE_EXPORT)

    def show_vertex(self, idx):
        if idx<0 or idx>=len(self.mesh.vertices): return
        self.p_vertex.load(idx, self.mesh)
        self._stack.setCurrentIndex(self.PAGE_VERTEX)

    def show_block(self, idx):
        if idx<0 or idx>=len(self.mesh.blocks): return
        self.p_block.load(idx, self.mesh)
        self._stack.setCurrentIndex(self.PAGE_BLOCK)

    def show_face(self, bi, fi):
        self.p_face.load(bi, fi, self.mesh)
        self._stack.setCurrentIndex(self.PAGE_FACE)

    def show_patch(self, idx):
        if idx<0 or idx>=len(self.mesh.patches): return
        self.p_patch.load(idx, self.mesh)
        self._stack.setCurrentIndex(self.PAGE_PATCH)

    # ── model mutation handlers ───────────────────────────────────────────────

    def _on_add_vertex(self, v: Vertex):
        self.mesh.vertices.append(v)
        self.changed.emit()

    def _on_vertex_changed(self):
        idx,x,y,z,lbl = self.p_vertex.get_pending()
        if 0<=idx<len(self.mesh.vertices):
            self.mesh.vertices[idx] = Vertex(x,y,z,lbl)
            self.p_vertex.load(idx,self.mesh)
        self.changed.emit()

    def _on_vertex_deleted(self):
        idx = self.p_vertex._idx
        if idx<0: return
        if any(idx in b.verts for b in self.mesh.blocks):
            QMessageBox.warning(self,"Cannot delete",
                                "Vertex is referenced by one or more blocks."); return
        del self.mesh.vertices[idx]
        for b in self.mesh.blocks:
            b.verts=[v if v<idx else v-1 for v in b.verts]
        self.mesh.arc_edges=[e for e in self.mesh.arc_edges if e.v0!=idx and e.v1!=idx]
        self.mesh.spline_edges=[e for e in self.mesh.spline_edges if e.v0!=idx and e.v1!=idx]
        self.show_empty(); self.vp.selected_vertex=-1
        self.changed.emit()

    def _on_block_deleted(self):
        idx=self.p_block._idx
        if idx<0: return
        del self.mesh.blocks[idx]
        for p in self.mesh.patches:
            p.faces=[f for f in p.faces if f.block_idx!=idx]
            for f in p.faces:
                if f.block_idx>idx: f.block_idx-=1
        self.show_empty(); self.changed.emit()

    def _on_patch_deleted(self):
        idx=self.p_patch._idx
        if idx<0: return
        del self.mesh.patches[idx]
        self.vp.selected_patch_idx=-1
        self.show_empty(); self.changed.emit()


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTLINER
# ═══════════════════════════════════════════════════════════════════════════════

class Outliner(QWidget):
    """
    Hierarchical tree of the scene.  Clicking an item selects it and
    tells the Inspector what to display.
    """
    item_selected = Signal(str, int)   # (kind, index)  kind = vertex/block/patch/edge_arc/edge_spline

    # Node type tags stored in Qt.UserRole
    KIND_VERTEX      = "vertex"
    KIND_BLOCK       = "block"
    KIND_PATCH       = "patch"
    KIND_ARC         = "edge_arc"
    KIND_SPLINE      = "edge_spline"

    def __init__(self, mesh: MeshModel):
        super().__init__()
        self.mesh=mesh
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self._tree=QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(12)
        self._tree.setStyleSheet("""
            QTreeWidget { background:#0f1520; border:none; color:#b0bcd0; }
            QTreeWidget::item:hover    { background:#1a2535; }
            QTreeWidget::item:selected { background:#1e3050; color:#e0e8ff; }
            QTreeWidget::branch { background:#0f1520; }
        """)
        self._tree.itemClicked.connect(self._on_click)
        lay.addWidget(self._tree)
        self._roots: dict = {}
        self.build()

    def build(self):
        self._tree.clear()
        m=self.mesh
        def root(label):
            item=QTreeWidgetItem([label])
            item.setFont(0,QFont("Consolas",9,QFont.Bold))
            item.setForeground(0,QColor("#7090a0"))
            self._tree.addTopLevelItem(item)
            item.setExpanded(True)
            return item

        # ── Vertices
        nv=len(m.vertices)
        rv=root(f"Vertices  ({nv})")
        for i,v in enumerate(m.vertices):
            lbl=f"  {i}   ({v.x:.4g}, {v.y:.4g}, {v.z:.4g})"
            if v.label: lbl+=f"  [{v.label}]"
            child=QTreeWidgetItem([lbl])
            child.setData(0,Qt.UserRole,(self.KIND_VERTEX,i))
            child.setForeground(0,QColor("#9ab0c8"))
            rv.addChild(child)

        # ── Blocks
        nb=len(m.blocks)
        rb=root(f"Blocks  ({nb})")
        for i,b in enumerate(m.blocks):
            cs="×".join(str(c) for c in b.cells)
            lbl=f"  Block {i}  [{cs}]"+(f"  {b.label}" if b.label else "")
            child=QTreeWidgetItem([lbl])
            child.setData(0,Qt.UserRole,(self.KIND_BLOCK,i))
            child.setForeground(0,QColor("#a0bcd0"))
            rb.addChild(child)

        # ── Patches
        unassigned=len(m.unassigned_boundary_faces())
        warn="" if unassigned==0 else f"  ⚠ {unassigned}"
        rp=root(f"Patches  ({len(m.patches)}){warn}")
        if unassigned: rp.setForeground(0,QColor("#c08040"))
        for i,p in enumerate(m.patches):
            n=len(p.faces)
            lbl=f"  {p.name}  [{p.ptype}]  — {n} face{'s' if n!=1 else ''}"
            child=QTreeWidgetItem([lbl])
            child.setData(0,Qt.UserRole,(self.KIND_PATCH,i))
            child.setForeground(0,QColor(p.color))
            rp.addChild(child)

        # ── Edges
        ne=len(m.arc_edges)+len(m.spline_edges)
        re=root(f"Edges  ({ne})")
        for i,e in enumerate(m.arc_edges):
            child=QTreeWidgetItem([f"  arc  {e.v0}→{e.v1}"])
            child.setData(0,Qt.UserRole,(self.KIND_ARC,i))
            child.setForeground(0,QColor("#c8a040")); re.addChild(child)
        for i,e in enumerate(m.spline_edges):
            child=QTreeWidgetItem([f"  spline  {e.v0}→{e.v1}  ({len(e.points)} pts)"])
            child.setData(0,Qt.UserRole,(self.KIND_SPLINE,i))
            child.setForeground(0,QColor("#60b0c8")); re.addChild(child)

    def refresh(self): self.build()

    def _on_click(self, item, _col):
        data=item.data(0,Qt.UserRole)
        if data: self.item_selected.emit(data[0],data[1])

    def highlight_vertex(self, idx):
        """Expand and select the vertex row."""
        self._select_item(self.KIND_VERTEX, idx)

    def _select_item(self, kind, idx):
        it=self._tree.invisibleRootItem()
        for ti in range(it.childCount()):
            node=it.child(ti)
            for ci in range(node.childCount()):
                child=node.child(ci)
                d=child.data(0,Qt.UserRole)
                if d and d[0]==kind and d[1]==idx:
                    self._tree.setCurrentItem(child); return


# ═══════════════════════════════════════════════════════════════════════════════
#  PIPELINE STATUS BAR
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineBar(QWidget):
    """
    Horizontal strip at the bottom of the viewport showing mesh pipeline status.
    Each stage shows a green ✓ or orange ⚠ with a short summary.
    """
    def __init__(self, mesh: MeshModel):
        super().__init__()
        self.mesh=mesh
        self.setFixedHeight(32)
        self.setStyleSheet("background:#0b1018;border-top:1px solid #1e2838;")
        self._lay=QHBoxLayout(self)
        self._lay.setContentsMargins(8,0,8,0); self._lay.setSpacing(0)
        self._labels: List[QLabel] = []
        stages=["Vertices","Blocks","Patches","Export"]
        for i,s in enumerate(stages):
            if i>0:
                div=QLabel(" │ "); div.setStyleSheet("color:#2a3a50;")
                self._lay.addWidget(div)
            lbl=QLabel(); lbl.setStyleSheet("font-size:10px;font-family:Consolas;padding:0 6px;")
            self._labels.append(lbl); self._lay.addWidget(lbl)
        self._lay.addStretch()
        self.refresh()

    def refresh(self):
        m=self.mesh
        nv=len(m.vertices); nb=len(m.blocks)
        np_=len(m.patches); un=len(m.unassigned_boundary_faces())
        issues=len(m.validate()) if nb>0 else 0

        def stat(ok,text):
            sym="✓" if ok else "⚠"
            col="#50c060" if ok else "#c08040"
            return f'<span style="color:{col};font-weight:bold;">{sym}</span> {text}'

        self._labels[0].setText(stat(nv>0, f"Vertices  {nv}"))
        self._labels[1].setText(stat(nb>0, f"Blocks  {nb}"))
        self._labels[2].setText(stat(un==0 and np_>0,
                                     f"Patches  {np_}" + (f"  ⚠{un} unassigned" if un else "")))
        self._labels[3].setText(stat(issues==0,
                                     "Export  ready" if issues==0 else f"Export  ⚠{issues} issues"))
        for lbl in self._labels: lbl.setTextFormat(Qt.RichText)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("blockMeshDict Creator")
        self.resize(1400, 860)
        self.mesh=MeshModel()
        self._dirty=False
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        self._MAX_UNDO=60

        # ── Viewport ──────────────────────────────────────────────────────────
        self.vp=Viewport3D(self.mesh)
        self.vp.hover_changed.connect(self.statusBar().showMessage)
        self.vp.vertex_clicked.connect(self._on_vp_vertex_click)
        self.vp.face_clicked.connect(self._on_vp_face_click)

        # ── Inspector + Outliner ──────────────────────────────────────────────
        self.inspector=Inspector(self.mesh, self.vp)
        self.inspector.changed.connect(self._on_changed)

        self.outliner=Outliner(self.mesh)
        self.outliner.item_selected.connect(self._on_outliner_select)

        # ── Pipeline bar ──────────────────────────────────────────────────────
        self.pipeline=PipelineBar(self.mesh)

        # ── Right panel: outliner (top) + inspector (bottom) ─────────────────
        right_split=QSplitter(Qt.Vertical)
        right_split.addWidget(self.outliner)
        right_split.addWidget(self.inspector)
        right_split.setSizes([320, 480])   # outliner gets ~40%, inspector ~60%
        right_split.setMinimumWidth(280)

        # ── Viewport + pipeline bar ───────────────────────────────────────────
        vp_container=QWidget()
        vcl=QVBoxLayout(vp_container); vcl.setContentsMargins(0,0,0,0); vcl.setSpacing(0)
        vcl.addWidget(self.vp,1); vcl.addWidget(self.pipeline)

        # ── Main splitter ─────────────────────────────────────────────────────
        main_split=QSplitter(Qt.Horizontal)
        main_split.addWidget(vp_container); main_split.addWidget(right_split)
        main_split.setStretchFactor(0,4); main_split.setStretchFactor(1,1)
        self.setCentralWidget(main_split)

        self._build_toolbar()
        self._load_theme()
        self.statusBar().showMessage("Ready — select a tool from the toolbar")

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb=self.addToolBar("Tools"); tb.setMovable(False)

        # File actions
        def act(lbl,slot,tip="",sc=""):
            a=QAction(lbl,self); a.setToolTip(tip)
            if sc: a.setShortcut(sc)
            a.triggered.connect(slot); tb.addAction(a); return a

        act("New",   self._new,  "New project","Ctrl+N")
        act("Open…", self._open, "Open project","Ctrl+O")
        act("Save…", self._save, "Save project","Ctrl+S")
        tb.addSeparator()
        self._act_undo=act("↩ Undo",self._undo,"Undo","Ctrl+Z"); self._act_undo.setEnabled(False)
        self._act_redo=act("↪ Redo",self._redo,"Redo","Ctrl+Y"); self._act_redo.setEnabled(False)
        tb.addSeparator()
        act("⊞ Frame",  self.vp.frame_all,  "Frame all","F")
        act("⟳ Reset",  self.vp.reset_view, "Reset view","R")
        tb.addSeparator()

        # Tool buttons (radio group)
        tool_group: List[QAction] = []
        def tool_act(lbl,tool,tip,sc):
            a=QAction(lbl,self); a.setToolTip(tip); a.setShortcut(sc)
            a.setCheckable(True)
            a.triggered.connect(lambda checked,t=tool: self._set_tool(t))
            tb.addAction(a); tool_group.append(a); return a

        self._tool_actions={
            TOOL_SELECT: tool_act("↖ Select","select","Select vertices and faces (S)","S"),
            TOOL_VERTEX: tool_act("+ Vertex","add_vertex","Add a new vertex (V)","V"),
            TOOL_BLOCK:  tool_act("⬡ Block", "add_block","Add a hex block (B)","B"),
            TOOL_EDGE:   tool_act("~ Edge",  "add_edge", "Add arc/spline edge (E)","E"),
            TOOL_PATCH:  tool_act("🎨 Patch","paint_patch","Paint faces onto patch (P)","P"),
        }
        tb.addSeparator()
        act("⚡ Auto patches", self._auto_patches, "Auto-generate patches from boundary faces")
        act("📋 Export",       self._show_export,  "Open export / validation panel")
        tb.addSeparator()

        # View toggles as checkable actions
        def view_tog(lbl, attr, default, tip):
            a=QAction(lbl,self); a.setCheckable(True); a.setChecked(default)
            a.setToolTip(tip)
            a.toggled.connect(lambda v,at=attr: setattr(self.vp,at,v) or self.vp.update())
            tb.addAction(a)

        view_tog("Axes",     "show_axes",             True,  "Show coordinate axes")
        view_tog("V.Labels", "show_labels",            True,  "Vertex index labels")
        view_tog("B.Labels", "show_block_labels",      True,  "Block centroid labels")
        view_tog("F.Labels", "show_face_patch_labels", False, "Patch name on each face")
        view_tog("Int.Edges","show_internal_edges",    True,  "Internal shared edges (purple)")
        view_tog("Normals",  "show_normals",           False, "Face outward normals")

        # Activate default tool
        self._set_tool(TOOL_SELECT)

    # ── tool switching ────────────────────────────────────────────────────────

    def _set_tool(self, tool: str):
        # Cancel any in-progress operations
        self.vp.block_pending = []
        self.vp.edge_v0 = -1
        self.vp.selected_vertex = -1
        self.vp.selected_face   = None

        self.vp.tool = tool
        for t,a in self._tool_actions.items():
            a.setChecked(t == tool)

        if tool == TOOL_VERTEX:
            self.inspector.show_add_vertex()
        elif tool == TOOL_SELECT:
            self.inspector.show_empty()
        elif tool == TOOL_PATCH:
            # Select first patch if none active
            if self.vp.selected_patch_idx < 0 and self.mesh.patches:
                self.vp.selected_patch_idx = 0
                self.inspector.show_patch(0)
                self.outliner._select_item(Outliner.KIND_PATCH, 0)
        self.vp.update()

    # ── viewport click handlers ───────────────────────────────────────────────

    def _on_vp_vertex_click(self, idx: int):
        tool = self.vp.tool
        if tool == TOOL_SELECT:
            self.inspector.show_vertex(idx)
            self.outliner._select_item(Outliner.KIND_VERTEX, idx)

        elif tool == TOOL_BLOCK:
            if idx in self.vp.block_pending:
                return
            self.vp.block_pending.append(idx)
            self.vp.update()
            if len(self.vp.block_pending) == 8:
                self._finish_block()

        elif tool == TOOL_EDGE:
            if self.vp.edge_v0 < 0:
                self.vp.edge_v0 = idx
                self.statusBar().showMessage(f"Edge: v0={idx} selected — click v1")
                self.vp.update()
            elif idx != self.vp.edge_v0:
                self._finish_edge(self.vp.edge_v0, idx)

    def _on_vp_face_click(self, bi: int, fi: int):
        tool = self.vp.tool
        if tool == TOOL_SELECT:
            self.inspector.show_face(bi, fi)
        elif tool == TOOL_PATCH:
            sel = self.vp.selected_patch_idx
            if sel < 0 or sel >= len(self.mesh.patches):
                return
            self._snapshot()
            patch = self.mesh.patches[sel]
            key   = self.mesh._face_key(bi, fi)
            if any(f.block_idx==bi and f.face_idx==fi for f in patch.faces):
                patch.faces=[f for f in patch.faces
                             if not (f.block_idx==bi and f.face_idx==fi)]
            else:
                for p in self.mesh.patches:
                    if p is patch: continue
                    p.faces=[f for f in p.faces
                              if self.mesh._face_key(f.block_idx,f.face_idx)!=key]
                patch.faces.append(BlockFaceRef(bi,fi))
            self._on_changed(snapshot=False)

    # ── block / edge finish ───────────────────────────────────────────────────

    def _finish_block(self):
        raw = list(self.vp.block_pending)
        try:    ordered = reorder_hex_vertices(raw, self.mesh.vertices)
        except: ordered = raw
        block = HexBlock(list(ordered))
        dlg = BlockDialog(self, block)
        if dlg.exec(): dlg.apply_to(block)
        self._snapshot()
        self.mesh.blocks.append(block)
        self.vp.block_pending = []
        self.inspector.show_block(len(self.mesh.blocks)-1)
        self._on_changed(snapshot=False)

    def _finish_edge(self, v0: int, v1: int):
        # Ask type via small dialog
        dlg = QDialog(self); dlg.setWindowTitle("Add Edge"); dlg.setFixedWidth(260)
        fl = QFormLayout(dlg)
        fl.addRow(QLabel(f"v0 = {v0},  v1 = {v1}"))
        tc = QComboBox(); tc.addItems(["arc","spline (polyLine)"]); fl.addRow("Type:",tc)
        mx=QDoubleSpinBox(decimals=6,minimum=-1e9,maximum=1e9)
        my=QDoubleSpinBox(decimals=6,minimum=-1e9,maximum=1e9)
        mz=QDoubleSpinBox(decimals=6,minimum=-1e9,maximum=1e9)
        if v0<len(self.mesh.vertices) and v1<len(self.mesh.vertices):
            p0=self.mesh.vertices[v0]; p1=self.mesh.vertices[v1]
            mx.setValue((p0.x+p1.x)/2); my.setValue((p0.y+p1.y)/2); mz.setValue((p0.z+p1.z)/2)
        arc_grp=QGroupBox("Arc midpoint"); af=QFormLayout(arc_grp)
        af.addRow("X:",mx); af.addRow("Y:",my); af.addRow("Z:",mz)
        fl.addRow(arc_grp)
        spl_grp=QGroupBox("Spline waypoints (x y z per line)")
        spl_grp.setVisible(False); sf=QVBoxLayout(spl_grp)
        spl_txt=QTextEdit(); spl_txt.setMaximumHeight(80); spl_txt.setFont(QFont("Consolas",9))
        sf.addWidget(spl_txt); fl.addRow(spl_grp)
        tc.currentIndexChanged.connect(lambda i: (arc_grp.setVisible(i==0), spl_grp.setVisible(i==1)))
        btns=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        fl.addRow(btns)
        if not dlg.exec(): self.vp.edge_v0=-1; self.vp.update(); return
        self._snapshot()
        if tc.currentIndex()==0:
            self.mesh.arc_edges.append(ArcEdge(v0,v1,(mx.value(),my.value(),mz.value())))
        else:
            pts=[]
            for raw in spl_txt.toPlainText().strip().splitlines():
                parts=raw.strip().split()
                if len(parts)>=3:
                    try: pts.append((float(parts[0]),float(parts[1]),float(parts[2])))
                    except: pass
            if pts: self.mesh.spline_edges.append(SplineEdge(v0,v1,pts))
        self.vp.edge_v0=-1
        self._on_changed(snapshot=False)

    # ── outliner selection ────────────────────────────────────────────────────

    def _on_outliner_select(self, kind: str, idx: int):
        if kind == Outliner.KIND_VERTEX:
            self.vp.selected_vertex=idx; self.vp.highlight_verts=[idx]
            self.inspector.show_vertex(idx)
        elif kind == Outliner.KIND_BLOCK:
            verts=self.mesh.blocks[idx].verts if idx<len(self.mesh.blocks) else []
            self.vp.highlight_verts=verts
            self.inspector.show_block(idx)
        elif kind == Outliner.KIND_PATCH:
            self.vp.selected_patch_idx=idx
            self.inspector.show_patch(idx)
            if idx<len(self.mesh.patches):
                self.vp.highlight_faces=[(r.block_idx,r.face_idx)
                                         for r in self.mesh.patches[idx].faces]
        elif kind in (Outliner.KIND_ARC, Outliner.KIND_SPLINE):
            self.inspector.show_empty()
        self.vp.update()

    # ── undo / redo ───────────────────────────────────────────────────────────

    def _snapshot(self):
        self._undo_stack.append(self.mesh.to_dict())
        if len(self._undo_stack)>self._MAX_UNDO: self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._act_undo.setEnabled(True); self._act_redo.setEnabled(False)

    def _restore(self, snap):
        nm=MeshModel.from_dict(snap); self.mesh.__dict__.update(nm.__dict__)
        if self.vp.selected_patch_idx>=len(self.mesh.patches):
            self.vp.selected_patch_idx=-1
        self._refresh_all()

    def _undo(self):
        if not self._undo_stack: return
        self._redo_stack.append(self.mesh.to_dict())
        self._restore(self._undo_stack.pop())
        self._act_undo.setEnabled(bool(self._undo_stack))
        self._act_redo.setEnabled(True)
        self.statusBar().showMessage("Undo",1500)

    def _redo(self):
        if not self._redo_stack: return
        self._undo_stack.append(self.mesh.to_dict())
        self._restore(self._redo_stack.pop())
        self._act_undo.setEnabled(True)
        self._act_redo.setEnabled(bool(self._redo_stack))
        self.statusBar().showMessage("Redo",1500)

    # ── change propagation ────────────────────────────────────────────────────

    def _on_changed(self, snapshot=True):
        if snapshot: self._snapshot()
        self._dirty=True; self._refresh_all()

    def _refresh_all(self):
        self.outliner.refresh(); self.pipeline.refresh()
        self.vp.update()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _auto_patches(self):
        self._snapshot(); self.mesh.auto_generate_patches()
        self._on_changed(snapshot=False)
        # Select first new patch in outliner
        if self.mesh.patches:
            self.vp.selected_patch_idx=0
            self.inspector.show_patch(0)
            self.outliner._select_item(Outliner.KIND_PATCH,0)

    def _show_export(self):
        self.inspector.show_export()

    # ── theme ─────────────────────────────────────────────────────────────────

    def _load_theme(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background:#12161f; color:#c8cfe0; }
        QPushButton { background:#1e2a3a; color:#c8d8f0; border:1px solid #2e3d55;
                      padding:4px 10px; border-radius:4px; }
        QPushButton:hover    { background:#253348; }
        QPushButton:pressed  { background:#1a2535; }
        QPushButton:checked  { background:#1a4060; border-color:#4090c0; }
        QPushButton:disabled { color:#4a5568; }
        QListWidget  { background:#151c28; border:1px solid #2a3040;
                       color:#b0bcd0; selection-background-color:#1e3050; }
        QTreeWidget  { background:#0f1520; border:none; color:#b0bcd0; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background:#151c28; color:#c8d8f0; border:1px solid #2a3040;
            padding:2px 4px; border-radius:3px; }
        QGroupBox { border:1px solid #2a3040; border-radius:4px;
                    margin-top:8px; color:#8899cc; }
        QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
        QLabel     { color:#9aabbd; }
        QToolBar   { background:#0e1420; border-bottom:1px solid #1e2838;
                     spacing:2px; padding:2px; }
        QToolBar QToolButton { color:#b0c0d8; padding:4px 10px; border-radius:4px; }
        QToolBar QToolButton:hover   { background:#1e2e40; }
        QToolBar QToolButton:checked { background:#1a4060; color:#80c0ff; }
        QStatusBar { background:#0b1018; color:#506070;
                     border-top:1px solid #1a2030; }
        QSplitter::handle          { background:#1e2838; }
        QSplitter::handle:vertical { height:5px; background:#1e2838;
                                     border-top:1px solid #2e4058;
                                     border-bottom:1px solid #2e4058; }
        QSplitter::handle:horizontal { width:4px; background:#1e2838;
                                       border-left:1px solid #2e4058;
                                       border-right:1px solid #2e4058; }
        QSplitter::handle:hover    { background:#2e4860; }
        QStackedWidget { background:#12161f; }
        QCheckBox { color:#9aabbd; }
        QScrollArea { border:none; }
        """)

    # ── file operations ───────────────────────────────────────────────────────

    def _new(self):
        if self._dirty and not self._confirm_discard(): return
        self.mesh.__init__()
        self.vp.block_pending=[]; self.vp.edge_v0=-1
        self.vp.selected_vertex=-1; self.vp.selected_patch_idx=-1
        self._undo_stack.clear(); self._redo_stack.clear()
        self._act_undo.setEnabled(False); self._act_redo.setEnabled(False)
        self._refresh_all(); self.inspector.show_empty()
        self._dirty=False; self.setWindowTitle("blockMeshDict Creator")

    def _open(self):
        if self._dirty and not self._confirm_discard(): return
        path,_=QFileDialog.getOpenFileName(self,"Open project","",
                                           "JSON project (*.json);;All files (*)")
        if not path: return
        try:
            with open(path) as fh: data=json.load(fh)
            nm=MeshModel.from_dict(data); self.mesh.__dict__.update(nm.__dict__)
            self.vp.selected_patch_idx=-1
            self._undo_stack.clear(); self._redo_stack.clear()
            self._act_undo.setEnabled(False); self._act_redo.setEnabled(False)
            self._refresh_all(); self.inspector.show_empty()
            self.vp.frame_all(); self._dirty=False
            self.setWindowTitle(f"blockMeshDict Creator — {path}")
        except Exception as exc:
            QMessageBox.critical(self,"Error loading file",str(exc))

    def _save(self):
        path,_=QFileDialog.getSaveFileName(self,"Save project","mesh_project.json",
                                           "JSON project (*.json);;All files (*)")
        if not path: return
        try:
            with open(path,"w") as fh: json.dump(self.mesh.to_dict(),fh,indent=2)
            self._dirty=False; self.setWindowTitle(f"blockMeshDict Creator — {path}")
        except Exception as exc:
            QMessageBox.critical(self,"Error saving",str(exc))

    def _confirm_discard(self):
        return QMessageBox.question(self,"Unsaved changes",
            "Discard unsaved changes?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes

    def closeEvent(self, ev):
        if self._dirty and not self._confirm_discard(): ev.ignore()
        else: ev.accept()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app=QApplication(sys.argv)
    app.setApplicationName("blockMeshDict Creator")
    win=MainWindow()

    # Demo: two connected blocks
    m=win.mesh
    for x,y,z in [(0,0,0),(1,0,0),(1,1,0),(0,1,0),
                  (0,0,1),(1,0,1),(1,1,1),(0,1,1),
                  (0,0,2),(1,0,2),(1,1,2),(0,1,2)]:
        m.vertices.append(Vertex(x,y,z))
    m.blocks.append(HexBlock([0,1,2,3,4,5,6,7],[10,10,10],"simpleGrading (1 1 1)","lower"))
    m.blocks.append(HexBlock([4,5,6,7,8,9,10,11],[10,10,10],"simpleGrading (1 1 1)","upper"))
    m.auto_generate_patches()
    win._refresh_all(); win._dirty=False; win.vp.frame_all()
    win.show(); sys.exit(app.exec())


if __name__=="__main__":
    main()
