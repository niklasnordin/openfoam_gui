"""
CaseManager — pure generator.
Reads all state from CaseDatabase, generates OpenFOAM dictionary content,
and writes the case directory to disk.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any


HEADER_TEMPLATE = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  {website}
    \\\\  /    A nd           | Version:  {version}
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       {class_type};
    location    "{location}";
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

FOOTER = "\n\n// ************************************************************************* //\n"


def foam_header(class_type, location, object_name, of_version=None):
    from of_version import OFVersion
    v = of_version or OFVersion()
    return HEADER_TEMPLATE.format(
        class_type=class_type, location=location, object_name=object_name,
        website=v.website, version=v.header_version)


def dict_to_foam(data, indent=0):
    lines = []
    pad = "    " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{pad}{key}")
                lines.append(f"{pad}{{")
                lines.append(dict_to_foam(value, indent + 1))
                lines.append(f"{pad}}}")
                lines.append("")
            elif isinstance(value, list):
                items = " ".join(str(v) for v in value)
                lines.append(f"{pad}{key}    ({items});")
            else:
                lines.append(f"{pad}{key}    {value};")
    return "\n".join(lines)


class CaseWriter:
    """Reads from CaseDatabase and writes a complete OpenFOAM case."""

    def __init__(self, db):
        self.db = db

    @property
    def _v(self):
        """Shortcut to the active OpenFOAM version."""
        return self.db.of_version

    def _h(self, class_type, location, object_name):
        """Version-aware FoamFile header."""
        return foam_header(class_type, location, object_name, self._v)

    def write_case(self, case_path: str):
        """Write the complete case to disk."""
        case = Path(case_path)

        for d in ["system", "constant", "constant/triSurface", "0"]:
            (case / d).mkdir(parents=True, exist_ok=True)

        # Copy STL files
        for entry in self.db.stl_entries:
            src = Path(entry["path"])
            if src.exists():
                shutil.copy2(src, case / "constant" / "triSurface" / src.name)

        # Generate and write all dictionaries
        tmpl = self.db.template
        if not tmpl:
            return

        # System + constant dicts
        bc_paths = {d["path"] for d in tmpl.get_base_dicts() if d["path"].startswith("0/")}
        mesh_paths = {"system/snappyHexMeshDict",
                      "system/surfaceFeatureExtractDict",
                      "system/surfaceFeaturesDict"}

        for dspec in tmpl.get_base_dicts():
            path = dspec["path"]
            if path in bc_paths:
                continue  # handled by BC generation
            settings = self.db.get_dict(path)
            content = self._generate_dict(path, settings)
            if content:
                self._write_file(case / path, content)

        # Mesh dicts (if STL loaded)
        if self.db.has_stl:
            for dspec in tmpl.get_mesh_dicts():
                path = dspec["path"]
                # Remap surfaceFeature dict name for version
                if "surfaceFeatureExtractDict" in path or "surfaceFeaturesDict" in path:
                    path = f"system/{self._v.surface_feature_dict_name}"
                settings = self.db.get_dict(dspec["path"])
                content = self._generate_dict(path, settings)
                if content:
                    self._write_file(case / path, content)

        # Boundary condition files
        patch_bcs = self.db.get_all_patch_bcs_for_export()
        for field in self.db.active_fields:
            ic = self._get_internal_field(field)
            content = self._gen_bc(field, patch_bcs, ic)
            if content:
                self._write_file(case / f"0/{field}", content)

        # Scripts
        self._write_allrun(case)
        self._write_allclean(case)

        # Function object files
        self._write_function_objects(case)

        # fvOptions file
        self._write_fv_options(case)

    def _write_function_objects(self, case: Path):
        """Write each function object to its own file in system/."""
        from func_objects import FUNCTION_OBJECT_CATALOG

        for name, fo_data in self.db.function_objects.items():
            fo_type = fo_data.get("type", "")
            params = fo_data.get("params", {})
            catalog = FUNCTION_OBJECT_CATALOG.get(fo_type)
            if not catalog:
                continue
            generator = catalog.get("generator")
            if not generator:
                continue
            content = generator(name, params)
            fo_path = case / "system" / name
            with open(fo_path, "w") as f:
                f.write(content)

    def _write_fv_options(self, case: Path):
        """Write system/fvOptions file if any fvOptions are configured."""
        from fv_options import FV_OPTIONS_CATALOG

        fv_opts = self.db.fv_options
        if not fv_opts:
            return

        h = self._h("dictionary", "system", "fvOptions")
        entries = []
        for name, opt_data in fv_opts.items():
            opt_type = opt_data.get("type", "")
            params = opt_data.get("params", {})
            catalog = FV_OPTIONS_CATALOG.get(opt_type)
            if not catalog:
                continue
            generator = catalog.get("generator")
            if not generator:
                continue
            entries.append(generator(name, params))

        body = "\n\n".join(entries)
        content = h + "\n" + body + FOOTER
        self._write_file(case / "system" / "fvOptions", content)

    def _write_file(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def _get_internal_field(self, field: str) -> str:
        """Read internal field value from the BC dict editor settings in the db."""
        ic_map = {
            "p":       ("0/p", "pInternal", lambda v: f"uniform {v}"),
            "p_rgh":   ("0/p_rgh", "p_rghInternal", lambda v: f"uniform {v}"),
            "T":       ("0/T", "TInternal", lambda v: f"uniform {v}"),
            "k":       ("0/k", "kInternal", lambda v: f"uniform {v}"),
            "epsilon": ("0/epsilon", "epsilonInternal", lambda v: f"uniform {v}"),
            "omega":   ("0/omega", "omegaInternal", lambda v: f"uniform {v}"),
            "nut":     ("0/nut", "nutInternal", lambda v: f"uniform {v}"),
            "alphat":  ("0/alphat", "alphatInternal", lambda v: f"uniform {v}"),
            "alpha.water": ("0/alpha.water", "alphaWaterInternal", lambda v: f"uniform {v}"),
        }
        if field == "U":
            vals = self.db.get_dict("0/U")
            ux = vals.get("Ux", 10)
            uy = vals.get("Uy", 0)
            uz = vals.get("Uz", 0)
            return f"uniform ({ux} {uy} {uz})"
        if field in ic_map:
            dict_path, key, fmt = ic_map[field]
            vals = self.db.get_dict(dict_path)
            if key in vals:
                return fmt(vals[key])
        # Fallback
        defaults = {
            "p": "uniform 0", "p_rgh": "uniform 0", "T": "uniform 300",
            "k": "uniform 0.1", "epsilon": "uniform 0.1", "omega": "uniform 1.0",
            "nut": "uniform 0", "alphat": "uniform 0", "alpha.water": "uniform 0",
        }
        return defaults.get(field, "uniform 0")

    # ================================================================ #
    #  Dictionary generators
    # ================================================================ #

    def _generate_dict(self, dict_name: str, s: dict) -> str:
        generators = {
            "system/controlDict": self._gen_control_dict,
            "system/fvSchemes": self._gen_fv_schemes,
            "system/fvSolution": self._gen_fv_solution,
            "system/fvOptions": self._gen_fv_options,
            "system/decomposeParDict": self._gen_decompose_par_dict,
            "constant/transportProperties": self._gen_transport_properties,
            "constant/turbulenceProperties": self._gen_turbulence_properties,
            "constant/thermophysicalProperties": self._gen_thermophysical_properties,
            "constant/combustionProperties": self._gen_combustion_properties,
            "constant/cloudProperties": self._gen_cloud_properties,
            "constant/reactingCloud1Properties": self._gen_reacting_cloud_properties,
            "system/blockMeshDict": self._gen_block_mesh_dict,
            "system/snappyHexMeshDict": self._gen_snappy,
            "system/surfaceFeatureExtractDict": self._gen_surface_feature_extract,
            "system/surfaceFeaturesDict": self._gen_surface_feature_extract,
            "constant/g": self._gen_gravity,
            "system/setFieldsDict": self._gen_setfields_dict,
        }
        gen = generators.get(dict_name)
        return gen(s) if gen else ""

    def _gen_control_dict(self, s):
        h = self._h("dictionary", "system", "controlDict")
        entries = {
            "application": s.get("application", self.db.solver),
            "startFrom": s.get("startFrom", "startTime"),
            "startTime": s.get("startTime", 0),
            "stopAt": s.get("stopAt", "endTime"),
            "endTime": s.get("endTime", 1000),
            "deltaT": s.get("deltaT", 1),
            "writeControl": s.get("writeControl", "timeStep"),
            "writeInterval": s.get("writeInterval", 100),
            "purgeWrite": s.get("purgeWrite", 0),
            "writeFormat": s.get("writeFormat", "ascii"),
            "writePrecision": s.get("writePrecision", 8),
            "writeCompression": s.get("writeCompression", "off"),
            "timeFormat": s.get("timeFormat", "general"),
            "timePrecision": s.get("timePrecision", 6),
            "runTimeModifiable": s.get("runTimeModifiable", "true"),
        }
        if "adjustTimeStep" in s:
            entries["adjustTimeStep"] = s["adjustTimeStep"]
            entries["maxCo"] = s.get("maxCo", 1.0)
            if "maxAlphaCo" in s:
                entries["maxAlphaCo"] = s["maxAlphaCo"]
            entries["maxDeltaT"] = s.get("maxDeltaT", 1.0)

        body = dict_to_foam(entries)

        # Append #include for each function object
        fo_names = self.db.get_func_object_names()
        if fo_names:
            body += "\n\nfunctions\n{\n"
            for name in fo_names:
                body += f'    #include "{name}"\n'
            body += "}"

        return h + "\n" + body + FOOTER

    def _gen_fv_schemes(self, s):
        h = self._h("dictionary", "system", "fvSchemes")

        # ---- ddt ----
        ddt = s.get("ddtScheme", "steadyState")
        if ddt == "CrankNicolson":
            coeff = s.get("ddtCoeff", 0.9)
            ddt = f"CrankNicolson {coeff}"

        # ---- grad ----
        grad_default = self._assemble_grad(s, "grad")
        grad_u = self._assemble_grad_u(s)

        # ---- div ----
        div_schemes = {"default": "none"}
        div_schemes["div(phi,U)"] = self._assemble_div(s, "divU")

        # Turbulence div schemes (skip for laminar-only solvers)
        tmpl = self.db.template
        is_laminar = not (tmpl and hasattr(tmpl, 'TURBULENCE_MODELS')
                         and tmpl.TURBULENCE_MODELS)
        if not is_laminar:
            div_k = self._assemble_div(s, "divTurb")
            div_schemes["div(phi,k)"] = div_k
            div_schemes["div(phi,epsilon)"] = div_k
            div_schemes["div(phi,omega)"] = div_k
            div_schemes["div((nuEff*dev2(T(grad(U)))))"] = "Gauss linear"

        # Energy div schemes (rhoSimpleFoam)
        if "divE_interp" in s:
            div_e = self._assemble_div(s, "divE")
            div_schemes["div(phi,e)"] = div_e
            div_schemes["div(phi,K)"] = div_e
            div_schemes["div(phi,Ekp)"] = div_e

        # Alpha/VOF div schemes (interFoam)
        is_vof = (tmpl and hasattr(tmpl, 'BASE_FIELDS')
                  and "alpha.water" in tmpl.BASE_FIELDS)
        if is_vof:
            alpha_interp = s.get("divAlpha_interp", "vanLeer")
            div_schemes["div(phi,alpha)"] = f"Gauss {alpha_interp}"
            div_schemes["div(phirb,alpha)"] = f"Gauss {alpha_interp}"
            div_schemes["div(rhoPhi,U)"] = div_schemes["div(phi,U)"]
            div_schemes["div(((rho*nuEff)*dev2(T(grad(U)))))"] = "Gauss linear"

        # ---- laplacian ----
        lap = self._assemble_laplacian(s)

        # ---- snGrad ----
        sn = self._assemble_sngrad(s, "snGrad")

        schemes_dict = {
            "ddtSchemes": {"default": ddt},
            "gradSchemes": {
                "default": grad_default,
                "grad(U)": grad_u,
            },
            "divSchemes": div_schemes,
            "laplacianSchemes": {"default": lap},
            "interpolationSchemes": {"default": "linear"},
            "snGradSchemes": {"default": sn},
        }
        if not is_laminar:
            schemes_dict["wallDist"] = {"method": "meshWave"}

        body = dict_to_foam(schemes_dict)
        return h + "\n" + body + FOOTER

    # ---- Scheme assembly helpers ----

    @staticmethod
    def _assemble_div(s, prefix):
        """Assemble a divergence scheme: [bounded] Gauss <interp> [arg]"""
        bounded = s.get(f"{prefix}_bounded", "")
        interp = s.get(f"{prefix}_interp", "upwind")
        arg = s.get(f"{prefix}_arg", "")

        # These interpolations need a gradient field argument
        needs_grad = {"linearUpwind", "linearUpwindV", "LUST"}
        # These need a coefficient
        needs_coeff = {"limitedLinear"}

        parts = []
        if bounded:
            parts.append(bounded)
        parts.append("Gauss")
        parts.append(interp)
        if interp in needs_grad and arg:
            parts.append(arg)
        elif interp in needs_coeff and arg:
            parts.append(arg)
        return " ".join(parts)

    @staticmethod
    def _assemble_grad(s, prefix):
        """Assemble default gradient scheme."""
        method = s.get(f"{prefix}Method", "Gauss")
        interp = s.get(f"{prefix}Interp", "linear")
        limiter = s.get(f"{prefix}Limiter", "none")
        coeff = s.get(f"{prefix}LimitCoeff", 1.0)

        if method == "leastSquares":
            if limiter != "none":
                return f"{limiter} {method} {coeff}"
            return method
        if method == "fourth":
            return method

        # Gauss-based
        if limiter != "none":
            return f"{limiter} Gauss {interp} {coeff}"
        return f"Gauss {interp}"

    @staticmethod
    def _assemble_grad_u(s):
        """Assemble grad(U) scheme."""
        method = s.get("gradU_method", "cellLimited Gauss")
        interp = s.get("gradU_interp", "linear")
        coeff = s.get("gradU_coeff", 1.0)

        if method == "leastSquares":
            return method
        if method == "Gauss":
            return f"Gauss {interp}"
        # cellLimited Gauss, faceLimited Gauss
        return f"{method} {interp} {coeff}"

    @staticmethod
    def _assemble_laplacian(s):
        """Assemble laplacian scheme: Gauss <interp> <snGrad>"""
        interp = s.get("lapInterp", "linear")
        sngrad = s.get("lapSnGrad", "corrected")
        coeff = s.get("lapLimitCoeff", 0.5)

        if sngrad == "limited":
            return f"Gauss {interp} limited {coeff}"
        return f"Gauss {interp} {sngrad}"

    @staticmethod
    def _assemble_sngrad(s, prefix):
        """Assemble snGrad scheme."""
        stype = s.get(f"{prefix}Type", "corrected")
        coeff = s.get(f"{prefix}LimitCoeff", 0.5)

        if stype == "limited":
            return f"limited {coeff}"
        return stype

    def _gen_fv_solution(self, s):
        h = self._h("dictionary", "system", "fvSolution")
        algorithm = s.get("algorithm", "SIMPLE")

        # Detect p_rgh solvers (buoyant*, interFoam)
        tmpl = self.db.template
        uses_p_rgh = (tmpl and hasattr(tmpl, 'BASE_FIELDS')
                      and "p_rgh" in tmpl.BASE_FIELDS)
        is_vof = (tmpl and hasattr(tmpl, 'BASE_FIELDS')
                  and "alpha.water" in tmpl.BASE_FIELDS)

        # Pressure field name
        p_name = "p_rgh" if uses_p_rgh else "p"

        # Detect laminar (no turb solver needed)
        is_laminar = not (tmpl and hasattr(tmpl, 'TURBULENCE_MODELS')
                         and tmpl.TURBULENCE_MODELS)

        solvers = {
            p_name: {"solver": s.get("pSolver", "GAMG"), "smoother": s.get("pSmoother", "GaussSeidel"),
                  "tolerance": s.get("pTolerance", "1e-7"), "relTol": s.get("pRelTol", "0.01")},
            "U": {"solver": s.get("USolver", "smoothSolver"), "smoother": s.get("USmoother", "GaussSeidel"),
                  "tolerance": s.get("UTolerance", "1e-8"), "relTol": s.get("URelTol", "0.1"), "nSweeps": s.get("UnSweeps", 1)},
        }

        if not is_laminar:
            solvers['"(k|epsilon|omega)"'] = {
                "solver": s.get("turbSolver", "smoothSolver"),
                "smoother": s.get("turbSmoother", "GaussSeidel"),
                "tolerance": s.get("turbTolerance", "1e-8"),
                "relTol": s.get("turbRelTol", "0.1"),
                "nSweeps": s.get("turbNSweeps", 1),
            }

        # Alpha solver for VOF
        if is_vof:
            solvers['"alpha.water.*"'] = {
                "solver": s.get("alphaSolver", "smoothSolver"),
                "smoother": s.get("alphaSmoother", "symGaussSeidel"),
                "tolerance": s.get("alphaTolerance", "1e-8"),
                "relTol": s.get("alphaRelTol", "0"),
                "nSweeps": 1,
            }
            solvers['"pcorr.*"'] = dict(solvers[p_name])
            solvers['"pcorr.*"']["relTol"] = "0"

        if algorithm in ("PIMPLE", "PISO"):
            p_final = f'"{p_name}Final"'
            final_pairs = [(p_final, p_name), ('"UFinal"', "U")]
            if not is_laminar:
                final_pairs.append(('"(k|epsilon|omega)Final"', '"(k|epsilon|omega)"'))
            for name, base in final_pairs:
                solvers[name] = dict(solvers[base])
                solvers[name]["relTol"] = "0"
                if name == p_final:
                    solvers[name]["tolerance"] = s.get("pFinalTol", "1e-7")

        residual = {p_name: s.get("pResidual", "1e-4"), "U": s.get("UResidual", "1e-4")}
        if not is_laminar:
            residual['"(k|epsilon|omega)"'] = s.get("turbResidual", "1e-4")

        # Relaxation — org puts p in equations, com puts p in fields
        p_relax = s.get("relaxP", 0.3)
        relax_eq = {"U": s.get("relaxU", 0.7)}
        if not is_laminar:
            relax_eq['"(k|epsilon|omega)"'] = s.get("relaxTurb", 0.7)
        relax_fields = {}

        if self._v.p_relax_in_fields:
            relax_fields[p_name] = p_relax
        else:
            relax_eq[p_name] = p_relax

        if "eSolver" in s:
            solvers["e"] = {"solver": s.get("eSolver", "smoothSolver"), "smoother": s.get("eSmoother", "symGaussSeidel"),
                            "tolerance": s.get("eTolerance", "1e-7"), "relTol": s.get("eRelTol", "0.1")}
        if "eResidual" in s:
            residual["e"] = s["eResidual"]
        if "relaxE" in s:
            relax_eq["e"] = s["relaxE"]
        if "relaxRho" in s:
            relax_fields["rho"] = s["relaxRho"]

        if algorithm == "PIMPLE":
            algo_block = {"nOuterCorrectors": s.get("nOuterCorrectors", 2),
                          "nCorrectors": s.get("nCorrectors", 1),
                          "nNonOrthogonalCorrectors": s.get("nNonOrthogonalCorrectors", 1)}
            if is_vof:
                algo_block["momentumPredictor"] = s.get("momentumPredictor", "no")
            if not is_vof:
                algo_block["residualControl"] = residual
        elif algorithm == "PISO":
            algo_block = {"nCorrectors": s.get("nCorrectors", 2),
                          "nNonOrthogonalCorrectors": s.get("nNonOrthogonalCorrectors", 1)}
            if s.get("pRefCell") is not None:
                algo_block["pRefCell"] = s.get("pRefCell", 0)
                algo_block["pRefValue"] = s.get("pRefValue", 0)
        else:
            algo_block = {"nNonOrthogonalCorrectors": s.get("nNonOrthogonalCorrectors", 1),
                          "consistent": s.get("consistent", "yes"),
                          "residualControl": residual}

        fv_sol = {"solvers": solvers, algorithm: algo_block}

        # Relaxation — skip for PISO (fully transient, no under-relaxation)
        if algorithm != "PISO":
            fv_sol["relaxationFactors"] = {"equations": relax_eq}
            if relax_fields:
                fv_sol["relaxationFactors"]["fields"] = relax_fields

        return h + "\n" + dict_to_foam(fv_sol) + FOOTER

    def _gen_decompose_par_dict(self, s):
        h = self._h("dictionary", "system", "decomposeParDict")
        return h + "\n" + dict_to_foam({"numberOfSubdomains": s.get("nProcs", 4),
                                        "method": s.get("method", "scotch")}) + FOOTER

    def _gen_transport_properties(self, s):
        h = self._h("dictionary", "constant", "transportProperties")

        # Two-phase (interFoam)
        tmpl = self.db.template
        if tmpl and hasattr(tmpl, 'BASE_FIELDS') and "alpha.water" in tmpl.BASE_FIELDS:
            body = f"""phases (water air);

