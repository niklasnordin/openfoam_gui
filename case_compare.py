"""
Case comparison and config diff view.

ConfigDiffDialog: compare current settings against a saved config or case.
CaseCompareDialog: load two exported cases and diff their dictionaries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QSplitter, QComboBox, QWidget,
    QMessageBox, QGroupBox,
)
from PySide6.QtCore import Qt


# ================================================================== #
#  Diff engine
# ================================================================== #

def diff_dicts(a: dict, b: dict, path: str = "") -> list[dict]:
    """Compare two nested dicts and return a list of differences.

    Returns list of {"path": str, "key": str, "a": val, "b": val, "type": str}
    where type is "changed", "added", "removed".
    """
    diffs = []
    all_keys = sorted(set(list(a.keys()) + list(b.keys())))

    for key in all_keys:
        full_path = f"{path}/{key}" if path else key
        in_a = key in a
        in_b = key in b

        if in_a and in_b:
            va, vb = a[key], b[key]
            if isinstance(va, dict) and isinstance(vb, dict):
                diffs.extend(diff_dicts(va, vb, full_path))
            elif str(va) != str(vb):
                diffs.append({
                    "path": path, "key": key,
                    "a": va, "b": vb, "type": "changed",
                })
        elif in_a and not in_b:
            diffs.append({
                "path": path, "key": key,
                "a": a[key], "b": None, "type": "removed",
            })
        else:
            diffs.append({
                "path": path, "key": key,
                "a": None, "b": b[key], "type": "added",
            })

    return diffs


def diff_to_html(diffs: list[dict], label_a: str = "Current",
                 label_b: str = "Other") -> str:
    """Convert diff list to a colour-coded HTML table."""
    if not diffs:
        return ("<p style='font-size:14px; padding:20px;'>"
                "\u2713 No differences found — configurations are identical.</p>")

    lines = [
        "<table style='border-collapse:collapse; width:100%;'>",
        "<tr>"
        "<th style='padding:6px 10px; text-align:left; border-bottom:2px solid #90A4AE;'>Setting</th>"
        f"<th style='padding:6px 10px; text-align:left; border-bottom:2px solid #90A4AE;'>{label_a}</th>"
        f"<th style='padding:6px 10px; text-align:left; border-bottom:2px solid #90A4AE;'>{label_b}</th>"
        "<th style='padding:6px 10px; text-align:left; border-bottom:2px solid #90A4AE;'>Status</th>"
        "</tr>"
    ]

    colors = {
        "changed": "#FFF3E0",
        "added":   "#E8F5E9",
        "removed": "#FFEBEE",
    }
    icons = {
        "changed": "\u0394",
        "added":   "+",
        "removed": "\u2212",
    }

    current_path = ""
    for d in diffs:
        path = d["path"]
        if path != current_path:
            current_path = path
            lines.append(
                f"<tr><td colspan='4' style='padding:8px 10px 4px; "
                f"font-weight:bold; border-top:1px solid #CFD8DC;'>"
                f"{path or '(root)'}</td></tr>")

        bg = colors.get(d["type"], "#FFFFFF")
        icon = icons.get(d["type"], "")
        va = d["a"] if d["a"] is not None else "—"
        vb = d["b"] if d["b"] is not None else "—"

        lines.append(
            f"<tr style='background:{bg};'>"
            f"<td style='padding:4px 10px;'>{d['key']}</td>"
            f"<td style='padding:4px 10px;'>{va}</td>"
            f"<td style='padding:4px 10px;'>{vb}</td>"
            f"<td style='padding:4px 10px; text-align:center;'>"
            f"<b>{icon}</b> {d['type']}</td>"
            f"</tr>")

    lines.append("</table>")
    return "".join(lines)


def _flatten_config(data: dict) -> dict[str, dict]:
    """Flatten a config JSON into {dict_path: {key: value}} structure."""
    result = {}

    # Top-level keys
    for key in ["solver", "turbulence_model"]:
        if key in data:
            result.setdefault("_solver", {})[key] = data[key]

    # Dicts
    for dict_path, values in data.get("dicts", {}).items():
        result[dict_path] = dict(values)

    return result


def _read_case_dicts(case_path: Path) -> dict[str, dict]:
    """Read key dictionaries from an exported OpenFOAM case as flat dicts."""
    from case_reader import parse_foam_dict

    result = {}

    # controlDict
    cd_path = case_path / "system" / "controlDict"
    if cd_path.exists():
        try:
            d = parse_foam_dict(cd_path.read_text(errors='replace'))
            result["system/controlDict"] = d
        except Exception:
            pass

    # fvSchemes
    fvs_path = case_path / "system" / "fvSchemes"
    if fvs_path.exists():
        try:
            d = parse_foam_dict(fvs_path.read_text(errors='replace'))
            result["system/fvSchemes"] = d
        except Exception:
            pass

    # fvSolution
    fvsol_path = case_path / "system" / "fvSolution"
    if fvsol_path.exists():
        try:
            d = parse_foam_dict(fvsol_path.read_text(errors='replace'))
            result["system/fvSolution"] = d
        except Exception:
            pass

    # transportProperties
    tp_path = case_path / "constant" / "transportProperties"
    if tp_path.exists():
        try:
            d = parse_foam_dict(tp_path.read_text(errors='replace'))
            result["constant/transportProperties"] = d
        except Exception:
            pass

    # turbulenceProperties
    turb_path = case_path / "constant" / "turbulenceProperties"
    if turb_path.exists():
        try:
            d = parse_foam_dict(turb_path.read_text(errors='replace'))
            result["constant/turbulenceProperties"] = d
        except Exception:
            pass

    # thermophysicalProperties
    thermo_path = case_path / "constant" / "thermophysicalProperties"
    if thermo_path.exists():
        try:
            d = parse_foam_dict(thermo_path.read_text(errors='replace'))
            result["constant/thermophysicalProperties"] = d
        except Exception:
            pass

    # blockMeshDict
    bmd_path = case_path / "system" / "blockMeshDict"
    if bmd_path.exists():
        try:
            d = parse_foam_dict(bmd_path.read_text(errors='replace'))
            result["system/blockMeshDict"] = d
        except Exception:
            pass

    return result


# ================================================================== #
#  Config Diff Dialog — compare current vs saved config
# ================================================================== #

class ConfigDiffDialog(QDialog):
    """Compare current case settings against a saved config JSON."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Config Diff — Compare Settings")
        self.setMinimumSize(800, 500)
        self.resize(950, 600)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Compare current settings against a saved config or exported case.</b>"
        ))

        # Source selector
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Compare with:"))

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Saved config (.json)", "Exported case (directory)"])
        src_row.addWidget(self._mode_combo)

        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        src_row.addWidget(btn_browse)

        self._path_label = QLabel("No file selected")
        self._path_label.setStyleSheet("font-size: 11px; padding: 0 8px;")
        src_row.addWidget(self._path_label, 1)

        layout.addLayout(src_row)

        # Summary
        self._summary = QLabel()
        self._summary.setStyleSheet("font-size: 13px; font-weight: bold; padding: 8px;")
        layout.addWidget(self._summary)

        # Diff view
        self._diff_view = QTextEdit()
        self._diff_view.setReadOnly(True)
        layout.addWidget(self._diff_view)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _browse(self):
        if self._mode_combo.currentIndex() == 0:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Config File", "", "JSON Files (*.json)")
            if path:
                self._compare_config(path)
        else:
            path = QFileDialog.getExistingDirectory(
                self, "Select OpenFOAM Case Directory")
            if path:
                self._compare_case(path)

    def _compare_config(self, config_path: str):
        self._path_label.setText(config_path)
        try:
            with open(config_path) as f:
                other_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))
            return

        current_data = json.loads(self.db.to_json())
        current_flat = _flatten_config(current_data)
        other_flat = _flatten_config(other_data)

        all_diffs = []
        all_paths = sorted(set(list(current_flat.keys()) + list(other_flat.keys())))
        for dp in all_paths:
            a = current_flat.get(dp, {})
            b = other_flat.get(dp, {})
            all_diffs.extend(diff_dicts(a, b, dp))

        n = len(all_diffs)
        self._summary.setText(
            f"{n} difference{'s' if n != 1 else ''} found "
            f"between current settings and {Path(config_path).name}")
        self._diff_view.setHtml(
            diff_to_html(all_diffs, "Current", Path(config_path).stem))

    def _compare_case(self, case_dir: str):
        self._path_label.setText(case_dir)
        case_path = Path(case_dir)
        if not (case_path / "system" / "controlDict").exists():
            QMessageBox.warning(self, "Not a Case",
                                "No system/controlDict found.")
            return

        other_dicts = _read_case_dicts(case_path)

        current_data = json.loads(self.db.to_json())
        current_flat = _flatten_config(current_data)

        all_diffs = []
        all_paths = sorted(set(list(current_flat.keys()) + list(other_dicts.keys())))
        for dp in all_paths:
            if dp == "_solver":
                continue  # skip solver meta
            a = current_flat.get(dp, {})
            b = other_dicts.get(dp, {})
            all_diffs.extend(diff_dicts(a, b, dp))

        n = len(all_diffs)
        self._summary.setText(
            f"{n} difference{'s' if n != 1 else ''} found "
            f"between current settings and {case_path.name}")
        self._diff_view.setHtml(
            diff_to_html(all_diffs, "Current", case_path.name))


