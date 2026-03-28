"""
LocationsInMeshEditor — table editor for snappyHexMesh locationsInMesh.

Supports manual editing in a table and import from CSV / text files.
All state lives in CaseDatabase.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QGroupBox, QAbstractItemView,
)
from PySide6.QtCore import Qt


class LocationsInMeshEditor(QWidget):
    """Editable table for multiple mesh location points."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        header = QLabel(
            "<b>Locations In Mesh</b>"
            "&nbsp;&nbsp;<span style=' font-size:10px;'>"
            "Points inside the mesh domain (one required, more for multi-region)</span>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # ---- Table ---- #
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name (optional)", "X", "Y", "Z"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, 120)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.table)

        # ---- Buttons ---- #
        btn_row = QHBoxLayout()

        btn_add = QPushButton("Add Row")
        btn_add.clicked.connect(self._add_row)
        btn_row.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_remove)

        btn_row.addStretch()

        btn_import = QPushButton("Import from File…")
        btn_import.setToolTip(
            "Import locations from a CSV or text file.\n"
            "Supported formats:\n"
            "  • CSV:  name,x,y,z  or  x,y,z\n"
            "  • Text: name x y z  or  x y z  (space/tab separated)\n"
            "  • Lines starting with # are skipped."
        )
        btn_import.clicked.connect(self._import_from_file)
        btn_row.addWidget(btn_import)

        layout.addLayout(btn_row)

        # Initial load
        self._load_from_db()

        # Observe db
        self.db.locations_changed.connect(self._load_from_db)

    # ================================================================ #
    #  Table ↔ DB sync
    # ================================================================ #

    def _load_from_db(self):
        """Populate table from database."""
        self._updating = True
        locs = self.db.locations_in_mesh

        self.table.setRowCount(len(locs))
        for row, loc in enumerate(locs):
            name_item = QTableWidgetItem(loc.get("name", ""))
            x_item = QTableWidgetItem(str(loc.get("x", 0.0)))
            y_item = QTableWidgetItem(str(loc.get("y", 0.0)))
            z_item = QTableWidgetItem(str(loc.get("z", 0.0)))

            x_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            y_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            z_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, x_item)
            self.table.setItem(row, 2, y_item)
            self.table.setItem(row, 3, z_item)

        self._updating = False

    def _on_cell_changed(self, row, col):
        """Write cell edit back to db."""
        if self._updating:
            return
        item = self.table.item(row, col)
        if not item:
            return

        text = item.text().strip()

        if col == 0:
            self.db.set_location_in_mesh(row, name=text)
        elif col == 1:
            try:
                self.db.set_location_in_mesh(row, x=float(text))
            except ValueError:
                pass
        elif col == 2:
            try:
                self.db.set_location_in_mesh(row, y=float(text))
            except ValueError:
                pass
        elif col == 3:
            try:
                self.db.set_location_in_mesh(row, z=float(text))
            except ValueError:
                pass

    # ================================================================ #
    #  Add / Remove
    # ================================================================ #

    def _add_row(self):
        self.db.add_location_in_mesh()
        self._load_from_db()

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()),
                       reverse=True)
        if not rows:
            return
        for row in rows:
            self.db.remove_location_in_mesh(row)
        self._load_from_db()

    # ================================================================ #
    #  File import
    # ================================================================ #

    def _import_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Locations",
            "", "All Supported (*.csv *.txt *.dat);;CSV (*.csv);;Text (*.txt *.dat);;All (*)")
        if not path:
            return

        try:
            locations = self._parse_locations_file(path)
        except Exception as e:
            QMessageBox.warning(self, "Import Error",
                                f"Failed to parse file:\n{e}")
            return

        if not locations:
            QMessageBox.information(self, "Import", "No valid locations found in file.")
            return

        # Ask whether to replace or append
        reply = QMessageBox.question(
            self, "Import Locations",
            f"Found {len(locations)} location(s).\n\n"
            "Replace existing locations or append?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            # Replace
            self.db.locations_in_mesh = locations
        else:
            # Append
            for loc in locations:
                self.db.add_location_in_mesh(
                    loc["x"], loc["y"], loc["z"], loc.get("name", ""))

        self._load_from_db()

    @staticmethod
    def _parse_locations_file(path: str) -> list[dict]:
        """Parse a CSV or whitespace-separated file into location dicts.

        Accepted formats per line (# comments and blank lines skipped):
            name, x, y, z          (CSV with name)
            x, y, z                (CSV without name)
            name  x  y  z          (space/tab with name)
            x  y  z                (space/tab without name)
        """
        result = []
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue

                # Try CSV first
                if "," in line:
                    parts = [p.strip() for p in line.split(",")]
                else:
                    parts = line.split()

                # Skip header-like lines
                if parts and parts[-1].lower() in ("z", "z-coord", "z_coord"):
                    continue

                name = ""
                coords = []

                # Try interpreting each part as a float from the right
                float_parts = []
                non_float_parts = []
                for p in parts:
                    try:
                        float_parts.append(float(p))
                    except ValueError:
                        non_float_parts.append(p)

                if len(float_parts) >= 3:
                    # Take last 3 floats as x, y, z
                    coords = float_parts[-3:]
                    # If there were non-float parts before, use as name
                    if non_float_parts:
                        name = " ".join(non_float_parts)
                    elif len(float_parts) > 3:
                        # Extra leading float — unusual, skip it
                        pass
                else:
                    continue  # not enough coordinates

                result.append({
                    "x": coords[0],
                    "y": coords[1],
                    "z": coords[2],
                    "name": name,
                })

        return result
