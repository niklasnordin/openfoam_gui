#!/usr/bin/env python3
"""
stl_viewer.py — Standalone STL viewer using software rendering (QPainter).

No OpenGL required — only PySide6 and numpy.

Features:
  - Loads ASCII and binary STL files (single or multi-solid)
  - Per-solid visibility toggles with color-coded legend
  - Bounding box and center of gravity display per solid
  - 3D rotation (LMB), pan (MMB/Shift+LMB), zoom (scroll)
  - Bounding box wireframe overlay, axes indicator
  - Drag-and-drop file loading
  - Painter's algorithm depth sorting with diffuse shading

Usage:
    python stl_viewer.py [file1.stl file2.stl ...]

Requirements:
    PySide6>=6.5, numpy
"""

from __future__ import annotations

import sys
import struct
import math
import re
from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSplitter, QToolBar, QFileDialog, QCheckBox, QFrame,
    QScrollArea, QGroupBox, QFormLayout, QPushButton, QMessageBox,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import (
    QAction, QColor, QPainter, QPen, QBrush, QPolygonF,
    QLinearGradient, QFont, QDragEnterEvent, QDropEvent,
)


# ================================================================ #
#  STL parser
# ================================================================ #

def parse_stl(filepath: str) -> dict:
    """Parse an STL file. Returns {solid_name: {triangles, normals}}.

    Tries ASCII parsing first (since ASCII format is unambiguous with
    solid/endsolid blocks).  Falls back to binary if ASCII yields nothing.
    """
    path = Path(filepath)
    raw = path.read_bytes()

    # Try ASCII first — it's unambiguous if we find solid/vertex/endsolid
    try:
        text = raw.decode('ascii', errors='replace')
        if ('vertex' in text.lower() and 'endsolid' in text.lower()):
            result = _parse_ascii(text, path.stem)
            if result and any(d["triangles"].shape[0] > 0
                              for d in result.values()):
                return result
    except Exception:
        pass

    # Binary fallback
    return _parse_binary(raw, path.stem)


def _parse_binary(data: bytes, default_name: str) -> dict:
    n_tri = struct.unpack_from('<I', data, 80)[0]
    tris = np.zeros((n_tri, 3, 3), dtype=np.float32)
    norms = np.zeros((n_tri, 3), dtype=np.float32)
    offset = 84
    for i in range(n_tri):
        vals = struct.unpack_from('<12fH', data, offset)
        norms[i] = vals[0:3]
        tris[i, 0] = vals[3:6]
        tris[i, 1] = vals[6:9]
        tris[i, 2] = vals[9:12]
        offset += 50
    return {default_name: {"triangles": tris, "normals": norms}}


def _parse_ascii(text: str, default_name: str) -> dict:
    solids = {}
    name_counts = {}  # track duplicates

    for match in re.finditer(
            r'solid\s+(\S*)(.*?)endsolid', text, re.DOTALL | re.IGNORECASE):
        raw_name = match.group(1).strip() or default_name
        # Strip .stl/.obj extension if it matches — tools often write filename as solid name
        for ext in ('.stl', '.obj', '.STL', '.OBJ'):
            if raw_name.endswith(ext):
                raw_name = raw_name[:-len(ext)]
                break

        block = match.group(2)
        verts = re.findall(
            r'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)',
            block, re.IGNORECASE)
        norm_matches = re.findall(
            r'facet\s+normal\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)',
            block, re.IGNORECASE)
        n_tri = len(verts) // 3
        if n_tri == 0:
            continue
        tris = np.zeros((n_tri, 3, 3), dtype=np.float32)
        norms = np.zeros((n_tri, 3), dtype=np.float32)
        for i in range(n_tri):
            for j in range(3):
                v = verts[i * 3 + j]
                tris[i, j] = [float(v[0]), float(v[1]), float(v[2])]
            if i < len(norm_matches):
                n = norm_matches[i]
                norms[i] = [float(n[0]), float(n[1]), float(n[2])]

        # Handle duplicate names by appending _0, _1, ...
        if raw_name in name_counts:
            count = name_counts[raw_name]
            # Rename the first occurrence when we discover the first duplicate
            if count == 1 and raw_name in solids:
                solids[f"{raw_name}_0"] = solids.pop(raw_name)
            unique_name = f"{raw_name}_{count}"
            name_counts[raw_name] = count + 1
        else:
            unique_name = raw_name
            name_counts[raw_name] = 1

        solids[unique_name] = {"triangles": tris, "normals": norms}

    if not solids:
        solids[default_name] = {
            "triangles": np.zeros((0, 3, 3), dtype=np.float32),
            "normals": np.zeros((0, 3), dtype=np.float32),
        }
    return solids


