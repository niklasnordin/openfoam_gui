"""
Workflow bar and case dashboard.

WorkflowBar: horizontal step indicator showing setup progress.
CaseDashboard: summary widget shown when no tree item is selected.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont


# ================================================================== #
#  Workflow step definitions
# ================================================================== #

WORKFLOW_STEPS = [
    {
        "id": "solver",
        "label": "Solver",
        "icon": "1",
        "description": "Choose solver and OpenFOAM version",
        "tree_paths": [],  # handled by solver combo, not tree
    },
    {
        "id": "mesh",
        "label": "Mesh",
        "icon": "2",
        "description": "Load STL, set blockMesh bounds and refinement",
        "tree_paths": ["system/blockMeshDict", "system/snappyHexMeshDict"],
        "tabs": ["STL", "Surfaces", "Regions", "Locations"],
    },
    {
        "id": "bcs",
        "label": "BCs",
        "icon": "3",
        "description": "Set boundary conditions for all patches",
        "tree_paths": ["__patch_editor__"],
    },
    {
        "id": "numerics",
        "label": "Numerics",
        "icon": "4",
        "description": "Configure fvSchemes, fvSolution, and fvOptions",
        "tree_paths": ["system/fvSchemes", "system/fvSolution", "system/fvOptions"],
    },
    {
        "id": "run",
        "label": "Run",
        "icon": "5",
        "description": "Time control, write settings, and parallel decomposition",
        "tree_paths": ["system/controlDict", "system/decomposeParDict"],
    },
    {
        "id": "export",
        "label": "Export",
        "icon": "6",
        "description": "Validate and export the case",
        "tree_paths": [],
    },
]


# ================================================================== #
#  Workflow step button
# ================================================================== #

class StepButton(QWidget):
    """Single step in the workflow bar."""

    clicked = Signal(str)

    def __init__(self, step: dict, parent=None):
        super().__init__(parent)
        self.step_id = step["id"]
        self._label = step["label"]
        self._icon_text = step["icon"]
        self._status = "default"  # default, active, done, warning, error

        self.setFixedHeight(48)
        self.setMinimumWidth(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(step["description"])

    def set_status(self, status: str):
        self._status = status
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit(self.step_id)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        colors = {
            "default":  (QColor("#546E7A"), QColor("#ECEFF1")),
            "active":   (QColor("#1976D2"), QColor("#E3F2FD")),
            "done":     (QColor("#43A047"), QColor("#E8F5E9")),
            "warning":  (QColor("#F57C00"), QColor("#FFF3E0")),
            "error":    (QColor("#E53935"), QColor("#FFEBEE")),
        }
        fg, bg = colors.get(self._status, colors["default"])

        # Circle
        circle_r = 14
        cx = 24
        cy = h // 2
        painter.setPen(QPen(fg, 2))
        painter.setBrush(bg)
        painter.drawEllipse(cx - circle_r, cy - circle_r,
                            circle_r * 2, circle_r * 2)

        # Step number or status icon
        painter.setPen(fg)
        font = QFont()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        icon = {"done": "\u2713", "error": "\u2717",
                "warning": "!"}.get(self._status, self._icon_text)
        painter.drawText(cx - circle_r, cy - circle_r,
                         circle_r * 2, circle_r * 2,
                         Qt.AlignmentFlag.AlignCenter, icon)

        # Label
        font.setPixelSize(11)
        font.setBold(self._status == "active")
        painter.setFont(font)
        text_x = cx + circle_r + 6
        painter.drawText(text_x, 0, w - text_x - 4, h,
                         Qt.AlignmentFlag.AlignVCenter, self._label)

        # Arrow connector (except last step)
        if self.step_id != "export":
            painter.setPen(QPen(QColor("#B0BEC5"), 1))
            painter.drawLine(w - 6, h // 2, w, h // 2)

        painter.end()


# ================================================================== #
#  Workflow bar
# ================================================================== #

class WorkflowBar(QWidget):
    """Horizontal step bar across the top of the window."""

    step_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflowBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._steps: dict[str, StepButton] = {}
        for step in WORKFLOW_STEPS:
            btn = StepButton(step)
            btn.clicked.connect(self._on_step_clicked)
            self._steps[step["id"]] = btn
            layout.addWidget(btn)

        layout.addStretch()

    def _on_step_clicked(self, step_id: str):
        self.step_clicked.emit(step_id)

    def set_active(self, step_id: str):
        """Highlight the active step."""
        for sid, btn in self._steps.items():
            if sid == step_id:
                btn.set_status("active")
            elif btn._status == "active":
                btn.set_status("default")

    def set_status(self, step_id: str, status: str):
        """Set step status: default, done, warning, error."""
        btn = self._steps.get(step_id)
        if btn:
            btn.set_status(status)

    def update_from_validation(self, step_issues: dict[str, str]):
        """Update all step statuses from validation results.
        step_issues maps step_id -> worst level ("error"/"warning"/"done")
        """
        for step_id, btn in self._steps.items():
            if btn._status == "active":
                continue  # don't override active state
            status = step_issues.get(step_id, "done")
            btn.set_status(status)


# ================================================================== #
#  Case dashboard
# ================================================================== #

class _DashCard(QFrame):
    """Small info card for the dashboard."""

    clicked = Signal(str)

    def __init__(self, title: str, action_id: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("dashCard")
        self._action_id = action_id
        if action_id:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._title = QLabel(f"<b>{title}</b>")
        layout.addWidget(self._title)

        self._value = QLabel()
        self._value.setWordWrap(True)
        layout.addWidget(self._value)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def set_value(self, text: str):
        self._value.setText(text)

    def set_status(self, text: str):
        self._status_label.setText(text)

    def mousePressEvent(self, event):
        if self._action_id:
            self.clicked.emit(self._action_id)


class CaseDashboard(QScrollArea):
    """Summary dashboard shown when no tree item is selected."""

    navigate_to = Signal(str)  # emitted with tree path or step id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._header = QLabel()
        self._header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 4px;")
        layout.addWidget(self._header)

        self._subtitle = QLabel()
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet("font-size: 12px; padding: 0 4px 8px 4px;")
        layout.addWidget(self._subtitle)

        # Cards grid
        grid = QGridLayout()
        grid.setSpacing(10)

        self._solver_card = _DashCard("Solver", "solver")
        self._solver_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._solver_card, 0, 0)

        self._mesh_card = _DashCard("Mesh", "mesh")
        self._mesh_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._mesh_card, 0, 1)

        self._bc_card = _DashCard("Boundary Conditions", "bcs")
        self._bc_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._bc_card, 0, 2)

        self._numerics_card = _DashCard("Numerics", "numerics")
        self._numerics_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._numerics_card, 1, 0)

        self._time_card = _DashCard("Run Settings", "run")
        self._time_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._time_card, 1, 1)

        self._validation_card = _DashCard("Validation", "export")
        self._validation_card.clicked.connect(self.navigate_to)
        grid.addWidget(self._validation_card, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()
        self.setWidget(container)

    def update_from_db(self, db):
        """Refresh dashboard content from the database."""
        tmpl = db.template
        if not tmpl:
            return

        solver = db.solver or "Not selected"
        desc = getattr(tmpl, 'SOLVER_DESCRIPTION', '')
        self._header.setText(f"Case Overview — {solver}")
        self._subtitle.setText(desc)

        # Solver card
        turb = db.turbulence_model or "laminar"
        fields = db.active_fields
        self._solver_card.set_value(f"{solver}")
        self._solver_card.set_status(
            f"Turbulence: {turb}\nFields: {', '.join(fields[:6])}")

        # Mesh card
        n_stl = len(db.stl_entries)
        n_surf = len(db.get_all_surface_names())
        bmd = db.get_dict("system/blockMeshDict")
        cell_size = bmd.get("cellSize", "?")
        if n_stl:
            self._mesh_card.set_value(f"{n_stl} STL file(s), {n_surf} surfaces")
        else:
            self._mesh_card.set_value("No STL loaded")
        self._mesh_card.set_status(f"Cell size: {cell_size} m")

        # BC card
        patches = db.get_patch_names()
        roles = {}
        for p in patches:
            r = db.get_patch(p).get("role", "wall")
            roles[r] = roles.get(r, 0) + 1
        role_str = ", ".join(f"{v} {k}" for k, v in roles.items())
        self._bc_card.set_value(f"{len(patches)} patches")
        self._bc_card.set_status(role_str or "No patches defined")

        # Numerics card
        fvsol = db.get_dict("system/fvSolution")
        algo = fvsol.get("algorithm", "?")
        relax_u = fvsol.get("relaxU", "—")
        relax_p = fvsol.get("relaxP", "—")
        self._numerics_card.set_value(f"Algorithm: {algo}")
        self._numerics_card.set_status(
            f"Relaxation: U={relax_u}, p={relax_p}")

        # Time card
        cd = db.get_dict("system/controlDict")
        dt = cd.get("deltaT", "?")
        end = cd.get("endTime", "?")
        adjust = cd.get("adjustTimeStep", "no")
        self._time_card.set_value(f"\u0394t = {dt},  endTime = {end}")
        self._time_card.set_status(
            f"Adjustable: {adjust}")

        # Validation card
        from case_validator import validate_case
        issues = validate_case(db)
        n_err = sum(1 for i in issues if i["level"] == "error")
        n_warn = sum(1 for i in issues if i["level"] == "warning")
        if n_err:
            self._validation_card.set_value(
                f"\u2716 {n_err} error(s), {n_warn} warning(s)")
        elif n_warn:
            self._validation_card.set_value(
                f"\u26A0 {n_warn} warning(s)")
        else:
            self._validation_card.set_value(
                "\u2713 Case looks good")
        top_issues = [i["message"] for i in issues
                      if i["level"] in ("error", "warning")][:3]
        self._validation_card.set_status("\n".join(top_issues) if top_issues else "")
