"""
STL Manager — add / remove STL files through CaseDatabase.
Tree rebuilds automatically from db.stl_changed signal.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QFileDialog,
    QMessageBox, QGroupBox,
)
from PySide6.QtCore import Signal


class STLManager(QWidget):
    """Panel for managing STL geometry files. All state in CaseDatabase."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("STL Geometry Files")
        g_layout = QVBoxLayout(group)

        info = QLabel(
            "Import STL files to enable snappyHexMeshDict and "
            "surfaceFeatureExtractDict. The blockMeshDict domain bounds "
            "will be auto-fitted to the STL bounding box. "
            "Each solid in the STL becomes a separate patch."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #546E7A; font-size: 11px; padding: 2px;")
        g_layout.addWidget(info)

        self.stl_tree = QTreeWidget()
        self.stl_tree.setHeaderLabels(["Name", "Details"])
        self.stl_tree.setAlternatingRowColors(True)
        self.stl_tree.setColumnWidth(0, 200)
        g_layout.addWidget(self.stl_tree)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add STL…")
        self.btn_add.clicked.connect(self._add_stl)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._remove_stl)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        g_layout.addLayout(btn_row)

        layout.addWidget(group)

        # Observe db — rebuild tree when STL list changes
        self.db.stl_changed.connect(self._rebuild_tree)

    def _add_stl(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select STL file(s)", "", "STL Files (*.stl *.STL);;All Files (*)"
        )
        if not paths:
            return
        for p in paths:
            try:
                self.db.add_stl(p)
            except FileNotFoundError as e:
                QMessageBox.warning(self, "File Not Found", str(e))

    def _remove_stl(self):
        item = self.stl_tree.currentItem()
        if not item:
            return
        if item.parent():
            item = item.parent()

        stl_stem = item.text(0).replace(".stl", "")
        for i, entry in enumerate(self.db.stl_entries):
            if entry["stem"] == stl_stem:
                self.db.remove_stl(i)
                break

    def _rebuild_tree(self):
        self.stl_tree.clear()
        for entry in self.db.stl_entries:
            file_item = QTreeWidgetItem(self.stl_tree)
            file_item.setText(0, f"{entry['stem']}.stl")
            file_item.setText(1, entry["path"])
            file_item.setExpanded(True)
            for solid in entry.get("solids", []):
                child = QTreeWidgetItem(file_item)
                child.setText(0, solid)
                child.setText(1, "solid region" if solid != entry["stem"] else "single solid")