# ================================================================ #
#  Solid data model
# ================================================================ #

SOLID_COLORS = [
    (77, 153, 230), (230, 102, 77), (77, 204, 115), (242, 191, 51),
    (179, 102, 217), (51, 204, 204), (242, 140, 77), (166, 191, 89),
    (217, 102, 166), (115, 166, 191),
]


# ================================================================ #
#  Mesh decimation (vertex clustering)
# ================================================================ #

def decimate_mesh(triangles, normals, max_triangles):
    """Decimate a triangle mesh using vertex clustering.

    Divides space into a grid, snaps every vertex to the nearest grid
    centre, and rebuilds triangles.  Degenerate triangles (where two or
    more vertices collapse to the same cell) are discarded.

    Uses binary search on grid resolution to hit the target count.

    Args:
        triangles: (N, 3, 3) float32 array of triangle vertices
        normals:   (N, 3)    float32 array of face normals
        max_triangles: target maximum triangle count

    Returns:
        (new_triangles, new_normals) — decimated arrays
    """
    n = len(triangles)
    if n <= max_triangles or n == 0:
        return triangles, normals

    all_v = triangles.reshape(-1, 3)
    bbox_min = all_v.min(axis=0)
    bbox_max = all_v.max(axis=0)
    bbox_size = bbox_max - bbox_min
    bbox_size[bbox_size < 1e-10] = 1e-10

    def _cluster(cells_per_axis):
        """Run vertex clustering at a given resolution, return (tris, norms, count)."""
        cpa = max(2, int(cells_per_axis))
        cs = bbox_size / cpa

        flat_v = triangles.reshape(-1, 3)
        ci = np.floor((flat_v - bbox_min) / cs).astype(np.int32)
        ci = np.clip(ci, 0, cpa - 1)

        cell_id = ci[:, 0] * cpa * cpa + ci[:, 1] * cpa + ci[:, 2]

        unique_ids, inverse = np.unique(cell_id, return_inverse=True)
        n_u = len(unique_ids)
        avg_pos = np.zeros((n_u, 3), dtype=np.float64)
        np.add.at(avg_pos, inverse, flat_v)
        counts = np.zeros(n_u, dtype=np.int32)
        np.add.at(counts, inverse, 1)
        avg_pos /= counts[:, None].clip(1)

        ti = inverse.reshape(-1, 3)
        valid = ((ti[:, 0] != ti[:, 1]) &
                 (ti[:, 1] != ti[:, 2]) &
                 (ti[:, 0] != ti[:, 2]))

        ti = ti[valid]
        new_tris = avg_pos[ti].astype(np.float32)

        # Recompute normals
        e0 = new_tris[:, 1] - new_tris[:, 0]
        e1 = new_tris[:, 2] - new_tris[:, 0]
        cn = np.cross(e0, e1)
        mg = np.linalg.norm(cn, axis=1, keepdims=True)
        mg[mg < 1e-10] = 1.0
        new_norms = (cn / mg).astype(np.float32)

        return new_tris, new_norms, len(new_tris)

    # Binary search: find the HIGHEST cells_per_axis where output ≤ max_triangles
    # Low cpa = coarse grid = fewer output triangles
    # High cpa = fine grid = more output triangles (closer to original)
    lo, hi = 2, max(4, int(math.sqrt(n) * 2))

    # Ensure hi is fine enough to exceed target (otherwise no decimation needed at hi)
    _, _, hi_count = _cluster(hi)
    if hi_count <= max_triangles:
        return _cluster(hi)[:2]  # full resolution already under target

    # Binary search (12 iterations gives precision within 1 cell)
    best_tris, best_norms = None, None
    for _ in range(12):
        mid = (lo + hi) // 2
        if mid <= lo:
            break
        t, nm, count = _cluster(mid)
        if count <= max_triangles:
            best_tris, best_norms = t, nm
            lo = mid  # try finer resolution (more output)
        else:
            hi = mid  # too many — need coarser grid

    if best_tris is not None:
        return best_tris, best_norms

    # Fallback: use coarsest grid, then subsample if still over target
    t, nm, count = _cluster(2)
    if count > max_triangles:
        # Random subsample to hit target
        idx = np.random.choice(count, max_triangles, replace=False)
        idx.sort()
        t = t[idx]
        nm = nm[idx]
    return t, nm


