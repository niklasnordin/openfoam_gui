"""
DictEditor — dynamic form for one OpenFOAM dictionary.
Reads/writes through CaseDatabase. Observes db.dict_changed to stay in sync.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QLabel,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Signal, Qt


_VALID_STYLE = ""
_INVALID_STYLE = "border: 2px solid #E53935;"


def _make_numeric_line_edit(default, is_int: bool = False):
    """Create a QLineEdit with numeric validation styling."""
    w = QLineEdit(str(default))

    def _validate(text, widget=w, integer=is_int):
        try:
            if integer:
                int(text)
            else:
                float(text)
            widget.setStyleSheet(_VALID_STYLE)
        except ValueError:
            if text.strip():
                widget.setStyleSheet(_INVALID_STYLE)

    w.textChanged.connect(_validate)
    return w


class DictEditor(QScrollArea):
    """A scrollable form for a single OpenFOAM dictionary.
    Writes every change to db.set_dict_value and listens for external changes."""

    def __init__(self, dict_spec: dict, db, parent=None):
        super().__init__(parent)
        self.dict_spec = dict_spec
        self.db = db
        self.dict_path = dict_spec["path"]
        self._widgets: dict[str, QWidget] = {}
        self._updating = False  # guard against signal loops

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        title = QLabel(f"<b>{dict_spec['label']}</b>  —  <code>{dict_spec['path']}</code>")
        title.setObjectName("header")
        layout.addWidget(title)

        self._conditional_groups: list[tuple[QGroupBox, list]] = []
        # Each entry: (widget, [(field_key, field_value), ...])
        # ALL conditions must match for the group to be visible

        for group_label, fields in dict_spec.get("groups", {}).items():
            # Parse conditional: "Label|field=value" or "Label|f1=v1&f2=v2"
            conditions = []
            display_label = group_label
            if "|" in group_label:
                display_label, cond_str = group_label.split("|", 1)
                for part in cond_str.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        conditions.append((k.strip(), v.strip()))

            group_box = QGroupBox(display_label.strip())
            form = QFormLayout()
            form.setContentsMargins(8, 12, 8, 8)
            form.setSpacing(6)
            for field in fields:
                label, key, default, ftype, options = field[:5]
                widget = self._make_field(key, default, ftype, options)
                form.addRow(label + ":", widget)
            group_box.setLayout(form)
            layout.addWidget(group_box)

            if conditions:
                self._conditional_groups.append((group_box, conditions))
                group_box.setVisible(False)  # hidden until checked

        # Info panel — driven by a combo field, shows descriptions per value
        self._info_label = None
        self._info_frame = None
        self._info_config = dict_spec.get("info")
        if self._info_config:
            self._info_frame = QFrame()
            self._info_frame.setObjectName("infoPanel")
            info_layout = QVBoxLayout(self._info_frame)
            info_layout.setContentsMargins(12, 12, 12, 12)
            self._info_label = QLabel()
            self._info_label.setWordWrap(True)
            self._info_label.setTextFormat(Qt.TextFormat.RichText)
            info_layout.addWidget(self._info_label)
            layout.addWidget(self._info_frame)

            # Connect the driving combo field(s) to _update_info
            driver_key = self._info_config.get("field", "")
            driver_widget = self._widgets.get(driver_key)
            if driver_widget and isinstance(driver_widget, QComboBox):
                driver_widget.currentTextChanged.connect(self._update_info)

            # Connect all field_map targets (e.g. both RASModel and LESModel)
            for mapped_key in self._info_config.get("field_map", {}).values():
                if mapped_key != driver_key:
                    w = self._widgets.get(mapped_key)
                    if w and isinstance(w, QComboBox):
                        w.currentTextChanged.connect(self._update_info)

            # Connect condition_field (e.g. simulationType)
            cf = self._info_config.get("condition_field", "")
            if cf:
                w = self._widgets.get(cf)
                if w and isinstance(w, QComboBox):
                    w.currentTextChanged.connect(self._update_info)

            # Legacy condition field
            cond_str = self._info_config.get("condition", "")
            if cond_str and "=" in cond_str:
                cond_key = cond_str.split("=")[0].strip()
                if cond_key != cf:
                    cond_widget = self._widgets.get(cond_key)
                    if cond_widget and isinstance(cond_widget, QComboBox):
                        cond_widget.currentTextChanged.connect(self._update_info)

            self._update_info()

        layout.addStretch()
        self.setWidget(container)

        # Connect driving fields for conditional groups
        driver_keys = set()
        for _, conditions in self._conditional_groups:
            for ck, _ in conditions:
                driver_keys.add(ck)
        for dk in driver_keys:
            w = self._widgets.get(dk)
            if w and isinstance(w, QComboBox):
                w.currentTextChanged.connect(self._update_conditional_groups)

        # Initialize db with defaults
        defaults = {}
        for _group, fields in dict_spec.get("groups", {}).items():
            for _label, key, default, _ftype, _options in fields:
                defaults[key] = default
        self.db.init_dict_defaults(self.dict_path, defaults)

        # Load current db values into widgets
        self._load_from_db()

        # Observe external db changes
        self.db.dict_changed.connect(self._on_db_changed)

    def _make_field(self, key, default, ftype, options):
        if ftype == "combo":
            w = QComboBox()
            w.addItems(options)
            idx = w.findText(str(default))
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.currentTextChanged.connect(lambda val, k=key: self._write_to_db(k, val))
            self._widgets[key] = w
        elif ftype == "int":
            w = _make_numeric_line_edit(default, is_int=True)
            w.textChanged.connect(lambda val, k=key: self._write_numeric(k, val, True))
            self._widgets[key] = w
        elif ftype == "float":
            w = _make_numeric_line_edit(default, is_int=False)
            w.textChanged.connect(lambda val, k=key: self._write_numeric(k, val, False))
            self._widgets[key] = w
        elif ftype == "bool":
            w = QComboBox()
            w.addItems(["true", "false"])
            w.setCurrentText(str(default).lower())
            w.currentTextChanged.connect(lambda val, k=key: self._write_to_db(k, val))
            self._widgets[key] = w
        else:
            w = QLineEdit(str(default))
            w.textChanged.connect(lambda val, k=key: self._write_to_db(k, val))
            self._widgets[key] = w
        return w

    def _write_numeric(self, key: str, text: str, is_int: bool):
        """Write numeric value to db only if valid."""
        if self._updating:
            return
        try:
            value = int(text) if is_int else float(text)
            self.db.set_dict_value(self.dict_path, key, value)
        except ValueError:
            pass  # invalid input — don't write

    def _write_to_db(self, key: str, value):
        """Widget changed → write to database."""
        if not self._updating:
            self.db.set_dict_value(self.dict_path, key, value)

    def _on_db_changed(self, dict_path: str):
        """Database changed externally → update widgets."""
        if dict_path == self.dict_path:
            self._load_from_db()

    def _load_from_db(self):
        """Read current db values into widgets (without triggering writes back)."""
        self._updating = True
        values = self.db.get_dict(self.dict_path)
        for key, widget in self._widgets.items():
            if key not in values:
                continue
            val = values[key]
            if isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
        self._updating = False
        if self._info_label:
            self._update_info()
        self._update_conditional_groups()

    def get_values(self) -> dict:
        """Read current values from the database (for case generation)."""
        return self.db.get_dict(self.dict_path)

    def _update_info(self):
        """Update the info panel content and visibility."""
        if not self._info_config or not self._info_label or not self._info_frame:
            return

        # Hide for certain values of a condition field (e.g. hide for "laminar")
        hide_values = self._info_config.get("hide_values", [])
        cond_field = self._info_config.get("condition_field", "")
        if cond_field and hide_values:
            w = self._widgets.get(cond_field)
            if w and isinstance(w, QComboBox):
                if w.currentText() in hide_values:
                    self._info_frame.setVisible(False)
                    return
                self._info_frame.setVisible(True)

        # Legacy single-field condition (e.g. "condition": "simulationType=RAS")
        cond_str = self._info_config.get("condition", "")
        if cond_str and "=" in cond_str:
            cond_key, cond_val = cond_str.split("=", 1)
            w = self._widgets.get(cond_key.strip())
            if w and isinstance(w, QComboBox):
                self._info_frame.setVisible(w.currentText() == cond_val.strip())
                if w.currentText() != cond_val.strip():
                    return

        # Determine which field drives the description lookup
        # field_map: {"RAS": "RASModel", "LES": "LESModel"}
        field_map = self._info_config.get("field_map", {})
        driver_key = self._info_config.get("field", "")
        if field_map and cond_field:
            cw = self._widgets.get(cond_field)
            if cw and isinstance(cw, QComboBox):
                driver_key = field_map.get(cw.currentText(), driver_key)

        descriptions = self._info_config.get("descriptions", {})
        driver_widget = self._widgets.get(driver_key)
        if driver_widget and isinstance(driver_widget, QComboBox):
            current = driver_widget.currentText()
            html = descriptions.get(current, f"<i>No description available for: {current}</i>")
            self._info_label.setText(html)

    def _update_conditional_groups(self):
        """Show/hide groups based on current field values (all conditions must match)."""
        for group_box, conditions in self._conditional_groups:
            visible = True
            for field_key, field_val in conditions:
                w = self._widgets.get(field_key)
                if w and isinstance(w, QComboBox):
                    if w.currentText() != field_val:
                        visible = False
                        break
                elif w and isinstance(w, QLineEdit):
                    if w.text() != field_val:
                        visible = False
                        break
                else:
                    visible = False
                    break
            group_box.setVisible(visible)
