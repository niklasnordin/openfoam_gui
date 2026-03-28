"""
SurfaceEditor — per-surface snappyHexMesh settings with group support.
Surfaces can be assigned to groups. Group settings propagate to all members.
All state lives in CaseDatabase.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem, QLabel, QComboBox, QSpinBox,
    QSplitter, QStackedWidget, QPushButton, QLineEdit,
    QFrame, QScrollArea, QMessageBox,
)
from PySide6.QtCore import Signal, Qt


class GroupSettingsWidget(QWidget):
    """Editable settings for one surface group."""

    def __init__(self, db, group_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.group_name = group_name
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel(f"<b>Group:</b> {group_name}")
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        settings = db.get_surface_group(group_name)

        ref = QGroupBox("Group Refinement Settings")
        form = QFormLayout(ref)

        self.min_level = QSpinBox()
        self.min_level.setRange(0, 10)
        self.min_level.setValue(settings.get("minLevel", 2))
        self.min_level.valueChanged.connect(lambda v: self._write("minLevel", v))
        form.addRow("Min Refinement Level:", self.min_level)

        self.max_level = QSpinBox()
        self.max_level.setRange(0, 10)
        self.max_level.setValue(settings.get("maxLevel", 4))
        self.max_level.valueChanged.connect(lambda v: self._write("maxLevel", v))
        form.addRow("Max Refinement Level:", self.max_level)

        self.feature_level = QSpinBox()
        self.feature_level.setRange(0, 10)
        self.feature_level.setValue(settings.get("featureLevel", 2))
        self.feature_level.valueChanged.connect(lambda v: self._write("featureLevel", v))
        form.addRow("Feature Edge Level:", self.feature_level)

        self.n_layers = QSpinBox()
        self.n_layers.setRange(0, 20)
        self.n_layers.setValue(settings.get("nLayers", 3))
        self.n_layers.valueChanged.connect(lambda v: self._write("nLayers", v))
        form.addRow("Surface Layers:", self.n_layers)

        self.patch_type = QComboBox()
        self.patch_type.addItems(["wall", "patch", "symmetry", "empty"])
        idx = self.patch_type.findText(settings.get("patchType", "wall"))
        if idx >= 0:
            self.patch_type.setCurrentIndex(idx)
        self.patch_type.currentTextChanged.connect(lambda v: self._write("patchType", v))
        form.addRow("Patch Type:", self.patch_type)

        layout.addWidget(ref)

        # Members list
        members_group = QGroupBox("Surfaces in this group")
        ml = QVBoxLayout(members_group)
        self.members_label = QLabel()
        self.members_label.setWordWrap(True)
        self.members_label.setStyleSheet("padding: 4px;")
        ml.addWidget(self.members_label)
        layout.addWidget(members_group)
        self._refresh_members()

        layout.addStretch()
        self.db.surfgroup_changed.connect(self._refresh_members)

    def _write(self, key, value):
        if not self._updating:
            self.db.set_surface_group_value(self.group_name, key, value)

    def _refresh_members(self):
        members = self.db.get_surfaces_in_group(self.group_name)
        if members:
            self.members_label.setText(", ".join(members))
        else:
            self.members_label.setText("<i>No surfaces assigned</i>")


class SingleSurfaceEditor(QWidget):
    """Editor for one surface — group assignment + individual settings."""

    def __init__(self, db, surface_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.surface_name = surface_name
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel(f"<b>Surface:</b> {surface_name}")
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        # Group assignment
        assign_row = QHBoxLayout()
        assign_row.addWidget(QLabel("Group:"))
        self.group_combo = QComboBox()
        self._refresh_group_combo()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        assign_row.addWidget(self.group_combo, 1)
        layout.addLayout(assign_row)

        self.group_info = QLabel()
        self.group_info.setWordWrap(True)
        self.group_info.setStyleSheet("font-size: 11px; padding: 4px;")
        layout.addWidget(self.group_info)

        # Individual settings (hidden when grouped)
        self.settings_group = QGroupBox("Individual Settings")
        form = QFormLayout(self.settings_group)

        settings = db.get_surface(surface_name)

        self.min_level = QSpinBox()
        self.min_level.setRange(0, 10)
        self.min_level.setValue(settings.get("minLevel", 2))
        self.min_level.valueChanged.connect(lambda v: self._write("minLevel", v))
        form.addRow("Min Refinement Level:", self.min_level)

        self.max_level = QSpinBox()
        self.max_level.setRange(0, 10)
        self.max_level.setValue(settings.get("maxLevel", 4))
        self.max_level.valueChanged.connect(lambda v: self._write("maxLevel", v))
        form.addRow("Max Refinement Level:", self.max_level)

        self.feature_level = QSpinBox()
        self.feature_level.setRange(0, 10)
        self.feature_level.setValue(settings.get("featureLevel", 2))
        self.feature_level.valueChanged.connect(lambda v: self._write("featureLevel", v))
        form.addRow("Feature Edge Level:", self.feature_level)

        self.n_layers = QSpinBox()
        self.n_layers.setRange(0, 20)
        self.n_layers.setValue(settings.get("nLayers", 3))
        self.n_layers.valueChanged.connect(lambda v: self._write("nLayers", v))
        form.addRow("Surface Layers:", self.n_layers)

        self.patch_type = QComboBox()
        self.patch_type.addItems(["wall", "patch", "symmetry", "empty"])
        idx = self.patch_type.findText(settings.get("patchType", "wall"))
        if idx >= 0:
            self.patch_type.setCurrentIndex(idx)
        self.patch_type.currentTextChanged.connect(lambda v: self._write("patchType", v))
        form.addRow("Patch Type:", self.patch_type)

        layout.addWidget(self.settings_group)
        layout.addStretch()

        self._update_visibility()
        self.db.surfgroup_changed.connect(self._on_groups_updated)

    def _refresh_group_combo(self):
        self.group_combo.blockSignals(True)
        current = self.db.get_surface(self.surface_name).get("group", "")
        self.group_combo.clear()
        self.group_combo.addItem("(ungrouped)", "")
        for gname in self.db.get_surface_groups():
            self.group_combo.addItem(gname, gname)
        for i in range(self.group_combo.count()):
            if self.group_combo.itemData(i) == current:
                self.group_combo.setCurrentIndex(i)
                break
        self.group_combo.blockSignals(False)

    def _on_group_changed(self, _text):
        group = self.group_combo.currentData()
        if group is None:
            group = ""
        self.db.assign_surface_to_group(self.surface_name, group)
        self._update_visibility()
        self._load_from_db()

    def _on_groups_updated(self):
        self._refresh_group_combo()
        self._update_visibility()
        self._load_from_db()

    def _update_visibility(self):
        s = self.db.get_surface(self.surface_name)
        group = s.get("group", "")
        if group:
            self.settings_group.setVisible(False)
            g = self.db.get_surface_group(group)
            self.group_info.setText(
                f"Using group <b>{group}</b>: "
                f"level {g.get('minLevel',2)}-{g.get('maxLevel',4)}, "
                f"layers {g.get('nLayers',3)}, "
                f"type {g.get('patchType','wall')}"
            )
            self.group_info.setVisible(True)
        else:
            self.settings_group.setVisible(True)
            self.group_info.setVisible(False)

    def _write(self, key, value):
        if not self._updating:
            self.db.set_surface_value(self.surface_name, key, value)

    def _load_from_db(self):
        self._updating = True
        s = self.db.get_surface(self.surface_name)
        self.min_level.setValue(s.get("minLevel", 2))
        self.max_level.setValue(s.get("maxLevel", 4))
        self.feature_level.setValue(s.get("featureLevel", 2))
        self.n_layers.setValue(s.get("nLayers", 3))
        idx = self.patch_type.findText(s.get("patchType", "wall"))
        if idx >= 0:
            self.patch_type.setCurrentIndex(idx)
        self._updating = False


class BatchSurfaceEditor(QScrollArea):
    """Batch editor — apply refinement settings to multiple selected surfaces."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("<b>Batch Edit — multiple surfaces selected</b>")
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        self.selected_label = QLabel()
        self.selected_label.setWordWrap(True)
        self.selected_label.setStyleSheet("padding: 4px;")
        layout.addWidget(self.selected_label)

        # Group assignment
        grp_assign = QGroupBox("Assign to Group")
        ga_layout = QHBoxLayout(grp_assign)
        self.group_combo = QComboBox()
        self.group_combo.addItem("— don't change —")
        ga_layout.addWidget(self.group_combo, 1)
        layout.addWidget(grp_assign)

        # Refinement settings
        ref = QGroupBox("Refinement Settings (leave -1 to skip)")
        form = QFormLayout(ref)

        self.min_level = QSpinBox()
        self.min_level.setRange(-1, 10)
        self.min_level.setValue(-1)
        self.min_level.setSpecialValueText("— skip —")
        form.addRow("Min Refinement Level:", self.min_level)

        self.max_level = QSpinBox()
        self.max_level.setRange(-1, 10)
        self.max_level.setValue(-1)
        self.max_level.setSpecialValueText("— skip —")
        form.addRow("Max Refinement Level:", self.max_level)

        self.feature_level = QSpinBox()
        self.feature_level.setRange(-1, 10)
        self.feature_level.setValue(-1)
        self.feature_level.setSpecialValueText("— skip —")
        form.addRow("Feature Edge Level:", self.feature_level)

        self.n_layers = QSpinBox()
        self.n_layers.setRange(-1, 20)
        self.n_layers.setValue(-1)
        self.n_layers.setSpecialValueText("— skip —")
        form.addRow("Surface Layers:", self.n_layers)

        self.patch_type = QComboBox()
        self.patch_type.addItem("— don't change —")
        self.patch_type.addItems(["wall", "patch", "symmetry", "empty"])
        form.addRow("Patch Type:", self.patch_type)

        layout.addWidget(ref)

        # Apply button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply = QPushButton("Apply to Selected Surfaces")
        self.btn_apply.setMinimumHeight(36)
        self.btn_apply.clicked.connect(self._on_apply)
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

        layout.addStretch()
        self.setWidget(container)

        self._selected_surfaces: list[str] = []

    def set_selected(self, surface_names: list[str]):
        """Update which surfaces are targeted."""
        self._selected_surfaces = list(surface_names)
        self.selected_label.setText(
            f"<b>{len(surface_names)}</b> surfaces: " + ", ".join(surface_names))
        self._refresh_group_combo()

    def _refresh_group_combo(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("— don't change —")
        self.group_combo.addItem("(ungrouped)")
        for gname in self.db.get_surface_groups():
            self.group_combo.addItem(gname)
        self.group_combo.blockSignals(False)

    def _on_apply(self):
        if not self._selected_surfaces:
            return

        # Apply group assignment
        group_text = self.group_combo.currentText()
        if group_text == "(ungrouped)":
            for sname in self._selected_surfaces:
                self.db.assign_surface_to_group(sname, "")
        elif group_text != "— don't change —":
            for sname in self._selected_surfaces:
                self.db.assign_surface_to_group(sname, group_text)

        # Apply refinement settings (only non-skip values)
        for sname in self._selected_surfaces:
            if self.min_level.value() >= 0:
                self.db.set_surface_value(sname, "minLevel", self.min_level.value())
            if self.max_level.value() >= 0:
                self.db.set_surface_value(sname, "maxLevel", self.max_level.value())
            if self.feature_level.value() >= 0:
                self.db.set_surface_value(sname, "featureLevel", self.feature_level.value())
            if self.n_layers.value() >= 0:
                self.db.set_surface_value(sname, "nLayers", self.n_layers.value())

            pt = self.patch_type.currentText()
            if pt != "— don't change —":
                self.db.set_surface_value(sname, "patchType", pt)

        self.db.any_changed.emit()

        # Trigger rebuild
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, SurfaceEditor):
                parent._rebuild()
                break
            parent = parent.parent()


