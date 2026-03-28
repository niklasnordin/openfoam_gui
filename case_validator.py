"""
Case validator — checks for common OpenFOAM setup mistakes.

Runs a series of checks on the CaseDatabase and returns warnings/errors.
Called before export and optionally on-demand from the GUI.
"""

from __future__ import annotations

from typing import Any


def validate_case(db) -> list[dict]:
    """Run all validation checks on a CaseDatabase.

    Returns list of {"level": "error"|"warning"|"info", "message": str,
                     "path": str (optional tree path)}
    """
    issues: list[dict] = []

    tmpl = db.template
    if not tmpl:
        issues.append({"level": "error", "message": "No solver template selected."})
        return issues

    _check_patches(db, issues)
    _check_boundary_conditions(db, issues)
    _check_locations_in_mesh(db, issues)
    _check_relaxation(db, issues)
    _check_time_settings(db, issues)
    _check_mesh_settings(db, issues)
    _check_stl(db, issues)
    _check_cfl_estimate(db, issues)

    if not issues:
        issues.append({"level": "info", "message": "No issues found — case looks good."})

    return issues


def validate_tree_markers(db) -> dict[str, str]:
    """Run validation and return per-tree-path status markers.

    Returns: {tree_path: "error"|"warning"|"ok"} for paths that have issues.
    Paths without issues are not included (assumed ok).
    """
    issues = validate_case(db)
    markers: dict[str, str] = {}

    for issue in issues:
        path = issue.get("path", "")
        level = issue["level"]
        if not path or level == "info":
            continue
        # Keep worst level per path
        current = markers.get(path, "ok")
        if level == "error" or (level == "warning" and current != "error"):
            markers[path] = level

    return markers


def validate_step_status(db) -> dict[str, str]:
    """Run validation and return per-workflow-step status.

    Returns: {step_id: "error"|"warning"|"done"}
    """
    issues = validate_case(db)

    # Map paths to workflow steps
    path_to_step = {
        "__patch_editor__": "bcs",
        "system/fvSchemes": "numerics",
        "system/fvSolution": "numerics",
        "system/fvOptions": "numerics",
        "system/controlDict": "run",
        "system/decomposeParDict": "run",
        "system/blockMeshDict": "mesh",
        "system/snappyHexMeshDict": "mesh",
    }

    step_status: dict[str, str] = {
        "solver": "done", "mesh": "done", "bcs": "done",
        "numerics": "done", "run": "done", "export": "done",
    }

    for issue in issues:
        level = issue["level"]
        if level == "info":
            continue
        path = issue.get("path", "")
        step = path_to_step.get(path, "export")

        current = step_status.get(step, "done")
        if level == "error" or (level == "warning" and current != "error"):
            step_status[step] = level

    return step_status


def _check_patches(db, issues):
    """Check that patches exist and have sensible roles."""
    names = db.get_patch_names()
    if not names:
        issues.append({"level": "error", "path": "__patch_editor__",
                       "message": "No patches defined. Load an STL or add patches."})
        return

    roles = {}
    for name in names:
        p = db.get_patch(name)
        role = p.get("role", "wall")
        roles.setdefault(role, []).append(name)

    if "inlet" not in roles and "wall" not in roles:
        issues.append({"level": "warning", "path": "__patch_editor__",
                       "message": "No inlet patches defined."})

    if "outlet" not in roles:
        issues.append({"level": "warning", "path": "__patch_editor__",
                       "message": "No outlet patches defined. "
                       "Closed domains need pRefCell/pRefValue."})


def _check_boundary_conditions(db, issues):
    """Check that all patches have BCs for all active fields."""
    names = db.get_patch_names()
    active = db.active_fields

    for patch_name in names:
        for field in active:
            bc_type, params = db.get_patch_bc(patch_name, field)
            if not bc_type:
                issues.append({
                    "level": "error", "path": "__patch_editor__",
                    "message": f"Patch '{patch_name}': no BC type set for field '{field}'."
                })

    # Check velocity inlet has non-zero velocity
    for patch_name in names:
        p = db.get_patch(patch_name)
        if p.get("role") == "inlet" and "U" in active:
            bc_type, params = db.get_patch_bc(patch_name, "U")
            if bc_type == "fixedValue":
                ux = _to_float(params.get("Ux", "0"))
                uy = _to_float(params.get("Uy", "0"))
                uz = _to_float(params.get("Uz", "0"))
                if abs(ux) + abs(uy) + abs(uz) < 1e-10:
                    issues.append({
                        "level": "warning", "path": "__patch_editor__",
                        "message": f"Inlet '{patch_name}': velocity is zero (Ux=Uy=Uz=0)."
                    })


