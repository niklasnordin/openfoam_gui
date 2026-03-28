"""
Shared dictionary specifications reused across solver templates.

Provides turbulence model coefficients/descriptions, mesh dicts, and
standard BC field specs to avoid repeating 500+ lines in every template.

Usage in a template file:
    from shared_dicts import (TURB_GROUPS_FULL, TURB_INFO, TURB_MODELS_INCOMP,
                              TURB_MODELS_COMP, MESH_BLOCK, MESH_SNAPPY, MESH_SFE,
                              bc_p, bc_u, bc_k, bc_epsilon, bc_omega, bc_nut, ...)
"""

from __future__ import annotations

# ------------------------------------------------------------------ #
#  Turbulence models field mappings
# ------------------------------------------------------------------ #

TURB_MODELS_INCOMP = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut"]},
    "SpalartAllmaras": {"fields": ["nut"]},
}

TURB_MODELS_COMP = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut", "alphat"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut", "alphat"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut", "alphat"]},
    "SpalartAllmaras": {"fields": ["nut", "alphat"]},
}

# ------------------------------------------------------------------ #
#  Turbulence coefficient groups (RAS + LES)
# ------------------------------------------------------------------ #

TURB_COEFF_GROUPS = {
    "kEpsilon Coefficients|simulationType=RAS&RASModel=kEpsilon": [
        ("Cmu", "kEps_Cmu", 0.09, "float", (0.0, 1.0)),
        ("C1", "kEps_C1", 1.44, "float", (0.0, 5.0)),
        ("C2", "kEps_C2", 1.92, "float", (0.0, 5.0)),
        ("sigmaK", "kEps_sigmaK", 1.0, "float", (0.0, 5.0)),
        ("sigmaEps", "kEps_sigmaEps", 1.3, "float", (0.0, 5.0)),
    ],
    "kOmegaSST Coefficients|simulationType=RAS&RASModel=kOmegaSST": [
        ("alphaK1", "sst_alphaK1", 0.85, "float", (0.0, 2.0)),
        ("alphaK2", "sst_alphaK2", 1.0, "float", (0.0, 2.0)),
        ("alphaOmega1", "sst_alphaOmega1", 0.5, "float", (0.0, 2.0)),
        ("alphaOmega2", "sst_alphaOmega2", 0.856, "float", (0.0, 2.0)),
        ("gamma1", "sst_gamma1", 0.5556, "float", (0.0, 2.0)),
        ("gamma2", "sst_gamma2", 0.4403, "float", (0.0, 2.0)),
        ("beta1", "sst_beta1", 0.075, "float", (0.0, 1.0)),
        ("beta2", "sst_beta2", 0.0828, "float", (0.0, 1.0)),
        ("betaStar", "sst_betaStar", 0.09, "float", (0.0, 1.0)),
        ("a1", "sst_a1", 0.31, "float", (0.0, 1.0)),
        ("c1", "sst_c1", 10.0, "float", (0.0, 20.0)),
    ],
    "realizableKE Coefficients|simulationType=RAS&RASModel=realizableKE": [
        ("A0", "rke_A0", 4.0, "float", (0.0, 10.0)),
        ("C2", "rke_C2", 1.9, "float", (0.0, 5.0)),
        ("sigmaK", "rke_sigmaK", 1.0, "float", (0.0, 5.0)),
        ("sigmaEps", "rke_sigmaEps", 1.2, "float", (0.0, 5.0)),
    ],
    "SpalartAllmaras Coefficients|simulationType=RAS&RASModel=SpalartAllmaras": [
        ("sigmaNut", "sa_sigmaNut", 0.66666, "float", (0.0, 2.0)),
        ("Cb1", "sa_Cb1", 0.1355, "float", (0.0, 1.0)),
        ("Cb2", "sa_Cb2", 0.622, "float", (0.0, 2.0)),
        ("Cw2", "sa_Cw2", 0.3, "float", (0.0, 1.0)),
        ("Cw3", "sa_Cw3", 2.0, "float", (0.0, 5.0)),
        ("Cv1", "sa_Cv1", 7.1, "float", (0.0, 15.0)),
        ("kappa", "sa_kappa", 0.41, "float", (0.0, 1.0)),
    ],
    "LRR Coefficients|simulationType=RAS&RASModel=LRR": [
        ("Cmu", "lrr_Cmu", 0.09, "float", (0.0, 1.0)),
        ("C1", "lrr_C1", 1.8, "float", (0.0, 5.0)),
        ("C2", "lrr_C2", 0.6, "float", (0.0, 5.0)),
        ("Ceps1", "lrr_Ceps1", 1.44, "float", (0.0, 5.0)),
        ("Ceps2", "lrr_Ceps2", 1.92, "float", (0.0, 5.0)),
        ("Cs", "lrr_Cs", 0.25, "float", (0.0, 1.0)),
        ("Ceps", "lrr_Ceps", 0.15, "float", (0.0, 1.0)),
    ],
    "LaunderSharmaKE Coefficients|simulationType=RAS&RASModel=LaunderSharmaKE": [
        ("Cmu", "lske_Cmu", 0.09, "float", (0.0, 1.0)),
        ("C1", "lske_C1", 1.44, "float", (0.0, 5.0)),
        ("C2", "lske_C2", 1.92, "float", (0.0, 5.0)),
        ("sigmaK", "lske_sigmaK", 1.0, "float", (0.0, 5.0)),
        ("sigmaEps", "lske_sigmaEps", 1.3, "float", (0.0, 5.0)),
    ],
    "Smagorinsky Coefficients|simulationType=LES&LESModel=Smagorinsky": [
        ("Ck", "smag_Ck", 0.094, "float", (0.0, 1.0)),
        ("Ce", "smag_Ce", 1.048, "float", (0.0, 5.0)),
    ],
    "kEqn Coefficients|simulationType=LES&LESModel=kEqn": [
        ("Ck", "keqn_Ck", 0.094, "float", (0.0, 1.0)),
        ("Ce", "keqn_Ce", 1.048, "float", (0.0, 5.0)),
    ],
    "WALE Coefficients|simulationType=LES&LESModel=WALE": [
        ("Cw", "wale_Cw", 0.325, "float", (0.0, 1.0)),
        ("Ck", "wale_Ck", 0.094, "float", (0.0, 1.0)),
        ("Ce", "wale_Ce", 1.048, "float", (0.0, 5.0)),
    ],
    "DES Coefficients|simulationType=LES&LESModel=SpalartAllmarasDES": [
        ("CDES", "des_CDES", 0.65, "float", (0.0, 2.0)),
        ("sigmaNut", "des_sigmaNut", 0.66666, "float", (0.0, 2.0)),
        ("kappa", "des_kappa", 0.41, "float", (0.0, 1.0)),
        ("Cb1", "des_Cb1", 0.1355, "float", (0.0, 1.0)),
        ("Cb2", "des_Cb2", 0.622, "float", (0.0, 2.0)),
    ],
    "DDES Coefficients|simulationType=LES&LESModel=SpalartAllmarasDDES": [
        ("CDES", "ddes_CDES", 0.65, "float", (0.0, 2.0)),
        ("sigmaNut", "ddes_sigmaNut", 0.66666, "float", (0.0, 2.0)),
        ("kappa", "ddes_kappa", 0.41, "float", (0.0, 1.0)),
        ("Cb1", "ddes_Cb1", 0.1355, "float", (0.0, 1.0)),
        ("Cb2", "ddes_Cb2", 0.622, "float", (0.0, 2.0)),
    ],
    "IDDES Coefficients|simulationType=LES&LESModel=SpalartAllmarasIDDES": [
        ("CDES", "iddes_CDES", 0.65, "float", (0.0, 2.0)),
        ("sigmaNut", "iddes_sigmaNut", 0.66666, "float", (0.0, 2.0)),
        ("kappa", "iddes_kappa", 0.41, "float", (0.0, 1.0)),
        ("Cb1", "iddes_Cb1", 0.1355, "float", (0.0, 1.0)),
        ("Cb2", "iddes_Cb2", 0.622, "float", (0.0, 2.0)),
    ],
}