water
{{
    transportModel  {s.get('transportModel_water', 'Newtonian')};
    nu              [0 2 -1 0 0 0 0] {s.get('nu_water', '1e-06')};
    rho             [1 -3 0 0 0 0 0] {s.get('rho_water', '1000')};
}}

air
{{
    transportModel  {s.get('transportModel_air', 'Newtonian')};
    nu              [0 2 -1 0 0 0 0] {s.get('nu_air', '1.48e-05')};
    rho             [1 -3 0 0 0 0 0] {s.get('rho_air', '1')};
}}

sigma           [1 0 -2 0 0 0 0] {s.get('sigma', '0.07')};"""
            return h + "\n" + body + FOOTER

        # Single-phase (simpleFoam etc)
        return h + "\n" + dict_to_foam({
            "transportModel": s.get("transportModel", "Newtonian"),
            "nu": f"[0 2 -1 0 0 0 0] {s.get('nu', '1e-06')}",
        }) + FOOTER

    def _gen_turbulence_properties(self, s):
        h = self._h("dictionary", "constant", "turbulenceProperties")
        sim_type = s.get("simulationType", "RAS")

        body = dict_to_foam({"simulationType": sim_type})

        if sim_type == "RAS":
            model = s.get("RASModel", "kEpsilon")
            ras_kw = self._v.ras_model_keyword  # 'RASModel' (org) or 'model' (com)
            ras_dict = {
                ras_kw: model,
                "turbulence": s.get("turbulence", "on"),
                "printCoeffs": s.get("printCoeffs", "on"),
            }
            body += "\n\n" + dict_to_foam({"RAS": ras_dict})
            coeffs_block = self._gen_model_coeffs(model, s)
            if coeffs_block:
                body += "\n\n" + coeffs_block

        elif sim_type == "LES":
            les_model = s.get("LESModel", "Smagorinsky")
            les_kw = self._v.les_model_keyword  # 'LESModel' (org) or 'model' (com)
            les_dict = {
                les_kw: les_model,
                "turbulence": s.get("turbulence", "on"),
                "printCoeffs": s.get("printCoeffs", "on"),
                "delta": s.get("delta", "cubeRootVol"),
            }
            body += "\n\n" + dict_to_foam({"LES": les_dict})
            coeffs_block = self._gen_model_coeffs(les_model, s)
            if coeffs_block:
                body += "\n\n" + coeffs_block

        # laminar: just simulationType, nothing else needed

        return h + "\n" + body + FOOTER

    @staticmethod
    def _gen_model_coeffs(model, s):
        """Generate a model coefficients block if any differ from defaults."""
        # Map: model -> (coeffs_name, [(foam_key, db_key, default), ...])
        model_coeffs = {
            "kEpsilon": ("kEpsilonCoeffs", [
                ("Cmu", "kEps_Cmu", 0.09),
                ("C1", "kEps_C1", 1.44),
                ("C2", "kEps_C2", 1.92),
                ("sigmaK", "kEps_sigmaK", 1.0),
                ("sigmaEps", "kEps_sigmaEps", 1.3),
            ]),
            "kOmegaSST": ("kOmegaSSTCoeffs", [
                ("alphaK1", "sst_alphaK1", 0.85),
                ("alphaK2", "sst_alphaK2", 1.0),
                ("alphaOmega1", "sst_alphaOmega1", 0.5),
                ("alphaOmega2", "sst_alphaOmega2", 0.856),
                ("gamma1", "sst_gamma1", 0.5556),
                ("gamma2", "sst_gamma2", 0.4403),
                ("beta1", "sst_beta1", 0.075),
                ("beta2", "sst_beta2", 0.0828),
                ("betaStar", "sst_betaStar", 0.09),
                ("a1", "sst_a1", 0.31),
                ("c1", "sst_c1", 10.0),
            ]),
            "realizableKE": ("realizableKECoeffs", [
                ("A0", "rke_A0", 4.0),
                ("C2", "rke_C2", 1.9),
                ("sigmaK", "rke_sigmaK", 1.0),
                ("sigmaEps", "rke_sigmaEps", 1.2),
            ]),
            "SpalartAllmaras": ("SpalartAllmarasCoeffs", [
                ("sigmaNut", "sa_sigmaNut", 0.66666),
                ("Cb1", "sa_Cb1", 0.1355),
                ("Cb2", "sa_Cb2", 0.622),
                ("Cw2", "sa_Cw2", 0.3),
                ("Cw3", "sa_Cw3", 2.0),
                ("Cv1", "sa_Cv1", 7.1),
                ("kappa", "sa_kappa", 0.41),
            ]),
            "LRR": ("LRRCoeffs", [
                ("Cmu", "lrr_Cmu", 0.09),
                ("C1", "lrr_C1", 1.8),
                ("C2", "lrr_C2", 0.6),
                ("Ceps1", "lrr_Ceps1", 1.44),
                ("Ceps2", "lrr_Ceps2", 1.92),
                ("Cs", "lrr_Cs", 0.25),
                ("Ceps", "lrr_Ceps", 0.15),
            ]),
            "LaunderSharmaKE": ("LaunderSharmaKECoeffs", [
                ("Cmu", "lske_Cmu", 0.09),
                ("C1", "lske_C1", 1.44),
                ("C2", "lske_C2", 1.92),
                ("sigmaK", "lske_sigmaK", 1.0),
                ("sigmaEps", "lske_sigmaEps", 1.3),
            ]),
            # LES models
            "Smagorinsky": ("SmagorinskyCoeffs", [
                ("Ck", "smag_Ck", 0.094),
                ("Ce", "smag_Ce", 1.048),
            ]),
            "kEqn": ("kEqnCoeffs", [
                ("Ck", "keqn_Ck", 0.094),
                ("Ce", "keqn_Ce", 1.048),
            ]),
            "WALE": ("WALECoeffs", [
                ("Cw", "wale_Cw", 0.325),
                ("Ck", "wale_Ck", 0.094),
                ("Ce", "wale_Ce", 1.048),
            ]),
            "SpalartAllmarasDES": ("SpalartAllmarasDESCoeffs", [
                ("CDES", "des_CDES", 0.65),
                ("sigmaNut", "des_sigmaNut", 0.66666),
                ("kappa", "des_kappa", 0.41),
                ("Cb1", "des_Cb1", 0.1355),
                ("Cb2", "des_Cb2", 0.622),
            ]),
            "SpalartAllmarasDDES": ("SpalartAllmarasDDESCoeffs", [
                ("CDES", "ddes_CDES", 0.65),
                ("sigmaNut", "ddes_sigmaNut", 0.66666),
                ("kappa", "ddes_kappa", 0.41),
                ("Cb1", "ddes_Cb1", 0.1355),
                ("Cb2", "ddes_Cb2", 0.622),
            ]),
            "SpalartAllmarasIDDES": ("SpalartAllmarasIDDESCoeffs", [
                ("CDES", "iddes_CDES", 0.65),
                ("sigmaNut", "iddes_sigmaNut", 0.66666),
                ("kappa", "iddes_kappa", 0.41),
                ("Cb1", "iddes_Cb1", 0.1355),
                ("Cb2", "iddes_Cb2", 0.622),
            ]),
        }

        if model not in model_coeffs:
            return ""

        coeffs_name, entries = model_coeffs[model]
        lines = []
        has_custom = False
        for foam_key, db_key, default in entries:
            val = s.get(db_key, default)
            try:
                if abs(float(val) - float(default)) > 1e-9:
                    has_custom = True
            except (ValueError, TypeError):
                pass
            lines.append(f"    {foam_key:<16s}{val};")

        # Always write the block so it's visible in the preview,
        # but OpenFOAM only needs it if values differ from defaults
        return f"{coeffs_name}\n{{\n" + "\n".join(lines) + "\n}"

    def _gen_thermophysical_properties(self, s):
        h = self._h("dictionary", "constant", "thermophysicalProperties")
        body = f"""thermoType
{{
    type            {s.get('thermoType', 'hePsiThermo')};
    mixture         {s.get('mixture', 'pureMixture')};
    transport       {s.get('transport', 'sutherland')};
    thermo          {s.get('thermo', 'hConst')};
    equationOfState {s.get('equationOfState', 'perfectGas')};
    specie          {s.get('specie', 'specie')};
    energy          {s.get('energy', 'sensibleEnthalpy')};
}}

