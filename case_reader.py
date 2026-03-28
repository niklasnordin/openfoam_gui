"""
case_reader.py — Read an existing OpenFOAM case into CaseDatabase.

Parses OpenFOAM dictionary files, maps values to database keys,
and populates patches, surfaces, and function objects.
"""

from __future__ import annotations

import re
import os
from pathlib import Path


# ================================================================ #
#  OpenFOAM dictionary parser
# ================================================================ #

def parse_foam_dict(text: str) -> dict:
    """Parse an OpenFOAM dictionary file into a nested Python dict.
    Handles: scalars, strings, lists (...), sub-dicts {}, #include, and comments."""

    # Strip C/C++ comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//.*', '', text)

    # Remove FoamFile header block
    text = re.sub(r'FoamFile\s*\{[^}]*\}', '', text, count=1)

    return _parse_block(text)


def _parse_block(text: str) -> dict:
    """Parse a block of OpenFOAM key-value pairs."""
    result = {}
    text = text.strip()

    i = 0
    n = len(text)

    while i < n:
        # Skip whitespace
        while i < n and text[i] in ' \t\n\r':
            i += 1
        if i >= n:
            break

        # Skip stray braces/semicolons
        if text[i] in '};':
            i += 1
            continue

        # #include directives
        if text[i] == '#':
            end = text.index('\n', i) if '\n' in text[i:] else n
            line = text[i:end].strip()
            m = re.match(r'#include\w*\s+"([^"]+)"', line)
            if m:
                result.setdefault("__includes__", []).append(m.group(1))
            i = end + 1
            continue

        # Read key (word or quoted string)
        key, i = _read_token(text, i)
        if not key:
            i += 1
            continue

        # Skip whitespace
        while i < n and text[i] in ' \t\n\r':
            i += 1
        if i >= n:
            break

        # Sub-dict
        if text[i] == '{':
            close = _find_matching_brace(text, i)
            inner = text[i+1:close]
            result[key] = _parse_block(inner)
            i = close + 1
            # Skip trailing ;
            while i < n and text[i] in ' \t\n\r;':
                i += 1
            continue

        # Value: read until ;
        semi = text.find(';', i)
        if semi < 0:
            break
        val_str = text[i:semi].strip()
        result[key] = _parse_value(val_str)
        i = semi + 1

    return result


def _read_token(text, i):
    """Read one token (word or quoted string)."""
    n = len(text)
    while i < n and text[i] in ' \t\n\r':
        i += 1
    if i >= n:
        return None, i

    if text[i] == '"':
        end = text.index('"', i + 1)
        return text[i+1:end], end + 1

    start = i
    while i < n and text[i] not in ' \t\n\r{};':
        i += 1
    return text[start:i], i


def _find_matching_brace(text, start):
    """Find matching } for { at position start."""
    depth = 1
    i = start + 1
    n = len(text)
    while i < n and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    return i - 1


def _parse_value(val_str):
    """Parse an OpenFOAM value string into Python types."""
    val_str = val_str.strip()

    # List: (a b c)
    if val_str.startswith('(') and val_str.endswith(')'):
        inner = val_str[1:-1].strip()
        if not inner:
            return []
        # Could be nested: list of sub-items
        return inner.split()

    # Try numeric
    try:
        if '.' in val_str or 'e' in val_str.lower():
            return float(val_str)
        return int(val_str)
    except ValueError:
        pass

    # Dimension string: [0 2 -2 0 0 0 0]
    if val_str.startswith('[') and val_str.endswith(']'):
        return val_str

    return val_str


# ================================================================ #
#  Case reader
# ================================================================ #

