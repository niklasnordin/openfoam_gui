"""
Application settings — persistent GUI appearance preferences.

Settings are stored as a JSON file (default: ~/.openfoam_gui_settings.json).
All colour values are stored as hex strings (#RRGGBB).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS_PATH = Path.home() / ".openfoam_gui_settings.json"

# ------------------------------------------------------------------ #
#  Default colour / font values
# ------------------------------------------------------------------ #

DEFAULTS: dict[str, Any] = {
    # Main window
    "window_bg":           "#FAFAFA",

    # Tree panel
    "tree_bg":             "#ECEFF1",
    "tree_text":           "#000000",
    "tree_selected_bg":    "#1976D2",
    "tree_selected_text":  "#FFFFFF",

    # Editor / forms area
    "editor_bg":           "#FFFFFF",
    "editor_text":         "#000000",

    # Preview pane (OpenFOAM text)
    "preview_bg":          "#1E1E1E",
    "preview_text":        "#D4D4D4",

    # Toolbar
    "toolbar_bg":          "#263238",
    "toolbar_text":        "#FFFFFF",

    # Status bar
    "statusbar_bg":        "#263238",
    "statusbar_text":      "#B0BEC5",

    # Buttons – primary
    "button_bg":           "#1976D2",
    "button_text":         "#FFFFFF",
    "button_hover_bg":     "#1565C0",

    # Buttons – secondary
    "button2_bg":          "#78909C",
    "button2_text":        "#FFFFFF",

    # Group boxes
    "groupbox_border":     "#CFD8DC",
    "groupbox_title":      "#37474F",

    # Splitter handle
    "splitter_handle":     "#CFD8DC",

    # Syntax highlighting (preview pane) — matches preview.py defaults
    "hl_keyword":          "#1565C0",
    "hl_number":           "#E65100",
    "hl_comment":          "#6A9955",
    "hl_brace":            "#B71C1C",
    "hl_string":           "#6A1B9A",
    "hl_header":           "#78909C",

    # Font
    "font_family":         "Segoe UI",
    "font_size":           10,
    "mono_font_family":    "Monospace",
    "mono_font_size":      9,
}

# ------------------------------------------------------------------ #
#  Dark theme preset
# ------------------------------------------------------------------ #

DARK_THEME: dict[str, Any] = {
    "window_bg":           "#1E1E1E",
    "tree_bg":             "#252526",
    "tree_text":           "#CCCCCC",
    "tree_selected_bg":    "#264F78",
    "tree_selected_text":  "#FFFFFF",
    "editor_bg":           "#333333",
    "editor_text":         "#D4D4D4",
    "preview_bg":          "#1E1E1E",
    "preview_text":        "#D4D4D4",
    "toolbar_bg":          "#2D2D2D",
    "toolbar_text":        "#CCCCCC",
    "statusbar_bg":        "#007ACC",
    "statusbar_text":      "#FFFFFF",
    "button_bg":           "#0E639C",
    "button_text":         "#FFFFFF",
    "button_hover_bg":     "#1177BB",
    "button2_bg":          "#3C3C3C",
    "button2_text":        "#CCCCCC",
    "groupbox_border":     "#4A4A4A",
    "groupbox_title":      "#4FC3F7",
    "splitter_handle":     "#4A4A4A",
    "hl_keyword":          "#569CD6",
    "hl_number":           "#B5CEA8",
    "hl_comment":          "#6A9955",
    "hl_brace":            "#FFD700",
    "hl_string":           "#CE9178",
    "hl_header":           "#608B4E",
    "font_family":         "Segoe UI",
    "font_size":           10,
    "mono_font_family":    "Monospace",
    "mono_font_size":      9,
}


class AppSettings:
    """Read / write GUI appearance settings."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_SETTINGS_PATH
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    # ---- persistence ------------------------------------------------ #

    def load(self) -> None:
        """Load settings from disk, keeping defaults for missing keys."""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                if isinstance(stored, dict):
                    self._data.update(stored)
            except (json.JSONDecodeError, OSError):
                pass  # silently fall back to defaults

    def save(self) -> None:
        """Persist current settings to disk."""
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def reset(self) -> None:
        """Restore factory defaults (does NOT auto-save)."""
        self._data = dict(DEFAULTS)

    # ---- access ----------------------------------------------------- #

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    # ---- stylesheet generation -------------------------------------- #

    def generate_stylesheet(self) -> str:
        """Build a Qt stylesheet string from current settings."""
        g = self.get
        return f"""
QMainWindow {{
    background: {g('window_bg')};
}}
QTreeWidget {{
    background: {g('tree_bg')};
    color: {g('tree_text')};
    border: none;
    font-size: {g('font_size')}px;
}}
QTreeWidget::item {{
    padding: 4px 2px;
    color: {g('tree_text')};
}}
QTreeWidget::item:selected {{
    background: {g('tree_selected_bg')};
    color: {g('tree_selected_text')};
}}
QTreeView::branch {{
    background: {g('tree_bg')};
}}
QTreeView::branch:selected {{
    background: {g('tree_selected_bg')};
}}
QGroupBox {{
    font-weight: bold;
    border: 1px solid {g('groupbox_border')};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
    background: {g('window_bg')};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {g('groupbox_title')};
}}
QPushButton {{
    background: {g('button_bg')};
    color: {g('button_text')};
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    background: {g('button_hover_bg')};
}}
QPushButton:pressed {{
    background: {g('button_hover_bg')};
}}
QPushButton#secondary {{
    background: {g('button2_bg')};
    color: {g('button2_text')};
}}
QPushButton#secondary:hover {{
    background: {g('button2_bg')};
}}
QPushButton#danger {{
    background: #E53935;
}}
QPushButton#danger:hover {{
    background: #C62828;
}}
QTabWidget::pane {{
    border: 1px solid {g('groupbox_border')};
    border-radius: 4px;
    background: {g('window_bg')};
}}
QToolBar {{
    background: {g('toolbar_bg')};
    spacing: 8px;
    padding: 4px;
}}
QStatusBar {{
    background: {g('statusbar_bg')};
    color: {g('statusbar_text')};
}}
QLabel#header {{
    font-size: 14px;
    font-weight: bold;
    color: {g('groupbox_title')};
    padding: 8px 4px;
}}
QSplitter::handle {{
    background: {g('splitter_handle')};
}}
QSplitter {{
    background: {g('window_bg')};
}}
QWidget#treePanel {{
    background: {g('tree_bg')};
}}
QWidget#treePanel QLabel {{
    color: {g('tree_text')};
}}
QWidget#treePanel QLabel#header {{
    color: {g('groupbox_title')};
}}
QWidget#editorPanel {{
    background: {g('window_bg')};
}}
QWidget#rightPanel {{
    background: {g('window_bg')};
}}
QListWidget {{
    background: {g('tree_bg')};
    color: {g('tree_text')};
    border: none;
}}
QListWidget::item {{
    padding: 4px;
    color: {g('tree_text')};
}}
QListWidget::item:selected {{
    background: {g('tree_selected_bg')};
    color: {g('tree_selected_text')};
}}
QComboBox#solverCombo {{
    font-size: 13px;
    font-weight: bold;
    padding: 6px 10px;
    border: 2px solid {g('button_bg')};
    border-radius: 4px;
    background: {g('editor_bg')};
    color: {g('editor_text')};
    min-height: 28px;
}}
QComboBox#solverCombo:hover {{
    border-color: {g('button_hover_bg')};
}}
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
    border: 1px solid {g('groupbox_border')};
    border-radius: 3px;
    padding: 3px 6px;
}}
QComboBox {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
    border: 1px solid {g('groupbox_border')};
    border-radius: 3px;
    padding: 3px 6px;
}}
QComboBox QAbstractItemView {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
    selection-background-color: {g('tree_selected_bg')};
    selection-color: {g('tree_selected_text')};
}}
QComboBox::drop-down {{
    border: none;
}}
QTextEdit {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
    border: 1px solid {g('groupbox_border')};
}}
QPlainTextEdit {{
    background: {g('preview_bg')};
    color: {g('preview_text')};
}}
QWidget {{
    color: {g('editor_text')};
}}
QMainWindow > QWidget {{
    background: {g('window_bg')};
}}
QStackedWidget {{
    background: {g('window_bg')};
}}
QStackedWidget > QWidget {{
    background: {g('window_bg')};
}}
QScrollArea {{
    background: {g('window_bg')};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: {g('window_bg')};
}}
QTabBar::tab {{
    background: {g('button2_bg')};
    color: {g('button2_text')};
    padding: 6px 14px;
    border: 1px solid {g('groupbox_border')};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {g('window_bg')};
    color: {g('editor_text')};
    border-bottom: 2px solid {g('button_bg')};
}}
QTabBar::tab:hover:!selected {{
    background: {g('groupbox_border')};
}}
QTableWidget {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
    gridline-color: {g('groupbox_border')};
    border: 1px solid {g('groupbox_border')};
}}
QTableWidget QHeaderView::section {{
    background: {g('button2_bg')};
    color: {g('button2_text')};
    padding: 4px;
    border: 1px solid {g('groupbox_border')};
}}
QCheckBox {{
    color: {g('editor_text')};
}}
QToolBar QLabel {{
    color: {g('toolbar_text')};
}}
QToolBar QComboBox {{
    background: {g('editor_bg')};
    color: {g('editor_text')};
}}
QToolButton {{
    color: {g('toolbar_text')};
    background: transparent;
    border: none;
    padding: 4px 8px;
}}
QToolButton:hover {{
    background: {g('groupbox_border')};
    border-radius: 3px;
}}
QFrame#infoPanel {{
    background: {g('tree_bg')};
    border: 1px solid {g('groupbox_border')};
    border-radius: 6px;
    padding: 12px;
}}
QWidget#workflowBar {{
    background: {g('toolbar_bg')};
    border-bottom: 1px solid {g('groupbox_border')};
}}
QFrame#dashCard {{
    background: {g('editor_bg')};
    border: 1px solid {g('groupbox_border')};
    border-radius: 6px;
}}
QFrame#dashCard:hover {{
    border-color: {g('button_bg')};
}}
"""