mixture
{{
    specie
    {{
        molWeight   {s.get('molWeight', '28.96')};
    }}
    thermodynamics
    {{
        Cp          {s.get('Cp', '1004.5')};
        Hf          {s.get('Hf', '0')};
    }}
    transport
    {{
        As          {s.get('As', '1.458e-06')};
        Ts          {s.get('Ts', '110.4')};
    }}
}}"""
        return h + "\n" + body + FOOTER

    def _gen_combustion_properties(self, s):
        h = self._h("dictionary", "constant", "combustionProperties")
        body = f"""combustionModel {s.get('combustionModel', 'none')};

active          {s.get('active', 'true')};"""
        return h + "\n" + body + FOOTER

    def _gen_cloud_properties(self, s):
        h = self._h("dictionary", "constant", "cloudProperties")
        body = f"""type            {s.get('type', 'reactingCloud')};

solution
{{
    active          true;
    coupled         true;
    transient       false;
    cellValueSourceCorrection on;
    maxCo           0.3;
}}

constantProperties
{{
    rho0            0;
    T0              0;
    Cp0             0;
    youngsModulus    0;
    poissonsRatio   0;
}}

subModels
{{
    particleForces
    {{
        sphereDrag;
        gravity;
    }}
    injectionModels {{}};
    dispersionModel none;
    patchInteractionModel none;
    heatTransferModel none;
    surfaceFilmModel none;
    stochasticCollisionModel none;
    radiation       off;
}}"""
        return h + "\n" + body + FOOTER

    def _gen_reacting_cloud_properties(self, s):
        h = self._h("dictionary", "constant", "reactingCloud1Properties")

        inj_model = s.get("injectionModel", "coneNozzleInjection")
        disp_model = s.get("dispersionModel", "stochasticDispersionRAS")
        pi_model = s.get("patchInteractionModel", "standardWallInteraction")
        ht_model = s.get("heatTransferModel", "RanzMarshall")
        comp_model = s.get("compositionModel", "singleMixtureFraction")
        pc_model = s.get("phaseChangeModel", "liquidEvaporation")
        drag_model = s.get("dragModel", "sphereDrag")
        sf_model = s.get("surfaceFilmModel", "none")
        sc_model = s.get("stochasticCollisionModel", "none")
        rad_model = s.get("cloudRadiationModel", "none")

        # Injection block
        if inj_model == "coneNozzleInjection":
            inj_block = f"""        model1
        {{
            type            {inj_model};
            SOI             {s.get('SOI', 0)};
            massTotal       {s.get('massTotal', 0.001)};
            parcelBasisType {s.get('parcelBasisType', 'mass')};
            nParticle       {s.get('nParticle', 1)};
            duration        {s.get('duration', 1e6)};
            parcelsPerSecond {s.get('parcelsPerSecond', 1000)};
            position        ({s.get('injPosX', '0')} {s.get('injPosY', '0')} {s.get('injPosZ', '0')});
            direction       ({s.get('injDirX', '1')} {s.get('injDirY', '0')} {s.get('injDirZ', '0')});
            outerConeAngle  {s.get('outerConeAngle', 10)};
            innerConeAngle  {s.get('innerConeAngle', 0)};
            injectionMethod {s.get('injectionMethod', 'disc')};
            flowType        {s.get('flowType', 'flowRateAndDischarge')};
            Cd              {s.get('Cd', 0.9)};
            outerDiameter   {s.get('outerDiameter', 0.001)};

            sizeDistribution
            {{
                type    {s.get('sizeDistribution', 'RosinRammler')};
                RosinRammlerDistribution
                {{
                    minValue    {s.get('dMin', '1e-6')};
                    maxValue    {s.get('dMax', '1e-3')};
                    d           {s.get('dChar', '5e-5')};
                    n           {s.get('nRR', '3')};
                }}
            }}

            flowRateProfile constant 1;
        }}"""
        elif inj_model == "patchInjection":
            inj_block = f"""        model1
        {{
            type            patchInjection;
            SOI             {s.get('SOI', 0)};
            massTotal       {s.get('massTotal', 0.001)};
            parcelBasisType {s.get('parcelBasisType', 'mass')};
            nParticle       {s.get('nParticle', 1)};
            duration        {s.get('duration', 1e6)};
            parcelsPerSecond {s.get('parcelsPerSecond', 1000)};
            patch           {s.get('injPatch', 'inlet')};
            U0              ({s.get('injU0', '10')} 0 0);

            sizeDistribution
            {{
                type    {s.get('sizeDistribution', 'RosinRammler')};
                RosinRammlerDistribution
                {{
                    minValue    {s.get('dMin', '1e-6')};
                    maxValue    {s.get('dMax', '1e-3')};
                    d           {s.get('dChar', '5e-5')};
                    n           {s.get('nRR', '3')};
                }}
            }}

            flowRateProfile constant 1;
        }}"""
        elif inj_model == "noInjection":
            inj_block = "        // No injection"
        else:
            inj_block = f"""        model1
        {{
            type            {inj_model};
            SOI             {s.get('SOI', 0)};
            massTotal       {s.get('massTotal', 0.001)};
            parcelBasisType {s.get('parcelBasisType', 'mass')};
            parcelsPerSecond {s.get('parcelsPerSecond', 1000)};
            duration        {s.get('duration', 1e6)};
        }}"""

        # Wall interaction
        wall_type = s.get("wallType", "rebound")
        wall_e = s.get("wallE", 1.0)
        wall_mu = s.get("wallMu", 0.0)

        body = f"""solution
{{
    active          {s.get('cloudActive', 'true')};
    coupled         {s.get('coupled', 'true')};
    transient       {s.get('transient', 'false')};
    cellValueSourceCorrection {s.get('cellValueSourceCorrection', 'on')};
    maxCo           {s.get('cloudMaxCo', 0.3)};
}}