# ================================================================== #
#  Case Compare Dialog — diff two exported cases
# ================================================================== #

class CaseCompareDialog(QDialog):
    """Load two exported cases and diff their dictionaries side by side."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Case Comparison — Side by Side Diff")
        self.setMinimumSize(850, 550)
        self.resize(1000, 650)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Compare two exported OpenFOAM cases.</b><br>"
            "<span style='font-size:11px;'>"
            "Select two case directories to see what changed between them.</span>"
        ))

        # Case selectors
        sel_row = QHBoxLayout()

        # Case A
        a_grp = QGroupBox("Case A")
        a_lay = QHBoxLayout(a_grp)
        self._a_label = QLabel("Not selected")
        self._a_label.setStyleSheet("font-size: 11px;")
        a_lay.addWidget(self._a_label, 1)
        btn_a = QPushButton("Browse…")
        btn_a.clicked.connect(lambda: self._browse("a"))
        a_lay.addWidget(btn_a)
        sel_row.addWidget(a_grp)

        # Case B
        b_grp = QGroupBox("Case B")
        b_lay = QHBoxLayout(b_grp)
        self._b_label = QLabel("Not selected")
        self._b_label.setStyleSheet("font-size: 11px;")
        b_lay.addWidget(self._b_label, 1)
        btn_b = QPushButton("Browse…")
        btn_b.clicked.connect(lambda: self._browse("b"))
        b_lay.addWidget(btn_b)
        sel_row.addWidget(b_grp)

        layout.addLayout(sel_row)

        # Compare button
        btn_compare_row = QHBoxLayout()
        btn_compare = QPushButton("Compare")
        btn_compare.setMinimumHeight(36)
        btn_compare.clicked.connect(self._compare)
        btn_compare_row.addWidget(btn_compare)
        btn_compare_row.addStretch()
        layout.addLayout(btn_compare_row)

        # Summary
        self._summary = QLabel()
        self._summary.setStyleSheet("font-size: 13px; font-weight: bold; padding: 8px;")
        layout.addWidget(self._summary)

        # Diff view
        self._diff_view = QTextEdit()
        self._diff_view.setReadOnly(True)
        layout.addWidget(self._diff_view)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._path_a: str | None = None
        self._path_b: str | None = None

    def _browse(self, which: str):
        path = QFileDialog.getExistingDirectory(
            self, f"Select Case {which.upper()} Directory")
        if not path:
            return
        if not (Path(path) / "system" / "controlDict").exists():
            QMessageBox.warning(self, "Not a Case",
                                "No system/controlDict found.")
            return
        if which == "a":
            self._path_a = path
            self._a_label.setText(path)
        else:
            self._path_b = path
            self._b_label.setText(path)

    def _compare(self):
        if not self._path_a or not self._path_b:
            QMessageBox.information(self, "Select Cases",
                                    "Please select both Case A and Case B.")
            return

        dicts_a = _read_case_dicts(Path(self._path_a))
        dicts_b = _read_case_dicts(Path(self._path_b))

        all_diffs = []
        all_paths = sorted(set(list(dicts_a.keys()) + list(dicts_b.keys())))
        for dp in all_paths:
            a = dicts_a.get(dp, {})
            b = dicts_b.get(dp, {})
            all_diffs.extend(diff_dicts(a, b, dp))

        n = len(all_diffs)
        name_a = Path(self._path_a).name
        name_b = Path(self._path_b).name
        self._summary.setText(
            f"{n} difference{'s' if n != 1 else ''} between "
            f"{name_a} and {name_b}")
        self._diff_view.setHtml(diff_to_html(all_diffs, name_a, name_b))
