"""
Porous media parameter database.

Stores named sets of Darcy-Forchheimer (or powerLaw) coefficients
in a JSON file at ~/.openfoam_gui_porous_db.json so they can be
reused across cases.

Each entry:
{
    "name": "catalyst_bed",
    "description": "Packed bed catalyst, dp=3mm, porosity=0.4",
    "porosityType": "DarcyForchheimer",
    "dx": "5e5", "dy": "5e5", "dz": "5e5",
    "fx": "100", "fy": "100", "fz": "100"
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".openfoam_gui_porous_db.json"

# Keys that define a porous media entry
POROUS_KEYS = [
    "porosityType",
    "dx", "dy", "dz",
    "fx", "fy", "fz",
]


class PorousDatabase:
    """Simple JSON-backed store for porous media parameter sets."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DB_PATH
        self._entries: list[dict] = []
        self.load()

    # ---- persistence ---- #

    def load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._entries = data
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    # ---- access ---- #

    def names(self) -> list[str]:
        return [e.get("name", "") for e in self._entries]

    def get(self, name: str) -> dict | None:
        for e in self._entries:
            if e.get("name") == name:
                return dict(e)
        return None

    def add(self, entry: dict):
        """Add or update an entry (matched by name)."""
        name = entry.get("name", "")
        if not name:
            return
        # Update existing
        for i, e in enumerate(self._entries):
            if e.get("name") == name:
                self._entries[i] = dict(entry)
                self.save()
                return
        # New
        self._entries.append(dict(entry))
        self.save()

    def remove(self, name: str):
        self._entries = [e for e in self._entries if e.get("name") != name]
        self.save()

    def all_entries(self) -> list[dict]:
        return [dict(e) for e in self._entries]

    @staticmethod
    def params_from_fvoption(params: dict) -> dict:
        """Extract porous-relevant keys from an fvOption params dict."""
        result = {}
        for key in POROUS_KEYS:
            if key in params:
                result[key] = str(params[key])
        return result

    @staticmethod
    def params_to_fvoption(entry: dict) -> dict:
        """Extract only the fvOption-compatible keys from a db entry."""
        result = {}
        for key in POROUS_KEYS:
            if key in entry:
                result[key] = entry[key]
        return result