constantProperties
{{
    rho0            {s.get('parcelRho0', 1000)};
    T0              {s.get('parcelT0', 300)};
    Cp0             {s.get('parcelCp0', 4187)};
    youngsModulus    {s.get('youngsModulus', 0)};
    poissonsRatio   {s.get('poissonsRatio', 0)};
}}

subModels
{{
    particleForces
    {{
        {drag_model};
        gravity;
    }}

    injectionModels
    {{
{inj_block}
    }}

    dispersionModel {disp_model};
    patchInteractionModel {pi_model};

    {pi_model}Coeffs
    {{
        type            {wall_type};
        e               {wall_e};
        mu              {wall_mu};
    }}

    heatTransferModel {ht_model};

    {ht_model}Coeffs
    {{
        BirdCorrection  true;
    }}

    compositionModel {comp_model};

    {comp_model}Coeffs
    {{
        phases
        (
            gas
            {{
            }}
            liquid
            {{
            }}
            solid
            {{
            }}
        );
    }}

    phaseChangeModel {pc_model};

    surfaceFilmModel {sf_model};

    stochasticCollisionModel {sc_model};

    radiation       {rad_model};
}}"""
        return h + "\n" + body + FOOTER

    def _gen_block_mesh_dict(self, s):
        h = self._h("dictionary", "system", "blockMeshDict")
        xmin, xmax = s.get("xMin", -5), s.get("xMax", 15)
        ymin, ymax = s.get("yMin", -5), s.get("yMax", 5)
        zmin, zmax = s.get("zMin", -5), s.get("zMax", 5)
        # Support both key naming conventions
        nx = s.get("nCellsX", s.get("cellsX", 20))
        ny = s.get("nCellsY", s.get("cellsY", 10))
        nz = s.get("nCellsZ", s.get("cellsZ", 10))
        gx = s.get("gradeX", 1)
        gy = s.get("gradeY", 1)
        gz = s.get("gradeZ", 1)
        body = f"""{self._v.scale_keyword} 1;

