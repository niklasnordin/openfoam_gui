"""
Settings dialog — lets the user customise GUI colours and fonts.

Opens from the toolbar ⚙ Settings button.  Changes are previewed live
and persisted to ~/.openfoam_gui_settings.json on "Apply" / "OK".
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTabWidget, QWidget,
    QColorDialog, QFontComboBox, QSpinBox, QScrollArea,
    QGroupBox, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

if TYPE_CHECKING:
    from app_settings import AppSettings


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

_SECTION_STYLE = """
QGroupBox {
    font-weight: bold; font-size: 12px;
    border: 1px solid #bbb; border-radius: 6px;
    margin-top: 14px; padding-top: 18px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
}
"""


def _color_button(color: str, callback) -> QPushButton:
    """Create a small square button that shows a colour swatch."""
    btn = QPushButton()
    btn.setFixedSize(36, 24)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"background: {color}; border: 1px solid #888; border-radius: 3px;"
    )
    btn.setToolTip(color)
    btn.clicked.connect(callback)
    return btn


# ------------------------------------------------------------------ #
#  Colour row definition
# ------------------------------------------------------------------ #

# (settings_key, human label)  — grouped by tab / section
_GENERAL_COLORS = [
    ("window_bg",          "Window background"),
    ("toolbar_bg",         "Toolbar background"),
    ("toolbar_text",       "Toolbar text"),
    ("statusbar_bg",       "Status-bar background"),
    ("statusbar_text",     "Status-bar text"),
    ("splitter_handle",    "Splitter handle"),
    ("groupbox_border",    "Group-box border"),
    ("groupbox_title",     "Group-box title text"),
]

_TREE_COLORS = [
    ("tree_bg",            "Background"),
    ("tree_text",          "Text"),
    ("tree_selected_bg",   "Selected background"),
    ("tree_selected_text", "Selected text"),
]

_EDITOR_COLORS = [
    ("editor_bg",          "Background"),
    ("editor_text",        "Text"),
]

_PREVIEW_COLORS = [
    ("preview_bg",         "Background"),
    ("preview_text",       "Text"),
]

_BUTTON_COLORS = [
    ("button_bg",          "Primary background"),
    ("button_text",        "Primary text"),
    ("button_hover_bg",    "Primary hover"),
    ("button2_bg",         "Secondary background"),
    ("button2_text",       "Secondary text"),
]

_SYNTAX_COLORS = [
    ("hl_keyword",         "Keywords"),
    ("hl_number",          "Numbers"),
    ("hl_comment",         "Comments"),
    ("hl_brace",           "Braces / brackets"),
    ("hl_string",          "Strings"),
    ("hl_header",          "File header"),
]


class SettingsDialog(QDialog):
    """Modal dialog for editing application appearance settings."""

    settings_applied = Signal()  # emitted when user clicks Apply or OK

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Appearance Settings")
        self.setMinimumSize(520, 560)
        self.resize(560, 640)

        self._settings = settings
        # Working copy so we can cancel without side effects
        self._draft: dict[str, object] = settings.all()
        # Map settings_key -> colour swatch button (for live update)
        self._swatches: dict[str, QPushButton] = {}

        self._build_ui()

    # ============================================================== #
    #  UI
    # ============================================================== #

    def _build_ui(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._make_colours_tab(), "Colours")
        tabs.addTab(self._make_fonts_tab(), "Fonts")
        root.addWidget(tabs)

        # ---- button row ---- #
        btn_row = QHBoxLayout()

        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.setObjectName("secondary")
        btn_reset.clicked.connect(self._on_reset)
        btn_row.addWidget(btn_reset)

        btn_dark = QPushButton("\u263E Dark Mode")
        btn_dark.setObjectName("secondary")
        btn_dark.clicked.connect(self._on_dark_mode)
        btn_row.addWidget(btn_dark)

        btn_row.addStretch()

        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(btn_apply)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        root.addLayout(btn_row)

    # ---- Colours tab ------------------------------------------------ #

    def _make_colours_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        container.setStyleSheet(_SECTION_STYLE)

        sections = [
            ("General",        _GENERAL_COLORS),
            ("Case Structure / Lists", _TREE_COLORS),
            ("Editor / forms", _EDITOR_COLORS),
            ("Preview pane",   _PREVIEW_COLORS),
            ("Buttons",        _BUTTON_COLORS),
            ("Syntax colours", _SYNTAX_COLORS),
        ]
        for title, rows in sections:
            layout.addWidget(self._colour_section(title, rows))

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _colour_section(self, title: str, rows: list[tuple[str, str]]) -> QGroupBox:
        grp = QGroupBox(title)
        grid = QGridLayout(grp)
        grid.setColumnStretch(1, 1)

        for i, (key, label) in enumerate(rows):
            lbl = QLabel(label)
            grid.addWidget(lbl, i, 0)

            colour = self._draft.get(key, "#000000")
            btn = _color_button(colour, partial(self._pick_colour, key))
            self._swatches[key] = btn
            grid.addWidget(btn, i, 1, Qt.AlignmentFlag.AlignRight)

        return grp

    # ---- Fonts tab -------------------------------------------------- #

    def _make_fonts_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # UI font
        grp_ui = QGroupBox("Interface font")
        g1 = QGridLayout(grp_ui)

        g1.addWidget(QLabel("Family"), 0, 0)
        self._ui_font_combo = QFontComboBox()
        self._ui_font_combo.setCurrentFont(QFont(self._draft.get("font_family", "Segoe UI")))
        g1.addWidget(self._ui_font_combo, 0, 1)

        g1.addWidget(QLabel("Size"), 1, 0)
        self._ui_font_size = QSpinBox()
        self._ui_font_size.setRange(7, 24)
        self._ui_font_size.setValue(int(self._draft.get("font_size", 10)))
        g1.addWidget(self._ui_font_size, 1, 1)
        layout.addWidget(grp_ui)

        # Mono font (preview pane)
        grp_mono = QGroupBox("Preview / monospace font")
        g2 = QGridLayout(grp_mono)

        g2.addWidget(QLabel("Family"), 0, 0)
        self._mono_font_combo = QFontComboBox()
        self._mono_font_combo.setCurrentFont(QFont(self._draft.get("mono_font_family", "Monospace")))
        g2.addWidget(self._mono_font_combo, 0, 1)

        g2.addWidget(QLabel("Size"), 1, 0)
        self._mono_font_size = QSpinBox()
        self._mono_font_size.setRange(7, 24)
        self._mono_font_size.setValue(int(self._draft.get("mono_font_size", 9)))
        g2.addWidget(self._mono_font_size, 1, 1)
        layout.addWidget(grp_mono)

        layout.addStretch()
        return w

    # ============================================================== #
    #  Slots
    # ============================================================== #

    def _pick_colour(self, key: str) -> None:
        current = QColor(self._draft.get(key, "#000000"))
        colour = QColorDialog.getColor(
            current, self, f"Pick colour — {key}",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if colour.isValid():
            hex_str = colour.name()  # #rrggbb
            self._draft[key] = hex_str
            btn = self._swatches.get(key)
            if btn:
                btn.setStyleSheet(
                    f"background: {hex_str}; border: 1px solid #888; border-radius: 3px;"
                )
                btn.setToolTip(hex_str)

    def _collect_fonts(self) -> None:
        """Read font widgets back into draft dict."""
        self._draft["font_family"] = self._ui_font_combo.currentFont().family()
        self._draft["font_size"] = self._ui_font_size.value()
        self._draft["mono_font_family"] = self._mono_font_combo.currentFont().family()
        self._draft["mono_font_size"] = self._mono_font_size.value()

    def _apply_to_settings(self) -> None:
        """Copy draft into the real AppSettings object and save."""
        self._collect_fonts()
        for k, v in self._draft.items():
            self._settings.set(k, v)
        self._settings.save()
        self.settings_applied.emit()

    def _on_apply(self) -> None:
        self._apply_to_settings()

    def _on_ok(self) -> None:
        self._apply_to_settings()
        self.accept()

    def _on_reset(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Restore all colours and fonts to factory defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from app_settings import DEFAULTS
            self._load_preset(DEFAULTS)

    def _on_dark_mode(self) -> None:
        from app_settings import DARK_THEME
        self._load_preset(DARK_THEME)

    def _load_preset(self, preset: dict) -> None:
        """Load a colour/font preset into the draft and update all widgets."""
        self._draft = dict(preset)
        for key, btn in self._swatches.items():
            c = self._draft.get(key, "#000000")
            btn.setStyleSheet(
                f"background: {c}; border: 1px solid #888; border-radius: 3px;"
            )
            btn.setToolTip(c)
        self._ui_font_combo.setCurrentFont(QFont(self._draft.get("font_family", "Segoe UI")))
        self._ui_font_size.setValue(int(self._draft.get("font_size", 10)))
        self._mono_font_combo.setCurrentFont(QFont(self._draft.get("mono_font_family", "Monospace")))
        self._mono_font_size.setValue(int(self._draft.get("mono_font_size", 9)))
