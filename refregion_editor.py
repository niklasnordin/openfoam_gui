"""
RefRegionEditor — add, remove, and configure volume refinement regions
for snappyHexMesh. Supports box, sphere, and cylinder shapes.
All state lives in CaseDatabase.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QComboBox, QLineEdit, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QFrame, QSplitter, QSpinBox,
    QDoubleSpinBox, QMessageBox,
)
from PySide6.QtCore import Qt


# Shape definitions: key -> (description, parameters)
REGION_SHAPES = {
    "searchableBox": {
        "description": "Axis-aligned box defined by min/max corners",
        "fields": [
            ("Min X", "minX", -0.1, "float", (-1e6, 1e6)),
            ("Min Y", "minY", -0.1, "float", (-1e6, 1e6)),
            ("Min Z", "minZ", -0.1, "float", (-1e6, 1e6)),
            ("Max X", "maxX", 0.1, "float", (-1e6, 1e6)),
            ("Max Y", "maxY", 0.1, "float", (-1e6, 1e6)),
            ("Max Z", "maxZ", 0.1, "float", (-1e6, 1e6)),
        ],
    },
    "searchableSphere": {
        "description": "Sphere defined by centre and radius",
        "fields": [
            ("Centre X", "centreX", 0.0, "float", (-1e6, 1e6)),
            ("Centre Y", "centreY", 0.0, "float", (-1e6, 1e6)),
            ("Centre Z", "centreZ", 0.0, "float", (-1e6, 1e6)),
            ("Radius [m]", "radius", 0.1, "float", (0.0, 1e6)),
        ],
    },
    "searchableCylinder": {
        "description": "Cylinder defined by two end-points and radius",
        "fields": [
            ("Point 1 X", "point1X", 0.0, "float", (-1e6, 1e6)),
            ("Point 1 Y", "point1Y", 0.0, "float", (-1e6, 1e6)),
            ("Point 1 Z", "point1Z", 0.0, "float", (-1e6, 1e6)),
            ("Point 2 X", "point2X", 0.0, "float", (-1e6, 1e6)),
            ("Point 2 Y", "point2Y", 0.1, "float", (-1e6, 1e6)),
            ("Point 2 Z", "point2Z", 0.0, "float", (-1e6, 1e6)),
            ("Radius [m]", "radius", 0.05, "float", (0.0, 1e6)),
        ],
    },
}


class SingleRegionEditor(QScrollArea):
    """Editor for one refinement region."""

    def __init__(self, db, region_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.region_name = region_name
        self._param_widgets: dict[str, QWidget] = {}
        self._updating = False

        region_data = db.get_ref_region(region_name)
        shape = region_data.get("shape", "searchableBox")

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel(f"<b>{region_name}</b>")
        header.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(header)

        shape_info = REGION_SHAPES.get(shape, {})
        desc = QLabel(shape_info.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; padding: 2px;")
        layout.addWidget(desc)

        # Refinement settings
        ref_group = QGroupBox("Refinement")
        ref_form = QFormLayout(ref_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["inside", "outside", "distance"])
        mode = region_data.get("params", {}).get("mode", "inside")
        idx = self.mode_combo.findText(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.currentTextChanged.connect(
            lambda v: self._write("mode", v))
        ref_form.addRow("Mode:", self.mode_combo)
        self._param_widgets["mode"] = self.mode_combo

        self.level_spin = QSpinBox()
        self.level_spin.setRange(0, 10)
        self.level_spin.setValue(
            int(region_data.get("params", {}).get("level", 3)))
        self.level_spin.valueChanged.connect(
            lambda v: self._write("level", v))
        ref_form.addRow("Refinement Level:", self.level_spin)
        self._param_widgets["level"] = self.level_spin

        # Distance (only for mode=distance)
        self.dist_spin = QDoubleSpinBox()
        self.dist_spin.setDecimals(6)
        self.dist_spin.setRange(0, 1e6)
        self.dist_spin.setValue(
            float(region_data.get("params", {}).get("distance", 0.1)))
        self.dist_spin.valueChanged.connect(
            lambda v: self._write("distance", v))
        ref_form.addRow("Distance [m]:", self.dist_spin)
        self._param_widgets["distance"] = self.dist_spin

        layout.addWidget(ref_group)

        # Shape-specific geometry
        geom_group = QGroupBox(f"Geometry — {shape.replace('searchable', '')}")
        geom_form = QFormLayout(geom_group)

        params = region_data.get("params", {})
        for field_spec in shape_info.get("fields", []):
            label, key, default, ftype, options = field_spec
            val = params.get(key, default)

            w = QDoubleSpinBox()
            w.setDecimals(6)
            if options:
                w.setMinimum(options[0])
                w.setMaximum(options[1])
            w.setValue(float(val))
            w.valueChanged.connect(lambda v, k=key: self._write(k, v))
            geom_form.addRow(label + ":", w)
            self._param_widgets[key] = w

        layout.addWidget(geom_group)
        layout.addStretch()
        self.setWidget(container)

    def _write(self, key, value):
        if not self._updating:
            self.db.set_ref_region_param(self.region_name, key, value)


class RefRegionEditor(QWidget):
    """Master widget: refinement region list + add/remove + per-region settings."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._editors: dict[str, SingleRegionEditor] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        info = QLabel(
            "Add volume refinement regions to refine the mesh inside "
            "boxes, spheres, or cylinders. These appear in the "
            "snappyHexMeshDict geometry and refinementRegions blocks."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 11px; padding: 4px;")
        layout.addWidget(info)

        # Add controls
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Shape:"))
        self.shape_combo = QComboBox()
        for shape, info_d in REGION_SHAPES.items():
            nice = shape.replace("searchable", "")
            self.shape_combo.addItem(f"{nice}  —  {info_d['description']}", shape)
        add_row.addWidget(self.shape_combo, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Region name")
        add_row.addWidget(self.name_edit)

        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._add_region)
        add_row.addWidget(self.btn_add)
        layout.addLayout(add_row)

        # Main area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("<b>Refinement Regions</b>")
        lbl.setStyleSheet("padding: 4px;")
        left_layout.addWidget(lbl)

        self.region_list = QListWidget()
        self.region_list.currentRowChanged.connect(self._on_region_selected)
        left_layout.addWidget(self.region_list)

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setStyleSheet("background: #E53935;")
        self.btn_remove.clicked.connect(self._remove_region)
        left_layout.addWidget(self.btn_remove)

        splitter.addWidget(left)

        self.editor_stack = QStackedWidget()
        placeholder = QLabel(
            "<center><br><br>Add a refinement region or<br>"
            "select one to configure</center>"
        )
        self.editor_stack.addWidget(placeholder)
        splitter.addWidget(self.editor_stack)

        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

        # Observe db
        self.db.refregions_changed.connect(self._rebuild)
        self._rebuild()

    def _add_region(self):
        shape = self.shape_combo.currentData()
        name = self.name_edit.text().strip()

        if not name:
            existing = self.db.get_ref_region_names()
            nice = shape.replace("searchable", "").lower()
            base = nice
            n = 1
            name = base
            while name in existing:
                name = f"{base}{n}"
                n += 1

        if name in self.db.get_ref_region_names():
            QMessageBox.warning(self, "Duplicate Name",
                                f"Region '{name}' already exists.")
            return

        # Build defaults from shape fields
        shape_info = REGION_SHAPES.get(shape, {})
        defaults = {"mode": "inside", "level": 3, "distance": 0.1}
        for _label, key, default, _ftype, _opts in shape_info.get("fields", []):
            defaults[key] = default

        self.db.add_ref_region(name, shape, defaults)
        self.name_edit.clear()

    def _remove_region(self):
        item = self.region_list.currentItem()
        if not item:
            return
        name = item.text().split("  (")[0]
        self.db.remove_ref_region(name)

    def _rebuild(self):
        current_name = None
        if self.region_list.currentItem():
            current_name = self.region_list.currentItem().text().split("  (")[0]

        self.region_list.clear()
        for name, editor in self._editors.items():
            self.editor_stack.removeWidget(editor)
            editor.deleteLater()
        self._editors.clear()

        for name in self.db.get_ref_region_names():
            region_data = self.db.get_ref_region(name)
            shape = region_data.get("shape", "searchableBox")

            editor = SingleRegionEditor(self.db, name)
            self._editors[name] = editor
            self.editor_stack.addWidget(editor)

            nice = shape.replace("searchable", "")
            self.region_list.addItem(f"{name}  ({nice})")

        if current_name:
            for i in range(self.region_list.count()):
                if self.region_list.item(i).text().startswith(current_name):
                    self.region_list.setCurrentRow(i)
                    break

    def _on_region_selected(self, row):
        if row < 0:
            return
        name = self.region_list.item(row).text().split("  (")[0]
        editor = self._editors.get(name)
        if editor:
            self.editor_stack.setCurrentWidget(editor)
