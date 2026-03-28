"""
CaseDatabase — single source of truth for all OpenFOAM case data.

All state lives here. Widgets read from and write to this database.
Changes emit Qt signals so all observers update automatically.

Schema:
    solver          str
    turbulence_model str
    active_fields   list[str]
    dicts           {dict_path: {key: value}}
    stl_files       [{path, stem, solids}]
    surfaces        {name: {minLevel, maxLevel, nLayers, patchType, featureLevel}}
    patches         {name: {role, fields: {field: {type, params}}}}
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal
from of_version import OFVersion


class CaseDatabase(QObject):
    """Reactive data store for OpenFOAM case configuration."""

    # Signals — emitted when a section changes
    solver_changed = Signal()
    turbulence_changed = Signal()
    dict_changed = Signal(str)        # dict_path
    stl_changed = Signal()
    surface_changed = Signal(str)     # surface name (or "" for bulk)
    surfgroup_changed = Signal()      # surface groups changed
    patch_changed = Signal(str)       # patch name (or "" for bulk)
    func_changed = Signal()           # function objects added/removed/modified
    fvoptions_changed = Signal()      # fvOptions added/removed/modified
    refregions_changed = Signal()     # refinement regions changed
    locations_changed = Signal()      # locationsInMesh changed
    version_changed = Signal()        # OpenFOAM distribution/version changed
    any_changed = Signal()            # fires on ANY change (for preview)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._of_version = OFVersion()
        self._data = {
            "solver": "simpleFoam",
            "turbulence_model": "kEpsilon",
            "active_fields": ["p", "U", "k", "epsilon", "nut"],
            "dicts": {},
            "stl_files": [],
            "surfaces": {},
            "surface_groups": {},
            "patches": {},
            "function_objects": {},
            "fv_options": {},
            "refinement_regions": {},
            "locations_in_mesh": [{"x": 0.0, "y": 0.0, "z": 0.0, "name": ""}],
        }
        # Now that _data exists, create default patches
        self._data["patches"] = {
            "inlet": self._default_patch("inlet"),
            "outlet": self._default_patch("outlet"),
            "walls": self._default_patch("wall"),
        }
        self._template = None

    # ================================================================ #
    #  Template
    # ================================================================ #

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, tmpl):
        self._template = tmpl
        self._init_template_defaults()

    # ================================================================ #
    #  OpenFOAM version (org vs com)
    # ================================================================ #

    @property
    def of_version(self) -> OFVersion:
        return self._of_version

    @of_version.setter
    def of_version(self, v: OFVersion):
        self._of_version = v
        self.version_changed.emit()
        self.any_changed.emit()

    # ================================================================ #
    #  Solver
    # ================================================================ #

    @property
    def solver(self) -> str:
        return self._data["solver"]

    @solver.setter
    def solver(self, name: str):
        if self._data["solver"] != name:
            self._data["solver"] = name
            self.solver_changed.emit()
            self.any_changed.emit()

    # ================================================================ #
    #  Turbulence model
    # ================================================================ #

    @property
    def turbulence_model(self) -> str:
        return self._data["turbulence_model"]

    @turbulence_model.setter
    def turbulence_model(self, model: str):
        if self._data["turbulence_model"] != model:
            self._data["turbulence_model"] = model
            self._recompute_active_fields()
            self.turbulence_changed.emit()
            self.any_changed.emit()

    @property
    def active_fields(self) -> list:
        return list(self._data["active_fields"])

    def _recompute_active_fields(self):
        tmpl = self._template
        if tmpl and hasattr(tmpl, 'get_turbulence_fields'):
            base = getattr(tmpl, 'BASE_FIELDS', ["p", "U"])
            turb = tmpl.get_turbulence_fields(self.turbulence_model)
            self._data["active_fields"] = list(base) + turb

    # ================================================================ #
    #  Dictionary settings (system/*, constant/*, 0/*)
    # ================================================================ #

    def get_dict(self, dict_path: str) -> dict:
        """Get all settings for a dictionary."""
        return dict(self._data["dicts"].get(dict_path, {}))

    def set_dict_value(self, dict_path: str, key: str, value: Any):
        """Set a single value in a dictionary."""
        if dict_path not in self._data["dicts"]:
            self._data["dicts"][dict_path] = {}
        if self._data["dicts"][dict_path].get(key) != value:
            self._data["dicts"][dict_path][key] = value
            self.dict_changed.emit(dict_path)
            self.any_changed.emit()

    def set_dict_values(self, dict_path: str, values: dict):
        """Set multiple values in a dictionary at once."""
        if dict_path not in self._data["dicts"]:
            self._data["dicts"][dict_path] = {}
        changed = False
        for key, value in values.items():
            if self._data["dicts"][dict_path].get(key) != value:
                self._data["dicts"][dict_path][key] = value
                changed = True
        if changed:
            self.dict_changed.emit(dict_path)
            self.any_changed.emit()

    def init_dict_defaults(self, dict_path: str, defaults: dict):
        """Set defaults for a dictionary (only if keys don't exist yet)."""
        if dict_path not in self._data["dicts"]:
            self._data["dicts"][dict_path] = {}
        for key, value in defaults.items():
            if key not in self._data["dicts"][dict_path]:
                self._data["dicts"][dict_path][key] = value

    # ================================================================ #
    #  STL files
    # ================================================================ #

    @property
    def stl_entries(self) -> list:
        return list(self._data["stl_files"])

    @property
    def has_stl(self) -> bool:
        return len(self._data["stl_files"]) > 0

    def add_stl(self, stl_path: str) -> dict:
        """Add an STL file. Returns the entry dict. Parses solids automatically."""
        src = Path(stl_path)
        if not src.exists():
            raise FileNotFoundError(f"STL file not found: {stl_path}")

        solids = self._parse_stl_solids(src)
        entry = {"path": str(src), "stem": src.stem, "solids": solids}
        self._data["stl_files"].append(entry)

        # Create default surface settings for each solid
        for solid in solids:
            if solid not in self._data["surfaces"]:
                self._data["surfaces"][solid] = {
                    "minLevel": 2, "maxLevel": 4, "nLayers": 3,
                    "patchType": "wall", "featureLevel": 2, "group": "",
                }

        # Create default patch for each solid
        for solid in solids:
            if solid not in self._data["patches"]:
                self._data["patches"][solid] = self._default_patch("wall")

        self.stl_changed.emit()
        self.any_changed.emit()
        return entry

    def remove_stl(self, index: int):
        """Remove an STL file by index. Cleans up surfaces and patches."""
        if 0 <= index < len(self._data["stl_files"]):
            entry = self._data["stl_files"].pop(index)
            base_patches = {"inlet", "outlet", "walls"}
            for solid in entry.get("solids", []):
                self._data["surfaces"].pop(solid, None)
                if solid not in base_patches:
                    self._data["patches"].pop(solid, None)
            self.stl_changed.emit()
            self.any_changed.emit()

    def get_all_surface_names(self) -> list:
        """Flat list of all solid names across all STLs."""
        names = []
        for entry in self._data["stl_files"]:
            names.extend(entry.get("solids", [entry["stem"]]))
        return names

    def stl_bounding_box(self) -> Optional[tuple]:
        """Combined bounding box of all STL files, or None."""
        if not self._data["stl_files"]:
            return None
        xmin = ymin = zmin = float('inf')
        xmax = ymax = zmax = float('-inf')
        for entry in self._data["stl_files"]:
            try:
                bx = self._stl_file_bbox(Path(entry["path"]))
                xmin, ymin, zmin = min(xmin, bx[0]), min(ymin, bx[1]), min(zmin, bx[2])
                xmax, ymax, zmax = max(xmax, bx[3]), max(ymax, bx[4]), max(zmax, bx[5])
            except Exception:
                continue
        return (xmin, ymin, zmin, xmax, ymax, zmax) if xmin != float('inf') else None

    # ================================================================ #
    #  Surface refinement settings
    # ================================================================ #

    @property
    def surfaces(self) -> dict:
        return dict(self._data["surfaces"])

    def get_surface(self, name: str) -> dict:
        return dict(self._data["surfaces"].get(name, {}))

    def set_surface(self, name: str, settings: dict):
        self._data["surfaces"][name] = settings
        self.surface_changed.emit(name)
        self.any_changed.emit()

    def set_surface_value(self, name: str, key: str, value: Any):
        if name in self._data["surfaces"]:
            if self._data["surfaces"][name].get(key) != value:
                self._data["surfaces"][name][key] = value
                self.surface_changed.emit(name)
                self.any_changed.emit()

    # ================================================================ #
    #  Surface groups
    # ================================================================ #

    def get_surface_groups(self) -> dict:
        return dict(self._data.get("surface_groups", {}))

    def get_surface_group(self, name: str) -> dict:
        return dict(self._data.get("surface_groups", {}).get(name, {}))

    def add_surface_group(self, name: str, settings: dict = None):
        if "surface_groups" not in self._data:
            self._data["surface_groups"] = {}
        self._data["surface_groups"][name] = settings or {
            "minLevel": 2, "maxLevel": 4, "nLayers": 3,
            "patchType": "wall", "featureLevel": 2,
        }
        self.surfgroup_changed.emit()
        self.any_changed.emit()

    def remove_surface_group(self, name: str):
        groups = self._data.get("surface_groups", {})
        if name in groups:
            del groups[name]
            # Unassign surfaces from this group
            for sname, sdata in self._data.get("surfaces", {}).items():
                if sdata.get("group") == name:
                    sdata["group"] = ""
            self.surfgroup_changed.emit()
            self.surface_changed.emit("")
            self.any_changed.emit()

    def set_surface_group_value(self, group_name: str, key: str, value: Any):
        grp = self._data.get("surface_groups", {}).get(group_name)
        if grp is not None:
            grp[key] = value
            # Propagate to all surfaces assigned to this group
            for sname, sdata in self._data.get("surfaces", {}).items():
                if sdata.get("group") == group_name:
                    sdata[key] = value
            self.surfgroup_changed.emit()
            self.surface_changed.emit("")
            self.any_changed.emit()

    def assign_surface_to_group(self, surface_name: str, group_name: str):
        """Assign a surface to a group. Empty string = ungrouped."""
        surf = self._data.get("surfaces", {}).get(surface_name)
        if surf is None:
            return
        surf["group"] = group_name
        if group_name:
            grp = self._data.get("surface_groups", {}).get(group_name, {})
            for key in ("minLevel", "maxLevel", "nLayers", "patchType", "featureLevel"):
                if key in grp:
                    surf[key] = grp[key]
        self.surface_changed.emit(surface_name)
        self.surfgroup_changed.emit()
        self.any_changed.emit()

    def get_surfaces_in_group(self, group_name: str) -> list:
        return [sname for sname, sdata in self._data.get("surfaces", {}).items()
                if sdata.get("group") == group_name]

    # ================================================================ #
    #  Patch boundary conditions
    # ================================================================ #

    @property
    def patches(self) -> dict:
        return dict(self._data["patches"])

    def get_patch(self, name: str) -> dict:
        return dict(self._data["patches"].get(name, {}))

    def get_patch_names(self) -> list:
        return list(self._data["patches"].keys())

    def add_patch(self, name: str, role: str = "wall"):
        if name not in self._data["patches"]:
            self._data["patches"][name] = self._default_patch(role)
            self.patch_changed.emit(name)
            self.any_changed.emit()

    def remove_patch(self, name: str):
        if name in self._data["patches"]:
            del self._data["patches"][name]
            self.patch_changed.emit(name)
            self.any_changed.emit()

    def set_patch_role(self, name: str, role: str):
        from bc_types import DEFAULT_PATCH_BCS
        if name in self._data["patches"]:
            self._data["patches"][name]["role"] = role
            # Reset fields to role defaults
            defaults = DEFAULT_PATCH_BCS.get(role, DEFAULT_PATCH_BCS["wall"])
            fields = {}
            for field in self.active_fields:
                if field in defaults:
                    bc_type, params = defaults[field]
                    fields[field] = {"type": bc_type, "params": dict(params)}
            self._data["patches"][name]["fields"] = fields
            self.patch_changed.emit(name)
            self.any_changed.emit()

    def set_patch_bc(self, patch_name: str, field: str, bc_type: str, params: dict):
        if patch_name in self._data["patches"]:
            if "fields" not in self._data["patches"][patch_name]:
                self._data["patches"][patch_name]["fields"] = {}
            self._data["patches"][patch_name]["fields"][field] = {
                "type": bc_type, "params": dict(params),
            }
            self.patch_changed.emit(patch_name)
            self.any_changed.emit()

    def get_patch_bc(self, patch_name: str, field: str) -> tuple:
        """Returns (bc_type, params) or ('zeroGradient', {})."""
        patch = self._data["patches"].get(patch_name, {})
        bc = patch.get("fields", {}).get(field, {})
        return (bc.get("type", "zeroGradient"), dict(bc.get("params", {})))

    def get_all_patch_bcs_for_export(self) -> dict:
        """Return {patch_name: {field: (type, params)}} for the case generator."""
        result = {}
        for name, patch in self._data["patches"].items():
            result[name] = {}
            for field, bc in patch.get("fields", {}).items():
                result[name][field] = (bc["type"], dict(bc.get("params", {})))
        return result

    def sync_patches_to_active_fields(self):
        """Add/remove field entries in patches when active_fields change."""
        from bc_types import DEFAULT_PATCH_BCS
        active = set(self.active_fields)
        changed = False
        for name, patch in self._data["patches"].items():
            role = patch.get("role", "wall")
            defaults = DEFAULT_PATCH_BCS.get(role, DEFAULT_PATCH_BCS["wall"])
            fields = patch.get("fields", {})
            # Remove fields no longer active
            for f in list(fields.keys()):
                if f not in active:
                    del fields[f]
                    changed = True
            # Add missing active fields
            for f in active:
                if f not in fields:
                    if f in defaults:
                        bc_type, params = defaults[f]
                        fields[f] = {"type": bc_type, "params": dict(params)}
                    else:
                        fields[f] = {"type": "zeroGradient", "params": {}}
                    changed = True
            patch["fields"] = fields
        if changed:
            self.patch_changed.emit("")
            self.any_changed.emit()

    # ================================================================ #
    #  Function objects
    # ================================================================ #

    def get_func_object_names(self) -> list:
        return list(self._data.get("function_objects", {}).keys())

    def get_func_object(self, name: str) -> dict:
        return dict(self._data.get("function_objects", {}).get(name, {}))

    def add_func_object(self, name: str, fo_type: str, params: dict):
        if "function_objects" not in self._data:
            self._data["function_objects"] = {}
        self._data["function_objects"][name] = {
            "type": fo_type,
            "params": dict(params),
        }
        self.func_changed.emit()
        self.any_changed.emit()

    def remove_func_object(self, name: str):
        fos = self._data.get("function_objects", {})
        if name in fos:
            del fos[name]
            self.func_changed.emit()
            self.any_changed.emit()

    def set_func_object_param(self, name: str, key: str, value: Any):
        fo = self._data.get("function_objects", {}).get(name)
        if fo:
            fo["params"][key] = value
            self.func_changed.emit()
            self.any_changed.emit()

    @property
    def function_objects(self) -> dict:
        return dict(self._data.get("function_objects", {}))

    # ================================================================ #
    #  fvOptions
    # ================================================================ #

    def get_fv_option_names(self) -> list:
        return list(self._data.get("fv_options", {}).keys())

    def get_fv_option(self, name: str) -> dict:
        return dict(self._data.get("fv_options", {}).get(name, {}))

    def add_fv_option(self, name: str, opt_type: str, params: dict):
        if "fv_options" not in self._data:
            self._data["fv_options"] = {}
        self._data["fv_options"][name] = {
            "type": opt_type,
            "params": dict(params),
        }
        self.fvoptions_changed.emit()
        self.any_changed.emit()

    def remove_fv_option(self, name: str):
        opts = self._data.get("fv_options", {})
        if name in opts:
            del opts[name]
            self.fvoptions_changed.emit()
            self.any_changed.emit()

    def set_fv_option_param(self, name: str, key: str, value: Any):
        opt = self._data.get("fv_options", {}).get(name)
        if opt:
            opt["params"][key] = value
            self.fvoptions_changed.emit()
            self.any_changed.emit()

    @property
    def fv_options(self) -> dict:
        return dict(self._data.get("fv_options", {}))

    # ================================================================ #
    #  Refinement regions (for snappyHexMesh)
    # ================================================================ #

    def get_ref_region_names(self) -> list:
        return list(self._data.get("refinement_regions", {}).keys())

    def get_ref_region(self, name: str) -> dict:
        return dict(self._data.get("refinement_regions", {}).get(name, {}))

    def add_ref_region(self, name: str, shape: str, params: dict):
        if "refinement_regions" not in self._data:
            self._data["refinement_regions"] = {}
        self._data["refinement_regions"][name] = {
            "shape": shape,
            "params": dict(params),
        }
        self.refregions_changed.emit()
        self.any_changed.emit()

    def remove_ref_region(self, name: str):
        rr = self._data.get("refinement_regions", {})
        if name in rr:
            del rr[name]
            self.refregions_changed.emit()
            self.any_changed.emit()

    def set_ref_region_param(self, name: str, key: str, value: Any):
        rr = self._data.get("refinement_regions", {}).get(name)
        if rr:
            rr["params"][key] = value
            self.refregions_changed.emit()
            self.any_changed.emit()

    @property
    def refinement_regions(self) -> dict:
        return dict(self._data.get("refinement_regions", {}))

    # ================================================================ #
    #  Locations in mesh
    # ================================================================ #

    @property
    def locations_in_mesh(self) -> list[dict]:
        """Return list of location dicts: [{"x":…,"y":…,"z":…,"name":…}, …]"""
        locs = self._data.get("locations_in_mesh", [])
        if not locs:
            locs = [{"x": 0.0, "y": 0.0, "z": 0.0, "name": ""}]
            self._data["locations_in_mesh"] = locs
        return locs

    @locations_in_mesh.setter
    def locations_in_mesh(self, locs: list[dict]):
        self._data["locations_in_mesh"] = locs
        self.locations_changed.emit()
        self.any_changed.emit()

    def add_location_in_mesh(self, x=0.0, y=0.0, z=0.0, name=""):
        locs = self._data.setdefault("locations_in_mesh", [])
        locs.append({"x": float(x), "y": float(y), "z": float(z), "name": str(name)})
        self.locations_changed.emit()
        self.any_changed.emit()

    def remove_location_in_mesh(self, index: int):
        locs = self._data.get("locations_in_mesh", [])
        if 0 <= index < len(locs):
            locs.pop(index)
        if not locs:
            locs.append({"x": 0.0, "y": 0.0, "z": 0.0, "name": ""})
        self.locations_changed.emit()
        self.any_changed.emit()

    def set_location_in_mesh(self, index: int, x=None, y=None, z=None, name=None):
        locs = self._data.get("locations_in_mesh", [])
        if 0 <= index < len(locs):
            if x is not None:
                locs[index]["x"] = float(x)
            if y is not None:
                locs[index]["y"] = float(y)
            if z is not None:
                locs[index]["z"] = float(z)
            if name is not None:
                locs[index]["name"] = str(name)
            self.any_changed.emit()

    # ================================================================ #
    #  Serialization
    # ================================================================ #

    def to_json(self) -> str:
        data = dict(self._data)
        data["of_version"] = self._of_version.to_dict()
        return json.dumps(data, indent=2, default=str)

    def from_json(self, json_str: str):
        self._data = json.loads(json_str)
        # Restore version
        v = self._data.pop("of_version", None)
        if v:
            self._of_version = OFVersion.from_dict(v)
        if "function_objects" not in self._data:
            self._data["function_objects"] = {}
        if "fv_options" not in self._data:
            self._data["fv_options"] = {}
        if "refinement_regions" not in self._data:
            self._data["refinement_regions"] = {}
        if "surface_groups" not in self._data:
            self._data["surface_groups"] = {}
        if "locations_in_mesh" not in self._data:
            # Migrate old locationX/Y/Z format
            snappy = self._data.get("dicts", {}).get("system/snappyHexMeshDict", {})
            x = float(snappy.get("locationX", 0))
            y = float(snappy.get("locationY", 0))
            z = float(snappy.get("locationZ", 0))
            self._data["locations_in_mesh"] = [{"x": x, "y": y, "z": z, "name": ""}]
        for name, patch in self._data.get("patches", {}).items():
            for field, bc in patch.get("fields", {}).items():
                if isinstance(bc, list) and len(bc) == 2:
                    patch["fields"][field] = {"type": bc[0], "params": bc[1]}
        self.solver_changed.emit()
        self.turbulence_changed.emit()
        self.stl_changed.emit()
        self.patch_changed.emit("")
        self.surface_changed.emit("")
        self.func_changed.emit()
        self.fvoptions_changed.emit()
        self.refregions_changed.emit()
        self.locations_changed.emit()
        self.version_changed.emit()
        self.any_changed.emit()

    def reset(self):
        """Clear all data to defaults."""
        self._data = {
            "solver": self._data.get("solver", "simpleFoam"),
            "turbulence_model": "kEpsilon",
            "active_fields": ["p", "U", "k", "epsilon", "nut"],
            "dicts": {},
            "stl_files": [],
            "surfaces": {},
            "surface_groups": {},
            "patches": {},
            "function_objects": {},
            "fv_options": {},
            "refinement_regions": {},
            "locations_in_mesh": [{"x": 0.0, "y": 0.0, "z": 0.0, "name": ""}],
        }
        self._recompute_active_fields()
        self._data["patches"] = {
            "inlet": self._default_patch("inlet"),
            "outlet": self._default_patch("outlet"),
            "walls": self._default_patch("wall"),
        }
        self._init_template_defaults()

    def _init_template_defaults(self):
        """Load default values from all template dict specs into the database."""
        tmpl = self._template
        if not tmpl:
            return
        all_dicts = list(tmpl.get_base_dicts())
        if hasattr(tmpl, 'get_mesh_dicts'):
            all_dicts.extend(tmpl.get_mesh_dicts())
        for dspec in all_dicts:
            path = dspec["path"]
            defaults = {}
            for _group, fields in dspec.get("groups", {}).items():
                for field in fields:
                    defaults[field[1]] = field[2]
            self.init_dict_defaults(path, defaults)

    # ================================================================ #
    #  Internal helpers
    # ================================================================ #

    def _default_patch(self, role: str) -> dict:
        from bc_types import DEFAULT_PATCH_BCS
        defaults = DEFAULT_PATCH_BCS.get(role, DEFAULT_PATCH_BCS["wall"])
        fields = {}
        for field in self._data.get("active_fields", ["p", "U", "k", "epsilon", "nut"]):
            if field in defaults:
                bc_type, params = defaults[field]
                fields[field] = {"type": bc_type, "params": dict(params)}
        return {"role": role, "fields": fields}

    @staticmethod
    def _parse_stl_solids(stl_path: Path) -> list:
        """Parse solid names from an STL file (ASCII or binary).

        Tries ASCII parsing first since it's unambiguous.
        Handles duplicate names and strips .stl/.obj extensions from solid names.
        """
        # Try ASCII first — look for solid/endsolid blocks
        solids = []
        try:
            with open(stl_path, 'r', errors='replace') as f:
                text = f.read()
            if 'endsolid' in text.lower() and 'vertex' in text.lower():
                raw_names = []
                for line in text.split('\n'):
                    stripped = line.strip()
                    if stripped.lower().startswith('solid '):
                        name = stripped[6:].strip()
                        if name and 'facet' not in name.lower():
                            # Strip file extensions from solid name
                            for ext in ('.stl', '.obj', '.STL', '.OBJ'):
                                if name.endswith(ext):
                                    name = name[:-len(ext)]
                                    break
                            raw_names.append(name)
                    elif stripped.lower() == 'solid':
                        raw_names.append(stl_path.stem)

                if raw_names:
                    # Handle duplicates by appending _0, _1, ...
                    seen = {}
                    for name in raw_names:
                        count = seen.get(name, 0)
                        if count == 0:
                            # Check if this name appears more than once
                            total = raw_names.count(name)
                            if total > 1:
                                solids.append(f"{name}_{count}")
                            else:
                                solids.append(name)
                        else:
                            solids.append(f"{name}_{count}")
                        seen[name] = count + 1

                if solids:
                    return solids
        except Exception:
            pass

        # Binary fallback
        return [stl_path.stem]

    @staticmethod
    def _stl_file_bbox(stl_path: Path) -> tuple:
        """Bounding box of a single STL file."""
        xmin = ymin = zmin = float('inf')
        xmax = ymax = zmax = float('-inf')

        with open(stl_path, 'rb') as f:
            f.read(80)
            f.seek(0, 2)
            file_size = f.tell()
            f.seek(80)
            num_bytes = f.read(4)
            if len(num_bytes) < 4:
                is_binary = False
            else:
                num_tri = struct.unpack('<I', num_bytes)[0]
                is_binary = (file_size == 80 + 4 + num_tri * 50)

        if is_binary:
            with open(stl_path, 'rb') as f:
                f.seek(80)
                num_tri = struct.unpack('<I', f.read(4))[0]
                for _ in range(num_tri):
                    data = f.read(50)
                    if len(data) < 50:
                        break
                    floats = struct.unpack('<12f', data[:48])
                    for v in range(3):
                        x, y, z = floats[3 + v*3], floats[4 + v*3], floats[5 + v*3]
                        xmin, ymin, zmin = min(xmin, x), min(ymin, y), min(zmin, z)
                        xmax, ymax, zmax = max(xmax, x), max(ymax, y), max(zmax, z)
        else:
            with open(stl_path, 'r', errors='replace') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('vertex'):
                        parts = stripped.split()
                        if len(parts) >= 4:
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            xmin, ymin, zmin = min(xmin, x), min(ymin, y), min(zmin, z)
                            xmax, ymax, zmax = max(xmax, x), max(ymax, y), max(zmax, z)

        if xmin == float('inf'):
            return (0, 0, 0, 0, 0, 0)
        return (xmin, ymin, zmin, xmax, ymax, zmax)
