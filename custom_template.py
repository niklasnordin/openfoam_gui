"""
CustomTemplate — loads a JSON template and exposes the same interface
as a built-in Python template module (SOLVER_NAME, get_base_dicts(), etc.).

JSON structure:
{
    "solver_name": "myFoam",
    "solver_description": "My custom solver",
    "base_fields": ["p", "U"],
    "turbulence_models": {
        "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
        ...
    },
    "field_info": {
        "p": {"dim": "[0 2 -2 0 0 0 0]", "class": "volScalarField"}
    },
    "base_dicts": [ { "path": ..., "label": ..., "icon": ..., "groups": {...} } ],
    "mesh_dicts": [ ... ]
}

Each field spec inside groups is a list:
    [label, key, default, type, options]
where type is "str"/"int"/"float"/"combo" and options is null, a list, or [min, max].
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default templates directory
CUSTOM_TEMPLATES_DIR = Path.home() / ".openfoam_gui_templates"
BUILTIN_TEMPLATES_DIR = CUSTOM_TEMPLATES_DIR / "builtins"


# ------------------------------------------------------------------ #
#  Standard field/turbulence presets for quick setup
# ------------------------------------------------------------------ #

PRESET_TURBULENCE_MODELS = {
    "incompressible": {
        "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
        "kOmegaSST": {"fields": ["k", "omega", "nut"]},
        "realizableKE": {"fields": ["k", "epsilon", "nut"]},
        "SpalartAllmaras": {"fields": ["nut"]},
    },
    "compressible": {
        "kEpsilon": {"fields": ["k", "epsilon", "nut", "alphat"]},
        "kOmegaSST": {"fields": ["k", "omega", "nut", "alphat"]},
        "realizableKE": {"fields": ["k", "epsilon", "nut", "alphat"]},
        "SpalartAllmaras": {"fields": ["nut", "alphat"]},
    },
}

PRESET_FIELD_INFO = {
    "p":            {"dim": "[0 2 -2 0 0 0 0]",   "class": "volScalarField",  "internal": "uniform 0"},
    "p_rgh":        {"dim": "[1 -1 -2 0 0 0 0]",  "class": "volScalarField",  "internal": "uniform 0"},
    "U":            {"dim": "[0 1 -1 0 0 0 0]",   "class": "volVectorField",  "internal": "uniform (0 0 0)"},
    "T":            {"dim": "[0 0 0 1 0 0 0]",    "class": "volScalarField",  "internal": "uniform 300"},
    "alpha.water":  {"dim": "[0 0 0 0 0 0 0]",    "class": "volScalarField",  "internal": "uniform 0"},
    "k":            {"dim": "[0 2 -2 0 0 0 0]",   "class": "volScalarField",  "internal": "uniform 0.1"},
    "epsilon":      {"dim": "[0 2 -3 0 0 0 0]",   "class": "volScalarField",  "internal": "uniform 0.1"},
    "omega":        {"dim": "[0 0 -1 0 0 0 0]",   "class": "volScalarField",  "internal": "uniform 1.0"},
    "nut":          {"dim": "[0 2 -1 0 0 0 0]",   "class": "volScalarField",  "internal": "uniform 0"},
    "alphat":       {"dim": "[1 -1 -1 0 0 0 0]",  "class": "volScalarField",  "internal": "uniform 0"},
}


def _convert_field_spec(spec: list) -> tuple:
    """Convert a JSON list [label, key, default, type, options] to the
    tuple format used internally."""
    label = spec[0]
    key = spec[1]
    default = spec[2]
    ftype = spec[3] if len(spec) > 3 else "str"
    options = spec[4] if len(spec) > 4 else None
    # Convert [min, max] lists back to tuples
    if isinstance(options, list) and len(options) == 2:
        try:
            options = (float(options[0]), float(options[1]))
        except (ValueError, TypeError):
            pass
    return (label, key, default, ftype, options)


def _convert_dict_spec(d: dict) -> dict:
    """Convert a JSON dict spec (with list field specs) to internal format
    (with tuple field specs)."""
    result = dict(d)
    if "groups" in result:
        new_groups = {}
        for group_name, fields in result["groups"].items():
            new_groups[group_name] = [_convert_field_spec(f) for f in fields]
        result["groups"] = new_groups
    return result


class CustomTemplate:
    """A template loaded from JSON that quacks like a Python template module."""

    def __init__(self, data: dict):
        self.SOLVER_NAME = data.get("solver_name", "customFoam")
        self.SOLVER_DESCRIPTION = data.get("solver_description", "Custom solver")
        self.BASE_FIELDS = data.get("base_fields", ["p", "U"])
        self.TURBULENCE_MODELS = data.get("turbulence_models",
                                          PRESET_TURBULENCE_MODELS["incompressible"])
        self.FIELD_INFO = {}
        for field, info in data.get("field_info", {}).items():
            self.FIELD_INFO[field] = dict(info)

        # Fill in FIELD_INFO for any base/turb fields not explicitly defined
        all_fields = set(self.BASE_FIELDS)
        for model_info in self.TURBULENCE_MODELS.values():
            all_fields.update(model_info.get("fields", []))
        for f in all_fields:
            if f not in self.FIELD_INFO and f in PRESET_FIELD_INFO:
                self.FIELD_INFO[f] = dict(PRESET_FIELD_INFO[f])

        self._base_dicts = [_convert_dict_spec(d) for d in data.get("base_dicts", [])]
        self._mesh_dicts = [_convert_dict_spec(d) for d in data.get("mesh_dicts", [])]
        self._source_path: str | None = data.get("_source_path")

    def get_base_dicts(self) -> list:
        return list(self._base_dicts)

    def get_mesh_dicts(self) -> list:
        return list(self._mesh_dicts)

    def get_turbulence_fields(self, model_name: str) -> list[str]:
        info = self.TURBULENCE_MODELS.get(model_name)
        if not info:
            first = next(iter(self.TURBULENCE_MODELS.values()), {})
            return first.get("fields", [])
        return info["fields"]

    def to_dict(self) -> dict:
        """Serialize back to a JSON-safe dict."""
        def spec_to_list(spec: tuple) -> list:
            label, key, default, ftype, options = spec
            if isinstance(options, tuple):
                options = list(options)
            return [label, key, default, ftype, options]

        def dict_spec_to_json(d: dict) -> dict:
            result = dict(d)
            if "groups" in result:
                new_groups = {}
                for gname, fields in result["groups"].items():
                    new_groups[gname] = [spec_to_list(f) for f in fields]
                result["groups"] = new_groups
            return result

        return {
            "solver_name": self.SOLVER_NAME,
            "solver_description": self.SOLVER_DESCRIPTION,
            "base_fields": list(self.BASE_FIELDS),
            "turbulence_models": self.TURBULENCE_MODELS,
            "field_info": self.FIELD_INFO,
            "base_dicts": [dict_spec_to_json(d) for d in self._base_dicts],
            "mesh_dicts": [dict_spec_to_json(d) for d in self._mesh_dicts],
        }

    def save(self, path: str | Path):
        """Save template to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> CustomTemplate:
        """Load a template from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_source_path"] = str(path)
        return cls(data)

    @classmethod
    def from_builtin(cls, module) -> CustomTemplate:
        """Create a CustomTemplate from a built-in Python template module,
        for cloning/editing purposes."""
        def spec_to_list(spec):
            label, key, default, ftype = spec[0], spec[1], spec[2], spec[3] if len(spec) > 3 else "str"
            options = spec[4] if len(spec) > 4 else None
            if isinstance(options, tuple):
                options = list(options)
            return [label, key, default, ftype, options]

        def dict_spec_to_json(d):
            result = {"path": d["path"], "label": d["label"],
                      "icon": d.get("icon", "SP_FileIcon")}
            if "groups" in d:
                groups = {}
                for gname, fields in d["groups"].items():
                    groups[gname] = [spec_to_list(f) for f in fields]
                result["groups"] = groups
            if "info" in d:
                result["info"] = d["info"]
            return result

        data = {
            "solver_name": module.SOLVER_NAME,
            "solver_description": getattr(module, 'SOLVER_DESCRIPTION', ''),
            "base_fields": getattr(module, 'BASE_FIELDS', ["p", "U"]),
            "turbulence_models": getattr(module, 'TURBULENCE_MODELS', {}),
            "field_info": getattr(module, 'FIELD_INFO', {}),
            "base_dicts": [dict_spec_to_json(d) for d in module.get_base_dicts()],
            "mesh_dicts": [dict_spec_to_json(d) for d in module.get_mesh_dicts()],
        }
        return cls(data)


def load_custom_templates(directory: str | Path | None = None) -> list[CustomTemplate]:
    """Load all .json templates from the custom templates directory.
    Does NOT load from builtins/ — those are starting points, not active solvers."""
    d = Path(directory) if directory else CUSTOM_TEMPLATES_DIR
    if not d.exists():
        return []
    templates = []
    for f in sorted(d.glob("*.json")):
        try:
            templates.append(CustomTemplate.load(f))
        except Exception as e:
            print(f"Warning: failed to load template {f}: {e}")
    return templates


def export_builtin_templates(modules: list, force: bool = False):
    """Export all built-in solver modules as JSON templates to builtins/.

    Args:
        modules: list of Python template modules (simplefoam, pimplefoam, etc.)
        force:   if True, overwrite existing files; otherwise skip existing
    """
    BUILTIN_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    exported = 0
    for module in modules:
        if module is None:
            continue
        name = module.SOLVER_NAME
        path = BUILTIN_TEMPLATES_DIR / f"{name}.json"
        if path.exists() and not force:
            continue
        try:
            ct = CustomTemplate.from_builtin(module)
            ct.save(path)
            exported += 1
        except Exception as e:
            print(f"Warning: failed to export {name}: {e}")
    return exported


def get_builtin_template_names() -> list[str]:
    """Return names of available built-in templates on disk."""
    if not BUILTIN_TEMPLATES_DIR.exists():
        return []
    return sorted(f.stem for f in BUILTIN_TEMPLATES_DIR.glob("*.json"))


def load_builtin_template(name: str) -> CustomTemplate | None:
    """Load a specific built-in template by solver name."""
    path = BUILTIN_TEMPLATES_DIR / f"{name}.json"
    if path.exists():
        return CustomTemplate.load(path)
    return None
