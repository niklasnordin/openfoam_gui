"""
PatchBCEditor — per-patch, per-field boundary condition configuration.
All state lives in CaseDatabase. Widgets observe db signals.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QComboBox, QLineEdit, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QFrame, QSplitter, QMenu,
)
from PySide6.QtCore import Signal, Qt, QTimer

from bc_types import ALL_BC_TYPES, DEFAULT_PATCH_BCS


class PatchFieldEditor(QWidget):
    """Editor for one field on one patch: BC type selector + params.
    Writes directly to the database on change."""

    def __init__(self, db, patch_name: str, field_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.patch_name = patch_name
        self.field_name = field_name
        self.bc_types = ALL_BC_TYPES.get(field_name, {})
        self._param_widgets: dict[str, QLineEdit] = {}
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel(f"<b>{field_name}</b> type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(self.bc_types.keys()))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo, 1)
        layout.addLayout(type_row)

        self.param_frame = QWidget()
        self.param_layout = QFormLayout(self.param_frame)
        self.param_layout.setContentsMargins(16, 4, 4, 4)
        self.param_layout.setSpacing(4)
        layout.addWidget(self.param_frame)

        # Load initial state from db
        self._load_from_db()

    def mousePressEvent(self, event):
        """When user clicks anywhere in this field editor, update preview."""
        super().mousePressEvent(event)
        self._notify_field_active()

    def _notify_field_active(self):
        """Tell PatchBCEditor which field is active for preview."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, PatchBCEditor):
                if parent.last_edited_field != self.field_name:
                    parent.last_edited_field = self.field_name
                    self.db.any_changed.emit()
                break
            parent = parent.parent()

    def _on_type_changed(self, _text):
        QTimer.singleShot(0, self._rebuild_and_write)

    def _rebuild_and_write(self):
        self._rebuild_params()
        if not self._updating:
            self._write_to_db()

    def _rebuild_params(self):
        self._param_widgets.clear()
        while self.param_layout.count():
            item = self.param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bc_name = self.type_combo.currentText()
        bc_def = self.bc_types.get(bc_name, {})

        # Get current params from db to preserve values
        _, db_params = self.db.get_patch_bc(self.patch_name, self.field_name)

        # Determine solver characteristics for conditional params
        tmpl = getattr(self.db, '_template', None)
        is_compressible = (tmpl and "T" in getattr(tmpl, 'BASE_FIELDS', []))

        for param_spec in bc_def.get("params", []):
            label, key, default = param_spec[0], param_spec[1], param_spec[2]
            wtype = param_spec[3] if len(param_spec) > 3 else "str"
            options = param_spec[4] if len(param_spec) > 4 else None
            conditions = param_spec[5] if len(param_spec) > 5 else None

            # Check conditions
            if conditions:
                if conditions.get("incompressible_only") and is_compressible:
                    continue

            val = db_params.get(key, str(default))

            if wtype == "combo" and options:
                w = QComboBox()
                w.addItems(options)
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)
                w.currentTextChanged.connect(lambda *_: self._write_to_db())
                self.param_layout.addRow(label + ":", w)
                self._param_widgets[key] = w
            else:
                le = QLineEdit(str(val))
                le.textChanged.connect(lambda *_: self._write_to_db())
                self.param_layout.addRow(label + ":", le)
                self._param_widgets[key] = le

        # Flush visible-only params to db so filtered-out keys are removed
        if not self._updating:
            bc_type = self.type_combo.currentText()
            params = {}
            for k, w in self._param_widgets.items():
                if isinstance(w, QComboBox):
                    params[k] = w.currentText()
                else:
                    params[k] = w.text()
            self.db.set_patch_bc(self.patch_name, self.field_name, bc_type, params)

    def _write_to_db(self):
        if self._updating:
            return
        # Set which field is active BEFORE the db write triggers preview
        self._notify_field_active_silent()
        bc_type = self.type_combo.currentText()
        params = {}
        for k, w in self._param_widgets.items():
            if isinstance(w, QComboBox):
                params[k] = w.currentText()
            else:
                params[k] = w.text()
        self.db.set_patch_bc(self.patch_name, self.field_name, bc_type, params)

    def _notify_field_active_silent(self):
        """Set last_edited_field on parent without emitting signals."""
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, PatchBCEditor):
                parent.last_edited_field = self.field_name
                break
            parent = parent.parent()

    def _load_from_db(self):
        self._updating = True
        bc_type, params = self.db.get_patch_bc(self.patch_name, self.field_name)
        idx = self.type_combo.findText(bc_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self._rebuild_params()
        for key, val in params.items():
            w = self._param_widgets.get(key)
            if w:
                if isinstance(w, QComboBox):
                    ci = w.findText(str(val))
                    if ci >= 0:
                        w.setCurrentIndex(ci)
                else:
                    w.setText(str(val))
        self._updating = False


class SinglePatchEditor(QScrollArea):
    """Editor panel for all fields on one patch."""

    def __init__(self, db, patch_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.patch_name = patch_name
        self.field_editors: dict[str, PatchFieldEditor] = {}

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(8)

        patch_data = db.get_patch(patch_name)
        role = patch_data.get("role", "wall")

        header = QLabel(
            f"<b>Patch:</b> {patch_name}  &nbsp; "
            f"<span>({role})</span>"
        )
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        self._layout.addWidget(header)

        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Patch role:"))
        self.role_combo = QComboBox()
        self.role_combo.addItems(["inlet", "outlet", "wall", "symmetry"])
        self.role_combo.setCurrentText(role)
        self.role_combo.currentTextChanged.connect(self._on_role_changed)
        role_row.addWidget(self.role_combo, 1)
        role_row.addStretch()
        self._layout.addLayout(role_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        self._layout.addWidget(sep)

        # Build field editors for active fields
        for field in db.active_fields:
            fe = PatchFieldEditor(db, patch_name, field)
            self.field_editors[field] = fe
            self._layout.addWidget(fe)

        self._layout.addStretch()
        self.setWidget(container)

    def _on_role_changed(self, role: str):
        self.db.set_patch_role(self.patch_name, role)
        # Reload field editors
        for fe in self.field_editors.values():
            fe._load_from_db()

    def rebuild_fields(self):
        """Called when active_fields change (turbulence model switch)."""
        active = set(self.db.active_fields)
        current = set(self.field_editors.keys())

        for f in current - active:
            fe = self.field_editors.pop(f)
            self._layout.removeWidget(fe)
            fe.deleteLater()

        for f in active - current:
            fe = PatchFieldEditor(self.db, self.patch_name, f)
            self.field_editors[f] = fe
            self._layout.insertWidget(self._layout.count() - 1, fe)


class BatchPatchEditor(QScrollArea):
    """Batch editor — apply BC settings to multiple selected patches at once."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("<b>Batch Edit — multiple patches selected</b>")
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        self.selected_label = QLabel()
        self.selected_label.setWordWrap(True)
        self.selected_label.setStyleSheet("padding: 4px;")
        layout.addWidget(self.selected_label)

        # Role
        role_group = QGroupBox("Patch Role")
        role_layout = QHBoxLayout(role_group)
        self.role_combo = QComboBox()
        self.role_combo.addItem("— don't change —")
        self.role_combo.addItems(["inlet", "outlet", "wall", "symmetry"])
        role_layout.addWidget(self.role_combo, 1)
        layout.addWidget(role_group)

        # Per-field BC type
        self._field_combos: dict[str, QComboBox] = {}
        self.fields_group = QGroupBox("Boundary Condition Types")
        self._fields_layout = QVBoxLayout(self.fields_group)
        layout.addWidget(self.fields_group)

        # Apply button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply = QPushButton("Apply to Selected Patches")
        self.btn_apply.setMinimumHeight(36)
        self.btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

        layout.addStretch()
        self.setWidget(container)

        self._selected_patches: list[str] = []

    def set_selected(self, patch_names: list[str]):
        """Update which patches are targeted."""
        self._selected_patches = list(patch_names)
        self.selected_label.setText(
            f"<b>{len(patch_names)}</b> patches: " + ", ".join(patch_names))
        self._rebuild_field_combos()

    def _rebuild_field_combos(self):
        """Build one combo per active field."""
        for w in self._field_combos.values():
            self._fields_layout.removeWidget(w.parent())
            w.parent().deleteLater()
        self._field_combos.clear()

        for field in self.db.active_fields:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 2, 0, 2)
            row_l.addWidget(QLabel(f"<b>{field}</b>:"))
            combo = QComboBox()
            combo.addItem("— don't change —")
            from bc_types import ALL_BC_TYPES
            bc_types = ALL_BC_TYPES.get(field, {})
            combo.addItems(list(bc_types.keys()))
            row_l.addWidget(combo, 1)
            self._fields_layout.addWidget(row_w)
            self._field_combos[field] = combo

    def _on_apply(self):
        if not self._selected_patches:
            return

        # Apply role if changed
        role_text = self.role_combo.currentText()
        if role_text != "— don't change —":
            for pname in self._selected_patches:
                self.db.set_patch_role(pname, role_text)

        # Apply BC types if changed
        for field, combo in self._field_combos.items():
            bc_text = combo.currentText()
            if bc_text == "— don't change —":
                continue
            from bc_types import ALL_BC_TYPES
            bc_def = ALL_BC_TYPES.get(field, {}).get(bc_text, {})
            default_params = {}
            for param_spec in bc_def.get("params", []):
                key, default = param_spec[1], param_spec[2]
                default_params[key] = str(default)
            for pname in self._selected_patches:
                self.db.set_patch_bc(pname, field, bc_text, default_params)

        self.db.any_changed.emit()

        # Notify parent to rebuild single editors too
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, PatchBCEditor):
                parent._rebuild_all()
                break
            parent = parent.parent()


class PatchBCEditor(QWidget):
    """Master widget: patch list + per-patch field editors.
    Supports multi-select with batch editing, copy/paste BCs, and filtering.
    Observes db for STL/turbulence changes."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._patch_editors: dict[str, SinglePatchEditor] = {}
        self.last_edited_field: str = "p"  # tracks which field the user last touched
        self._copied_bcs: dict | None = None  # stored BC data for paste

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        hint = QLabel("<b>Patches</b> <span style=' font-size:10px;'>"
                      "(Ctrl/Shift-click to multi-select)</span>")
        hint.setStyleSheet("padding: 4px;")
        left_layout.addWidget(hint)

        # Filter box
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter patches…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        left_layout.addWidget(self._filter)

        self.patch_list = QListWidget()
        self.patch_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.patch_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.patch_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.patch_list.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.patch_list)
        splitter.addWidget(left)

        self.editor_stack = QStackedWidget()
        placeholder = QLabel(
            "<center><br><br>Select a patch to configure<br>boundary conditions</center>"
        )
        self.editor_stack.addWidget(placeholder)

        # Batch editor (always in the stack, shown when multi-select)
        self._batch_editor = BatchPatchEditor(db)
        self.editor_stack.addWidget(self._batch_editor)

        splitter.addWidget(self.editor_stack)

        splitter.setSizes([180, 400])
        layout.addWidget(splitter)

        # Build initial patches from db
        self._rebuild_all()

        # Observe db signals
        self.db.stl_changed.connect(self._rebuild_all)
        self.db.turbulence_changed.connect(self._on_turb_changed)

    def _apply_filter(self, text):
        """Show/hide patches based on filter text."""
        filt = text.lower()
        for i in range(self.patch_list.count()):
            item = self.patch_list.item(i)
            item.setHidden(filt not in item.text().lower())

    def _show_context_menu(self, pos):
        """Right-click context menu with Copy/Paste BCs."""
        menu = QMenu(self)
        selected = self.patch_list.selectedItems()

        if len(selected) == 1:
            act_copy = menu.addAction("Copy BCs")
            act_copy.triggered.connect(lambda: self._copy_bcs(selected[0].text()))

        if self._copied_bcs and selected:
            n = len(selected)
            act_paste = menu.addAction(
                f"Paste BCs to {n} patch{'es' if n > 1 else ''}")
            act_paste.triggered.connect(
                lambda: self._paste_bcs([it.text() for it in selected]))

        if menu.actions():
            menu.exec(self.patch_list.mapToGlobal(pos))

    def _copy_bcs(self, patch_name: str):
        """Copy all BC settings from a patch."""
        self._copied_bcs = {}
        for field in self.db.active_fields:
            bc_type, params = self.db.get_patch_bc(patch_name, field)
            self._copied_bcs[field] = {"type": bc_type, "params": dict(params)}
        # Also copy role
        p = self.db.get_patch(patch_name)
        self._copied_bcs["_role"] = p.get("role", "wall")

    def _paste_bcs(self, patch_names: list[str]):
        """Paste copied BC settings to one or more patches."""
        if not self._copied_bcs:
            return
        role = self._copied_bcs.get("_role")
        for pname in patch_names:
            if role:
                self.db.set_patch_role(pname, role)
            for field in self.db.active_fields:
                if field in self._copied_bcs:
                    bc = self._copied_bcs[field]
                    self.db.set_patch_bc(pname, field,
                                        bc["type"], dict(bc["params"]))
        self.db.any_changed.emit()
        self._rebuild_all()

    def _rebuild_all(self):
        """Rebuild entire patch list from database."""
        selected_names = set()
        for item in self.patch_list.selectedItems():
            selected_names.add(item.text())

        self.patch_list.clear()
        for name, editor in self._patch_editors.items():
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
        self._patch_editors.clear()

        for name in self.db.get_patch_names():
            editor = SinglePatchEditor(self.db, name)
            self._patch_editors[name] = editor
            self.editor_stack.addWidget(editor)
            self.patch_list.addItem(name)

        # Restore selection
        if selected_names:
            for i in range(self.patch_list.count()):
                if self.patch_list.item(i).text() in selected_names:
                    self.patch_list.item(i).setSelected(True)

    def _on_turb_changed(self):
        self.db.sync_patches_to_active_fields()
        for editor in self._patch_editors.values():
            editor.rebuild_fields()
        # Refresh batch editor combos if visible
        if self.editor_stack.currentWidget() is self._batch_editor:
            self._batch_editor._rebuild_field_combos()

    def _on_selection_changed(self):
        selected = self.patch_list.selectedItems()
        if len(selected) == 0:
            self.editor_stack.setCurrentIndex(0)  # placeholder
        elif len(selected) == 1:
            name = selected[0].text()
            editor = self._patch_editors.get(name)
            if editor:
                self.editor_stack.setCurrentWidget(editor)
        else:
            names = [item.text() for item in selected]
            self._batch_editor.set_selected(names)
            self.editor_stack.setCurrentWidget(self._batch_editor)