def _check_locations_in_mesh(db, issues):
    """Check locationsInMesh entries."""
    locs = db.locations_in_mesh
    if not locs:
        issues.append({"level": "error", "path": "system/snappyHexMeshDict",
                       "message": "No locationInMesh defined."})
        return

    # Check if all locations are at the origin (likely user forgot to set them)
    all_zero = all(
        abs(loc.get("x", 0)) < 1e-10 and
        abs(loc.get("y", 0)) < 1e-10 and
        abs(loc.get("z", 0)) < 1e-10
        for loc in locs
    )
    if all_zero and db.has_stl:
        issues.append({
            "level": "warning", "path": "system/snappyHexMeshDict",
            "message": "All locationsInMesh are at (0, 0, 0). "
            "Ensure they are inside the mesh domain and outside STL geometry."
        })


def _check_relaxation(db, issues):
    """Check for unreasonable relaxation factors."""
    tmpl = db.template
    if not tmpl:
        return

    s = db.get_dict("system/fvSolution")
    algo = s.get("algorithm", "SIMPLE")

    if algo == "SIMPLE":
        relax_u = _to_float(s.get("relaxU", 0.7))
        relax_p = _to_float(s.get("relaxP", 0.3))

        if relax_u > 0.95:
            issues.append({"level": "warning",
                           "path": "system/fvSolution",
                           "message": f"U relaxation factor ({relax_u}) is very high "
                           "for SIMPLE. Typical: 0.5-0.9."})
        if relax_p > 0.5:
            issues.append({"level": "warning",
                           "path": "system/fvSolution",
                           "message": f"p relaxation factor ({relax_p}) is high "
                           "for SIMPLE. Typical: 0.1-0.3."})
        if relax_u < 0.1:
            issues.append({"level": "warning",
                           "path": "system/fvSolution",
                           "message": f"U relaxation factor ({relax_u}) is very low. "
                           "Convergence will be extremely slow."})


def _check_time_settings(db, issues):
    """Check time control settings."""
    s = db.get_dict("system/controlDict")
    dt = _to_float(s.get("deltaT", 1))
    end_time = _to_float(s.get("endTime", 1000))

    if dt <= 0:
        issues.append({"level": "error",
                       "path": "system/controlDict",
                       "message": "deltaT must be positive."})
    if end_time <= 0:
        issues.append({"level": "error",
                       "path": "system/controlDict",
                       "message": "endTime must be positive."})
    if dt > end_time:
        issues.append({"level": "error",
                       "path": "system/controlDict",
                       "message": f"deltaT ({dt}) is larger than endTime ({end_time})."})

    # Check write interval
    write_interval = _to_float(s.get("writeInterval", 100))
    if write_interval <= 0:
        issues.append({"level": "warning",
                       "path": "system/controlDict",
                       "message": "writeInterval should be positive."})


def _check_mesh_settings(db, issues):
    """Check blockMesh and snappy settings."""
    bmd = db.get_dict("system/blockMeshDict")
    if bmd:
        xmin = _to_float(bmd.get("xMin", -1))
        xmax = _to_float(bmd.get("xMax", 1))
        ymin = _to_float(bmd.get("yMin", -1))
        ymax = _to_float(bmd.get("yMax", 1))
        zmin = _to_float(bmd.get("zMin", -1))
        zmax = _to_float(bmd.get("zMax", 1))

        if xmin >= xmax or ymin >= ymax or zmin >= zmax:
            issues.append({"level": "error",
                           "path": "system/blockMeshDict",
                           "message": "blockMeshDict: min >= max in one or more directions. "
                           "Domain has zero or negative volume."})

        cells_x = int(_to_float(bmd.get("cellsX", 20)))
        cells_y = int(_to_float(bmd.get("cellsY", 20)))
        cells_z = int(_to_float(bmd.get("cellsZ", 20)))
        total = cells_x * cells_y * cells_z

        if total > 10_000_000:
            issues.append({"level": "warning",
                           "path": "system/blockMeshDict",
                           "message": f"blockMesh will create {total:,} cells. "
                           "This is very large for a background mesh."})

    if db.has_stl:
        snappy = db.get_dict("system/snappyHexMeshDict")
        max_global = int(_to_float(snappy.get("maxGlobalCells", 2000000)))
        if max_global < 100000:
            issues.append({"level": "warning",
                           "path": "system/snappyHexMeshDict",
                           "message": f"maxGlobalCells ({max_global:,}) is low. "
                           "May run out of cells during refinement."})