vertices
(
    ({xmin} {ymin} {zmin})
    ({xmax} {ymin} {zmin})
    ({xmax} {ymax} {zmin})
    ({xmin} {ymax} {zmin})
    ({xmin} {ymin} {zmax})
    ({xmax} {ymin} {zmax})
    ({xmax} {ymax} {zmax})
    ({xmin} {ymax} {zmax})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading ({gx} {gy} {gz})
);

edges
(
);

boundary
(
    inlet
    {{
        type patch;
        faces
        (
            (0 4 7 3)
        );
    }}
    outlet
    {{
        type patch;
        faces
        (
            (1 2 6 5)
        );
    }}
    walls
    {{
        type wall;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
            (0 1 5 4)
            (3 7 6 2)
        );
    }}
);

mergePatchPairs
(
);"""
        return h + "\n" + body + FOOTER

    def _gen_snappy(self, s):
        h = self._h("dictionary", "system", "snappyHexMeshDict")
        surfaces = self.db.surfaces

        geom_lines, refine_lines, layer_lines, feature_entries = [], [], [], []
        ref_region_geom_lines = []
        ref_region_refine_lines = []

        for entry in self.db.stl_entries:
            fname = entry["stem"]
            solids = entry.get("solids", [fname])

            feature_entries.append(
                f'        {{\n            file "{fname}.eMesh";\n'
                f'            level {s.get("featureRefLevel", 2)};\n        }}')

            if len(solids) == 1 and solids[0] == fname:
                ss = surfaces.get(fname, {})
                min_l, max_l = ss.get("minLevel", 2), ss.get("maxLevel", 4)
                n_layers = ss.get("nLayers", 3)
                p_type = ss.get("patchType", "wall")

                geom_lines.append(f"    {fname}.stl\n    {{\n        type triSurfaceMesh;\n        name {fname};\n    }}")
                refine_lines.append(f"        {fname}\n        {{\n            level ({min_l} {max_l});\n            patchInfo\n            {{\n                type {p_type};\n            }}\n        }}")
                layer_lines.append(f'        "{fname}.*"\n        {{\n            nSurfaceLayers {n_layers};\n        }}')
            else:
                rg, rr = [], []
                for solid in solids:
                    rg.append(f"            {solid} {{ name {solid}; }}")
                    ss = surfaces.get(solid, {})
                    min_l, max_l = ss.get("minLevel", 2), ss.get("maxLevel", 4)
                    n_layers, p_type = ss.get("nLayers", 3), ss.get("patchType", "wall")
                    rr.append(
                        f"                {solid}\n"
                        f"                {{\n"
                        f"                    level ({min_l} {max_l});\n"
                        f"                    patchInfo\n"
                        f"                    {{\n"
                        f"                        type {p_type};\n"
                        f"                    }}\n"
                        f"                }}")
                    layer_lines.append(f'        "{solid}"\n        {{\n            nSurfaceLayers {n_layers};\n        }}')

                geom_lines.append(
                    f"    {fname}.stl\n"
                    f"    {{\n"
                    f"        type triSurfaceMesh;\n"
                    f"        name {fname};\n"
                    f"        regions\n"
                    f"        {{\n"
                    + "\n".join(rg) + "\n"
                    f"        }}\n"
                    f"    }}")
                refine_lines.append(
                    f"        {fname}\n"
                    f"        {{\n"
                    f"            level (2 4);\n"
                    f"            regions\n"
                    f"            {{\n"
                    + "\n".join(rr) + "\n"
                    f"            }}\n"
                    f"        }}")

        # Refinement regions (box, sphere, cylinder)
        for rname, rdata in self.db.refinement_regions.items():
            shape = rdata.get("shape", "searchableBox")
            params = rdata.get("params", {})
            mode = params.get("mode", "inside")
            level = int(params.get("level", 3))
            distance = float(params.get("distance", 0.1))

            # Geometry block
            if shape == "searchableBox":
                ref_region_geom_lines.append(
                    f"    {rname}\n    {{\n"
                    f"        type searchableBox;\n"
                    f"        min ({params.get('minX', 0)} {params.get('minY', 0)} {params.get('minZ', 0)});\n"
                    f"        max ({params.get('maxX', 0.1)} {params.get('maxY', 0.1)} {params.get('maxZ', 0.1)});\n"
                    f"    }}")
            elif shape == "searchableSphere":
                ref_region_geom_lines.append(
                    f"    {rname}\n    {{\n"
                    f"        type searchableSphere;\n"
                    f"        centre ({params.get('centreX', 0)} {params.get('centreY', 0)} {params.get('centreZ', 0)});\n"
                    f"        radius {params.get('radius', 0.1)};\n"
                    f"    }}")
            elif shape == "searchableCylinder":
                ref_region_geom_lines.append(
                    f"    {rname}\n    {{\n"
                    f"        type searchableCylinder;\n"
                    f"        point1 ({params.get('point1X', 0)} {params.get('point1Y', 0)} {params.get('point1Z', 0)});\n"
                    f"        point2 ({params.get('point2X', 0)} {params.get('point2Y', 0.1)} {params.get('point2Z', 0)});\n"
                    f"        radius {params.get('radius', 0.05)};\n"
                    f"    }}")

            # Refinement block
            if mode == "distance":
                ref_region_refine_lines.append(
                    f"        {rname}\n        {{\n"
                    f"            mode distance;\n"
                    f"            levels (({distance} {level}));\n"
                    f"        }}")
            else:
                ref_region_refine_lines.append(
                    f"        {rname}\n        {{\n"
                    f"            mode {mode};\n"
                    f"            levels ((1e15 {level}));\n"
                    f"        }}")

        # Combine geometry
        all_geom = geom_lines + ref_region_geom_lines
        geom_block = "\n".join(all_geom) or "    // No geometry"
        refine_block = "\n".join(refine_lines) or "        // No surfaces"
        layer_block = "\n".join(layer_lines) or "        // No layers"
        features_block = "\n".join(feature_entries) or ""
        ref_regions_block = "\n".join(ref_region_refine_lines) or "        // No refinement regions"

        loc_x, loc_y, loc_z = s.get("locationX", 0), s.get("locationY", 0), s.get("locationZ", 0)

        # Build locationsInMesh block from database
        locs = self.db.locations_in_mesh
        if len(locs) == 1 and not locs[0].get("name"):
            # Single unnamed location: use simple locationInMesh
            loc_line = f"    locationInMesh ({locs[0]['x']} {locs[0]['y']} {locs[0]['z']});"
        else:
            # Multiple locations or named: use locationsInMesh
            loc_entries = []
            for loc in locs:
                name = loc.get("name", "")
                if name:
                    loc_entries.append(
                        f"        {{\n            name {name};\n"
                        f"            (({loc['x']} {loc['y']} {loc['z']}));\n        }}")
                else:
                    loc_entries.append(
                        f"        (({loc['x']} {loc['y']} {loc['z']}))")
            loc_line = "    locationsInMesh\n    (\n" + "\n".join(loc_entries) + "\n    );"

        body = f"""castellatedMesh {s.get('castellatedMesh', 'true')};