# ------------------------------------------------------------------ #
#  Turbulence model descriptions (HTML)
# ------------------------------------------------------------------ #

TURB_DESCRIPTIONS = {
    "kEpsilon": "<h3>Standard k-\u03b5</h3><p>C\u03bc=0.09, C1=1.44, C2=1.92</p>",
    "kOmegaSST": "<h3>k-\u03c9 SST</h3><p>Menter's blended model. Best general-purpose choice.</p>",
    "realizableKE": "<h3>Realizable k-\u03b5</h3><p>Variable C\u03bc. Better for swirl/curvature.</p>",
    "SpalartAllmaras": "<h3>Spalart-Allmaras</h3><p>One-equation model. Good for external aero.</p>",
    "LRR": "<h3>LRR Reynolds Stress</h3><p>7 equations. Captures anisotropy.</p>",
    "LaunderSharmaKE": "<h3>Launder-Sharma k-\u03b5</h3><p>Low-Re, resolves viscous sublayer (y+\u22481).</p>",
    "Smagorinsky": "<h3>Smagorinsky</h3><p>Algebraic SGS. Ck=0.094, Ce=1.048.</p>",
    "kEqn": "<h3>kEqn</h3><p>One-equation SGS transport model.</p>",
    "dynamicKEqn": "<h3>Dynamic kEqn</h3><p>Dynamic Ck via Germano identity.</p>",
    "WALE": "<h3>WALE</h3><p>Proper wall scaling, no damping functions.</p>",
    "DeardorffDiffStress": "<h3>Deardorff</h3><p>Full SGS stress model (6 extra eqs).</p>",
    "SpalartAllmarasDES": "<h3>SA-DES</h3><p>RANS near walls, LES in separated regions.</p>",
    "SpalartAllmarasDDES": "<h3>SA-DDES</h3><p>Delayed DES. Shields BL from LES.</p>",
    "SpalartAllmarasIDDES": "<h3>SA-IDDES</h3><p>Improved DDES + WMLES capability.</p>",
}