class SurfaceEditor(QWidget):
    """Master widget: group management + surface list + editors.
    Supports multi-select with batch editing."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._surface_editors = {}
        self._group_editors = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Group management bar
        gbar = QHBoxLayout()
        gbar.addWidget(QLabel("<b>Groups:</b>"))
        self.group_name_edit = QLineEdit()
        self.group_name_edit.setPlaceholderText("New group name")
        self.group_name_edit.setMaximumWidth(150)
        gbar.addWidget(self.group_name_edit)
        btn_add = QPushButton("Add Group")
        btn_add.clicked.connect(self._add_group)
        gbar.addWidget(btn_add)
        btn_del = QPushButton("Remove Group")
        btn_del.setStyleSheet("background: #E53935;")
        btn_del.clicked.connect(self._remove_group)
        gbar.addWidget(btn_del)
        gbar.addStretch()
        layout.addLayout(gbar)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.setSpacing(2)
        hint = QLabel("<b>Groups & Surfaces</b> "
                      "<span style=' font-size:10px;'>"
                      "(Ctrl/Shift-click to multi-select)</span>")
        hint.setStyleSheet("padding: 4px;")
        ll.addWidget(hint)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter surfaces…")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        ll.addWidget(self._filter)

        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.item_list.itemSelectionChanged.connect(self._on_selection_changed)
        ll.addWidget(self.item_list)
        splitter.addWidget(left)

        self.editor_stack = QStackedWidget()
        placeholder = QLabel(
            "<center><br><br>Select a group or surface<br>to configure</center>"
        )
        self.editor_stack.addWidget(placeholder)

        # Batch editor (always in the stack)
        self._batch_editor = BatchSurfaceEditor(db)
        self.editor_stack.addWidget(self._batch_editor)

        splitter.addWidget(self.editor_stack)

        splitter.setSizes([220, 400])
        layout.addWidget(splitter)

        self.db.stl_changed.connect(self._rebuild)
        self.db.surfgroup_changed.connect(self._rebuild)

    def _apply_filter(self, text):
        """Show/hide items based on filter text."""
        filt = text.lower()
        for i in range(self.item_list.count()):
            item = self.item_list.item(i)
            item.setHidden(filt not in item.text().lower())

    def _add_group(self):
        name = self.group_name_edit.text().strip()
        if not name:
            return
        if name in self.db.get_surface_groups():
            QMessageBox.warning(self, "Duplicate", f"Group '{name}' exists.")
            return
        self.db.add_surface_group(name)
        self.group_name_edit.clear()

    def _remove_group(self):
        selected = self.item_list.selectedItems()
        for item in selected:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data.startswith("group:"):
                self.db.remove_surface_group(data[6:])

    def _rebuild(self):
        selected_data = set()
        for item in self.item_list.selectedItems():
            d = item.data(Qt.ItemDataRole.UserRole)
            if d:
                selected_data.add(d)

        self.item_list.clear()
        for ed in self._surface_editors.values():
            self.editor_stack.removeWidget(ed)
            ed.deleteLater()
        for ed in self._group_editors.values():
            self.editor_stack.removeWidget(ed)
            ed.deleteLater()
        self._surface_editors.clear()
        self._group_editors.clear()

        # Groups
        for gname in self.db.get_surface_groups():
            members = self.db.get_surfaces_in_group(gname)
            item = QListWidgetItem(f"\u2630 {gname}  ({len(members)})")
            item.setData(Qt.ItemDataRole.UserRole, f"group:{gname}")
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.item_list.addItem(item)

            ed = GroupSettingsWidget(self.db, gname)
            self._group_editors[gname] = ed
            self.editor_stack.addWidget(ed)

        # Separator
        if self.db.get_surface_groups() and self.db.stl_entries:
            sep = QListWidgetItem("─────────────")
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            self.item_list.addItem(sep)

        # Surfaces
        for entry in self.db.stl_entries:
            fname = entry["stem"]
            for solid in entry.get("solids", [fname]):
                s = self.db.get_surface(solid)
                group = s.get("group", "")
                label = f"    {solid}  [{group}]" if group else solid
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, f"surface:{solid}")
                self.item_list.addItem(item)

                ed = SingleSurfaceEditor(self.db, solid)
                self._surface_editors[solid] = ed
                self.editor_stack.addWidget(ed)

        # Restore selection
        if selected_data:
            for i in range(self.item_list.count()):
                d = self.item_list.item(i).data(Qt.ItemDataRole.UserRole)
                if d and d in selected_data:
                    self.item_list.item(i).setSelected(True)

    def _on_selection_changed(self):
        selected = self.item_list.selectedItems()
        # Filter out separators
        valid = [item for item in selected if item.data(Qt.ItemDataRole.UserRole)]

        if len(valid) == 0:
            self.editor_stack.setCurrentIndex(0)  # placeholder
        elif len(valid) == 1:
            data = valid[0].data(Qt.ItemDataRole.UserRole)
            if data.startswith("group:"):
                ed = self._group_editors.get(data[6:])
                if ed:
                    self.editor_stack.setCurrentWidget(ed)
            elif data.startswith("surface:"):
                ed = self._surface_editors.get(data[8:])
                if ed:
                    self.editor_stack.setCurrentWidget(ed)
        else:
            # Multi-select: collect surface names (skip groups from batch)
            surface_names = []
            for item in valid:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data.startswith("surface:"):
                    surface_names.append(data[8:])
            if surface_names:
                self._batch_editor.set_selected(surface_names)
                self.editor_stack.setCurrentWidget(self._batch_editor)
            elif len(valid) == 1:
                # Only one group selected alongside separators
                data = valid[0].data(Qt.ItemDataRole.UserRole)
                if data.startswith("group:"):
                    ed = self._group_editors.get(data[6:])
                    if ed:
                        self.editor_stack.setCurrentWidget(ed)
