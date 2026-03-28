"""
TemplateEditor — dialog for creating and editing custom solver templates.

Opens from the toolbar. Allows defining solver name, base fields,
turbulence models, and dictionary specifications. Saves as JSON to
~/.openfoam_gui_templates/.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QPushButton, QLabel, QTabWidget, QWidget, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QGroupBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QMessageBox, QFileDialog, QScrollArea, QFrame,
    QSplitter, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal

from custom_template import (
    CustomTemplate, CUSTOM_TEMPLATES_DIR, PRESET_TURBULENCE_MODELS,
    PRESET_FIELD_INFO,
)

# Standard fields the user can pick from
KNOWN_FIELDS = ["p", "p_rgh", "U", "T", "alpha.water",
                "k", "epsilon", "omega", "nut", "alphat"]

FIELD_TYPES = ["str", "int", "float", "combo"]

ICON_CHOICES = [
    "SP_FileIcon", "SP_ArrowDown", "SP_ArrowForward", "SP_MediaVolume",
    "SP_DriveNetIcon", "SP_BrowserReload", "SP_ComputerIcon",
    "SP_FileDialogDetailedView", "SP_FileDialogContentsView",
    "SP_DialogResetButton", "SP_DialogApplyButton",
]

# Standard dict paths
KNOWN_DICT_PATHS = [
    "system/controlDict", "system/fvSchemes", "system/fvSolution",
    "system/decomposeParDict", "system/setFieldsDict",
    "system/blockMeshDict", "system/snappyHexMeshDict",
    "system/surfaceFeatureExtractDict",
    "constant/transportProperties", "constant/turbulenceProperties",
    "constant/g", "constant/thermophysicalProperties",
    "constant/combustionProperties",
]


# ================================================================== #
#  Field spec editor (one row in a group)
# ================================================================== #

class FieldSpecRow(QWidget):
    """Editor for a single field spec: (label, key, default, type, options)."""
    removed = Signal(object)
    changed = Signal()

    def __init__(self, spec: list | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)

        self.label_edit = QLineEdit(spec[0] if spec else "Label")
        self.label_edit.setPlaceholderText("Label")
        self.label_edit.setMaximumWidth(180)
        self.label_edit.textChanged.connect(lambda: self.changed.emit())
        lay.addWidget(self.label_edit)

        self.key_edit = QLineEdit(spec[1] if spec else "key")
        self.key_edit.setPlaceholderText("key")
        self.key_edit.setMaximumWidth(140)
        self.key_edit.textChanged.connect(lambda: self.changed.emit())
        lay.addWidget(self.key_edit)

        self.default_edit = QLineEdit(str(spec[2]) if spec else "")
        self.default_edit.setPlaceholderText("default")
        self.default_edit.setMaximumWidth(120)
        self.default_edit.textChanged.connect(lambda: self.changed.emit())
        lay.addWidget(self.default_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(FIELD_TYPES)
        if spec and len(spec) > 3:
            idx = self.type_combo.findText(spec[3])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
        self.type_combo.setMaximumWidth(80)
        self.type_combo.currentTextChanged.connect(lambda: self.changed.emit())
        lay.addWidget(self.type_combo)

        self.options_edit = QLineEdit()
        self.options_edit.setPlaceholderText("options (comma-sep or min,max)")
        if spec and len(spec) > 4 and spec[4] is not None:
            if isinstance(spec[4], (list, tuple)):
                self.options_edit.setText(",".join(str(x) for x in spec[4]))
            else:
                self.options_edit.setText(str(spec[4]))
        self.options_edit.textChanged.connect(lambda: self.changed.emit())
        lay.addWidget(self.options_edit, 1)

        btn_del = QPushButton("✕")
        btn_del.setFixedWidth(28)
        btn_del.setStyleSheet("background: #E53935; padding: 2px;")
        btn_del.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(btn_del)

    def to_list(self) -> list:
        label = self.label_edit.text()
        key = self.key_edit.text()
        default_str = self.default_edit.text()
        ftype = self.type_combo.currentText()
        opts_str = self.options_edit.text().strip()

        # Parse default
        if ftype == "int":
            try:
                default = int(default_str)
            except ValueError:
                default = 0
        elif ftype == "float":
            try:
                default = float(default_str)
            except ValueError:
                default = 0.0
        else:
            default = default_str

        # Parse options
        options = None
        if opts_str:
            parts = [p.strip() for p in opts_str.split(",")]
            if ftype in ("int", "float") and len(parts) == 2:
                try:
                    options = [float(parts[0]), float(parts[1])]
                except ValueError:
                    options = parts
            else:
                options = parts

        return [label, key, default, ftype, options]


# ================================================================== #
#  Group editor (one group within a dict)
# ================================================================== #

class GroupEditor(QWidget):
    """Editor for a dict group: name + list of field specs."""
    changed = Signal()
    removed = Signal(object)

    def __init__(self, group_name: str = "", specs: list | None = None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)

        header = QHBoxLayout()
        header.addWidget(QLabel("Group name:"))
        self.name_edit = QLineEdit(group_name)
        self.name_edit.textChanged.connect(lambda: self.changed.emit())
        header.addWidget(self.name_edit, 1)

        btn_add_field = QPushButton("+ Field")
        btn_add_field.clicked.connect(self._add_field)
        header.addWidget(btn_add_field)

        btn_del_group = QPushButton("Remove Group")
        btn_del_group.setStyleSheet("background: #E53935;")
        btn_del_group.clicked.connect(lambda: self.removed.emit(self))
        header.addWidget(btn_del_group)

        lay.addLayout(header)

        self._fields_layout = QVBoxLayout()
        lay.addLayout(self._fields_layout)

        self._field_rows: list[FieldSpecRow] = []

        if specs:
            for s in specs:
                self._add_field(s)

    def _add_field(self, spec: list | None = None):
        row = FieldSpecRow(spec)
        row.removed.connect(self._remove_field)
        row.changed.connect(lambda: self.changed.emit())
        self._field_rows.append(row)
        self._fields_layout.addWidget(row)
        self.changed.emit()

    def _remove_field(self, row):
        if row in self._field_rows:
            self._field_rows.remove(row)
            self._fields_layout.removeWidget(row)
            row.deleteLater()
            self.changed.emit()

    def to_data(self) -> tuple[str, list]:
        name = self.name_edit.text().strip() or "Unnamed"
        specs = [r.to_list() for r in self._field_rows]
        return name, specs


# ================================================================== #
#  Dict spec editor (one dict like system/controlDict)
# ================================================================== #

class DictSpecEditor(QScrollArea):
    """Editor for a complete dict specification."""
    changed = Signal()

    def __init__(self, dict_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(8, 8, 8, 8)

        # Path
        path_row = QFormLayout()
        self.path_edit = QLineEdit(dict_data.get("path", "") if dict_data else "")
        path_row.addRow("Dict path:", self.path_edit)
        self.label_edit = QLineEdit(dict_data.get("label", "") if dict_data else "")
        path_row.addRow("Label:", self.label_edit)
        self.icon_combo = QComboBox()
        self.icon_combo.addItems(ICON_CHOICES)
        if dict_data and dict_data.get("icon"):
            idx = self.icon_combo.findText(dict_data["icon"])
            if idx >= 0:
                self.icon_combo.setCurrentIndex(idx)
        path_row.addRow("Icon:", self.icon_combo)
        self._layout.addLayout(path_row)

        # Add group button
        btn_add = QPushButton("+ Add Group")
        btn_add.clicked.connect(lambda: self._add_group())
        self._layout.addWidget(btn_add)

        self._groups_layout = QVBoxLayout()
        self._layout.addLayout(self._groups_layout)
        self._layout.addStretch()
        self.setWidget(container)

        self._group_editors: list[GroupEditor] = []

        # Load existing groups
        if dict_data and "groups" in dict_data:
            for gname, specs in dict_data["groups"].items():
                self._add_group(gname, specs)

    def _add_group(self, name: str = "", specs: list | None = None):
        ge = GroupEditor(name, specs)
        ge.changed.connect(lambda: self.changed.emit())
        ge.removed.connect(self._remove_group)
        self._group_editors.append(ge)
        self._groups_layout.addWidget(ge)
        self.changed.emit()

    def _remove_group(self, ge):
        if ge in self._group_editors:
            self._group_editors.remove(ge)
            self._groups_layout.removeWidget(ge)
            ge.deleteLater()
            self.changed.emit()

    def to_data(self) -> dict:
        result = {
            "path": self.path_edit.text().strip(),
            "label": self.label_edit.text().strip(),
            "icon": self.icon_combo.currentText(),
            "groups": {},
        }
        for ge in self._group_editors:
            name, specs = ge.to_data()
            result["groups"][name] = specs
        return result


# ================================================================== #
#  Main template editor dialog
# ================================================================== #

class TemplateEditorDialog(QDialog):
    """Dialog for creating/editing custom solver templates."""

    template_saved = Signal()

    def __init__(self, template: CustomTemplate | None = None,
                 builtin_modules: list | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Template Editor" if template else "Create New Template")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        self._builtin_modules = builtin_modules or []
        self._template = template

        self._build_ui()
        if template:
            self._load_template(template)

    def _build_ui(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._make_starting_tab(), "Starting Templates")
        tabs.addTab(self._make_general_tab(), "General")
        tabs.addTab(self._make_turb_tab(), "Turbulence Models")
        tabs.addTab(self._make_dicts_tab(), "Dictionaries")
        self._tabs = tabs
        root.addWidget(tabs)

        # Button row
        btn_row = QHBoxLayout()

        btn_import = QPushButton("Import JSON…")
        btn_import.setObjectName("secondary")
        btn_import.clicked.connect(self._import_json)
        btn_row.addWidget(btn_import)

        btn_row.addStretch()

        btn_save = QPushButton("Save Template")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

    # ---- Starting Templates tab ---- #

    def _make_starting_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        lay.addWidget(QLabel(
            "<b>Select a starting template to clone and customise.</b><br>"
            "<span style='color:#546E7A;'>These are the built-in solver "
            "templates exported as JSON. Pick one, modify it in the other "
            "tabs, then save with a new name.</span>"
        ))

        self._starting_list = QListWidget()
        self._starting_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection)
        lay.addWidget(self._starting_list)

        # Description label
        self._starting_desc = QLabel()
        self._starting_desc.setWordWrap(True)
        self._starting_desc.setStyleSheet(
            "color: #546E7A; font-size: 11px; padding: 4px;")
        lay.addWidget(self._starting_desc)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("Load Selected as Starting Point")
        btn_load.setMinimumHeight(36)
        btn_load.clicked.connect(self._load_starting_template)
        btn_row.addWidget(btn_load)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self._refresh_starting_list)
        btn_row.addWidget(btn_refresh)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._starting_list.currentRowChanged.connect(
            self._on_starting_selected)
        self._refresh_starting_list()

        return w

    def _refresh_starting_list(self):
        from custom_template import (get_builtin_template_names,
                                     load_builtin_template,
                                     BUILTIN_TEMPLATES_DIR)
        self._starting_list.clear()
        self._starting_templates = {}

        names = get_builtin_template_names()
        for name in names:
            ct = load_builtin_template(name)
            if ct:
                self._starting_templates[name] = ct
                self._starting_list.addItem(
                    f"{name}  —  {ct.SOLVER_DESCRIPTION}")

        if not names:
            self._starting_desc.setText(
                f"No built-in templates found in {BUILTIN_TEMPLATES_DIR}.\n"
                "They are generated automatically on first startup.")

    def _on_starting_selected(self, row):
        if row < 0:
            self._starting_desc.clear()
            return
        names = list(self._starting_templates.keys())
        if row < len(names):
            ct = self._starting_templates[names[row]]
            fields = ct.BASE_FIELDS
            turb_models = list(ct.TURBULENCE_MODELS.keys())
            n_dicts = len(ct.get_base_dicts())
            n_mesh = len(ct.get_mesh_dicts())
            self._starting_desc.setText(
                f"<b>{ct.SOLVER_NAME}</b>: {ct.SOLVER_DESCRIPTION}<br>"
                f"Base fields: {', '.join(fields)}<br>"
                f"Turbulence models: {', '.join(turb_models)}<br>"
                f"Dictionaries: {n_dicts} base + {n_mesh} mesh"
            )

    def _load_starting_template(self):
        row = self._starting_list.currentRow()
        names = list(self._starting_templates.keys())
        if row < 0 or row >= len(names):
            QMessageBox.information(self, "Select Template",
                                    "Please select a template first.")
            return
        ct = self._starting_templates[names[row]]
        self._load_template(ct)
        # Suggest a new name
        self.name_edit.setText(f"{ct.SOLVER_NAME}_custom")
        self._tabs.setCurrentIndex(1)  # Switch to General tab

    # ---- General tab ---- #

    def _make_general_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. myCustomFoam")
        form.addRow("Solver Name:", self.name_edit)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Short description of the solver")
        form.addRow("Description:", self.desc_edit)
        lay.addLayout(form)

        # Base fields
        grp = QGroupBox("Base Fields (always active, independent of turbulence model)")
        gl = QVBoxLayout(grp)
        self._field_checks: dict[str, QCheckBox] = {}
        for field in KNOWN_FIELDS:
            cb = QCheckBox(field)
            if field in ("p", "U"):
                cb.setChecked(True)
            self._field_checks[field] = cb
            gl.addWidget(cb)

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Custom field:"))
        self._custom_field_edit = QLineEdit()
        self._custom_field_edit.setPlaceholderText("e.g. s, C, phi")
        custom_row.addWidget(self._custom_field_edit, 1)
        btn_add_custom = QPushButton("Add")
        btn_add_custom.clicked.connect(self._add_custom_field)
        custom_row.addWidget(btn_add_custom)
        gl.addLayout(custom_row)

        lay.addWidget(grp)

        # Field info table
        grp2 = QGroupBox("Field Info (dimensions, class, default internal — auto-filled for known fields)")
        gl2 = QVBoxLayout(grp2)

        self._fi_table = QTableWidget()
        self._fi_table.setColumnCount(4)
        self._fi_table.setHorizontalHeaderLabels(["Field", "Dimensions", "Class", "Internal Field"])
        self._fi_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._fi_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._fi_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._fi_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._fi_table.setColumnWidth(0, 110)
        self._fi_table.setColumnWidth(2, 130)
        gl2.addWidget(self._fi_table)

        fi_btn_row = QHBoxLayout()
        btn_fi_add = QPushButton("+ Add Field")
        btn_fi_add.clicked.connect(self._fi_add_row)
        fi_btn_row.addWidget(btn_fi_add)
        btn_fi_remove = QPushButton("Remove Selected")
        btn_fi_remove.clicked.connect(self._fi_remove_selected)
        fi_btn_row.addWidget(btn_fi_remove)
        btn_fi_auto = QPushButton("Auto-fill Known Fields")
        btn_fi_auto.setObjectName("secondary")
        btn_fi_auto.clicked.connect(self._fi_auto_fill)
        fi_btn_row.addWidget(btn_fi_auto)
        fi_btn_row.addStretch()
        gl2.addLayout(fi_btn_row)
        lay.addWidget(grp2)

        lay.addStretch()
        return w

    def _fi_add_row(self, field="", dim="[0 0 0 0 0 0 0]",
                    cls_name="volScalarField", internal="uniform 0"):
        row = self._fi_table.rowCount()
        self._fi_table.setRowCount(row + 1)
        self._fi_table.setItem(row, 0, QTableWidgetItem(field))
        self._fi_table.setItem(row, 1, QTableWidgetItem(dim))

        cls_combo = QComboBox()
        cls_combo.addItems(["volScalarField", "volVectorField"])
        idx = cls_combo.findText(cls_name)
        if idx >= 0:
            cls_combo.setCurrentIndex(idx)
        self._fi_table.setCellWidget(row, 2, cls_combo)

        self._fi_table.setItem(row, 3, QTableWidgetItem(internal))

    def _fi_remove_selected(self):
        rows = sorted(set(idx.row() for idx in self._fi_table.selectedIndexes()),
                       reverse=True)
        for row in rows:
            self._fi_table.removeRow(row)

    def _fi_auto_fill(self):
        """Add missing known fields to the table."""
        existing = set()
        for row in range(self._fi_table.rowCount()):
            item = self._fi_table.item(row, 0)
            if item:
                existing.add(item.text())

        # Gather all fields from base + turb
        all_fields = set()
        for f, cb in self._field_checks.items():
            if cb.isChecked():
                all_fields.add(f)
        for row in range(self._turb_table.rowCount()):
            fields_item = self._turb_table.item(row, 1)
            if fields_item:
                for f in fields_item.text().split(","):
                    f = f.strip()
                    if f:
                        all_fields.add(f)

        for f in sorted(all_fields - existing):
            preset = PRESET_FIELD_INFO.get(f, {})
            self._fi_add_row(
                field=f,
                dim=preset.get("dim", "[0 0 0 0 0 0 0]"),
                cls_name=preset.get("class", "volScalarField"),
                internal=preset.get("internal", "uniform 0"),
            )

    def _fi_collect(self) -> dict:
        """Collect field_info from the table."""
        result = {}
        for row in range(self._fi_table.rowCount()):
            name_item = self._fi_table.item(row, 0)
            dim_item = self._fi_table.item(row, 1)
            cls_widget = self._fi_table.cellWidget(row, 2)
            internal_item = self._fi_table.item(row, 3)
            if not name_item or not name_item.text().strip():
                continue
            field = name_item.text().strip()
            result[field] = {
                "dim": dim_item.text().strip() if dim_item else "[0 0 0 0 0 0 0]",
                "class": cls_widget.currentText() if cls_widget else "volScalarField",
                "internal": internal_item.text().strip() if internal_item else "uniform 0",
            }
        return result

    def _fi_load(self, fi: dict):
        """Load field_info into the table."""
        self._fi_table.setRowCount(0)
        for field, info in fi.items():
            self._fi_add_row(
                field=field,
                dim=info.get("dim", "[0 0 0 0 0 0 0]"),
                cls_name=info.get("class", "volScalarField"),
                internal=info.get("internal", "uniform 0"),
            )

    def _add_custom_field(self):
        name = self._custom_field_edit.text().strip()
        if not name or name in self._field_checks:
            return
        cb = QCheckBox(name)
        cb.setChecked(True)
        self._field_checks[name] = cb
        # Insert before the custom field row
        grp_layout = list(self._field_checks.values())[0].parent().layout()
        grp_layout.insertWidget(grp_layout.count() - 1, cb)
        self._custom_field_edit.clear()

    # ---- Turbulence tab ---- #

    TURB_FIELDS = ["k", "epsilon", "omega", "nut", "alphat", "nuTilda", "R"]

    def _make_turb_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        lay.addWidget(QLabel(
            "<b>Turbulence Models</b><br>"
            "<span style='color:#546E7A;'>Define which fields each "
            "turbulence model requires. Tick the fields each model solves for.</span>"
        ))

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Load preset:"))
        for name in PRESET_TURBULENCE_MODELS:
            btn = QPushButton(name)
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _, n=name: self._load_turb_preset(n))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        lay.addLayout(preset_row)

        # Table: columns = Model Name, then one per turb field
        self._turb_table = QTableWidget()
        n_fields = len(self.TURB_FIELDS)
        self._turb_table.setColumnCount(2)
        self._turb_table.setHorizontalHeaderLabels(["Model Name", "Fields (comma-separated)"])
        self._turb_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._turb_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._turb_table.setColumnWidth(0, 180)
        lay.addWidget(self._turb_table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Model")
        btn_add.clicked.connect(self._turb_add_row)
        btn_row.addWidget(btn_add)
        btn_rem = QPushButton("Remove Selected")
        btn_rem.clicked.connect(self._turb_remove_selected)
        btn_row.addWidget(btn_rem)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        return w

    def _turb_add_row(self, model_name="", fields_str=""):
        row = self._turb_table.rowCount()
        self._turb_table.setRowCount(row + 1)
        self._turb_table.setItem(row, 0, QTableWidgetItem(model_name))
        self._turb_table.setItem(row, 1, QTableWidgetItem(fields_str))

    def _turb_remove_selected(self):
        rows = sorted(set(idx.row() for idx in self._turb_table.selectedIndexes()),
                       reverse=True)
        for row in rows:
            self._turb_table.removeRow(row)

    def _load_turb_preset(self, name: str):
        data = PRESET_TURBULENCE_MODELS.get(name, {})
        self._turb_table.setRowCount(0)
        for model, info in data.items():
            fields = info.get("fields", [])
            self._turb_add_row(model, ", ".join(fields))

    def _turb_collect(self) -> dict:
        """Collect turbulence_models from the table."""
        result = {}
        for row in range(self._turb_table.rowCount()):
            name_item = self._turb_table.item(row, 0)
            fields_item = self._turb_table.item(row, 1)
            if not name_item or not name_item.text().strip():
                continue
            model = name_item.text().strip()
            fields_str = fields_item.text().strip() if fields_item else ""
            fields = [f.strip() for f in fields_str.split(",") if f.strip()]
            result[model] = {"fields": fields}
        return result

    def _turb_load(self, turb: dict):
        """Load turbulence_models into the table."""
        self._turb_table.setRowCount(0)
        for model, info in turb.items():
            fields = info.get("fields", [])
            self._turb_add_row(model, ", ".join(fields))

    # ---- Dictionaries tab ---- #

    def _make_dicts_tab(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: dict list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(QLabel("<b>Dictionaries</b>"))

        self.dict_list = QListWidget()
        self.dict_list.currentRowChanged.connect(self._on_dict_selected)
        ll.addWidget(self.dict_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Dict")
        btn_add.clicked.connect(self._add_dict)
        btn_row.addWidget(btn_add)
        btn_rem = QPushButton("Remove")
        btn_rem.setStyleSheet("background: #E53935;")
        btn_rem.clicked.connect(self._remove_dict)
        btn_row.addWidget(btn_rem)
        ll.addLayout(btn_row)

        # Checkbox: is this a mesh dict?
        self._mesh_check = QCheckBox("Mesh dict (only shown when STL is loaded)")
        self._mesh_check.stateChanged.connect(self._on_mesh_check_changed)
        ll.addWidget(self._mesh_check)

        splitter.addWidget(left)

        # Right: dict editor
        self.dict_stack = QStackedWidget()
        placeholder = QLabel("<center><br>Select a dictionary<br>to edit its fields</center>")
        placeholder.setStyleSheet("color: #90A4AE;")
        self.dict_stack.addWidget(placeholder)
        splitter.addWidget(self.dict_stack)

        splitter.setSizes([220, 550])
        lay.addWidget(splitter)

        self._dict_editors: list[DictSpecEditor] = []
        self._dict_is_mesh: list[bool] = []

        return w

    def _add_dict(self, data: dict | None = None, is_mesh: bool = False):
        editor = DictSpecEditor(data)
        self._dict_editors.append(editor)
        self._dict_is_mesh.append(is_mesh)
        self.dict_stack.addWidget(editor)

        label = (data or {}).get("path", "new/dict")
        self.dict_list.addItem(label)
        self.dict_list.setCurrentRow(self.dict_list.count() - 1)

    def _remove_dict(self):
        row = self.dict_list.currentRow()
        if row < 0:
            return
        self.dict_list.takeItem(row)
        editor = self._dict_editors.pop(row)
        self._dict_is_mesh.pop(row)
        self.dict_stack.removeWidget(editor)
        editor.deleteLater()

    def _on_dict_selected(self, row):
        if 0 <= row < len(self._dict_editors):
            self.dict_stack.setCurrentWidget(self._dict_editors[row])
            self._mesh_check.blockSignals(True)
            self._mesh_check.setChecked(self._dict_is_mesh[row])
            self._mesh_check.blockSignals(False)

    def _on_mesh_check_changed(self, state):
        row = self.dict_list.currentRow()
        if 0 <= row < len(self._dict_is_mesh):
            self._dict_is_mesh[row] = bool(state)

    # ---- Clone / import ---- #

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Template", "", "JSON Files (*.json)")
        if path:
            try:
                ct = CustomTemplate.load(path)
                self._load_template(ct)
            except Exception as e:
                QMessageBox.warning(self, "Import Error", str(e))

    # ---- Load / save ---- #

    def _load_template(self, ct: CustomTemplate):
        self.name_edit.setText(ct.SOLVER_NAME)
        self.desc_edit.setText(ct.SOLVER_DESCRIPTION)

        # Base fields
        for cb in self._field_checks.values():
            cb.setChecked(False)
        for f in ct.BASE_FIELDS:
            if f in self._field_checks:
                self._field_checks[f].setChecked(True)
            else:
                # Add custom checkbox
                cb = QCheckBox(f)
                cb.setChecked(True)
                self._field_checks[f] = cb
                grp_layout = list(self._field_checks.values())[0].parent().layout()
                grp_layout.insertWidget(grp_layout.count() - 1, cb)

        # Field info
        fi = ct.FIELD_INFO or {}
        self._fi_load(fi)

        # Turbulence
        self._turb_load(ct.TURBULENCE_MODELS or {})

        # Dicts — clear existing
        while self.dict_list.count():
            self._remove_dict_at(0)

        data = ct.to_dict()
        for d in data.get("base_dicts", []):
            self._add_dict(d, is_mesh=False)
        for d in data.get("mesh_dicts", []):
            self._add_dict(d, is_mesh=True)

    def _remove_dict_at(self, row):
        self.dict_list.takeItem(row)
        editor = self._dict_editors.pop(row)
        self._dict_is_mesh.pop(row)
        self.dict_stack.removeWidget(editor)
        editor.deleteLater()

    def _collect(self) -> dict:
        """Collect all editor state into a dict."""
        base_fields = [f for f, cb in self._field_checks.items() if cb.isChecked()]

        turb = self._turb_collect()
        fi = self._fi_collect()

        # Auto-fill field info for known fields not already in table
        all_fields = set(base_fields)
        for model_info in turb.values():
            all_fields.update(model_info.get("fields", []))
        for f in all_fields:
            if f not in fi and f in PRESET_FIELD_INFO:
                fi[f] = dict(PRESET_FIELD_INFO[f])

        base_dicts = []
        mesh_dicts = []
        for i, editor in enumerate(self._dict_editors):
            d = editor.to_data()
            if self._dict_is_mesh[i]:
                mesh_dicts.append(d)
            else:
                base_dicts.append(d)

        return {
            "solver_name": self.name_edit.text().strip() or "customFoam",
            "solver_description": self.desc_edit.text().strip(),
            "base_fields": base_fields,
            "turbulence_models": turb,
            "field_info": fi,
            "base_dicts": base_dicts,
            "mesh_dicts": mesh_dicts,
        }

    def _save(self):
        data = self._collect()
        name = data["solver_name"]

        CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        path = CUSTOM_TEMPLATES_DIR / f"{name}.json"

        if path.exists():
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"Template '{name}' already exists.\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            ct = CustomTemplate(data)
            ct.save(path)
            QMessageBox.information(
                self, "Saved",
                f"Template saved to:\n{path}\n\n"
                f"Restart the application or re-open the template editor "
                f"to use '{name}' from the solver dropdown.")
            self.template_saved.emit()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