TURB_INFO = {
    "field": "RASModel",
    "field_map": {"RAS": "RASModel", "LES": "LESModel"},
    "condition_field": "simulationType",
    "hide_values": ["laminar"],
    "descriptions": TURB_DESCRIPTIONS,
}


def make_turb_properties_dict(extra_groups: dict | None = None) -> dict:
    """Build a complete turbulenceProperties dict spec with all coefficients."""
    groups = {
        "Simulation Type": [
            ("Simulation Type", "simulationType", "RAS", "combo",
             ["RAS", "LES", "laminar"]),
        ],
        "RAS Settings|simulationType=RAS": [
            ("RAS Model", "RASModel", "kEpsilon", "combo",
             ["kEpsilon", "kOmegaSST", "realizableKE",
              "SpalartAllmaras", "LRR", "LaunderSharmaKE"]),
            ("Turbulence", "turbulence", "on", "combo", ["on", "off"]),
            ("Print Coefficients", "printCoeffs", "on", "combo", ["on", "off"]),
        ],
        "LES Settings|simulationType=LES": [
            ("LES Model", "LESModel", "Smagorinsky", "combo",
             ["Smagorinsky", "kEqn", "dynamicKEqn", "WALE",
              "DeardorffDiffStress", "SpalartAllmarasDES",
              "SpalartAllmarasDDES", "SpalartAllmarasIDDES"]),
            ("LES Delta", "delta", "cubeRootVol", "combo",
             ["cubeRootVol", "vanDriest", "smooth", "Prandtl"]),
            ("Turbulence", "turbulence", "on", "combo", ["on", "off"]),
            ("Print Coefficients", "printCoeffs", "on", "combo", ["on", "off"]),
        ],
    }
    groups.update(TURB_COEFF_GROUPS)
    if extra_groups:
        groups.update(extra_groups)
    return {
        "path": "constant/turbulenceProperties",
        "label": "turbulenceProperties",
        "icon": "SP_BrowserReload",
        "groups": groups,
        "info": TURB_INFO,
    }


# ------------------------------------------------------------------ #
#  Standard dict specs
# ------------------------------------------------------------------ #

DECOMPOSE_PAR_DICT = {
    "path": "system/decomposeParDict",
    "label": "decomposeParDict",
    "icon": "SP_ComputerIcon",
    "groups": {
        "Parallel Decomposition": [
            ("Number of Processors", "nProcs", 4, "int", (1, 1024)),
            ("Method", "method", "scotch", "combo",
             ["scotch", "simple", "hierarchical", "kahip"]),
        ],
    },
}

