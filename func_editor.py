"""
FuncObjectEditor — add, remove, and configure OpenFOAM function objects.
All state lives in CaseDatabase. Each function object writes to its own
file in system/ and controlDict gets #include directives.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QComboBox, QLineEdit, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QFrame, QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt

from func_objects import FUNCTION_OBJECT_CATALOG, FUNC_OBJECT_PRESETS
from dict_editor import _make_numeric_line_edit


class SingleFuncEditor(QScrollArea):
    """Editor for one function object instance. Writes to db on change."""

    def __init__(self, db, fo_name: str, fo_type: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.fo_name = fo_name
        self.fo_type = fo_type
        self._widgets: dict[str, QWidget] = {}
        self._updating = False

        catalog = FUNCTION_OBJECT_CATALOG.get(fo_type, {})

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel(
            f"<b>{fo_name}</b>  —  "
            f"<span style='color:#1976D2;'>{fo_type}</span>"
        )
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        desc = QLabel(catalog.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; padding: 2px;")
        layout.addWidget(desc)

        group = QGroupBox("Settings")
        form = QFormLayout(group)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(6)

        for field_spec in catalog.get("fields", []):
            label, key, default, ftype, options = field_spec
            widget = self._make_field(key, default, ftype, options)
            form.addRow(label + ":", widget)

        layout.addWidget(group)
        layout.addStretch()
        self.setWidget(container)

        # Load current values from db
        self._load_from_db()

    def _make_field(self, key, default, ftype, options):
        if ftype == "combo":
            w = QComboBox()
            w.addItems(options)
            idx = w.findText(str(default))
            if idx >= 0:
                w.setCurrentIndex(idx)
            w.currentTextChanged.connect(lambda val, k=key: self._write(k, val))
            self._widgets[key] = w
        elif ftype == "int":
            w = _make_numeric_line_edit(default, is_int=True)
            w.textChanged.connect(lambda val, k=key: self._write_numeric(k, val, True))
            self._widgets[key] = w
        elif ftype == "float":
            w = _make_numeric_line_edit(default, is_int=False)
            w.textChanged.connect(lambda val, k=key: self._write_numeric(k, val, False))
            self._widgets[key] = w
        else:
            w = QLineEdit(str(default))
            w.textChanged.connect(lambda val, k=key: self._write(k, val))
            self._widgets[key] = w
        return w

    def _write(self, key, value):
        if not self._updating:
            self.db.set_func_object_param(self.fo_name, key, value)

    def _write_numeric(self, key, text, is_int):
        if self._updating:
            return
        try:
            value = int(text) if is_int else float(text)
            self.db.set_func_object_param(self.fo_name, key, value)
        except ValueError:
            pass

    def _load_from_db(self):
        self._updating = True
        fo_data = self.db.get_func_object(self.fo_name)
        params = fo_data.get("params", {})
        for key, widget in self._widgets.items():
            if key not in params:
                continue
            val = params[key]
            if isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
        self._updating = False


class FuncObjectEditor(QWidget):
    """Master widget: function object list + add/remove + per-FO settings.
    Observes db.func_changed to stay in sync."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._editors: dict[str, SingleFuncEditor] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Add controls
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add:"))
        self.type_combo = QComboBox()
        for fo_type, info in FUNCTION_OBJECT_CATALOG.items():
            self.type_combo.addItem(f"{fo_type}  —  {info['description']}", fo_type)
        add_row.addWidget(self.type_combo, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Function object name")
        add_row.addWidget(self.name_edit)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._add_func_object)
        add_row.addWidget(self.btn_add)

        layout.addLayout(add_row)

        # Preset templates row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("— select template —")
        for name, preset in FUNC_OBJECT_PRESETS.items():
            self._preset_combo.addItem(name, name)
        preset_row.addWidget(self._preset_combo, 1)
        btn_load_preset = QPushButton("Load Preset")
        btn_load_preset.setObjectName("secondary")
        btn_load_preset.clicked.connect(self._load_preset)
        preset_row.addWidget(btn_load_preset)
        layout.addLayout(preset_row)

        # Main area: list + editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("<b>Active Function Objects</b>")
        lbl.setStyleSheet("padding: 4px;")
        left_layout.addWidget(lbl)

        self.fo_list = QListWidget()
        self.fo_list.currentRowChanged.connect(self._on_fo_selected)
        left_layout.addWidget(self.fo_list)

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setStyleSheet("background: #E53935;")
        self.btn_remove.clicked.connect(self._remove_func_object)
        left_layout.addWidget(self.btn_remove)

        splitter.addWidget(left)

        self.editor_stack = QStackedWidget()
        placeholder = QLabel(
            "<center><br><br>Add a function object or<br>"
            "select one to configure</center>"
        )
        self.editor_stack.addWidget(placeholder)
        splitter.addWidget(self.editor_stack)

        splitter.setSizes([220, 400])
        layout.addWidget(splitter)

        # Observe db
        self.db.func_changed.connect(self._rebuild)

        # Initial build
        self._rebuild()

    def _add_func_object(self):
        fo_type = self.type_combo.currentData()
        name = self.name_edit.text().strip()

        if not name:
            # Auto-generate name
            existing = self.db.get_func_object_names()
            base = fo_type
            n = 1
            name = base
            while name in existing:
                name = f"{base}_{n}"
                n += 1

        if name in self.db.get_func_object_names():
            QMessageBox.warning(self, "Duplicate Name",
                                f"Function object '{name}' already exists.")
            return

        # Get defaults from catalog
        catalog = FUNCTION_OBJECT_CATALOG.get(fo_type, {})
        defaults = {}
        for _label, key, default, _ftype, _options in catalog.get("fields", []):
            defaults[key] = default

        self.db.add_func_object(name, fo_type, defaults)
        self.name_edit.clear()

    def _remove_func_object(self):
        item = self.fo_list.currentItem()
        if not item:
            return
        # Extract name (strip the type annotation)
        name = item.text().split("  (")[0]
        self.db.remove_func_object(name)

    def _rebuild(self):
        current_name = None
        if self.fo_list.currentItem():
            current_name = self.fo_list.currentItem().text().split("  (")[0]

        self.fo_list.clear()
        for name, editor in self._editors.items():
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
        self._editors.clear()

        for name in self.db.get_func_object_names():
            fo_data = self.db.get_func_object(name)
            fo_type = fo_data.get("type", "")

            editor = SingleFuncEditor(self.db, name, fo_type)
            self._editors[name] = editor
            self.editor_stack.addWidget(editor)

            self.fo_list.addItem(f"{name}  ({fo_type})")

        # Restore selection
        if current_name:
            for i in range(self.fo_list.count()):
                if self.fo_list.item(i).text().startswith(current_name):
                    self.fo_list.setCurrentRow(i)
                    break

    def _on_fo_selected(self, row):
        if row < 0:
            return
        name = self.fo_list.item(row).text().split("  (")[0]
        editor = self._editors.get(name)
        if editor:
            self.editor_stack.setCurrentWidget(editor)

    def _load_preset(self):
        """Load a preset template — adds multiple function objects at once."""
        preset_name = self._preset_combo.currentData()
        if not preset_name or preset_name not in FUNC_OBJECT_PRESETS:
            return

        preset = FUNC_OBJECT_PRESETS[preset_name]
        existing = set(self.db.get_func_object_names())
        added = 0

        for fo_name, fo_spec in preset.get("objects", {}).items():
            # Avoid duplicates
            name = fo_name
            n = 1
            while name in existing:
                name = f"{fo_name}_{n}"
                n += 1

            fo_type = fo_spec.get("type", "")
            params = dict(fo_spec.get("params", {}))
            self.db.add_func_object(name, fo_type, params)
            existing.add(name)
            added += 1

        if added:
            self.statusBar_msg = f"Loaded preset: {preset_name} ({added} objects)"