snap            {s.get('snap', 'true')};
addLayers       {s.get('addLayers', 'true')};

geometry
{{
{geom_block}
}};

castellatedMeshControls
{{
    maxLocalCells       {s.get('maxLocalCells', 100000)};
    maxGlobalCells      {s.get('maxGlobalCells', 2000000)};
    minRefinementCells  {s.get('minRefinementCells', 10)};
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels {s.get('nCellsBetweenLevels', 3)};

    features
    (
{features_block}
    );

    refinementSurfaces
    {{
{refine_block}
    }}

    resolveFeatureAngle {s.get('resolveFeatureAngle', 30)};

    refinementRegions
    {{
{ref_regions_block}
    }}

{loc_line}
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch    {s.get('nSmoothPatch', 3)};
    tolerance       {s.get('snapTolerance', 2.0)};
    nSolveIter      {s.get('nSolveIter', 100)};
    nRelaxIter      {s.get('nRelaxIter', 5)};
    nFeatureSnapIter {s.get('nFeatureSnapIter', 10)};
    implicitFeatureSnap {s.get('implicitFeatureSnap', 'true')};
    explicitFeatureSnap false;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes   true;
    layers
    {{
{layer_block}
    }}
    expansionRatio      {s.get('expansionRatio', 1.2)};
    finalLayerThickness {s.get('finalLayerThickness', 0.5)};
    minThickness        {s.get('minThickness', 0.1)};
    nGrow               0;
    featureAngle        {s.get('featureAngle', 130)};
    nRelaxIter          5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals      3;
    nSmoothThickness    10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle  90;
    nBufferCellsNoExtrude 0;
    nLayerIter          50;
}}