THERMOPHYSICAL_PROPERTIES = {
    "path": "constant/thermophysicalProperties",
    "label": "thermophysicalProperties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Thermo Type": [
            ("Type", "thermoType", "hePsiThermo", "combo",
             ["hePsiThermo", "heRhoThermo"]),
            ("Mixture", "mixture", "pureMixture", "combo", ["pureMixture"]),
            ("Transport", "transport", "sutherland", "combo",
             ["sutherland", "const", "polynomial"]),
            ("Thermo", "thermo", "hConst", "combo",
             ["hConst", "janaf", "hPolynomial"]),
            ("Equation of State", "equationOfState", "perfectGas", "combo",
             ["perfectGas", "rhoConst", "incompressiblePerfectGas",
              "PengRobinsonGas"]),
            ("Specie", "specie", "specie", "combo", ["specie"]),
            ("Energy", "energy", "sensibleEnthalpy", "combo",
             ["sensibleEnthalpy", "sensibleInternalEnergy"]),
        ],
        "Mixture \u2014 Specie": [
            ("Molecular Weight [kg/kmol]", "molWeight", "28.96", "str", None),
        ],
        "Mixture \u2014 Thermodynamics": [
            ("Cp [J/(kg\u00b7K)]", "Cp", "1004.5", "str", None),
            ("Hf [J/kg]", "Hf", "0", "str", None),
        ],
        "Mixture \u2014 Transport (Sutherland)": [
            ("As [kg/(m\u00b7s\u00b7\u221aK)]", "As", "1.458e-06", "str", None),
            ("Ts [K]", "Ts", "110.4", "str", None),
        ],
        "Mixture \u2014 Transport (const)": [
            ("mu [Pa\u00b7s]", "mu", "1.84e-05", "str", None),
            ("Pr [-]", "Pr", "0.7", "str", None),
        ],
    },
}

GRAVITY = {
    "path": "constant/g",
    "label": "g (gravity)",
    "icon": "SP_ArrowDown",
    "groups": {
        "Gravity Vector": [
            ("g_x [m/s\u00b2]", "gx", 0, "float", (-100, 100)),
            ("g_y [m/s\u00b2]", "gy", 0, "float", (-100, 100)),
            ("g_z [m/s\u00b2]", "gz", -9.81, "float", (-100, 100)),
        ],
    },
}

BLOCK_MESH_DICT = {
    "path": "system/blockMeshDict",
    "label": "blockMeshDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Domain Size": [
            ("X min", "xMin", -1.0, "float", (-1e6, 1e6)),
            ("X max", "xMax", 1.0, "float", (-1e6, 1e6)),
            ("Y min", "yMin", -1.0, "float", (-1e6, 1e6)),
            ("Y max", "yMax", 1.0, "float", (-1e6, 1e6)),
            ("Z min", "zMin", -1.0, "float", (-1e6, 1e6)),
            ("Z max", "zMax", 1.0, "float", (-1e6, 1e6)),
        ],
        "Cell Counts": [
            ("Cells X", "cellsX", 20, "int", (1, 10000)),
            ("Cells Y", "cellsY", 20, "int", (1, 10000)),
            ("Cells Z", "cellsZ", 20, "int", (1, 10000)),
            ("Cell Size [m]", "cellSize", 0.1, "float", (1e-6, 100.0)),
            ("Margin [%]", "margin", 10, "float", (0, 200)),
        ],
        "Cell Grading": [
            ("Grading X", "gradeX", 1.0, "float", (0.001, 1000.0)),
            ("Grading Y", "gradeY", 1.0, "float", (0.001, 1000.0)),
            ("Grading Z", "gradeZ", 1.0, "float", (0.001, 1000.0)),
        ],
    },
}