class SolidData:
    """Holds mesh data and metadata for one STL solid.

    Original data is kept for accurate metrics.  For rendering, a
    decimated copy is stored in `display_triangles` / `display_normals`.
    """

    # Default cap for the display mesh — per solid
    MAX_DISPLAY_TRIANGLES = 50_000

    def __init__(self, name, triangles, normals, color, file_name=""):
        self.name = name
        self.file_name = file_name
        self.triangles = triangles      # original — used for metrics
        self.normals = normals
        self.color = color  # (R, G, B) 0-255
        self.visible = True
        self.n_triangles = len(triangles)

        if self.n_triangles > 0:
            all_v = triangles.reshape(-1, 3)
            self.bbox_min = all_v.min(axis=0)
            self.bbox_max = all_v.max(axis=0)
            centroids = triangles.mean(axis=1)
            v0 = triangles[:, 1] - triangles[:, 0]
            v1 = triangles[:, 2] - triangles[:, 0]
            areas = 0.5 * np.linalg.norm(np.cross(v0, v1), axis=1)
            total = areas.sum()
            self.cog = ((centroids * areas[:, None]).sum(0) / total
                        if total > 0 else centroids.mean(0))
            self.surface_area = float(total)

            # Fix zero normals
            mag = np.linalg.norm(self.normals, axis=1)
            bad = mag < 1e-10
            if bad.any():
                comp = np.cross(v0[bad], v1[bad])
                nm = np.linalg.norm(comp, axis=1, keepdims=True)
                nm[nm < 1e-10] = 1.0
                self.normals[bad] = comp / nm
        else:
            self.bbox_min = self.bbox_max = self.cog = np.zeros(3)
            self.surface_area = 0.0

        # Display data — decimated if needed
        self._build_display_mesh(self.MAX_DISPLAY_TRIANGLES)

    def _build_display_mesh(self, max_tris):
        """Build or rebuild the decimated display mesh."""
        self.display_triangles, self.display_normals = decimate_mesh(
            self.triangles, self.normals, max_tris)
        self.n_display_triangles = len(self.display_triangles)
        self.is_decimated = self.n_display_triangles < self.n_triangles

    def set_max_display_triangles(self, max_tris):
        """Change the display triangle budget and rebuild."""
        self.MAX_DISPLAY_TRIANGLES = max_tris
        self._build_display_mesh(max_tris)

    @property
    def bbox_size(self):
        return self.bbox_max - self.bbox_min

    @property
    def bbox_center(self):
        return (self.bbox_min + self.bbox_max) / 2


# ================================================================ #
#  Software 3D viewport (QPainter)
# ================================================================ #

def _rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float64)

def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float64)