meshQualityControls
{{
    maxNonOrtho         {s.get('maxNonOrtho', 65)};
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave          {s.get('maxConcave', 80)};
    minVol              {s.get('minVol', '1e-13')};
    minTetQuality       1e-15;
    minArea             -1;
    minTwist            0.02;
    minDeterminant      {s.get('minDeterminant', 0.001)};
    minFaceWeight       0.05;
    minVolRatio         0.01;
    minTriangleTwist    -1;
    nSmoothScale        4;
    errorReduction      0.75;
    relaxed
    {{
        maxNonOrtho     75;
    }}
}}

debug 0;
mergeTolerance 1e-6;"""
        return h + "\n" + body + FOOTER

    def _gen_surface_feature_extract(self, s):
        dict_name = self._v.surface_feature_dict_name
        h = self._h("dictionary", "system", dict_name)
        angle = s.get('includedAngle', 150)

        if self._v.is_org:
            # openfoam.org (v6+): surfaceFeaturesDict
            # Per-surface named blocks with surfaces (...) list
            entries = []
            for entry in self.db.stl_entries:
                name = entry['stem']
                entries.append(f"""{name}
{{
    surfaces ("{name}.stl");

    includedAngle   {angle};

    writeObj        yes;
}}""")
            body = "\n\n".join(entries) or "// No STL files"
        else:
            # openfoam.com: surfaceFeatureExtractDict
            # Per-STL blocks with extractionMethod + extractFromSurfaceCoeffs
            entries = []
            for entry in self.db.stl_entries:
                entries.append(f"""{entry['stem']}.stl
{{
    extractionMethod    extractFromSurface;

    extractFromSurfaceCoeffs
    {{
        includedAngle   {angle};
    }}

    writeObj            yes;
}}""")
            body = "\n\n".join(entries) or "// No STL files"

        return h + "\n" + body + FOOTER

    def _gen_gravity(self, s):
        h = self._h("uniformDimensionedVectorField", "constant", "g")
        gx = s.get("gx", 0)
        gy = s.get("gy", 0)
        gz = s.get("gz", -9.81)
        return h + f"\ndimensions      [0 1 -2 0 0 0 0];\nvalue           ({gx} {gy} {gz});" + FOOTER

    def _gen_setfields_dict(self, s):
        h = self._h("dictionary", "system", "setFieldsDict")
        default_alpha = s.get("defaultAlpha", 0)

        body = f"defaultFieldValues\n(\n    volScalarFieldValue alpha.water {default_alpha}\n);\n"

        regions = []

        # Box region
        if s.get("useBox", "true") == "true":
            box_alpha = s.get("boxAlpha", 1)
            min_x = s.get("boxMinX", -1e6)
            min_y = s.get("boxMinY", -1e6)
            min_z = s.get("boxMinZ", -1e6)
            max_x = s.get("boxMaxX", 1e6)
            max_y = s.get("boxMaxY", 0)
            max_z = s.get("boxMaxZ", 1e6)
            regions.append(f"""    boxToCell
    {{
        box ({min_x} {min_y} {min_z}) ({max_x} {max_y} {max_z});
        fieldValues
        (
            volScalarFieldValue alpha.water {box_alpha}
        );
    }}""")

        # Cylinder region
        if s.get("useCylinder", "false") == "true":
            cyl_alpha = s.get("cylAlpha", 1)
            p1 = f"({s.get('cylP1X', 0)} {s.get('cylP1Y', 0)} {s.get('cylP1Z', 0)})"
            p2 = f"({s.get('cylP2X', 0)} {s.get('cylP2Y', 1)} {s.get('cylP2Z', 0)})"
            r = s.get("cylRadius", 0.1)
            regions.append(f"""    cylinderToCell
    {{
        p1 {p1};
        p2 {p2};
        radius {r};
        fieldValues
        (
            volScalarFieldValue alpha.water {cyl_alpha}
        );
    }}""")

        # Sphere region
        if s.get("useSphere", "false") == "true":
            sph_alpha = s.get("sphAlpha", 1)
            centre = f"({s.get('sphCX', 0)} {s.get('sphCY', 0)} {s.get('sphCZ', 0)})"
            r = s.get("sphRadius", 0.1)
            regions.append(f"""    sphereToCell
    {{
        centre {centre};
        radius {r};
        fieldValues
        (
            volScalarFieldValue alpha.water {sph_alpha}
        );
    }}""")

        if regions:
            body += "\nregions\n(\n" + "\n\n".join(regions) + "\n);"
        else:
            body += "\nregions\n(\n);"

        return h + "\n" + body + FOOTER

    def _gen_fv_options(self, s):
        """Generate system/fvOptions content for preview and export."""
        from fv_options import FV_OPTIONS_CATALOG

        h = self._h("dictionary", "system", "fvOptions")
        fv_opts = self.db.fv_options
        if not fv_opts:
            return h + "\n// No fvOptions configured" + FOOTER

        entries = []
        for name, opt_data in fv_opts.items():
            opt_type = opt_data.get("type", "")
            params = opt_data.get("params", {})
            catalog = FV_OPTIONS_CATALOG.get(opt_type)
            if catalog and catalog.get("generator"):
                entries.append(catalog["generator"](name, params))

        body = "\n\n".join(entries) if entries else "// No fvOptions configured"
        return h + "\n" + body + FOOTER

    # ================================================================ #
    #  Boundary condition generation
    # ================================================================ #

    def _gen_bc(self, field: str, patch_bcs: dict, internal_field: str) -> str:
        from bc_types import format_bc_block

        default_info = {
            "p":       {"dim": "[0 2 -2 0 0 0 0]", "class": "volScalarField"},
            "p_rgh":   {"dim": "[1 -1 -2 0 0 0 0]", "class": "volScalarField"},
            "U":       {"dim": "[0 1 -1 0 0 0 0]",  "class": "volVectorField"},
            "T":       {"dim": "[0 0 0 1 0 0 0]",   "class": "volScalarField"},
            "alpha.water": {"dim": "[0 0 0 0 0 0 0]", "class": "volScalarField"},
            "k":       {"dim": "[0 2 -2 0 0 0 0]",  "class": "volScalarField"},
            "epsilon": {"dim": "[0 2 -3 0 0 0 0]",  "class": "volScalarField"},
            "omega":   {"dim": "[0 0 -1 0 0 0 0]",  "class": "volScalarField"},
            "nut":     {"dim": "[0 2 -1 0 0 0 0]",  "class": "volScalarField"},
            "alphat":  {"dim": "[1 -1 -1 0 0 0 0]", "class": "volScalarField"},
        }
        tmpl = self.db.template
        if tmpl and hasattr(tmpl, 'FIELD_INFO'):
            info = tmpl.FIELD_INFO.get(field, default_info.get(field, {}))
        else:
            info = default_info.get(field, {})

        if not info:
            return ""

        h = self._h(info["class"], "0", field)
        dim = info.get("dim", "[0 0 0 0 0 0 0]")

        bc_blocks = []
        for patch_name, fields_dict in patch_bcs.items():
            if field in fields_dict:
                bc_type, params = fields_dict[field]
                bc_blocks.append(format_bc_block(patch_name, field, bc_type, params))

        body = f"""dimensions      {dim};

