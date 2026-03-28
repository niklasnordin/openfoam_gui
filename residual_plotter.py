"""
Residual plotter — parse OpenFOAM solver log files and display
convergence history for p, U, k, epsilon, omega, continuity, etc.

Uses QPainter for plotting (no matplotlib dependency).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QCheckBox, QGroupBox, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath


# ------------------------------------------------------------------ #
#  Log parser
# ------------------------------------------------------------------ #

# Matches lines like:
#   smoothSolver:  Solving for Ux, Initial residual = 0.1, Final residual = 1e-6, No Iterations 2
#   GAMG:  Solving for p, Initial residual = 0.5, Final residual = 1e-7, No Iterations 10
_RESIDUAL_RE = re.compile(
    r"Solving for (\S+),\s+Initial residual\s*=\s*([\d.eE+\-]+),\s+"
    r"Final residual\s*=\s*([\d.eE+\-]+)")

# Matches: time step continuity errors : sum local = 1e-10, global = -1e-15, cumulative = 1e-12
_CONTINUITY_RE = re.compile(
    r"continuity errors\s*:\s*sum local\s*=\s*([\d.eE+\-]+)")

# Matches: Time = 0.5
_TIME_RE = re.compile(r"^Time\s*=\s*([\d.eE+\-]+)", re.MULTILINE)

# Matches: ExecutionTime = 1.23 s
_EXEC_TIME_RE = re.compile(r"ExecutionTime\s*=\s*([\d.eE+\-]+)")


def parse_log(path: str | Path) -> dict[str, list[float]]:
    """Parse an OpenFOAM log file and extract residual histories.

    Returns:
        {"Ux": [r1, r2, ...], "p": [...], "continuity": [...],
         "time": [...], "iteration": [1, 2, 3, ...]}
    """
    residuals: dict[str, list[float]] = {}
    times: list[float] = []
    iterations: list[float] = []
    current_time = 0.0
    iteration = 0

    with open(path, "r", errors="replace") as f:
        for line in f:
            # Time step
            m = _TIME_RE.match(line)
            if m:
                current_time = float(m.group(1))
                iteration += 1

            # Residuals
            m = _RESIDUAL_RE.search(line)
            if m:
                field = m.group(1)
                initial = float(m.group(2))
                # Store initial residual (more useful for convergence)
                if field not in residuals:
                    residuals[field] = []
                residuals[field].append(initial)

                # Track iteration count per field to align
                key = f"_{field}_iter"
                if key not in residuals:
                    residuals[key] = []
                residuals[key].append(iteration)

            # Continuity
            m = _CONTINUITY_RE.search(line)
            if m:
                val = float(m.group(1))
                if "continuity" not in residuals:
                    residuals["continuity"] = []
                residuals["continuity"].append(val)

    # Build iteration list from max length
    max_len = max((len(v) for k, v in residuals.items()
                   if not k.startswith("_")), default=0)

    # Clean up internal keys
    residuals = {k: v for k, v in residuals.items() if not k.startswith("_")}

    return residuals


# ------------------------------------------------------------------ #
#  Plotting colors
# ------------------------------------------------------------------ #

FIELD_COLORS = {
    "Ux":         QColor("#E53935"),
    "Uy":         QColor("#D81B60"),
    "Uz":         QColor("#8E24AA"),
    "p":          QColor("#1E88E5"),
    "p_rgh":      QColor("#1565C0"),
    "k":          QColor("#43A047"),
    "epsilon":    QColor("#FB8C00"),
    "omega":      QColor("#F4511E"),
    "nut":        QColor("#6D4C41"),
    "T":          QColor("#00ACC1"),
    "e":          QColor("#7CB342"),
    "h":          QColor("#C0CA33"),
    "continuity": QColor("#78909C"),
    "alpha.water":QColor("#0097A7"),
}

def _get_color(field: str) -> QColor:
    if field in FIELD_COLORS:
        return FIELD_COLORS[field]
    # Deterministic color from hash
    h = hash(field) % 360
    return QColor.fromHsv(h, 200, 180)


# ------------------------------------------------------------------ #
#  Plot widget
# ------------------------------------------------------------------ #

class ResidualPlotWidget(QWidget):
    """Canvas that draws residual convergence plot with log scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        self._data: dict[str, list[float]] = {}
        self._visible: dict[str, bool] = {}
        self._margin = {"left": 70, "right": 20, "top": 20, "bottom": 40}

    def set_data(self, data: dict[str, list[float]]):
        self._data = data
        self._visible = {k: True for k in data}
        self.update()

    def set_field_visible(self, field: str, visible: bool):
        self._visible[field] = visible
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        m = self._margin
        plot_w = w - m["left"] - m["right"]
        plot_h = h - m["top"] - m["bottom"]

        if plot_w < 50 or plot_h < 50:
            return

        # Background
        painter.fillRect(m["left"], m["top"], plot_w, plot_h, QColor("#FAFAFA"))

        # Determine data range
        visible_data = {k: v for k, v in self._data.items()
                        if self._visible.get(k, True) and v}
        if not visible_data:
            painter.end()
            return

        max_len = max(len(v) for v in visible_data.values())
        all_vals = [val for v in visible_data.values() for val in v if val > 0]
        if not all_vals:
            painter.end()
            return

        y_min_val = min(all_vals)
        y_max_val = max(all_vals)

        # Log scale
        log_min = math.floor(math.log10(max(y_min_val, 1e-20)))
        log_max = math.ceil(math.log10(max(y_max_val, 1e-20)))
        if log_min == log_max:
            log_min -= 1
        log_range = log_max - log_min

        def x_pos(i):
            return m["left"] + (i / max(max_len - 1, 1)) * plot_w

        def y_pos(val):
            if val <= 0:
                return m["top"] + plot_h
            lv = math.log10(val)
            frac = (lv - log_min) / log_range if log_range > 0 else 0.5
            return m["top"] + plot_h * (1 - frac)

        # Grid lines
        painter.setPen(QPen(QColor("#E0E0E0"), 1))
        for exp in range(log_min, log_max + 1):
            y = y_pos(10.0 ** exp)
            painter.drawLine(QPointF(m["left"], y), QPointF(w - m["right"], y))

        # Axes
        painter.setPen(QPen(QColor("#333333"), 1))
        painter.drawRect(m["left"], m["top"], plot_w, plot_h)

        # Y-axis labels
        font = QFont("sans-serif", 8)
        painter.setFont(font)
        for exp in range(log_min, log_max + 1):
            y = y_pos(10.0 ** exp)
            painter.drawText(QRectF(0, y - 8, m["left"] - 4, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"1e{exp}")

        # X-axis labels
        step = max(1, max_len // 8)
        for i in range(0, max_len, step):
            x = x_pos(i)
            painter.drawText(QRectF(x - 20, h - m["bottom"] + 4, 40, 16),
                             Qt.AlignmentFlag.AlignCenter, str(i))

        # X-axis title
        painter.drawText(QRectF(m["left"], h - 16, plot_w, 16),
                         Qt.AlignmentFlag.AlignCenter, "Iteration")

        # Plot data
        for field, values in visible_data.items():
            color = _get_color(field)
            painter.setPen(QPen(color, 2))

            path = QPainterPath()
            started = False
            for i, val in enumerate(values):
                if val <= 0:
                    continue
                x = x_pos(i)
                y = y_pos(val)
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            if started:
                painter.drawPath(path)

        painter.end()


# ------------------------------------------------------------------ #
#  Main residual plotter widget
# ------------------------------------------------------------------ #

class ResidualPlotter(QWidget):
    """Complete widget: file selector + checkboxes + plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Residual Plotter</b>"))
        top.addStretch()

        btn_open = QPushButton("Open Log File\u2026")
        btn_open.clicked.connect(self._open_log)
        top.addWidget(btn_open)

        self._auto_refresh = QCheckBox("Auto-refresh (5s)")
        self._auto_refresh.stateChanged.connect(self._toggle_refresh)
        top.addWidget(self._auto_refresh)

        layout.addLayout(top)

        self._file_label = QLabel(
            "<span>No log file loaded</span>")
        self._file_label.setWordWrap(True)
        layout.addWidget(self._file_label)

        # Main area: checkboxes + plot
        main_row = QHBoxLayout()

        # Checkbox panel
        cb_frame = QWidget()
        cb_frame.setMaximumWidth(150)
        self._cb_layout = QVBoxLayout(cb_frame)
        self._cb_layout.setContentsMargins(4, 4, 4, 4)
        self._cb_layout.setSpacing(2)
        self._cb_layout.addWidget(QLabel("<b>Fields</b>"))
        self._cb_layout.addStretch()
        main_row.addWidget(cb_frame)

        # Plot
        self.plot = ResidualPlotWidget()
        main_row.addWidget(self.plot, 1)

        layout.addLayout(main_row, 1)

        # State
        self._log_path: str | None = None
        self._checkboxes: dict[str, QCheckBox] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)

    def _open_log(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open OpenFOAM Log File", "",
            "Log Files (*.log *.txt);;All Files (*)")
        if not path:
            return
        self._log_path = path
        self._file_label.setText(f"<b>File:</b> {path}")
        self._refresh()

    def _refresh(self):
        if not self._log_path:
            return
        try:
            data = parse_log(self._log_path)
        except Exception as e:
            self._file_label.setText(f"<span style='color:red;'>Error: {e}</span>")
            return

        # Update checkboxes
        for field in data:
            if field not in self._checkboxes:
                cb = QCheckBox(field)
                cb.setChecked(True)
                color = _get_color(field)
                cb.setStyleSheet(f"color: {color.name()};")
                cb.stateChanged.connect(
                    lambda state, f=field: self.plot.set_field_visible(f, bool(state)))
                self._checkboxes[field] = cb
                # Insert before stretch
                self._cb_layout.insertWidget(self._cb_layout.count() - 1, cb)

        self.plot.set_data(data)

        # Update iteration count
        max_iters = max((len(v) for v in data.values()), default=0)
        self._file_label.setText(
            f"<b>File:</b> {self._log_path}  "
            f"<span>({max_iters} iterations, "
            f"{len(data)} fields)</span>")

    def _toggle_refresh(self, state):
        if state:
            self._timer.start(5000)
        else:
            self._timer.stop()