class SoftwareViewport(QWidget):
    """3D viewport using QPainter with painter's-algorithm depth sort."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.solids: list[SolidData] = []
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self._rot_x_deg = 30.0
        self._rot_y_deg = -45.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom = 1.0
        self._center = np.zeros(3)
        self._radius = 1.0

        self._last_pos = None
        self._mouse_btn = None

        self.show_wireframe = False
        self.show_bbox = True
        self.show_axes = True

        self._light_dir = np.array([0.57, 0.57, 0.57])  # normalized

    def set_solids(self, solids):
        self.solids = solids
        self._fit_scene()
        self.update()

    def _fit_scene(self):
        all_min = np.full(3, 1e30)
        all_max = np.full(3, -1e30)
        for s in self.solids:
            if s.n_triangles > 0:
                all_min = np.minimum(all_min, s.bbox_min)
                all_max = np.maximum(all_max, s.bbox_max)
        if all_min[0] > all_max[0]:
            all_min, all_max = np.zeros(3), np.ones(3)
        self._center = (all_min + all_max) / 2
        self._radius = max(float(np.linalg.norm(all_max - all_min)) / 2, 1e-6)
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0

    def _view_matrix(self):
        rx = math.radians(self._rot_x_deg)
        ry = math.radians(self._rot_y_deg)
        return _rot_x(rx) @ _rot_y(ry)

    def _project(self, pts_world):
        """World coords → screen coords. Returns (N,3) with z for depth."""
        R = self._view_matrix()
        centered = pts_world - self._center
        view = (R @ centered.T).T  # (N, 3)

        w, h = self.width(), self.height()
        scale = min(w, h) * 0.4 * self._zoom / self._radius

        screen = np.empty_like(view)
        screen[:, 0] = view[:, 0] * scale + w / 2 + self._pan_x * scale
        screen[:, 1] = -view[:, 1] * scale + h / 2 + self._pan_y * scale
        screen[:, 2] = view[:, 2]  # depth
        return screen

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(30, 33, 38))
        grad.setColorAt(1, QColor(18, 20, 24))
        p.fillRect(self.rect(), grad)

        R = self._view_matrix()

        # Collect all visible triangles for depth sorting
        all_tris = []  # list of (depth, color_rgb, screen_pts_3x2, normal_shade)

        for solid in self.solids:
            if not solid.visible or solid.n_display_triangles == 0:
                continue

            # Project all vertices at once — use display (decimated) mesh
            flat_v = solid.display_triangles.reshape(-1, 3).astype(np.float64)
            screen = self._project(flat_v).reshape(-1, 3, 3)

            # Depth = average z of each triangle (for sorting)
            depths = screen[:, :, 2].mean(axis=1)

            # Shading: dot(normal, light)
            rot_normals = (R @ solid.display_normals.astype(np.float64).T).T
            shade = np.clip(rot_normals @ self._light_dir, 0.0, 1.0)
            # Ambient + diffuse
            brightness = 0.25 + 0.75 * shade

            r0, g0, b0 = solid.color
            for i in range(solid.n_display_triangles):
                bri = brightness[i]
                cr = int(min(255, r0 * bri))
                cg = int(min(255, g0 * bri))
                cb = int(min(255, b0 * bri))
                pts = screen[i, :, :2]  # (3, 2)
                all_tris.append((depths[i], (cr, cg, cb), pts,
                                 (r0, g0, b0)))

        # Sort back to front (most negative z first)
        all_tris.sort(key=lambda t: t[0])

        # Draw triangles
        for depth, (cr, cg, cb), pts, base_col in all_tris:
            poly = QPolygonF([QPointF(pts[0,0], pts[0,1]),
                              QPointF(pts[1,0], pts[1,1]),
                              QPointF(pts[2,0], pts[2,1])])
            fill_color = QColor(cr, cg, cb)
            if self.show_wireframe:
                p.setPen(QPen(fill_color, 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
            else:
                p.setPen(QPen(QColor(cr//2, cg//2, cb//2), 1))
                p.setBrush(QBrush(fill_color))
            p.drawPolygon(poly)

        # Bounding boxes
        if self.show_bbox:
            self._draw_bboxes(p)

        # Axes
        if self.show_axes:
            self._draw_axes(p)

        # Triangle count
        disp_total = sum(s.n_display_triangles for s in self.solids if s.visible)
        orig_total = sum(s.n_triangles for s in self.solids if s.visible)
        any_decimated = any(s.is_decimated for s in self.solids if s.visible)
        p.setPen(QPen(QColor(120, 144, 156), 1))
        p.setFont(QFont("monospace", 9))
        if any_decimated:
            p.drawText(8, self.height() - 8,
                       f"Display: {disp_total:,} tris  (original: {orig_total:,})")
        else:
            p.drawText(8, self.height() - 8, f"{orig_total:,} triangles")

        p.end()

    def _draw_bboxes(self, p: QPainter):
        for solid in self.solids:
            if not solid.visible or solid.n_triangles == 0:
                continue
            mn, mx = solid.bbox_min, solid.bbox_max
            corners = np.array([
                [mn[0],mn[1],mn[2]], [mx[0],mn[1],mn[2]],
                [mx[0],mx[1],mn[2]], [mn[0],mx[1],mn[2]],
                [mn[0],mn[1],mx[2]], [mx[0],mn[1],mx[2]],
                [mx[0],mx[1],mx[2]], [mn[0],mx[1],mx[2]],
            ], dtype=np.float64)
            sc = self._project(corners)
            edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                     (0,4),(1,5),(2,6),(3,7)]
            r, g, b = solid.color
            p.setPen(QPen(QColor(r, g, b, 100), 1, Qt.PenStyle.DashLine))
            for a, b_ in edges:
                p.drawLine(QPointF(sc[a,0], sc[a,1]),
                           QPointF(sc[b_,0], sc[b_,1]))

    def _draw_axes(self, p: QPainter):
        length = self._radius * 0.15
        origin = self._center.copy()
        pts = np.array([origin,
                        origin + [length,0,0],
                        origin + [0,length,0],
                        origin + [0,0,length]], dtype=np.float64)
        sc = self._project(pts)
        for i, (color, label) in enumerate([
                (QColor(255,70,70), "X"),
                (QColor(70,255,70), "Y"),
                (QColor(80,100,255), "Z")]):
            p.setPen(QPen(color, 2))
            p.drawLine(QPointF(sc[0,0], sc[0,1]),
                       QPointF(sc[i+1,0], sc[i+1,1]))
            p.setFont(QFont("monospace", 9, QFont.Weight.Bold))
            p.drawText(int(sc[i+1,0])+4, int(sc[i+1,1])-4, label)

    # ---- Mouse interaction ----

    def mousePressEvent(self, event):
        self._last_pos = event.position()
        self._mouse_btn = event.button()

    def mouseMoveEvent(self, event):
        if self._last_pos is None:
            return
        pos = event.position()
        dx = pos.x() - self._last_pos.x()
        dy = pos.y() - self._last_pos.y()

        shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        if self._mouse_btn == Qt.MouseButton.LeftButton and not shift:
            self._rot_x_deg += dy * 0.5
            self._rot_y_deg += dx * 0.5
        elif (self._mouse_btn == Qt.MouseButton.MiddleButton or
              (self._mouse_btn == Qt.MouseButton.LeftButton and shift)):
            scale = self._radius * 0.003 / self._zoom
            self._pan_x += dx * scale
            self._pan_y += dy * scale
        elif self._mouse_btn == Qt.MouseButton.RightButton:
            self._zoom *= 1.0 + dy * 0.005
            self._zoom = max(0.01, min(100, self._zoom))

        self._last_pos = pos
        self.update()

    def mouseReleaseEvent(self, event):
        self._last_pos = None
        self._mouse_btn = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self._zoom *= 1.0 + delta * 0.001
        self._zoom = max(0.01, min(100, self._zoom))
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        window = self.window()
        if hasattr(window, 'load_file'):
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith('.stl'):
                    window.load_file(path)


# ================================================================ #
#  Info panel
# ================================================================ #

class SolidInfoPanel(QScrollArea):
    """Displays per-solid info with visibility checkboxes."""

    visibility_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self.setWidget(self._container)

    def set_solids(self, solids):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not solids:
            lbl = QLabel("<center><br><i>No STL loaded.<br>Drag & drop or Open.</i></center>")
            lbl.setStyleSheet("color: #78909C;")
            self._layout.addWidget(lbl)
            self._layout.addStretch()
            return

        # Global
        total_tris = sum(s.n_triangles for s in solids)
        total_area = sum(s.surface_area for s in solids)
        vis = [s for s in solids if s.n_triangles > 0]
        if vis:
            all_min = np.min([s.bbox_min for s in vis], axis=0)
            all_max = np.max([s.bbox_max for s in vis], axis=0)
        else:
            all_min = all_max = np.zeros(3)
        sz = all_max - all_min

        gbox = QGroupBox("Global")
        gbox.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #455A64; "
            "border-radius: 4px; margin-top: 8px; padding-top: 12px; }"
            "QGroupBox::title { color: #B0BEC5; }")
        gf = QFormLayout(gbox)
        gf.setContentsMargins(8, 8, 8, 8)
        gf.addRow("Solids:", self._v(f"{len(solids)}"))
        gf.addRow("Triangles:", self._v(f"{total_tris:,}"))
        gf.addRow("Area:", self._v(f"{total_area:.4g} m²"))
        gf.addRow("Size:", self._v(f"{sz[0]:.4g} × {sz[1]:.4g} × {sz[2]:.4g}"))
        gf.addRow("Min:", self._v(f"({all_min[0]:.4g}, {all_min[1]:.4g}, {all_min[2]:.4g})"))
        gf.addRow("Max:", self._v(f"({all_max[0]:.4g}, {all_max[1]:.4g}, {all_max[2]:.4g})"))
        self._layout.addWidget(gbox)

        for solid in solids:
            self._layout.addWidget(self._card(solid))

        self._layout.addStretch()

    def _card(self, solid):
        r, g, b = solid.color
        hex_c = f"#{r:02x}{g:02x}{b:02x}"
        box = QGroupBox()
        box.setStyleSheet(
            f"QGroupBox {{ border: 2px solid {hex_c}; border-radius: 4px; "
            f"margin-top: 8px; padding-top: 8px; }}")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        cb = QCheckBox(solid.name)
        cb.setChecked(solid.visible)
        cb.setStyleSheet(f"QCheckBox {{ font-weight: bold; font-size: 12px; }}")
        cb.toggled.connect(lambda on, s=solid: self._toggle(s, on))
        hdr.addWidget(cb)
        sw = QLabel("█")
        sw.setStyleSheet(f"color: {hex_c}; font-size: 16px;")
        hdr.addWidget(sw)
        hdr.addStretch()
        lay.addLayout(hdr)

        if solid.file_name:
            lay.addWidget(QLabel(
                f"<span style='color:#78909C; font-size:10px;'>{solid.file_name}</span>"))

        fm = QFormLayout()
        fm.setContentsMargins(0, 4, 0, 0)
        fm.setSpacing(2)
        fm.addRow("Triangles:", self._v(f"{solid.n_triangles:,}"))
        if solid.is_decimated:
            fm.addRow("Display:", self._v(
                f"{solid.n_display_triangles:,}  "
                f"({100*solid.n_display_triangles/max(solid.n_triangles,1):.0f}%)"))
        fm.addRow("Area:", self._v(f"{solid.surface_area:.4g} m²"))
        fm.addRow("Size:", self._v(
            f"{solid.bbox_size[0]:.4g} × {solid.bbox_size[1]:.4g} × {solid.bbox_size[2]:.4g}"))
        fm.addRow("BBox min:", self._v(
            f"({solid.bbox_min[0]:.4g}, {solid.bbox_min[1]:.4g}, {solid.bbox_min[2]:.4g})"))
        fm.addRow("BBox max:", self._v(
            f"({solid.bbox_max[0]:.4g}, {solid.bbox_max[1]:.4g}, {solid.bbox_max[2]:.4g})"))
        fm.addRow("CoG:", self._v(
            f"({solid.cog[0]:.4g}, {solid.cog[1]:.4g}, {solid.cog[2]:.4g})"))
        lay.addLayout(fm)
        return box

    def _toggle(self, solid, on):
        solid.visible = on
        self.visibility_changed.emit()

    @staticmethod
    def _v(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #CFD8DC; font-family: monospace; font-size: 11px;")
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl


# ================================================================ #
#  Main window
# ================================================================ #

STYLESHEET = """
QMainWindow { background: #1E1E1E; }
QToolBar { background: #263238; border: none; spacing: 6px; padding: 4px; }
QToolBar QLabel { color: #ECEFF1; font-size: 13px; font-weight: bold; }
QPushButton {
    background: #37474F; color: #ECEFF1; border: 1px solid #455A64;
    border-radius: 3px; padding: 4px 12px; }
QPushButton:hover { background: #455A64; }
QPushButton:checked { background: #1976D2; border-color: #42A5F5; }
QGroupBox { color: #B0BEC5; }
QLabel { color: #B0BEC5; }
QCheckBox { color: #ECEFF1; }
QScrollArea { background: #1E1E1E; }
QStatusBar { background: #263238; color: #78909C; }
QSplitter::handle { background: #37474F; width: 3px; }
"""


class STLViewer(QMainWindow):
    """Main STL viewer window."""

    def __init__(self, files=None):
        super().__init__()
        self.setWindowTitle("STL Viewer")
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(STYLESHEET)
        self.solids = []
        self._ci = 0

        # Toolbar
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addWidget(QLabel("  STL Viewer  "))
        tb.addSeparator()

        a = QAction("Open STL…", self)
        a.triggered.connect(self._open_file)
        tb.addAction(a)
        a = QAction("Clear All", self)
        a.triggered.connect(self._clear)
        tb.addAction(a)
        tb.addSeparator()

        self.btn_wire = QPushButton("Wireframe")
        self.btn_wire.setCheckable(True)
        self.btn_wire.toggled.connect(self._set_wireframe)
        tb.addWidget(self.btn_wire)

        self.btn_bbox = QPushButton("BBox")
        self.btn_bbox.setCheckable(True)
        self.btn_bbox.setChecked(True)
        self.btn_bbox.toggled.connect(self._set_bbox)
        tb.addWidget(self.btn_bbox)

        self.btn_axes = QPushButton("Axes")
        self.btn_axes.setCheckable(True)
        self.btn_axes.setChecked(True)
        self.btn_axes.toggled.connect(self._set_axes)
        tb.addWidget(self.btn_axes)

        tb.addSeparator()
        tb.addWidget(QLabel(" Max tris: "))
        self.quality_combo = QComboBox()
        self.quality_combo.setStyleSheet(
            "QComboBox { background: #37474F; color: #ECEFF1; "
            "border: 1px solid #455A64; padding: 2px 8px; }")
        for label, value in [("10k", 10_000), ("25k", 25_000),
                              ("50k", 50_000), ("100k", 100_000),
                              ("200k", 200_000), ("Unlimited", 0)]:
            self.quality_combo.addItem(label, value)
        self.quality_combo.setCurrentIndex(2)  # 50k default
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        tb.addWidget(self.quality_combo)

        tb.addSeparator()
        a = QAction("Fit View", self)
        a.triggered.connect(self._fit)
        tb.addAction(a)
        a = QAction("Reset Camera", self)
        a.triggered.connect(self._reset_cam)
        tb.addAction(a)

        # Layout
        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.viewport = SoftwareViewport()
        splitter.addWidget(self.viewport)

        self.info = SolidInfoPanel()
        self.info.visibility_changed.connect(self.viewport.update)
        splitter.addWidget(self.info)

        splitter.setSizes([700, 300])
        ml.addWidget(splitter)

        self.statusBar().showMessage("Drag & drop STL files or use Open STL…")

        if files:
            for f in files:
                self.load_file(f)

    def _current_max_tris(self):
        v = self.quality_combo.currentData()
        return 10_000_000 if v == 0 else v

    def load_file(self, filepath):
        try:
            path = Path(filepath)
            parsed = parse_stl(str(path))
            max_t = self._current_max_tris()
            for name, data in parsed.items():
                color = SOLID_COLORS[self._ci % len(SOLID_COLORS)]
                self._ci += 1
                sd = SolidData(name, data["triangles"], data["normals"],
                               color, path.name)
                sd.set_max_display_triangles(max_t)
                self.solids.append(sd)
            self.viewport.set_solids(self.solids)
            self.info.set_solids(self.solids)
            total = sum(s.n_triangles for s in self.solids)
            disp = sum(s.n_display_triangles for s in self.solids)
            msg = f"{path.name} — {len(self.solids)} solid(s), {total:,} triangles"
            if disp < total:
                msg += f" (display: {disp:,})"
            self.statusBar().showMessage(msg)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}")

    def load_from_db(self, db):
        """Load STL data using solid/surface names from CaseDatabase.

        The db already knows the correct solid names from when the STL
        was imported.  We only re-read the file for triangle geometry.
        """
        max_t = self._current_max_tris()

        for entry in db.stl_entries:
            filepath = entry["path"]
            stem = entry["stem"]
            db_solids = entry.get("solids", [stem])

            try:
                path = Path(filepath)
                parsed = parse_stl(str(path))
            except Exception as e:
                self.statusBar().showMessage(f"Error loading {filepath}: {e}")
                continue

            parsed_names = list(parsed.keys())
            parsed_data = list(parsed.values())

            # Case 1: parser found same number of solids as db
            # → use db names with parser geometry (1:1 mapping)
            if len(parsed_names) == len(db_solids):
                for dbname, data in zip(db_solids, parsed_data):
                    color = SOLID_COLORS[self._ci % len(SOLID_COLORS)]
                    self._ci += 1
                    sd = SolidData(dbname, data["triangles"],
                                   data["normals"], color, path.name)
                    sd.set_max_display_triangles(max_t)
                    self.solids.append(sd)

            # Case 2: parser found 1 solid (binary) but db has multiple
            # → one entry per db solid, all sharing the same geometry
            elif len(parsed_data) == 1 and len(db_solids) > 1:
                tris = parsed_data[0]["triangles"]
                norms = parsed_data[0]["normals"]
                for dbname in db_solids:
                    color = SOLID_COLORS[self._ci % len(SOLID_COLORS)]
                    self._ci += 1
                    sd = SolidData(dbname, tris, norms, color, path.name)
                    sd.set_max_display_triangles(max_t)
                    self.solids.append(sd)

            # Case 3: parser found MORE solids than db knows about
            # → use parser results (has the real solid names from file)
            elif len(parsed_names) > len(db_solids):
                for pname, data in zip(parsed_names, parsed_data):
                    color = SOLID_COLORS[self._ci % len(SOLID_COLORS)]
                    self._ci += 1
                    sd = SolidData(pname, data["triangles"],
                                   data["normals"], color, path.name)
                    sd.set_max_display_triangles(max_t)
                    self.solids.append(sd)

            # Case 4: anything else — use parser names
            else:
                for name, data in parsed.items():
                    color = SOLID_COLORS[self._ci % len(SOLID_COLORS)]
                    self._ci += 1
                    sd = SolidData(name, data["triangles"],
                                   data["normals"], color, path.name)
                    sd.set_max_display_triangles(max_t)
                    self.solids.append(sd)

        if self.solids:
            self.viewport.set_solids(self.solids)
            self.info.set_solids(self.solids)
            total = sum(s.n_triangles for s in self.solids)
            self.statusBar().showMessage(
                f"{len(self.solids)} solid(s), {total:,} triangles")

    def _open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open STL", "", "STL (*.stl);;All (*)")
        for p in paths:
            self.load_file(p)

    def _clear(self):
        self.solids.clear()
        self._ci = 0
        self.viewport.set_solids([])
        self.info.set_solids([])

    def _set_wireframe(self, on):
        self.viewport.show_wireframe = on
        self.viewport.update()

    def _set_bbox(self, on):
        self.viewport.show_bbox = on
        self.viewport.update()

    def _set_axes(self, on):
        self.viewport.show_axes = on
        self.viewport.update()

    def _on_quality_changed(self, _index):
        max_tris = self.quality_combo.currentData()
        if max_tris == 0:
            max_tris = 10_000_000  # effectively unlimited
        for solid in self.solids:
            solid.set_max_display_triangles(max_tris)
        self.viewport.update()
        self.info.set_solids(self.solids)
        disp = sum(s.n_display_triangles for s in self.solids)
        orig = sum(s.n_triangles for s in self.solids)
        if disp < orig:
            self.statusBar().showMessage(
                f"Display: {disp:,} tris (original: {orig:,})")
        else:
            self.statusBar().showMessage(f"{orig:,} triangles (full detail)")

    def _fit(self):
        self.viewport._fit_scene()
        self.viewport.update()

    def _reset_cam(self):
        self.viewport._rot_x_deg = 30.0
        self.viewport._rot_y_deg = -45.0
        self.viewport._fit_scene()
        self.viewport.update()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = STLViewer(sys.argv[1:] or None)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