internalField   {internal_field};

boundaryField
{{
{chr(10).join(bc_blocks)}
}}"""
        return h + "\n" + body + FOOTER

    # ================================================================ #
    #  Run scripts
    # ================================================================ #

    def _write_allrun(self, case: Path):
        lines = ["#!/bin/bash", "cd ${0%/*} || exit 1", "",
                 ". ${WM_PROJECT_DIR:?}/bin/tools/RunFunctions", ""]
        if self.db.has_stl:
            sf_cmd = self._v.surface_feature_command
            lines += ["# Extract surface features", f"runApplication {sf_cmd}", "",
                       "# Generate background mesh", "runApplication blockMesh", "",
                       "# Run snappyHexMesh", "runApplication snappyHexMesh -overwrite", ""]

        # setFields for VOF (interFoam)
        tmpl = self.db.template
        if tmpl and hasattr(tmpl, 'BASE_FIELDS') and "alpha.water" in tmpl.BASE_FIELDS:
            lines += ["# Set initial phase distribution", "runApplication setFields", ""]

        lines += ["# Decompose and run", "runApplication decomposePar",
                   f"runParallel {self.db.solver}", "runApplication reconstructPar", "",
                   "#" + "-" * 78]
        script = case / "Allrun"
        with open(script, "w") as f:
            f.write("\n".join(lines))
        script.chmod(0o755)

    def _write_allclean(self, case: Path):
        lines = ["#!/bin/bash", "cd ${0%/*} || exit 1", "",
                 ". ${WM_PROJECT_DIR:?}/bin/tools/CleanFunctions", "",
                 "cleanCase", "", "#" + "-" * 78]
        script = case / "Allclean"
        with open(script, "w") as f:
            f.write("\n".join(lines))
        script.chmod(0o755)