class CaseReader:
    """Read an OpenFOAM case directory into CaseDatabase."""

    KNOWN_SOLVERS = {
        "simpleFoam": "simplefoam",
        "rhoSimpleFoam": "rhosimplefoam",
        "pimpleFoam": "pimplefoam",
        "simpleReactingParcelFoam": "simplereactingparcelfoam",
        "interFoam": "interfoam",
        "icoFoam": "icofoam",
        "pisoFoam": "pisofoam",
        "buoyantSimpleFoam": "buoyantsimplefoam",
        "buoyantPimpleFoam": "buoyantpimplefoam",
        "rhoPimpleFoam": "rhopimplefoam",
        "potentialFoam": "potentialfoam",
    }

    def __init__(self, db):
        self.db = db

    def read_case(self, case_path: str) -> dict:
        """Read a case and populate the database. Returns a status dict."""
        case = Path(case_path)
        status = {"errors": [], "warnings": [], "loaded": []}

        if not case.is_dir():
            status["errors"].append(f"Not a directory: {case_path}")
            return status

        # 1. Detect solver from controlDict
        solver_name = self._detect_solver(case, status)

        # 2. Set template
        tmpl = self._set_solver(solver_name, status)
        if not tmpl:
            return status

        # 3. Read system/ dictionaries
        self._read_control_dict(case, status)
        self._read_fv_schemes(case, status)
        self._read_fv_solution(case, status)
        self._read_decompose_par(case, status)

        # 4. Read constant/ dictionaries
        #    Determine which files are expected based on template
        has_turb = bool(getattr(tmpl, 'TURBULENCE_MODELS', {}))
        base_fields = getattr(tmpl, 'BASE_FIELDS', ["p", "U"])
        uses_thermo = any(
            d.get("path") == "constant/thermophysicalProperties"
            for d in tmpl.get_base_dicts()
        )
        uses_transport = any(
            d.get("path") == "constant/transportProperties"
            for d in tmpl.get_base_dicts()
        )
        uses_gravity = any(
            d.get("path") == "constant/g"
            for d in tmpl.get_base_dicts()
        )

        # Only warn about missing files that are actually expected
        self._read_transport_properties(case, status,
                                        quiet=not uses_transport)
        self._read_turbulence_properties(case, status,
                                         quiet=not has_turb)
        if uses_thermo:
            self._read_thermophysical_properties(case, status)
        if uses_gravity:
            self._read_gravity(case, status)

        # 5. Read blockMeshDict
        self._read_block_mesh_dict(case, status)

        # 6. STL files
        self._read_stl_files(case, status)

        # 7. snappyHexMeshDict (only present if STL loaded — don't warn)
        self._read_snappy(case, status, quiet=True)

        # 8. Boundary conditions from 0/
        self._read_boundary_conditions(case, status)

        # 9. fvOptions
        self._read_fv_options(case, status)

        # 10. Function objects from controlDict #includes
        self._read_function_objects(case, status)

        return status

    # ---- Solver detection ---- #

    def _detect_solver(self, case, status):
        cd_path = case / "system" / "controlDict"
        if not cd_path.exists():
            status["errors"].append("system/controlDict not found")
            return "simpleFoam"

        raw = cd_path.read_text(errors='replace')
        d = parse_foam_dict(raw)
        app = d.get("application", "simpleFoam")
        status["loaded"].append(f"Detected solver: {app}")

        # Detect openfoam.org vs .com from header
        from of_version import OFVersion
        if "openfoam.com" in raw or "www.openfoam.com" in raw:
            # Extract version string from "Version:" line
            import re
            m = re.search(r'Version:\s*(v?\d+)', raw)
            ver = m.group(1) if m else None
            self.db.of_version = OFVersion(OFVersion.COM, ver)
            status["loaded"].append(f"Detected distribution: openfoam.com {ver or ''}")
        elif "openfoam.org" in raw:
            import re
            m = re.search(r'Version:\s*(\d+)', raw)
            ver = m.group(1) if m else None
            self.db.of_version = OFVersion(OFVersion.ORG, ver)
            status["loaded"].append(f"Detected distribution: openfoam.org {ver or ''}")

        return str(app)

    def _set_solver(self, solver_name, status):
        import importlib
        mod_name = self.KNOWN_SOLVERS.get(solver_name)
        if not mod_name:
            status["warnings"].append(
                f"Unknown solver '{solver_name}', defaulting to simpleFoam")
            mod_name = "simplefoam"
            solver_name = "simpleFoam"

        try:
            tmpl = importlib.import_module(mod_name)
            self.db.template = tmpl
            self.db.solver = solver_name
            self.db._recompute_active_fields()
            self.db.reset()
            return tmpl
        except ImportError as e:
            status["errors"].append(f"Cannot load template '{mod_name}': {e}")
            return None

    # ---- System dictionaries ---- #

    def _read_control_dict(self, case, status):
        d = self._read_dict(case / "system" / "controlDict", status)
        if not d:
            return

        key_map = {
            "application": "application", "startFrom": "startFrom",
            "startTime": "startTime", "stopAt": "stopAt",
            "endTime": "endTime", "deltaT": "deltaT",
            "writeControl": "writeControl", "writeInterval": "writeInterval",
            "purgeWrite": "purgeWrite", "writeFormat": "writeFormat",
            "writePrecision": "writePrecision",
            "writeCompression": "writeCompression",
            "timeFormat": "timeFormat", "timePrecision": "timePrecision",
            "runTimeModifiable": "runTimeModifiable",
            "adjustTimeStep": "adjustTimeStep",
            "maxCo": "maxCo", "maxDeltaT": "maxDeltaT",
        }
        self._map_values(d, key_map, "system/controlDict")
        status["loaded"].append("system/controlDict")

    def _read_fv_schemes(self, case, status):
        d = self._read_dict(case / "system" / "fvSchemes", status)
        if not d:
            return

        vals = {}

        # ddt
        ddt_block = d.get("ddtSchemes", {})
        ddt_default = str(ddt_block.get("default", "steadyState"))
        if ddt_default.startswith("CrankNicolson"):
            parts = ddt_default.split()
            vals["ddtScheme"] = "CrankNicolson"
            if len(parts) > 1:
                vals["ddtCoeff"] = float(parts[1])
        else:
            vals["ddtScheme"] = ddt_default

        # grad
        grad_block = d.get("gradSchemes", {})
        grad_default = str(grad_block.get("default", "Gauss linear"))
        self._parse_grad_scheme(grad_default, vals, "grad")
        grad_u = str(grad_block.get("grad(U)", "cellLimited Gauss linear 1"))
        self._parse_grad_u(grad_u, vals)

        # div
        div_block = d.get("divSchemes", {})
        div_u = str(div_block.get("div(phi,U)", "bounded Gauss linearUpwind grad(U)"))
        self._parse_div_scheme(div_u, vals, "divU")

        # Use first turbulence div scheme found
        for key in ["div(phi,k)", "div(phi,epsilon)", "div(phi,omega)"]:
            if key in div_block:
                self._parse_div_scheme(str(div_block[key]), vals, "divTurb")
                break

        # Energy schemes (rhoSimpleFoam)
        if "div(phi,e)" in div_block:
            self._parse_div_scheme(str(div_block["div(phi,e)"]), vals, "divE")

        # laplacian
        lap_block = d.get("laplacianSchemes", {})
        lap_default = str(lap_block.get("default", "Gauss linear corrected"))
        self._parse_laplacian(lap_default, vals)

        # snGrad
        sn_block = d.get("snGradSchemes", {})
        sn_default = str(sn_block.get("default", "corrected"))
        self._parse_sngrad(sn_default, vals)

        self.db.set_dict_values("system/fvSchemes", vals)
        status["loaded"].append("system/fvSchemes")

    def _read_fv_solution(self, case, status):
        d = self._read_dict(case / "system" / "fvSolution", status)
        if not d:
            return

        vals = {}
        solvers = d.get("solvers", {})

        # p solver
        p = solvers.get("p", {})
        if isinstance(p, dict):
            vals["pSolver"] = str(p.get("solver", "GAMG"))
            vals["pSmoother"] = str(p.get("smoother", "GaussSeidel"))
            vals["pTolerance"] = str(p.get("tolerance", "1e-7"))
            vals["pRelTol"] = str(p.get("relTol", "0.01"))

        # U solver
        u = solvers.get("U", {})
        if isinstance(u, dict):
            vals["USolver"] = str(u.get("solver", "smoothSolver"))
            vals["USmoother"] = str(u.get("smoother", "GaussSeidel"))
            vals["UTolerance"] = str(u.get("tolerance", "1e-8"))
            vals["URelTol"] = str(u.get("relTol", "0.1"))

        # Turbulence solver
        for tkey in ['"(k|epsilon|omega)"', "k"]:
            t = solvers.get(tkey, {})
            if isinstance(t, dict) and t:
                vals["turbSolver"] = str(t.get("solver", "smoothSolver"))
                vals["turbSmoother"] = str(t.get("smoother", "GaussSeidel"))
                vals["turbTolerance"] = str(t.get("tolerance", "1e-8"))
                vals["turbRelTol"] = str(t.get("relTol", "0.1"))
                break

        # Algorithm detection
        if "SIMPLE" in d:
            vals["algorithm"] = "SIMPLE"
            simple = d["SIMPLE"]
            if isinstance(simple, dict):
                vals["nNonOrthogonalCorrectors"] = simple.get(
                    "nNonOrthogonalCorrectors", 1)
                vals["consistent"] = str(simple.get("consistent", "yes"))
                rc = simple.get("residualControl", {})
                if isinstance(rc, dict):
                    vals["pResidual"] = str(rc.get("p", "1e-4"))
                    vals["UResidual"] = str(rc.get("U", "1e-4"))
                    for tk in ['"(k|epsilon|omega)"', "k"]:
                        if tk in rc:
                            vals["turbResidual"] = str(rc[tk])
                            break

        elif "PIMPLE" in d:
            vals["algorithm"] = "PIMPLE"
            pimple = d["PIMPLE"]
            if isinstance(pimple, dict):
                vals["nOuterCorrectors"] = pimple.get("nOuterCorrectors", 2)
                vals["nCorrectors"] = pimple.get("nCorrectors", 1)
                vals["nNonOrthogonalCorrectors"] = pimple.get(
                    "nNonOrthogonalCorrectors", 1)

        # Relaxation
        relax = d.get("relaxationFactors", {})
        eq = relax.get("equations", {})
        if isinstance(eq, dict):
            if "U" in eq:
                vals["relaxU"] = float(eq["U"])
            if "p" in eq:
                vals["relaxP"] = float(eq["p"])
            for tk in ['"(k|epsilon|omega)"', "k"]:
                if tk in eq:
                    vals["relaxTurb"] = float(eq[tk])
                    break

        self.db.set_dict_values("system/fvSolution", vals)
        status["loaded"].append("system/fvSolution")

    def _read_decompose_par(self, case, status):
        d = self._read_dict(case / "system" / "decomposeParDict", status)
        if not d:
            return
        vals = {}
        if "numberOfSubdomains" in d:
            vals["nProcs"] = int(d["numberOfSubdomains"])
        if "method" in d:
            vals["method"] = str(d["method"])
        self.db.set_dict_values("system/decomposeParDict", vals)
        status["loaded"].append("system/decomposeParDict")

    # ---- Constant dictionaries ---- #

    def _read_transport_properties(self, case, status, quiet=False):
        d = self._read_dict(case / "constant" / "transportProperties",
                            status, quiet=quiet)
        if not d:
            return
        vals = {}
        if "transportModel" in d:
            vals["transportModel"] = str(d["transportModel"])
        nu = d.get("nu", "")
        if isinstance(nu, str) and ']' in nu:
            # "[0 2 -1 0 0 0 0] 1e-06" -> extract value
            parts = nu.split(']')
            if len(parts) > 1:
                vals["nu"] = parts[1].strip()
        elif isinstance(nu, (int, float)):
            vals["nu"] = str(nu)
        self.db.set_dict_values("constant/transportProperties", vals)
        status["loaded"].append("constant/transportProperties")

    def _read_turbulence_properties(self, case, status, quiet=False):
        d = self._read_dict(case / "constant" / "turbulenceProperties",
                            status, quiet=quiet)
        if not d:
            return
        vals = {}
        sim_type = str(d.get("simulationType", "RAS"))
        vals["simulationType"] = sim_type

        if sim_type == "RAS":
            ras = d.get("RAS", {})
            if isinstance(ras, dict):
                # org uses 'RASModel', com uses 'model'
                vals["RASModel"] = str(
                    ras.get("RASModel", ras.get("model", "kEpsilon")))
                vals["turbulence"] = str(ras.get("turbulence", "on"))
                vals["printCoeffs"] = str(ras.get("printCoeffs", "on"))

            # Read model coefficients
            model = vals.get("RASModel", "kEpsilon")
            coeffs_key = f"{model}Coeffs"
            coeffs = d.get(coeffs_key, {})
            if isinstance(coeffs, dict):
                self._read_coeffs(coeffs, model, vals)

        elif sim_type == "LES":
            les = d.get("LES", {})
            if isinstance(les, dict):
                # org uses 'LESModel', com uses 'model'
                vals["LESModel"] = str(
                    les.get("LESModel", les.get("model", "Smagorinsky")))
                vals["turbulence"] = str(les.get("turbulence", "on"))
                vals["printCoeffs"] = str(les.get("printCoeffs", "on"))
                vals["delta"] = str(les.get("delta", "cubeRootVol"))

            model = vals.get("LESModel", "Smagorinsky")
            coeffs_key = f"{model}Coeffs"
            coeffs = d.get(coeffs_key, {})
            if isinstance(coeffs, dict):
                self._read_coeffs(coeffs, model, vals)

        self.db.set_dict_values("constant/turbulenceProperties", vals)
        status["loaded"].append("constant/turbulenceProperties")

    def _read_thermophysical_properties(self, case, status):
        d = self._read_dict(
            case / "constant" / "thermophysicalProperties", status)
        if not d:
            return
        vals = {}
        tt = d.get("thermoType", {})
        if isinstance(tt, dict):
            for k in ["type", "mixture", "transport", "thermo",
                       "equationOfState", "specie", "energy"]:
                if k in tt:
                    key_map = {"type": "thermoType"}.get(k, k)
                    vals[key_map] = str(tt[k])
        mix = d.get("mixture", {})
        if isinstance(mix, dict):
            sp = mix.get("specie", {})
            if isinstance(sp, dict) and "molWeight" in sp:
                vals["molWeight"] = str(sp["molWeight"])
            thermo = mix.get("thermodynamics", {})
            if isinstance(thermo, dict):
                for k in ["Cp", "Hf"]:
                    if k in thermo:
                        vals[k] = str(thermo[k])
            tr = mix.get("transport", {})
            if isinstance(tr, dict):
                for k in ["As", "Ts"]:
                    if k in tr:
                        vals[k] = str(tr[k])

        self.db.set_dict_values(
            "constant/thermophysicalProperties", vals)
        status["loaded"].append("constant/thermophysicalProperties")

    def _read_gravity(self, case, status):
        """Read constant/g (gravity vector)."""
        path = case / "constant" / "g"
        if not path.exists():
            return
        try:
            content = path.read_text(errors='replace')
        except Exception:
            return

        import re
        m = re.search(r'value\s*\(\s*([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s*\)',
                      content)
        if m:
            vals = {
                "gx": float(m.group(1)),
                "gy": float(m.group(2)),
                "gz": float(m.group(3)),
            }
            self.db.set_dict_values("constant/g", vals)
            status["loaded"].append("constant/g")

    # ---- Mesh ---- #

    def _read_block_mesh_dict(self, case, status):
        d = self._read_dict(case / "system" / "blockMeshDict", status)
        if not d:
            return
        vals = {}

        # Read the raw file for vertices and blocks (regex is more reliable
        # than the dict parser for blockMeshDict's special syntax)
        try:
            raw = (case / "system" / "blockMeshDict").read_text(errors='replace')

            # Extract vertices: find the vertices (...) block and parse (x y z) tuples inside
            vert_section = re.search(
                r'vertices\s*\((.*?)\)\s*;', raw, re.DOTALL)
            if vert_section:
                vert_matches = re.findall(
                    r'\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)',
                    vert_section.group(1))
                if len(vert_matches) >= 8:
                    xs = [float(v[0]) for v in vert_matches[:8]]
                    ys = [float(v[1]) for v in vert_matches[:8]]
                    zs = [float(v[2]) for v in vert_matches[:8]]
                    vals["xMin"] = min(xs)
                    vals["xMax"] = max(xs)
                    vals["yMin"] = min(ys)
                    vals["yMax"] = max(ys)
                    vals["zMin"] = min(zs)
                    vals["zMax"] = max(zs)

            # Extract cell counts from blocks section: hex (...) (nx ny nz)
            blocks_section = re.search(
                r'blocks\s*\((.*?)\)\s*;', raw, re.DOTALL)
            if blocks_section:
                m = re.search(
                    r'\)\s*\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)',
                    blocks_section.group(1))
                if m:
                    vals["nCellsX"] = int(m.group(1))
                    vals["nCellsY"] = int(m.group(2))
                    vals["nCellsZ"] = int(m.group(3))

            # Compute cellSize from bounds and cell count
            if all(k in vals for k in ("xMin", "xMax", "nCellsX")):
                dx = vals["xMax"] - vals["xMin"]
                nx = vals["nCellsX"]
                if nx > 0:
                    vals["cellSize"] = round(dx / nx, 8)

        except Exception:
            pass

        self.db.set_dict_values("system/blockMeshDict", vals)
        status["loaded"].append("system/blockMeshDict")

    # ---- STL + Snappy ---- #

    def _read_stl_files(self, case, status):
        tri_dir = case / "constant" / "triSurface"
        if not tri_dir.exists():
            return
        for stl_file in sorted(tri_dir.glob("*.stl")):
            try:
                self.db.add_stl(str(stl_file))
                status["loaded"].append(f"STL: {stl_file.name}")
            except Exception as e:
                status["warnings"].append(f"STL {stl_file.name}: {e}")

    def _read_snappy(self, case, status, quiet=False):
        d = self._read_dict(
            case / "system" / "snappyHexMeshDict", status, quiet=quiet)
        if not d:
            return

        vals = {}

        # Top-level flags
        for key, db_key in [("castellatedMesh", "castellatedMesh"),
                            ("snap", "snap"),
                            ("addLayers", "addLayers")]:
            if key in d:
                vals[db_key] = str(d[key])

        # castellatedMeshControls
        cc = d.get("castellatedMeshControls", {})
        if isinstance(cc, dict):
            for key, db_key in [
                ("maxLocalCells", "maxLocalCells"),
                ("maxGlobalCells", "maxGlobalCells"),
                ("resolveFeatureAngle", "resolveFeatureAngle"),
                ("nCellsBetweenLevels", "nCellsBetweenLevels"),
                ("minRefinementCells", "minRefinementCells"),
            ]:
                if key in cc:
                    vals[db_key] = cc[key]

            loc = cc.get("locationInMesh", "")
            locs_in_mesh = cc.get("locationsInMesh", None)

            if locs_in_mesh is not None:
                # Multiple locations format
                parsed_locs = []
                if isinstance(locs_in_mesh, list):
                    for entry in locs_in_mesh:
                        if isinstance(entry, dict):
                            name = entry.get("name", "")
                            coords = entry.get("coords", entry)
                            if isinstance(coords, (list, tuple)) and len(coords) >= 3:
                                parsed_locs.append({
                                    "x": float(coords[0]),
                                    "y": float(coords[1]),
                                    "z": float(coords[2]),
                                    "name": name,
                                })
                            else:
                                # Try parsing nested tuples e.g. ((x y z))
                                for c in coords if isinstance(coords, list) else [coords]:
                                    if isinstance(c, (list, tuple)) and len(c) >= 3:
                                        parsed_locs.append({
                                            "x": float(c[0]),
                                            "y": float(c[1]),
                                            "z": float(c[2]),
                                            "name": name,
                                        })
                        elif isinstance(entry, (list, tuple)) and len(entry) >= 3:
                            parsed_locs.append({
                                "x": float(entry[0]),
                                "y": float(entry[1]),
                                "z": float(entry[2]),
                                "name": "",
                            })
                if parsed_locs:
                    self.db._data["locations_in_mesh"] = parsed_locs
                    status.setdefault("loaded", []).append("locationsInMesh")
            elif loc:
                # Single location format
                lx, ly, lz = 0.0, 0.0, 0.0
                if isinstance(loc, list) and len(loc) >= 3:
                    lx, ly, lz = float(loc[0]), float(loc[1]), float(loc[2])
                elif isinstance(loc, str) and '(' in loc:
                    parts = loc.strip('()').split()
                    if len(parts) >= 3:
                        lx, ly, lz = float(parts[0]), float(parts[1]), float(parts[2])
                self.db._data["locations_in_mesh"] = [
                    {"x": lx, "y": ly, "z": lz, "name": ""}]
                # Also set legacy keys for dict_editor display
                vals["locationX"] = lx
                vals["locationY"] = ly
                vals["locationZ"] = lz

            # Read refinement surfaces for surface settings
            rs = cc.get("refinementSurfaces", {})
            if isinstance(rs, dict):
                self._read_refinement_surfaces(rs)

        # snapControls
        sc = d.get("snapControls", {})
        if isinstance(sc, dict):
            for key, db_key in [
                ("nSmoothPatch", "nSmoothPatch"),
                ("tolerance", "snapTolerance"),
                ("nSolveIter", "nSolveIter"),
                ("nRelaxIter", "nRelaxIter"),
                ("nFeatureSnapIter", "nFeatureSnapIter"),
            ]:
                if key in sc:
                    vals[db_key] = sc[key]

        # addLayersControls
        alc = d.get("addLayersControls", {})
        if isinstance(alc, dict):
            for key, db_key in [
                ("expansionRatio", "expansionRatio"),
                ("finalLayerThickness", "finalLayerThickness"),
                ("minThickness", "minThickness"),
                ("featureAngle", "featureAngle"),
            ]:
                if key in alc:
                    vals[db_key] = alc[key]

            # Read layer counts per surface
            layers = alc.get("layers", {})
            if isinstance(layers, dict):
                for name, ldata in layers.items():
                    clean_name = name.strip('"').rstrip('.*')
                    if isinstance(ldata, dict) and "nSurfaceLayers" in ldata:
                        n = int(ldata["nSurfaceLayers"])
                        self.db.set_surface_value(clean_name, "nLayers", n)

        # meshQualityControls
        mqc = d.get("meshQualityControls", {})
        if isinstance(mqc, dict):
            for key, db_key in [
                ("maxNonOrtho", "maxNonOrtho"),
                ("maxConcave", "maxConcave"),
            ]:
                if key in mqc:
                    vals[db_key] = mqc[key]

        self.db.set_dict_values("system/snappyHexMeshDict", vals)
        status["loaded"].append("system/snappyHexMeshDict")

    def _read_refinement_surfaces(self, rs):
        """Parse refinementSurfaces block for per-surface settings."""
        for geom_name, geom_data in rs.items():
            if not isinstance(geom_data, dict):
                continue

            # Top-level level for single-solid
            level = geom_data.get("level", [])
            pi = geom_data.get("patchInfo", {})
            if isinstance(level, list) and len(level) >= 2:
                self.db.set_surface_value(
                    geom_name, "minLevel", int(level[0]))
                self.db.set_surface_value(
                    geom_name, "maxLevel", int(level[1]))
            if isinstance(pi, dict) and "type" in pi:
                self.db.set_surface_value(
                    geom_name, "patchType", str(pi["type"]))

            # Regions for multi-solid
            regions = geom_data.get("regions", {})
            if isinstance(regions, dict):
                for rname, rdata in regions.items():
                    if not isinstance(rdata, dict):
                        continue
                    rl = rdata.get("level", [])
                    rpi = rdata.get("patchInfo", {})
                    if isinstance(rl, list) and len(rl) >= 2:
                        self.db.set_surface_value(
                            rname, "minLevel", int(rl[0]))
                        self.db.set_surface_value(
                            rname, "maxLevel", int(rl[1]))
                    if isinstance(rpi, dict) and "type" in rpi:
                        self.db.set_surface_value(
                            rname, "patchType", str(rpi["type"]))

    # ---- Boundary conditions ---- #

    def _read_boundary_conditions(self, case, status):
        bc_dir = case / "0"
        if not bc_dir.exists():
            return

        from bc_types import ALL_BC_TYPES

        for bc_file in sorted(bc_dir.iterdir()):
            if not bc_file.is_file():
                continue
            field = bc_file.name
            if field not in ALL_BC_TYPES and field not in (
                    "p", "U", "T", "k", "epsilon", "omega", "nut", "alphat"):
                continue

            d = self._read_dict(bc_file, status, quiet=True)
            if not d:
                continue

            # Read internalField
            internal = d.get("internalField", "")
            if isinstance(internal, str):
                self._set_internal_field(field, internal)

            # Read boundaryField patches
            bf = d.get("boundaryField", {})
            if not isinstance(bf, dict):
                continue

            for patch_name, patch_data in bf.items():
                if not isinstance(patch_data, dict):
                    continue

                bc_type = str(patch_data.get("type", "zeroGradient"))
                params = {}

                # Extract known parameters
                for k, v in patch_data.items():
                    if k == "type":
                        continue
                    if isinstance(v, str) and v.startswith("uniform"):
                        # "uniform (10 0 0)" or "uniform 0"
                        v = v.replace("uniform", "").strip()
                        if v.startswith("(") and v.endswith(")"):
                            # Vector
                            parts = v[1:-1].split()
                            if field == "U" and len(parts) == 3:
                                params["Ux"] = parts[0]
                                params["Uy"] = parts[1]
                                params["Uz"] = parts[2]
                                continue
                        params[k] = v
                    elif isinstance(v, (int, float)):
                        params[k] = str(v)
                    elif isinstance(v, str):
                        params[k] = v

                # Ensure patch exists in db
                self.db.add_patch(patch_name, self._guess_role(
                    patch_name, bc_type, field))
                self.db.set_patch_bc(patch_name, field, bc_type, params)

            status["loaded"].append(f"0/{field}")

    def _set_internal_field(self, field, value_str):
        """Parse internalField and store in db."""
        v = str(value_str).replace("uniform", "").strip()
        if field == "U" and v.startswith("("):
            parts = v[1:-1].split()
            if len(parts) >= 3:
                self.db.set_dict_value("0/U", "Ux", float(parts[0]))
                self.db.set_dict_value("0/U", "Uy", float(parts[1]))
                self.db.set_dict_value("0/U", "Uz", float(parts[2]))
        else:
            key_map = {
                "p": ("0/p", "pInternal"),
                "T": ("0/T", "TInternal"),
                "k": ("0/k", "kInternal"),
                "epsilon": ("0/epsilon", "epsilonInternal"),
                "omega": ("0/omega", "omegaInternal"),
                "nut": ("0/nut", "nutInternal"),
                "alphat": ("0/alphat", "alphatInternal"),
            }
            if field in key_map:
                path, key = key_map[field]
                try:
                    self.db.set_dict_value(path, key, v)
                except Exception:
                    pass

    @staticmethod
    def _guess_role(patch_name, bc_type, field):
        name_lower = patch_name.lower()
        if "inlet" in name_lower:
            return "inlet"
        if "outlet" in name_lower:
            return "outlet"
        if bc_type == "noSlip" or "wall" in name_lower:
            return "wall"
        if "symmetry" in name_lower:
            return "symmetry"
        return "wall"

    # ---- fvOptions ---- #

    def _read_fv_options(self, case, status):
        d = self._read_dict(case / "system" / "fvOptions", status, quiet=True)
        if not d:
            return

        from fv_options import FV_OPTIONS_CATALOG

        for name, opt_data in d.items():
            if name.startswith("__"):
                continue
            if not isinstance(opt_data, dict):
                continue
            opt_type = str(opt_data.get("type", ""))
            if opt_type in FV_OPTIONS_CATALOG:
                # Flatten nested coeffs into params
                params = self._flatten_dict(opt_data)
                params.pop("type", None)
                self.db.add_fv_option(name, opt_type, params)
                status["loaded"].append(f"fvOption: {name} ({opt_type})")

    # ---- Function objects ---- #

    def _read_function_objects(self, case, status):
        from func_objects import FUNCTION_OBJECT_CATALOG

        # Read #includes from controlDict
        cd_path = case / "system" / "controlDict"
        if not cd_path.exists():
            return

        d = parse_foam_dict(cd_path.read_text(errors='replace'))
        funcs = d.get("functions", {})

        # Check #includes in functions block
        includes = []
        if isinstance(funcs, dict):
            includes = funcs.get("__includes__", [])

        # Also check top-level includes
        includes += d.get("__includes__", [])

        for inc_name in includes:
            fo_path = case / "system" / inc_name
            if not fo_path.exists():
                continue
            fo_d = parse_foam_dict(fo_path.read_text(errors='replace'))

            # Find the function object entry (usually named same as file)
            fo_data = None
            for k, v in fo_d.items():
                if isinstance(v, dict) and "type" in v:
                    fo_data = v
                    break

            if not fo_data:
                continue

            fo_type = str(fo_data.get("type", ""))
            if fo_type in FUNCTION_OBJECT_CATALOG:
                params = self._flatten_dict(fo_data)
                params.pop("type", None)
                params.pop("libs", None)
                self.db.add_func_object(inc_name, fo_type, params)
                status["loaded"].append(
                    f"Function object: {inc_name} ({fo_type})")

    # ---- Helpers ---- #

    def _read_dict(self, path, status, quiet=False):
        """Read and parse an OpenFOAM dict file."""
        if not path.exists():
            if not quiet:
                status["warnings"].append(f"File not found: {path.name}")
            return None
        try:
            return parse_foam_dict(path.read_text(errors='replace'))
        except Exception as e:
            status["warnings"].append(f"Parse error in {path.name}: {e}")
            return None

    def _map_values(self, d, key_map, dict_path):
        """Map parsed dict values to db keys."""
        vals = {}
        for foam_key, db_key in key_map.items():
            if foam_key in d:
                vals[db_key] = d[foam_key]
        if vals:
            self.db.set_dict_values(dict_path, vals)

    @staticmethod
    def _flatten_dict(d, prefix=""):
        """Flatten nested dict for fvOptions/funcObj params."""
        result = {}
        for k, v in d.items():
            if isinstance(v, dict):
                result.update(CaseReader._flatten_dict(v, prefix))
            elif isinstance(v, list):
                result[k] = " ".join(str(x) for x in v)
            else:
                result[k] = str(v)
        return result

    def _read_coeffs(self, coeffs_dict, model, vals):
        """Map turbulence model coefficients to db keys."""
        coeff_map = {
            "kEpsilon": {"Cmu": "kEps_Cmu", "C1": "kEps_C1",
                         "C2": "kEps_C2", "sigmaK": "kEps_sigmaK",
                         "sigmaEps": "kEps_sigmaEps"},
            "kOmegaSST": {"alphaK1": "sst_alphaK1", "alphaK2": "sst_alphaK2",
                          "alphaOmega1": "sst_alphaOmega1",
                          "alphaOmega2": "sst_alphaOmega2",
                          "gamma1": "sst_gamma1", "gamma2": "sst_gamma2",
                          "beta1": "sst_beta1", "beta2": "sst_beta2",
                          "betaStar": "sst_betaStar",
                          "a1": "sst_a1", "c1": "sst_c1"},
            "realizableKE": {"A0": "rke_A0", "C2": "rke_C2",
                             "sigmaK": "rke_sigmaK",
                             "sigmaEps": "rke_sigmaEps"},
            "SpalartAllmaras": {"sigmaNut": "sa_sigmaNut", "Cb1": "sa_Cb1",
                                "Cb2": "sa_Cb2", "Cw2": "sa_Cw2",
                                "Cw3": "sa_Cw3", "Cv1": "sa_Cv1",
                                "kappa": "sa_kappa"},
            "Smagorinsky": {"Ck": "smag_Ck", "Ce": "smag_Ce"},
            "WALE": {"Cw": "wale_Cw", "Ck": "wale_Ck", "Ce": "wale_Ce"},
        }
        cmap = coeff_map.get(model, {})
        for foam_key, db_key in cmap.items():
            if foam_key in coeffs_dict:
                vals[db_key] = coeffs_dict[foam_key]

    # ---- Scheme parsers ---- #

    @staticmethod
    def _parse_div_scheme(scheme_str, vals, prefix):
        """Parse 'bounded Gauss linearUpwind grad(U)' into components."""
        parts = scheme_str.split()
        bounded = ""
        idx = 0
        if parts and parts[0] == "bounded":
            bounded = "bounded"
            idx = 1

        vals[f"{prefix}_bounded"] = bounded

        # Skip 'Gauss'
        if idx < len(parts) and parts[idx] == "Gauss":
            idx += 1

        if idx < len(parts):
            vals[f"{prefix}_interp"] = parts[idx]
            idx += 1

        if idx < len(parts):
            vals[f"{prefix}_arg"] = " ".join(parts[idx:])
        else:
            vals[f"{prefix}_arg"] = ""

    @staticmethod
    def _parse_grad_scheme(scheme_str, vals, prefix):
        """Parse gradient scheme."""
        parts = scheme_str.split()
        if not parts:
            return

        if parts[0] in ("leastSquares", "fourth"):
            vals[f"{prefix}Method"] = parts[0]
            vals[f"{prefix}Limiter"] = "none"
            return

        limiter = "none"
        idx = 0
        if parts[0] in ("cellLimited", "faceLimited"):
            limiter = parts[0]
            idx = 1

        vals[f"{prefix}Limiter"] = limiter

        if idx < len(parts) and parts[idx] == "Gauss":
            vals[f"{prefix}Method"] = "Gauss"
            idx += 1

        if idx < len(parts):
            vals[f"{prefix}Interp"] = parts[idx]
            idx += 1

        if limiter != "none" and idx < len(parts):
            try:
                vals[f"{prefix}LimitCoeff"] = float(parts[idx])
            except ValueError:
                pass

    @staticmethod
    def _parse_grad_u(scheme_str, vals):
        """Parse grad(U) scheme."""
        parts = scheme_str.split()
        if not parts:
            return

        if parts[0] in ("leastSquares",):
            vals["gradU_method"] = "leastSquares"
            return

        if parts[0] in ("cellLimited", "faceLimited"):
            method = parts[0]
            idx = 1
            if idx < len(parts) and parts[idx] == "Gauss":
                method += " Gauss"
                idx += 1
            vals["gradU_method"] = method
            if idx < len(parts):
                vals["gradU_interp"] = parts[idx]
                idx += 1
            if idx < len(parts):
                try:
                    vals["gradU_coeff"] = float(parts[idx])
                except ValueError:
                    pass
        elif parts[0] == "Gauss":
            vals["gradU_method"] = "Gauss"
            if len(parts) > 1:
                vals["gradU_interp"] = parts[1]

    @staticmethod
    def _parse_laplacian(scheme_str, vals):
        """Parse 'Gauss linear corrected'."""
        parts = scheme_str.split()
        idx = 0
        if idx < len(parts) and parts[idx] == "Gauss":
            idx += 1
        if idx < len(parts):
            vals["lapInterp"] = parts[idx]
            idx += 1
        if idx < len(parts):
            if parts[idx] == "limited":
                vals["lapSnGrad"] = "limited"
                idx += 1
                if idx < len(parts):
                    try:
                        vals["lapLimitCoeff"] = float(parts[idx])
                    except ValueError:
                        pass
            else:
                vals["lapSnGrad"] = parts[idx]

    @staticmethod
    def _parse_sngrad(scheme_str, vals):
        """Parse 'corrected' or 'limited 0.5'."""
        parts = scheme_str.split()
        if not parts:
            return
        if parts[0] == "limited":
            vals["snGradType"] = "limited"
            if len(parts) > 1:
                try:
                    vals["snGradLimitCoeff"] = float(parts[1])
                except ValueError:
                    pass
        else:
            vals["snGradType"] = parts[0]
