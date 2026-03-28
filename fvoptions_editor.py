"""
FvOptionsEditor — add, remove, and configure OpenFOAM fvOptions source terms.
All state lives in CaseDatabase. Writes to system/fvOptions on export.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QComboBox, QLineEdit, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QFrame, QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt

from fv_options import FV_OPTIONS_CATALOG
from porous_db import PorousDatabase, POROUS_KEYS
from dict_editor import _make_numeric_line_edit


class SingleOptionEditor(QScrollArea):
    """Editor for one fvOption instance. Writes to db on change."""

    def __init__(self, db, opt_name: str, opt_type: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.opt_name = opt_name
        self.opt_type = opt_type
        self._widgets: dict[str, QWidget] = {}
        self._updating = False

        catalog = FV_OPTIONS_CATALOG.get(opt_type, {})

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel(
            f"<b>{opt_name}</b>  —  "
            f"<span style='color:#E65100;'>{opt_type}</span>"
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

        # ---- Porous media database buttons ---- #
        if opt_type == "explicitPorositySource":
            self._porous_db = PorousDatabase()

            pdb_group = QGroupBox("Porous Media Database")
            pdb_layout = QVBoxLayout(pdb_group)

            # Load row
            load_row = QHBoxLayout()
            load_row.addWidget(QLabel("Load preset:"))
            self._porous_combo = QComboBox()
            self._refresh_porous_combo()
            load_row.addWidget(self._porous_combo, 1)
            btn_load = QPushButton("Load")
            btn_load.clicked.connect(self._load_porous_preset)
            load_row.addWidget(btn_load)
            btn_delete = QPushButton("Delete")
            btn_delete.setStyleSheet("background: #E53935;")
            btn_delete.clicked.connect(self._delete_porous_preset)
            load_row.addWidget(btn_delete)
            pdb_layout.addLayout(load_row)

            # Save row
            save_row = QHBoxLayout()
            save_row.addWidget(QLabel("Save as:"))
            self._porous_name_edit = QLineEdit()
            self._porous_name_edit.setPlaceholderText("Preset name")
            save_row.addWidget(self._porous_name_edit, 1)
            save_row.addWidget(QLabel("Notes:"))
            self._porous_desc_edit = QLineEdit()
            self._porous_desc_edit.setPlaceholderText("Optional description")
            save_row.addWidget(self._porous_desc_edit, 1)
            btn_save = QPushButton("Save to DB")
            btn_save.clicked.connect(self._save_porous_preset)
            save_row.addWidget(btn_save)
            pdb_layout.addLayout(save_row)

            # Info label
            self._porous_info = QLabel()
            self._porous_info.setWordWrap(True)
            self._porous_info.setStyleSheet(
                "font-size: 10px; padding: 2px;")
            pdb_layout.addWidget(self._porous_info)
            self._update_porous_info()

            layout.addWidget(pdb_group)

        layout.addStretch()
        self.setWidget(container)

        self._load_from_db()

    def _refresh_porous_combo(self):
        self._porous_combo.clear()
        self._porous_combo.addItem("— select —")
        pdb = self._porous_db
        for entry in pdb.all_entries():
            name = entry.get("name", "")
            desc = entry.get("description", "")
            label = f"{name}  —  {desc}" if desc else name
            self._porous_combo.addItem(label, name)

    def _update_porous_info(self):
        n = len(self._porous_db.all_entries())
        self._porous_info.setText(
            f"Database: {self._porous_db.path}  ({n} preset{'s' if n != 1 else ''})")

    def _load_porous_preset(self):
        name = self._porous_combo.currentData()
        if not name:
            return
        entry = self._porous_db.get(name)
        if not entry:
            return
        params = PorousDatabase.params_to_fvoption(entry)
        self._updating = True
        for key, val in params.items():
            widget = self._widgets.get(key)
            if widget:
                if isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
            self.db.set_fv_option_param(self.opt_name, key, val)
        self._updating = False
        self.db.any_changed.emit()

        # Pre-fill save fields
        self._porous_name_edit.setText(name)
        self._porous_desc_edit.setText(entry.get("description", ""))

    def _save_porous_preset(self):
        name = self._porous_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Save", "Please enter a preset name.")
            return

        # Check overwrite
        if self._porous_db.get(name):
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"Preset '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        opt_data = self.db.get_fv_option(self.opt_name)
        params = opt_data.get("params", {})
        entry = PorousDatabase.params_from_fvoption(params)
        entry["name"] = name
        entry["description"] = self._porous_desc_edit.text().strip()
        self._porous_db.add(entry)
        self._refresh_porous_combo()
        self._update_porous_info()
        QMessageBox.information(self, "Saved",
                                f"Preset '{name}' saved to database.")

    def _delete_porous_preset(self):
        name = self._porous_combo.currentData()
        if not name:
            return
        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{name}' from database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._porous_db.remove(name)
            self._refresh_porous_combo()
            self._update_porous_info()

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
            self.db.set_fv_option_param(self.opt_name, key, value)

    def _write_numeric(self, key, text, is_int):
        if self._updating:
            return
        try:
            value = int(text) if is_int else float(text)
            self.db.set_fv_option_param(self.opt_name, key, value)
        except ValueError:
            pass

    def _load_from_db(self):
        self._updating = True
        opt_data = self.db.get_fv_option(self.opt_name)
        params = opt_data.get("params", {})
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


class FvOptionsEditor(QWidget):
    """Master widget: fvOption list + add/remove + per-option settings.
    Observes db.fvoptions_changed to stay in sync."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._editors: dict[str, SingleOptionEditor] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Add controls
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add:"))
        self.type_combo = QComboBox()
        for opt_type, info in FV_OPTIONS_CATALOG.items():
            self.type_combo.addItem(f"{opt_type}  —  {info['description']}", opt_type)
        add_row.addWidget(self.type_combo, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Source term name")
        add_row.addWidget(self.name_edit)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._add_option)
        add_row.addWidget(self.btn_add)

        layout.addLayout(add_row)

        # Main area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("<b>Active fvOptions</b>")
        lbl.setStyleSheet("padding: 4px;")
        left_layout.addWidget(lbl)

        self.opt_list = QListWidget()
        self.opt_list.currentRowChanged.connect(self._on_opt_selected)
        left_layout.addWidget(self.opt_list)

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setStyleSheet("background: #E53935;")
        self.btn_remove.clicked.connect(self._remove_option)
        left_layout.addWidget(self.btn_remove)

        splitter.addWidget(left)

        self.editor_stack = QStackedWidget()
        placeholder = QLabel(
            "<center><br><br>Add an fvOption source term<br>"
            "or select one to configure</center>"
        )
        self.editor_stack.addWidget(placeholder)
        splitter.addWidget(self.editor_stack)

        splitter.setSizes([220, 400])
        layout.addWidget(splitter)

        # Observe db
        self.db.fvoptions_changed.connect(self._rebuild)
        self._rebuild()

    def _add_option(self):
        opt_type = self.type_combo.currentData()
        name = self.name_edit.text().strip()

        if not name:
            existing = self.db.get_fv_option_names()
            base = opt_type
            n = 1
            name = base
            while name in existing:
                name = f"{base}_{n}"
                n += 1

        if name in self.db.get_fv_option_names():
            QMessageBox.warning(self, "Duplicate Name",
                                f"fvOption '{name}' already exists.")
            return

        catalog = FV_OPTIONS_CATALOG.get(opt_type, {})
        defaults = {}
        for _label, key, default, _ftype, _options in catalog.get("fields", []):
            defaults[key] = default

        self.db.add_fv_option(name, opt_type, defaults)
        self.name_edit.clear()

    def _remove_option(self):
        item = self.opt_list.currentItem()
        if not item:
            return
        name = item.text().split("  (")[0]
        self.db.remove_fv_option(name)

    def _rebuild(self):
        current_name = None
        if self.opt_list.currentItem():
            current_name = self.opt_list.currentItem().text().split("  (")[0]

        self.opt_list.clear()
        for name, editor in self._editors.items():
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
        self._editors.clear()

        for name in self.db.get_fv_option_names():
            opt_data = self.db.get_fv_option(name)
            opt_type = opt_data.get("type", "")

            editor = SingleOptionEditor(self.db, name, opt_type)
            self._editors[name] = editor
            self.editor_stack.addWidget(editor)

            self.opt_list.addItem(f"{name}  ({opt_type})")

        if current_name:
            for i in range(self.opt_list.count()):
                if self.opt_list.item(i).text().startswith(current_name):
                    self.opt_list.setCurrentRow(i)
                    break

    def _on_opt_selected(self, row):
        if row < 0:
            return
        name = self.opt_list.item(row).text().split("  (")[0]
        editor = self._editors.get(name)
        if editor:
            self.editor_stack.setCurrentWidget(editor)
