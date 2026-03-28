"""
OpenFOAM Case Setup GUI — Main Window

Architecture:
  CaseDatabase is the single source of truth for ALL state.
  All widgets read from and write to the database.
  Database signals trigger automatic GUI updates.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QPushButton, QFileDialog, QMessageBox, QStatusBar,
    QLabel, QToolBar, QTabWidget, QFrame, QComboBox, QInputDialog,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut, QColor

from case_db import CaseDatabase
from case_manager import CaseWriter
from case_reader import CaseReader
from of_version import OFVersion
from app_settings import AppSettings
from settings_dialog import SettingsDialog
import simplefoam
import rhosimplefoam
import pimplefoam
import simplereactingparcelfoam
import interfoam
import icofoam
import pisofoam
import buoyantsimplefoam
import buoyantpimplefoam
import rhopimplefoam
import potentialfoam
from dict_editor import DictEditor
from preview import PreviewWidget
from stl_manager import STLManager
from patch_editor import PatchBCEditor
from surface_editor import SurfaceEditor
from func_editor import FuncObjectEditor
from fvoptions_editor import FvOptionsEditor
from refregion_editor import RefRegionEditor
from locations_editor import LocationsInMeshEditor
from calculators import CalculatorsWidget
from case_validator import validate_case, ValidationDialog, validate_tree_markers, validate_step_status
from residual_plotter import ResidualPlotter
from workflow import WorkflowBar, CaseDashboard, WORKFLOW_STEPS
from presets import PresetDialog
from case_compare import ConfigDiffDialog, CaseCompareDialog
from custom_template import (CustomTemplate, load_custom_templates,
                              export_builtin_templates)
from template_editor import TemplateEditorDialog


# ------------------------------------------------------------------ #
#  Solver registry
# ------------------------------------------------------------------ #

SOLVER_REGISTRY = [
    ("simpleFoam",          "Steady-state incompressible turbulent (SIMPLE)",     simplefoam),
    ("pimpleFoam",          "Transient incompressible turbulent (PIMPLE)",        pimplefoam),
    ("rhoSimpleFoam",       "Steady-state compressible turbulent",               rhosimplefoam),
    ("simpleReactingParcelFoam", "Steady compressible + Lagrangian parcels",     simplereactingparcelfoam),
    ("pisoFoam",            "Transient incompressible turbulent (PISO)",          pisofoam),
    ("icoFoam",             "Transient incompressible laminar",                   icofoam),
    ("buoyantSimpleFoam",   "Steady-state buoyant turbulent",                    buoyantsimplefoam),
    ("buoyantPimpleFoam",   "Transient buoyant turbulent",                       buoyantpimplefoam),
    ("rhoPimpleFoam",       "Transient compressible turbulent",                  rhopimplefoam),
    ("potentialFoam",       "Potential flow initialisation",                      potentialfoam),
    ("interFoam",           "Two-phase VOF",                                     interfoam),
]

# Export built-in solver templates as JSON (once, on first run)
_BUILTIN_MODULES = [tmpl for _, _, tmpl in SOLVER_REGISTRY if tmpl is not None]
export_builtin_templates(_BUILTIN_MODULES)

# Load user-defined templates from ~/.openfoam_gui_templates/
def _load_custom_into_registry():
    """Append custom JSON templates to SOLVER_REGISTRY."""
    builtin_names = {name for name, _, _ in SOLVER_REGISTRY}
    for ct in load_custom_templates():
        if ct.SOLVER_NAME not in builtin_names:
            SOLVER_REGISTRY.append(
                (ct.SOLVER_NAME, ct.SOLVER_DESCRIPTION + "  [custom]", ct))

_load_custom_into_registry()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1400, 850)

        # ---- Database: single source of truth ---- #
        self.db = CaseDatabase()
        self.db.template = simplefoam
        self.db.solver = simplefoam.SOLVER_NAME
        self.db._recompute_active_fields()

        # ---- Case writer (pure generator) ---- #
        self.writer = CaseWriter(self.db)

        # Current template reference
        self._tmpl = simplefoam

        # Widget tracking
        self._editors: dict[str, DictEditor] = {}
        self._tree_items: dict[str, QTreeWidgetItem] = {}
        self._mesh_tree_items: list[QTreeWidgetItem] = []
        self._turb_bc_items: dict[str, QTreeWidgetItem] = {}

        # ---- Appearance settings (loaded from ~/.openfoam_gui_settings.json) ---- #
        self.app_settings = AppSettings()

        self._build_ui()
        self._populate_tree()
        self._connect_db_signals()

        # Apply saved font settings to preview pane
        self._apply_font_settings()

        self.statusBar().showMessage("Ready — select a dictionary to edit")

    # ============================================================== #
    #  UI
    # ============================================================== #

    def _build_ui(self):
        self.setStyleSheet(self.app_settings.generate_stylesheet())
        self.setWindowTitle(f"OpenFOAM Case Setup — {self._tmpl.SOLVER_NAME}")

        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._toolbar_label = QLabel("  OpenFOAM Case Setup  ")
        self._toolbar_label.setStyleSheet(
            f"color: {self.app_settings.get('toolbar_text')}; font-size: 14px; font-weight: bold;")
        toolbar.addWidget(self._toolbar_label)
        toolbar.addSeparator()

        for text, slot, shortcut in [
            ("Save Config…", self._save_config, "Ctrl+S"),
            ("Load Config…", self._load_config, "Ctrl+O"),
        ]:
            act = QAction(text, self)
            act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(slot)
            toolbar.addAction(act)

        toolbar.addSeparator()
        act_export = QAction("Export Case…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._export_case)
        toolbar.addAction(act_export)

        act_load_case = QAction("Load Case…", self)
        act_load_case.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_load_case.triggered.connect(self._load_case)
        toolbar.addAction(act_load_case)

        toolbar.addSeparator()
        act_stl_viewer = QAction("STL Viewer", self)
        act_stl_viewer.triggered.connect(self._open_stl_viewer)
        toolbar.addAction(act_stl_viewer)

        toolbar.addSeparator()
        act_settings = QAction("⚙ Settings…", self)
        act_settings.triggered.connect(self._open_settings)
        toolbar.addAction(act_settings)

        act_tmpl_editor = QAction("📋 Template Editor…", self)
        act_tmpl_editor.triggered.connect(self._open_template_editor)
        toolbar.addAction(act_tmpl_editor)

        act_presets = QAction("🚀 Presets…", self)
        act_presets.triggered.connect(self._open_presets)
        toolbar.addAction(act_presets)

        act_diff = QAction("Diff…", self)
        act_diff.triggered.connect(self._open_diff)
        toolbar.addAction(act_diff)

        act_compare = QAction("Compare…", self)
        act_compare.triggered.connect(self._open_compare)
        toolbar.addAction(act_compare)

        toolbar.addSeparator()
        act_validate = QAction("✓ Validate", self)
        act_validate.setShortcut(QKeySequence("Ctrl+Shift+V"))
        act_validate.triggered.connect(self._validate_case)
        toolbar.addAction(act_validate)

        # Recent files dropdown
        toolbar.addSeparator()
        self._recent_combo = QComboBox()
        self._recent_combo.setMinimumWidth(200)
        self._recent_combo.setPlaceholderText("Recent files…")
        self._recent_combo.activated.connect(self._open_recent)
        toolbar.addWidget(self._recent_combo)
        self._load_recent_list()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Workflow bar
        self.workflow_bar = WorkflowBar()
        self.workflow_bar.step_clicked.connect(self._on_workflow_step)
        main_layout.addWidget(self.workflow_bar)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: solver selector + tree
        tree_frame = QWidget()
        tree_frame.setObjectName("treePanel")
        tree_layout = QVBoxLayout(tree_frame)
        tree_layout.setContentsMargins(4, 4, 4, 4)
        tree_layout.setSpacing(6)

        solver_label = QLabel("Application")
        solver_label.setObjectName("header")
        tree_layout.addWidget(solver_label)

        self.solver_combo = QComboBox()
        self.solver_combo.setObjectName("solverCombo")
        self._populate_solver_combo()
        tree_layout.addWidget(self.solver_combo)

        self.solver_desc = QLabel()
        self.solver_desc.setWordWrap(True)
        self.solver_desc.setStyleSheet("font-size: 11px; padding: 2px 4px 6px 4px;")
        self._update_solver_description()
        tree_layout.addWidget(self.solver_desc)

        # OpenFOAM version selector
        ver_row = QHBoxLayout()
        self.dist_combo = QComboBox()
        self.dist_combo.addItem("openfoam.org", OFVersion.ORG)
        self.dist_combo.addItem("openfoam.com", OFVersion.COM)
        self.dist_combo.currentIndexChanged.connect(self._on_dist_changed)
        ver_row.addWidget(self.dist_combo)

        self.ver_combo = QComboBox()
        self._populate_ver_combo()
        self.ver_combo.currentIndexChanged.connect(self._on_ver_changed)
        ver_row.addWidget(self.ver_combo)
        tree_layout.addLayout(ver_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        tree_layout.addWidget(sep)

        tree_header = QLabel("Case Structure")
        tree_header.setObjectName("header")
        tree_layout.addWidget(tree_header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        tree_layout.addWidget(self.tree)
        self.splitter.addWidget(tree_frame)

        # Centre: stacked editors
        editor_frame = QWidget()
        editor_frame.setObjectName("editorPanel")
        editor_layout = QVBoxLayout(editor_frame)
        editor_layout.setContentsMargins(4, 4, 4, 4)
        self.editor_header = QLabel("Dictionary Settings")
        self.editor_header.setObjectName("header")
        editor_layout.addWidget(self.editor_header)
        self.editor_stack = QStackedWidget()
        editor_layout.addWidget(self.editor_stack)
        self.splitter.addWidget(editor_frame)

        # Right: preview + STL + surfaces
        right_frame = QWidget()
        right_frame.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.right_tabs = QTabWidget()
        self.right_tabs.setUsesScrollButtons(True)
        self.right_tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.preview = PreviewWidget()
        self.right_tabs.addTab(self.preview, "Preview")
        self.right_tabs.setTabToolTip(0, "File Preview")

        self.stl_manager = STLManager(self.db)
        self.right_tabs.addTab(self.stl_manager, "STL")
        self.right_tabs.setTabToolTip(1, "STL Geometry")

        self.surface_editor = SurfaceEditor(self.db)
        self.right_tabs.addTab(self.surface_editor, "Surfaces")
        self.right_tabs.setTabToolTip(2, "Surface Refinement")

        self.refregion_editor = RefRegionEditor(self.db)
        self.right_tabs.addTab(self.refregion_editor, "Regions")
        self.right_tabs.setTabToolTip(3, "Refinement Regions")

        self.locations_editor = LocationsInMeshEditor(self.db)
        self.right_tabs.addTab(self.locations_editor, "Locations")
        self.right_tabs.setTabToolTip(4, "Locations In Mesh")

        self.func_editor = FuncObjectEditor(self.db)
        self.right_tabs.addTab(self.func_editor, "Functions")
        self.right_tabs.setTabToolTip(5, "Function Objects")

        self.fvoptions_editor = FvOptionsEditor(self.db)
        self.right_tabs.addTab(self.fvoptions_editor, "fvOptions")
        self.right_tabs.setTabToolTip(6, "fvOptions Source Terms")

        self.calculators = CalculatorsWidget()
        self.right_tabs.addTab(self.calculators, "Calculators")
        self.right_tabs.setTabToolTip(7, "CFD Calculators")

        self.residual_plotter = ResidualPlotter()
        self.right_tabs.addTab(self.residual_plotter, "Residuals")
        self.right_tabs.setTabToolTip(8, "Residual Plotter")

        right_layout.addWidget(self.right_tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_export = QPushButton("Export Case…")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.clicked.connect(self._export_case)
        btn_row.addWidget(self.btn_export)
        right_layout.addLayout(btn_row)

        self.splitter.addWidget(right_frame)
        self.splitter.setSizes([260, 500, 440])
        main_layout.addWidget(self.splitter)

    # ============================================================== #
    #  Solver combo
    # ============================================================== #

    def _populate_solver_combo(self):
        self.solver_combo.clear()
        model = self.solver_combo.model()
        for i, (name, desc, template) in enumerate(SOLVER_REGISTRY):
            if template:
                self.solver_combo.addItem(name)
            else:
                self.solver_combo.addItem(f"{name}  (coming soon)")
                model.item(self.solver_combo.count() - 1).setEnabled(False)
        idx = self.solver_combo.findText(self._tmpl.SOLVER_NAME)
        if idx >= 0:
            self.solver_combo.setCurrentIndex(idx)
        self.solver_combo.currentIndexChanged.connect(self._on_solver_changed)

    def _update_solver_description(self):
        idx = self.solver_combo.currentIndex()
        if 0 <= idx < len(SOLVER_REGISTRY):
            self.solver_desc.setText(SOLVER_REGISTRY[idx][1])

    def _on_solver_changed(self, index):
        if index < 0 or index >= len(SOLVER_REGISTRY):
            return
        name, desc, template = SOLVER_REGISTRY[index]
        if not template or template is self._tmpl:
            self._update_solver_description()
            return

        reply = QMessageBox.question(
            self, "Switch Solver",
            f"Switch to {name}?\nThis will reset all settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            idx = self.solver_combo.findText(self._tmpl.SOLVER_NAME)
            if idx >= 0:
                self.solver_combo.blockSignals(True)
                self.solver_combo.setCurrentIndex(idx)
                self.solver_combo.blockSignals(False)
            return

        self._tmpl = template
        self.db.template = template
        self.db.solver = template.SOLVER_NAME
        self.db.reset()
        self.db._recompute_active_fields()
        self._populate_tree()
        self._update_solver_description()
        self.setWindowTitle(f"OpenFOAM Case Setup — {name}")
        self.statusBar().showMessage(f"Switched to {name}")

    # ============================================================== #
    #  OpenFOAM version
    # ============================================================== #

    def _populate_ver_combo(self):
        self.ver_combo.blockSignals(True)
        self.ver_combo.clear()
        dist = self.dist_combo.currentData() or OFVersion.ORG
        for v in OFVersion.VERSIONS.get(dist, []):
            self.ver_combo.addItem(v, v)
        # Select current
        current = self.db.of_version.version
        idx = self.ver_combo.findData(current)
        if idx >= 0:
            self.ver_combo.setCurrentIndex(idx)
        self.ver_combo.blockSignals(False)

    def _on_dist_changed(self, _index):
        dist = self.dist_combo.currentData()
        if not dist:
            return
        self._populate_ver_combo()
        ver = self.ver_combo.currentData() or OFVersion.DEFAULT_VERSION.get(dist)
        self.db.of_version = OFVersion(dist, ver)
        self.statusBar().showMessage(f"OpenFOAM: {self.db.of_version.label}")

    def _on_ver_changed(self, _index):
        dist = self.dist_combo.currentData() or OFVersion.ORG
        ver = self.ver_combo.currentData()
        if ver:
            self.db.of_version = OFVersion(dist, ver)
            self.statusBar().showMessage(f"OpenFOAM: {self.db.of_version.label}")

    def _sync_version_combos(self):
        """Set version combos to match db.of_version (after load)."""
        v = self.db.of_version
        self.dist_combo.blockSignals(True)
        for i in range(self.dist_combo.count()):
            if self.dist_combo.itemData(i) == v.dist:
                self.dist_combo.setCurrentIndex(i)
                break
        self.dist_combo.blockSignals(False)
        self._populate_ver_combo()
        self.ver_combo.blockSignals(True)
        idx = self.ver_combo.findData(v.version)
        if idx >= 0:
            self.ver_combo.setCurrentIndex(idx)
        self.ver_combo.blockSignals(False)

    # ============================================================== #
    #  Tree
    # ============================================================== #

    def _populate_tree(self):
        self.tree.clear()
        self._editors.clear()
        self._tree_items.clear()
        self._mesh_tree_items.clear()
        self._turb_bc_items.clear()

        while self.editor_stack.count():
            w = self.editor_stack.widget(0)
            self.editor_stack.removeWidget(w)
            w.deleteLater()

        placeholder = CaseDashboard()
        placeholder.navigate_to.connect(self._on_workflow_step)
        self._dashboard = placeholder
        self.editor_stack.addWidget(placeholder)

        # Patch editor — pass correct initial active fields
        self.patch_editor = PatchBCEditor(self.db)
        self.editor_stack.addWidget(self.patch_editor)

        root = QTreeWidgetItem(self.tree, [f"{self._tmpl.SOLVER_NAME} Case"])
        root.setExpanded(True)

        system_node = QTreeWidgetItem(root, ["system/"])
        constant_node = QTreeWidgetItem(root, ["constant/"])
        bc_node = QTreeWidgetItem(root, ["0/  (boundary conditions)"])
        mesh_node = QTreeWidgetItem(root, ["snappy mesh (add STL to enable)"])

        for node in (root, system_node, constant_node, bc_node, mesh_node):
            node.setExpanded(True)

        self._mesh_node = mesh_node

        patch_item = QTreeWidgetItem(bc_node, ["Patch BC Editor"])
        patch_item.setData(0, Qt.ItemDataRole.UserRole, "__patch_editor__")
        self._tree_items["__patch_editor__"] = patch_item

        for dspec in self._tmpl.get_base_dicts():
            path = dspec["path"]
            parent_map = {"system": system_node, "constant": constant_node, "0": bc_node}
            parent = parent_map.get(path.split("/")[0], root)

            item = QTreeWidgetItem(parent, [dspec["label"]])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self._tree_items[path] = item

            editor = DictEditor(dspec, self.db)
            self.editor_stack.addWidget(editor)
            self._editors[path] = editor

            if path in ("0/k", "0/epsilon", "0/omega", "0/nut", "0/alphat"):
                self._turb_bc_items[path] = item

        # fvOptions preview entry under system/
        fvoptions_item = QTreeWidgetItem(system_node, ["fvOptions"])
        fvoptions_item.setData(0, Qt.ItemDataRole.UserRole, "system/fvOptions")
        self._tree_items["system/fvOptions"] = fvoptions_item

        for dspec in self._tmpl.get_mesh_dicts():
            path = dspec["path"]
            item = QTreeWidgetItem(mesh_node, [dspec["label"]])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setHidden(True)
            self._tree_items[path] = item
            self._mesh_tree_items.append(item)

            editor = DictEditor(dspec, self.db)
            self.editor_stack.addWidget(editor)
            self._editors[path] = editor

        mesh_node.setHidden(True)

        # Apply initial visibility
        self._on_turb_changed()
        self._on_stl_changed()

        # Add cell size calculation button to blockMeshDict editor
        self._inject_calc_button()

        # Initial validation markers + dashboard
        self._update_validation_markers()
        self._dashboard.update_from_db(self.db)

    # ============================================================== #
    #  Database signal connections
    # ============================================================== #

    def _connect_db_signals(self):
        self.tree.currentItemChanged.connect(self._on_tree_selection)
        self.db.stl_changed.connect(self._on_stl_changed)
        self.db.turbulence_changed.connect(self._on_turb_changed)
        self.db.any_changed.connect(self._on_any_changed)

        # Watch turbulenceProperties dict for RASModel changes
        self.db.dict_changed.connect(self._on_dict_changed_for_turb)
        # Watch blockMeshDict for cellSize changes
        self.db.dict_changed.connect(self._on_dict_changed_for_mesh)

    def _on_tree_selection(self, current, _previous):
        if current is None:
            self.editor_stack.setCurrentWidget(self._dashboard)
            self._dashboard.update_from_db(self.db)
            self.editor_header.setText("Case Overview")
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            # Clicked a folder node — show dashboard
            self.editor_stack.setCurrentWidget(self._dashboard)
            self._dashboard.update_from_db(self.db)
            self.editor_header.setText("Case Overview")
            return

        if path == "__patch_editor__":
            self.editor_stack.setCurrentWidget(self.patch_editor)
            field = getattr(self.patch_editor, 'last_edited_field', 'p')
            self.editor_header.setText(
                f"Boundary Conditions — Per-Patch Editor  "
                f"<span style='color:#1976D2;'>(previewing 0/{field})</span>"
            )
            self._update_preview_for_path(path)
            self.workflow_bar.set_active("bcs")
            return

        if path in self._editors:
            self.editor_stack.setCurrentWidget(self._editors[path])
            self.editor_header.setText(f"Dictionary Settings — {path}")
            self._update_preview_for_path(path)
            # Set active workflow step based on path
            step_map = {
                "system/controlDict": "run", "system/decomposeParDict": "run",
                "system/fvSchemes": "numerics", "system/fvSolution": "numerics",
                "system/blockMeshDict": "mesh", "system/snappyHexMeshDict": "mesh",
            }
            step = step_map.get(path)
            if step:
                self.workflow_bar.set_active(step)
            elif path.startswith("0/"):
                self.workflow_bar.set_active("bcs")
            elif path.startswith("constant/"):
                self.workflow_bar.set_active("solver")
            return

        # Preview-only items (no editor widget, just preview content)
        if path == "system/fvOptions":
            self.right_tabs.setCurrentWidget(self.fvoptions_editor)
            self.editor_header.setText("fvOptions — Source Terms")
            self.workflow_bar.set_active("numerics")

        self._update_preview_for_path(path)

    def _on_dict_changed_for_turb(self, dict_path: str):
        """Detect turbulence model changes from the turbulenceProperties editor."""
        if dict_path == "constant/turbulenceProperties":
            vals = self.db.get_dict("constant/turbulenceProperties")
            model = vals.get("RASModel", "kEpsilon")
            if model != self.db.turbulence_model:
                self.db.turbulence_model = model

    def _on_turb_changed(self):
        """Show/hide BC items based on turbulence model."""
        if not hasattr(self._tmpl, 'get_turbulence_fields'):
            return
        needed = self._tmpl.get_turbulence_fields(self.db.turbulence_model)
        field_to_path = {"k": "0/k", "epsilon": "0/epsilon", "omega": "0/omega",
                         "nut": "0/nut", "alphat": "0/alphat"}
        for field, path in field_to_path.items():
            item = self._turb_bc_items.get(path)
            if item:
                item.setHidden(field not in needed)

    def _on_stl_changed(self):
        has_stl = self.db.has_stl
        self._mesh_node.setHidden(not has_stl)
        for item in self._mesh_tree_items:
            item.setHidden(not has_stl)

        if has_stl:
            self._update_block_mesh_from_stl()
            surfaces = self.db.get_all_surface_names()
            self.statusBar().showMessage(
                f"{len(self.db.stl_entries)} STL file(s), {len(surfaces)} surface(s)")
        else:
            self.statusBar().showMessage("All STL files removed")

    def _on_any_changed(self):
        """Update preview for the currently selected tree item."""
        current = self.tree.currentItem()
        if current:
            path = current.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self._update_preview_for_path(path)
                # Update header if on patch editor to show current field
                if path == "__patch_editor__":
                    field = getattr(self.patch_editor, 'last_edited_field', 'p')
                    self.editor_header.setText(
                        f"Boundary Conditions — Per-Patch Editor  "
                        f"<span style='color:#1976D2;'>(previewing 0/{field})</span>"
                    )
            else:
                # On a folder/dashboard — refresh dashboard
                self._dashboard.update_from_db(self.db)
        else:
            self._dashboard.update_from_db(self.db)

        # Refresh inline validation markers
        self._update_validation_markers()

    # ============================================================== #
    #  Workflow navigation
    # ============================================================== #

    def _on_workflow_step(self, step_id: str):
        """Navigate to the relevant tree item / tab for a workflow step."""
        if step_id == "solver":
            # Focus on solver combo — deselect tree to show dashboard
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
            self.editor_stack.setCurrentWidget(self._dashboard)
            self._dashboard.update_from_db(self.db)
            self.editor_header.setText("Case Overview")
            self.solver_combo.setFocus()
            self.workflow_bar.set_active("solver")
            return

        if step_id == "export":
            self._validate_case()
            return

        # Find step definition
        step = next((s for s in WORKFLOW_STEPS if s["id"] == step_id), None)
        if not step:
            return

        self.workflow_bar.set_active(step_id)

        # Navigate to first tree path in the step
        paths = step.get("tree_paths", [])
        for path in paths:
            item = self._tree_items.get(path)
            if item and not item.isHidden():
                self.tree.setCurrentItem(item)
                break

        # Switch to relevant right-panel tab if specified
        tabs = step.get("tabs", [])
        if tabs:
            for i in range(self.right_tabs.count()):
                if self.right_tabs.tabText(i) in tabs:
                    self.right_tabs.setCurrentIndex(i)
                    break

    # ============================================================== #
    #  Inline validation markers
    # ============================================================== #

    _MARKER_ICONS = {
        "error":   "\u2716 ",
        "warning": "\u26A0 ",
    }

    def _update_validation_markers(self):
        """Refresh tree item icons and workflow bar from validation."""
        markers = validate_tree_markers(self.db)
        step_status = validate_step_status(self.db)

        # Update tree items: prepend/remove status icons from labels
        for path, item in self._tree_items.items():
            original = item.text(0)
            # Strip any existing marker prefix
            for prefix in self._MARKER_ICONS.values():
                if original.startswith(prefix):
                    original = original[len(prefix):]
                    break

            status = markers.get(path)
            if status in self._MARKER_ICONS:
                item.setText(0, self._MARKER_ICONS[status] + original)
                color = "#E53935" if status == "error" else "#F57C00"
                item.setForeground(0, QColor(color))
            else:
                item.setText(0, original)
                # Reset to theme color
                item.setData(0, Qt.ItemDataRole.ForegroundRole, None)

        # Update workflow bar
        self.workflow_bar.update_from_validation(step_status)

    def _update_preview_for_path(self, path: str):
        """Generate and display a preview for any dict path."""
        if path == "__patch_editor__":
            # Show the BC file for the field the user is currently editing
            field = getattr(self.patch_editor, 'last_edited_field', 'p')
            if field not in self.db.active_fields:
                field = self.db.active_fields[0] if self.db.active_fields else 'p'
            patch_bcs = self.db.get_all_patch_bcs_for_export()
            ic = self.writer._get_internal_field(field)
            content = self.writer._gen_bc(field, patch_bcs, ic)
            if content:
                self.preview.set_content(content)
            return

        # Try system/constant dict generator
        settings = self.db.get_dict(path)
        content = self.writer._generate_dict(path, settings)
        if content:
            self.preview.set_content(content)
            return

        # For BC paths (0/p, 0/U, etc.), generate from patch BCs
        if path.startswith("0/"):
            field = path[2:]  # "0/p" -> "p"
            patch_bcs = self.db.get_all_patch_bcs_for_export()
            ic = self.writer._get_internal_field(field)
            content = self.writer._gen_bc(field, patch_bcs, ic)
            if content:
                self.preview.set_content(content)

    def _update_block_mesh_from_stl(self):
        bbox = self.db.stl_bounding_box()
        if not bbox:
            return
        xmin_s, ymin_s, zmin_s, xmax_s, ymax_s, zmax_s = bbox
        margin_pct = float(self.db.get_dict("system/blockMeshDict").get("domainMargin", 50)) / 100.0

        dx = max(xmax_s - xmin_s, 1e-6)
        dy = max(ymax_s - ymin_s, 1e-6)
        dz = max(zmax_s - zmin_s, 1e-6)

        self.db.set_dict_values("system/blockMeshDict", {
            "xMin": round(xmin_s - dx * margin_pct, 6),
            "xMax": round(xmax_s + dx * margin_pct, 6),
            "yMin": round(ymin_s - dy * margin_pct, 6),
            "yMax": round(ymax_s + dy * margin_pct, 6),
            "zMin": round(zmin_s - dz * margin_pct, 6),
            "zMax": round(zmax_s + dz * margin_pct, 6),
        })

        self.db.set_dict_values("system/snappyHexMeshDict", {
            "locationX": round((xmin_s + xmax_s) / 2, 6),
            "locationY": round((ymin_s + ymax_s) / 2, 6),
            "locationZ": round((zmin_s + zmax_s) / 2, 6),
        })

        # Recalculate cell counts from new bounds and current cell size
        self._calc_cells_from_size()

    def _on_dict_changed_for_mesh(self, dict_path: str):
        """When cellSize, bounds, or margin changes in blockMeshDict, recalculate."""
        if dict_path != "system/blockMeshDict":
            return
        if getattr(self, '_updating_cells', False):
            return

        vals = self.db.get_dict("system/blockMeshDict")

        # Check if domainMargin changed → recompute bounds from STL
        new_margin = str(vals.get("domainMargin", "50"))
        old_margin = getattr(self, '_last_margin', None)
        if old_margin is not None and new_margin != old_margin and self.db.has_stl:
            self._last_margin = new_margin
            self._update_block_mesh_from_stl()  # this also calls _calc_cells
            return
        self._last_margin = new_margin

        # Check if cellSize or bounds changed → recompute cell counts
        recalc_keys = ("cellSize", "xMin", "xMax", "yMin", "yMax", "zMin", "zMax")
        new_fp = tuple(str(vals.get(k, "")) for k in recalc_keys)
        old_fp = getattr(self, '_last_mesh_fingerprint', None)
        if new_fp != old_fp:
            self._last_mesh_fingerprint = new_fp
            if old_fp is not None:  # skip first init
                self._calc_cells_from_size()

    def _calc_cells_from_size(self):
        """Compute nCellsX/Y/Z from domain bounds and cellSize."""
        vals = self.db.get_dict("system/blockMeshDict")
        cell_size = float(vals.get("cellSize", 0.008))
        if cell_size <= 0:
            return

        xmin = float(vals.get("xMin", -5))
        xmax = float(vals.get("xMax", 15))
        ymin = float(vals.get("yMin", -5))
        ymax = float(vals.get("yMax", 5))
        zmin = float(vals.get("zMin", -5))
        zmax = float(vals.get("zMax", 5))

        nx = max(1, math.ceil(abs(xmax - xmin) / cell_size))
        ny = max(1, math.ceil(abs(ymax - ymin) / cell_size))
        nz = max(1, math.ceil(abs(zmax - zmin) / cell_size))

        self._updating_cells = True
        self.db.set_dict_values("system/blockMeshDict", {
            "nCellsX": nx,
            "nCellsY": ny,
            "nCellsZ": nz,
        })
        self._updating_cells = False

    def _inject_calc_button(self):
        """Add a 'Calculate Cells' button to the blockMeshDict editor."""
        bm_editor = self._editors.get("system/blockMeshDict")
        if not bm_editor:
            return
        container = bm_editor.widget()
        if not container:
            return
        layout = container.layout()
        if not layout:
            return

        btn = QPushButton("Calculate Cell Count from Cell Size")
        btn.setToolTip("Recalculate nCellsX/Y/Z from the domain bounds and cell size")
        btn.clicked.connect(self._calc_cells_from_size)
        # Insert before the stretch at the end
        layout.insertWidget(layout.count() - 1, btn)

    # ============================================================== #
    #  Export / Save / Load — all read from database
    # ============================================================== #

    def _validate_case(self):
        """Run validation checks and show results."""
        issues = validate_case(self.db)
        dlg = ValidationDialog(issues, parent=self)
        dlg.exec()

    def _export_case(self):
        # Validate first
        issues = validate_case(self.db)
        errors = [i for i in issues if i["level"] == "error"]
        warnings = [i for i in issues if i["level"] == "warning"]

        if errors:
            dlg = ValidationDialog(issues, parent=self)
            dlg.exec()
            reply = QMessageBox.question(
                self, "Validation Errors",
                f"There are {len(errors)} error(s) and {len(warnings)} warning(s).\n"
                "Export anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        elif warnings:
            reply = QMessageBox.question(
                self, "Validation Warnings",
                f"There are {len(warnings)} warning(s).\n"
                "Continue with export?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        parent_dir = QFileDialog.getExistingDirectory(self, "Select Parent Directory")
        if not parent_dir:
            return

        case_name, ok = QInputDialog.getText(
            self, "Case Name", "Enter case name:",
            text=f"{self._tmpl.SOLVER_NAME}_case")
        if not ok or not case_name.strip():
            return

        case_dir = str(Path(parent_dir) / case_name.strip().replace(" ", "_"))
        try:
            self.writer.write_case(case_dir)
            n = len(self.db.stl_entries)
            s = len(self.db.get_all_surface_names())
            QMessageBox.information(self, "Export Complete",
                f"Case written to:\n{case_dir}\n\n"
                f"Solver: {self.db.solver}\n"
                f"STL files: {n}  ({s} surfaces)\n"
                f"Turbulence: {self.db.turbulence_model}\n"
                f"Scripts: Allrun, Allclean")
            self.statusBar().showMessage(f"Case exported to {case_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _save_config(self):
        default_name = f"{self.db.solver}_config.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", default_name, "JSON Files (*.json)")
        if not path:
            return
        with open(path, "w") as f:
            f.write(self.db.to_json())
        self._add_recent(path, "config")
        self.statusBar().showMessage(f"Config saved to {path}")

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                json_str = f.read()

            data = json.loads(json_str)
            saved_solver = data.get("solver", "simpleFoam")

            # Switch template if needed
            for i, (name, _desc, template) in enumerate(SOLVER_REGISTRY):
                if name == saved_solver and template:
                    self._tmpl = template
                    self.db.template = template
                    self.solver_combo.blockSignals(True)
                    self.solver_combo.setCurrentIndex(i)
                    self.solver_combo.blockSignals(False)
                    break

            self.db.from_json(json_str)
            self._populate_tree()
            self._on_stl_changed()
            self._on_turb_changed()
            self._update_solver_description()
            self._sync_version_combos()
            self.setWindowTitle(f"OpenFOAM Case Setup — {self.db.solver}")
            self._add_recent(path, "config")
            self.statusBar().showMessage(f"Config loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _open_stl_viewer(self):
        """Open the standalone STL viewer with currently loaded STL files."""
        try:
            from stl_viewer import STLViewer
            self._stl_viewer = STLViewer()
            if self.db.stl_entries:
                self._stl_viewer.load_from_db(self.db)
            self._stl_viewer.show()
        except ImportError as e:
            QMessageBox.warning(
                self, "Missing Dependencies",
                f"STL Viewer requires numpy.\n\n"
                f"Install with: pip install numpy\n\n{e}")

    def _apply_font_settings(self):
        """Apply font/colour settings to the preview pane (used at startup + on change)."""
        mono_family = self.app_settings.get("mono_font_family")
        mono_size = int(self.app_settings.get("mono_font_size"))
        mono = QFont(mono_family, mono_size)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(mono)

        if hasattr(self.preview, '_highlighter'):
            self.preview._highlighter.update_colours(self.app_settings)

    def _open_settings(self):
        """Open the appearance settings dialog."""
        dlg = SettingsDialog(self.app_settings, parent=self)
        dlg.settings_applied.connect(self._apply_settings)
        dlg.exec()

    def _apply_settings(self):
        """Re-apply the stylesheet after the user changed colours/fonts."""
        self.setStyleSheet(self.app_settings.generate_stylesheet())

        # Toolbar label colour
        self._toolbar_label.setStyleSheet(
            f"color: {self.app_settings.get('toolbar_text')}; "
            f"font-size: 14px; font-weight: bold;")

        # Preview pane font + syntax colours
        self._apply_font_settings()

        self.statusBar().showMessage("Settings applied")

    def _open_template_editor(self):
        """Open the template creator/editor dialog."""
        builtin_mods = [tmpl for _, _, tmpl in SOLVER_REGISTRY if tmpl is not None]
        dlg = TemplateEditorDialog(builtin_modules=builtin_mods, parent=self)
        dlg.template_saved.connect(self._reload_custom_templates)
        dlg.exec()

    def _open_presets(self):
        """Open the preset browser dialog."""
        dlg = PresetDialog(self.db, SOLVER_REGISTRY, parent=self)
        dlg.preset_applied.connect(self._on_preset_applied)
        dlg.exec()

    def _on_preset_applied(self):
        """Refresh the entire GUI after a preset is applied."""
        # Sync solver combo
        for i, (name, _desc, template) in enumerate(SOLVER_REGISTRY):
            if name == self.db.solver and template:
                self._tmpl = template
                self.solver_combo.blockSignals(True)
                self.solver_combo.setCurrentIndex(i)
                self.solver_combo.blockSignals(False)
                break
        self._populate_tree()
        self._update_solver_description()
        self._sync_version_combos()
        self.setWindowTitle(f"OpenFOAM Case Setup — {self.db.solver}")
        self.statusBar().showMessage(
            f"Preset applied — {self.db.solver} / {self.db.turbulence_model}")

    def _open_diff(self):
        """Open the config diff dialog."""
        dlg = ConfigDiffDialog(self.db, parent=self)
        dlg.exec()

    def _open_compare(self):
        """Open the case comparison dialog."""
        dlg = CaseCompareDialog(parent=self)
        dlg.exec()

    def _reload_custom_templates(self):
        """Reload custom templates into the registry and refresh the combo."""
        # Remove existing custom entries
        SOLVER_REGISTRY[:] = [(n, d, t) for n, d, t in SOLVER_REGISTRY
                              if not d.endswith("[custom]")]
        _load_custom_into_registry()
        # Refresh the combo — disconnect first to avoid double-connect
        self.solver_combo.blockSignals(True)
        try:
            self.solver_combo.currentIndexChanged.disconnect(self._on_solver_changed)
        except RuntimeError:
            pass
        current = self._tmpl.SOLVER_NAME
        self._populate_solver_combo()
        idx = self.solver_combo.findText(current)
        if idx >= 0:
            self.solver_combo.setCurrentIndex(idx)
        self.solver_combo.blockSignals(False)
        self.statusBar().showMessage("Custom templates reloaded")

    def _load_case(self):
        """Load an existing OpenFOAM case directory into the GUI."""
        case_dir = QFileDialog.getExistingDirectory(
            self, "Select OpenFOAM Case Directory")
        if not case_dir:
            return

        # Verify it looks like an OpenFOAM case
        case_path = Path(case_dir)
        if not (case_path / "system" / "controlDict").exists():
            QMessageBox.warning(
                self, "Not an OpenFOAM Case",
                f"No system/controlDict found in:\n{case_dir}\n\n"
                "Please select a valid OpenFOAM case directory.")
            return

        self._load_case_from_path(case_dir)

    # ---- Recent files ---- #

    RECENT_FILE = Path.home() / ".openfoam_gui_recent.json"
    MAX_RECENT = 10

    def _add_recent(self, path: str, kind: str = "config"):
        """Add a path to the recent files list."""
        recents = self._get_recents()
        entry = {"path": str(path), "kind": kind}
        # Remove duplicates
        recents = [r for r in recents if r.get("path") != str(path)]
        recents.insert(0, entry)
        recents = recents[:self.MAX_RECENT]
        try:
            with open(self.RECENT_FILE, "w") as f:
                json.dump(recents, f, indent=2)
        except OSError:
            pass
        self._load_recent_list()

    def _get_recents(self) -> list:
        if self.RECENT_FILE.exists():
            try:
                with open(self.RECENT_FILE) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _load_recent_list(self):
        """Populate the recent files combo from disk."""
        self._recent_combo.clear()
        recents = self._get_recents()
        if not recents:
            self._recent_combo.setPlaceholderText("No recent files")
            return
        self._recent_combo.setPlaceholderText("Recent files…")
        for entry in recents:
            p = entry.get("path", "")
            kind = entry.get("kind", "config")
            label = f"[{kind}] {Path(p).name}  —  {p}"
            self._recent_combo.addItem(label, p)

    def _open_recent(self, index):
        """Open a file from the recent files combo."""
        path = self._recent_combo.itemData(index)
        if not path:
            return
        recents = self._get_recents()
        entry = recents[index] if index < len(recents) else {}
        kind = entry.get("kind", "config")

        if not Path(path).exists():
            QMessageBox.warning(self, "Not Found",
                                f"Path no longer exists:\n{path}")
            return

        if kind == "case":
            self._load_case_from_path(path)
        else:
            try:
                with open(path) as f:
                    json_str = f.read()
                data = json.loads(json_str)
                saved_solver = data.get("solver", "simpleFoam")
                for i, (name, _desc, template) in enumerate(SOLVER_REGISTRY):
                    if name == saved_solver and template:
                        self._tmpl = template
                        self.db.template = template
                        self.solver_combo.blockSignals(True)
                        self.solver_combo.setCurrentIndex(i)
                        self.solver_combo.blockSignals(False)
                        break
                self.db.from_json(json_str)
                self._populate_tree()
                self._on_stl_changed()
                self._on_turb_changed()
                self._update_solver_description()
                self._sync_version_combos()
                self.setWindowTitle(
                    f"OpenFOAM Case Setup — {self.db.solver}")
                self._add_recent(path, "config")
                self.statusBar().showMessage(f"Config loaded from {path}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def _load_case_from_path(self, case_dir: str):
        """Load a case directory (called from recent files or _load_case)."""
        try:
            reader = CaseReader(self.db)
            status = reader.read_case(case_dir)

            loaded = status.get("loaded", [])
            warnings = status.get("warnings", [])
            errors = status.get("errors", [])

            # Sync GUI to loaded data
            for i, (name, _desc, template) in enumerate(SOLVER_REGISTRY):
                if name == self.db.solver and template:
                    self._tmpl = template
                    self.solver_combo.blockSignals(True)
                    self.solver_combo.setCurrentIndex(i)
                    self.solver_combo.blockSignals(False)
                    break

            self._populate_tree()
            self._on_stl_changed()
            self._on_turb_changed()
            self._update_solver_description()
            self._sync_version_combos()
            self.setWindowTitle(
                f"OpenFOAM Case Setup — {self.db.solver}")

            msg = f"Case loaded from:\n{case_dir}\n\n"
            msg += f"Loaded: {len(loaded)} items\n"
            if warnings:
                msg += f"\nWarnings ({len(warnings)}):\n"
                for w in warnings[:10]:
                    msg += f"  • {w}\n"
            if errors:
                msg += f"\nErrors ({len(errors)}):\n"
                for e in errors[:10]:
                    msg += f"  • {e}\n"

            if errors:
                QMessageBox.warning(self, "Case Loaded with Errors", msg)
            else:
                QMessageBox.information(self, "Case Loaded", msg)

            self.statusBar().showMessage(
                f"Case loaded: {self.db.solver} — "
                f"{len(loaded)} items, {len(warnings)} warnings")
            self._add_recent(case_dir, "case")

        except Exception as e:
            QMessageBox.critical(self, "Load Case Error", str(e))


# ================================================================== #
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