SNAPPY_HEX_MESH_DICT = {
    "path": "system/snappyHexMeshDict",
    "label": "snappyHexMeshDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Mesh Steps": [
            ("Castellated Mesh", "castellatedMesh", "true", "combo", ["true", "false"]),
            ("Snap", "snap", "true", "combo", ["true", "false"]),
            ("Add Layers", "addLayers", "true", "combo", ["true", "false"]),
        ],
        "Castellated Mesh Controls": [
            ("Max Local Cells", "maxLocalCells", 100000, "int", (1000, 100000000)),
            ("Max Global Cells", "maxGlobalCells", 2000000, "int", (10000, 1000000000)),
            ("Min Refinement Cells", "minRefinementCells", 10, "int", (0, 10000)),
            ("Cells Between Levels", "nCellsBetweenLevels", 3, "int", (1, 20)),
            ("Resolve Feature Angle", "resolveFeatureAngle", 30, "int", (0, 180)),
        ],
        "Snap Controls": [
            ("Smooth Patch", "nSmoothPatch", 3, "int", (0, 20)),
            ("Snap Tolerance", "snapTolerance", 2.0, "float", (0.1, 10.0)),
            ("Solve Iterations", "nSolveIter", 100, "int", (1, 1000)),
            ("Relax Iterations", "nRelaxIter", 5, "int", (1, 100)),
            ("Feature Snap Iterations", "nFeatureSnapIter", 10, "int", (1, 100)),
            ("Implicit Feature Snap", "implicitFeatureSnap", "true", "combo", ["true", "false"]),
        ],
        "Layer Controls": [
            ("Expansion Ratio", "expansionRatio", 1.2, "float", (1.0, 3.0)),
            ("Final Layer Thickness", "finalLayerThickness", 0.5, "float", (0.01, 1.0)),
            ("Min Thickness", "minThickness", 0.1, "float", (0.001, 1.0)),
            ("Feature Angle", "featureAngle", 130, "int", (0, 180)),
            ("Layer Iterations", "nLayerIter", 50, "int", (1, 200)),
        ],
        "Mesh Quality": [
            ("Max Non-Orthogonality", "maxNonOrtho", 65, "int", (0, 180)),
            ("Max Concavity", "maxConcave", 80, "int", (0, 180)),
            ("Min Vol", "minVol", "1e-13", "str", None),
            ("Min Determinant", "minDeterminant", 0.001, "float", (0, 1)),
        ],
    },
}

SURFACE_FEATURE_EXTRACT_DICT = {
    "path": "system/surfaceFeatureExtractDict",
    "label": "surfaceFeatureExtractDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Feature Extraction": [
            ("Included Angle [\u00b0]", "includedAngle", 150, "int", (0, 180)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  Standard BC field specs
# ------------------------------------------------------------------ #

def bc_p(internal=0, dim="[0 2 -2 0 0 0 0]", unit="m\u00b2/s\u00b2") -> dict:
    return {"path": "0/p", "label": "p (pressure)", "icon": "SP_ArrowDown",
            "groups": {"Pressure Field": [
                (f"Internal Field [{unit}]", "pInternal", internal, "float", (-1e9, 1e9)),
            ]}}

def bc_p_rgh() -> dict:
    return {"path": "0/p_rgh", "label": "p_rgh (pressure - hydrostatic)",
            "icon": "SP_ArrowDown",
            "groups": {"p_rgh Field": [
                ("Internal Field [Pa]", "p_rghInternal", 0, "float", (-1e9, 1e9)),
            ]}}

def bc_u(ux=10.0) -> dict:
    return {"path": "0/U", "label": "U (velocity)", "icon": "SP_ArrowForward",
            "groups": {"Velocity Field": [
                ("Ux [m/s]", "Ux", ux, "float", (-1e6, 1e6)),
                ("Uy [m/s]", "Uy", 0.0, "float", (-1e6, 1e6)),
                ("Uz [m/s]", "Uz", 0.0, "float", (-1e6, 1e6)),
            ]}}

def bc_t() -> dict:
    return {"path": "0/T", "label": "T (temperature)", "icon": "SP_MediaVolume",
            "groups": {"Temperature Field": [
                ("Internal Field [K]", "TInternal", 300, "float", (0, 10000)),
            ]}}

BC_K = {"path": "0/k", "label": "k (turb. kinetic energy)", "icon": "SP_MediaVolume",
        "groups": {"k Field": [("Internal / Inlet Value [m\u00b2/s\u00b2]", "kInternal", "0.1", "str", None)]}}

BC_EPSILON = {"path": "0/epsilon", "label": "epsilon (dissipation)", "icon": "SP_MediaVolume",
              "groups": {"Epsilon Field": [("Internal / Inlet Value [m\u00b2/s\u00b3]", "epsilonInternal", "0.1", "str", None)]}}

BC_OMEGA = {"path": "0/omega", "label": "omega (specific dissipation)", "icon": "SP_MediaVolume",
            "groups": {"Omega Field": [("Internal / Inlet Value [1/s]", "omegaInternal", "1.0", "str", None)]}}

BC_NUT = {"path": "0/nut", "label": "nut (turb. viscosity)", "icon": "SP_MediaVolume",
          "groups": {"nut Field": [("Internal Value [m\u00b2/s]", "nutInternal", "0", "str", None)]}}

BC_ALPHAT = {"path": "0/alphat", "label": "alphat (turb. thermal diffusivity)", "icon": "SP_MediaVolume",
             "groups": {"alphat Field": [("Internal Value [kg/(m\u00b7s)]", "alphatInternal", "0", "str", None)]}}