def _check_stl(db, issues):
    """Check STL-related settings."""
    if db.has_stl:
        # Check surfaces have refinement levels
        for entry in db.stl_entries:
            for solid in entry.get("solids", [entry["stem"]]):
                s = db.get_surface(solid)
                min_level = int(s.get("minLevel", 0))
                max_level = int(s.get("maxLevel", 0))
                if max_level == 0:
                    issues.append({
                        "level": "warning",
                        "path": "system/snappyHexMeshDict",
                        "message": f"Surface '{solid}': maxLevel is 0 "
                        "(no refinement). Set refinement levels in "
                        "Surface Refinement tab."
                    })
                if min_level > max_level:
                    issues.append({
                        "level": "error",
                        "path": "system/snappyHexMeshDict",
                        "message": f"Surface '{solid}': minLevel ({min_level}) > "
                        f"maxLevel ({max_level})."
                    })


def _check_cfl_estimate(db, issues):
    """Estimate CFL number and warn if too high."""
    s_ctrl = db.get_dict("system/controlDict")
    s_mesh = db.get_dict("system/blockMeshDict")

    ddt = db.get_dict("system/fvSchemes").get("ddtScheme", "steadyState")
    if ddt == "steadyState":
        return  # no CFL concern for steady-state

    dt = _to_float(s_ctrl.get("deltaT", 0.001))
    adjust = s_ctrl.get("adjustTimeStep", "no")
    if adjust == "yes":
        return  # adjustable timestep handles CFL automatically

    cell_size = _to_float(s_mesh.get("cellSize", 0.1))
    if cell_size <= 0:
        return

    # Estimate velocity from BC
    u_bc = db.get_dict("0/U")
    ux = abs(_to_float(u_bc.get("Ux", 0)))
    uy = abs(_to_float(u_bc.get("Uy", 0)))
    uz = abs(_to_float(u_bc.get("Uz", 0)))
    u_mag = (ux ** 2 + uy ** 2 + uz ** 2) ** 0.5

    if u_mag > 0 and dt > 0:
        cfl = u_mag * dt / cell_size
        if cfl > 1.0:
            issues.append({
                "level": "warning",
                "path": "system/controlDict",
                "message": f"Estimated CFL \u2248 {cfl:.1f} "
                f"(U={u_mag:.1f} m/s, \u0394t={dt:.2g}, \u0394x={cell_size:.3g} m). "
                "Consider reducing deltaT or enabling adjustableTimeStep."
            })
        elif cfl > 0.5:
            issues.append({
                "level": "info",
                "path": "system/controlDict",
                "message": f"Estimated CFL \u2248 {cfl:.2f}. "
                "Acceptable but monitor during run."
            })


def _to_float(val: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ================================================================== #
#  Validation result widget
# ================================================================== #

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout,
)


class ValidationDialog(QDialog):
    """Dialog that shows validation results."""

    def __init__(self, issues: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Case Validation")
        self.setMinimumSize(500, 350)
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # Count by level
        errors = sum(1 for i in issues if i["level"] == "error")
        warnings = sum(1 for i in issues if i["level"] == "warning")
        infos = sum(1 for i in issues if i["level"] == "info")

        summary = []
        if errors:
            summary.append(f"<span style='color:#E53935;'>\u2716 {errors} error(s)</span>")
        if warnings:
            summary.append(f"<span style='color:#F57C00;'>\u26A0 {warnings} warning(s)</span>")
        if infos:
            summary.append(f"<span style='color:#1976D2;'>\u2139 {infos} info</span>")

        header = QLabel("&nbsp;&nbsp;".join(summary) if summary else "No issues")
        header.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(header)

        # Detailed list
        text = QTextEdit()
        text.setReadOnly(True)

        icons = {"error": "\u2716", "warning": "\u26A0", "info": "\u2139"}
        colors = {"error": "#E53935", "warning": "#F57C00", "info": "#1976D2"}

        html_lines = []
        for issue in issues:
            level = issue["level"]
            icon = icons.get(level, "\u2022")
            color = colors.get(level, "#000")
            html_lines.append(
                f"<p><span style='color:{color}; font-size:14px;'>{icon}</span> "
                f"<b style='color:{color};'>[{level.upper()}]</b> "
                f"{issue['message']}</p>"
            )
        text.setHtml("".join(html_lines))
        layout.addWidget(text)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._has_errors = errors > 0

    @property
    def has_errors(self) -> bool:
        return self._has_errors
