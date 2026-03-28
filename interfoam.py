"""
Template for interFoam solver.
Two-phase Volume of Fluid (VOF) solver for immiscible, incompressible fluids.

Key features:
  - Phase fraction field alpha.water (VOF)
  - p_rgh (pressure minus hydrostatic) instead of p
  - Two-phase transportProperties (water + air with separate nu, rho)
  - Gravity vector g
  - MULES for alpha transport
  - setFieldsDict for initial phase distribution
  - Adjustable time stepping with maxCo and maxAlphaCo

Each field spec: (label, key, default, type, options)
"""

from __future__ import annotations

SOLVER_NAME = "interFoam"
SOLVER_DESCRIPTION = "Two-phase VOF solver for immiscible, incompressible fluids"

# Base fields always active — alpha.water is the VOF phase fraction
BASE_FIELDS = ["p_rgh", "U", "alpha.water"]

TURBULENCE_MODELS = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut"]},
    "SpalartAllmaras": {"fields": ["nut"]},
}

# Field metadata — p_rgh has hydrostatic-removed pressure dimensions
FIELD_INFO = {
    "p_rgh":        {"dim": "[1 -1 -2 0 0 0 0]", "class": "volScalarField",
                     "internal": "uniform 0"},
    "U":            {"dim": "[0 1 -1 0 0 0 0]",   "class": "volVectorField",
                     "internal": "uniform (0 0 0)"},
    "alpha.water":  {"dim": "[0 0 0 0 0 0 0]",    "class": "volScalarField",
                     "internal": "uniform 0"},
    "k":            {"dim": "[0 2 -2 0 0 0 0]",    "class": "volScalarField",
                     "internal": "uniform 0.1"},
    "epsilon":      {"dim": "[0 2 -3 0 0 0 0]",    "class": "volScalarField",
                     "internal": "uniform 0.1"},
    "omega":        {"dim": "[0 0 -1 0 0 0 0]",    "class": "volScalarField",
                     "internal": "uniform 1.0"},
    "nut":          {"dim": "[0 2 -1 0 0 0 0]",    "class": "volScalarField",
                     "internal": "uniform 0"},
}


# ------------------------------------------------------------------ #
#  controlDict — transient with adjustable time step + alpha Courant
# ------------------------------------------------------------------ #

CONTROL_DICT = {
    "path": "system/controlDict",
    "label": "controlDict",
    "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "interFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo",
             ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo",
             ["endTime", "writeNow", "noWriteNow", "nextWrite"]),
            ("End Time", "endTime", 1.0, "float", (0, 1e9)),
            ("Delta T", "deltaT", 0.001, "float", (1e-12, 1e6)),
            ("Adjustable Time Step", "adjustTimeStep", "yes", "combo",
             ["yes", "no"]),
            ("Max Courant Number", "maxCo", 1.0, "float", (0.01, 100.0)),
            ("Max Alpha Courant", "maxAlphaCo", 1.0, "float", (0.01, 100.0)),
            ("Max Delta T", "maxDeltaT", 1.0, "float", (1e-9, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "adjustableRunTime", "combo",
             ["timeStep", "runTime", "adjustableRunTime", "cpuTime", "clockTime"]),
            ("Write Interval", "writeInterval", 0.05, "float", (1e-9, 100000)),
            ("Purge Write", "purgeWrite", 0, "int", (0, 1000)),
            ("Write Format", "writeFormat", "ascii", "combo", ["ascii", "binary"]),
            ("Write Precision", "writePrecision", 8, "int", (1, 20)),
            ("Write Compression", "writeCompression", "off", "combo",
             ["off", "on", "compressed", "uncompressed"]),
        ],
        "Time Format": [
            ("Time Format", "timeFormat", "general", "combo",
             ["fixed", "scientific", "general"]),
            ("Time Precision", "timePrecision", 6, "int", (1, 20)),
            ("Run Time Modifiable", "runTimeModifiable", "true", "combo",
             ["true", "false"]),
        ],
    },
}


# ------------------------------------------------------------------ #
#  fvSchemes — includes MULES for alpha transport
# ------------------------------------------------------------------ #

FV_SCHEMES = {
    "path": "system/fvSchemes",
    "label": "fvSchemes",
    "icon": "SP_FileDialogContentsView",
    "groups": {
        "Time Schemes": [
            ("ddt Scheme", "ddtScheme", "Euler", "combo",
             ["Euler", "backward", "CrankNicolson", "localEuler"]),
            ("CrankNicolson Coeff (0=Euler, 1=pure CN)", "ddtCoeff", 0.9,
             "float", (0.0, 1.0)),
        ],
        "Gradient Schemes": [
            ("Default Method", "gradMethod", "Gauss", "combo",
             ["Gauss", "leastSquares", "fourth"]),
            ("Default Interpolation", "gradInterp", "linear", "combo",
             ["linear", "pointLinear", "leastSquares"]),
            ("Default Limiter", "gradLimiter", "none", "combo",
             ["none", "cellLimited", "faceLimited"]),
            ("Limiter Coefficient", "gradLimitCoeff", 1.0, "float", (0.0, 1.0)),
            ("grad(U) Method", "gradU_method", "cellLimited Gauss", "combo",
             ["Gauss", "cellLimited Gauss", "faceLimited Gauss", "leastSquares"]),
            ("grad(U) Interpolation", "gradU_interp", "linear", "combo",
             ["linear", "pointLinear", "leastSquares"]),
            ("grad(U) Limiter Coeff", "gradU_coeff", 1.0, "float", (0.0, 1.0)),
        ],
        "div(phi,U)": [
            ("Bounded", "divU_bounded", "", "combo", ["bounded", ""]),
            ("Interpolation", "divU_interp", "linearUpwindV", "combo",
             ["upwind", "linearUpwind", "linearUpwindV", "linear",
              "limitedLinear", "LUST", "vanLeer", "MUSCL", "Minmod"]),
            ("Gradient / Coeff", "divU_arg", "grad(U)", "combo",
             ["grad(U)", "default", "0.2", "0.5", "0.75", "1.0"]),
        ],
        "div(phi, turbulence)": [
            ("Bounded", "divTurb_bounded", "", "combo", ["bounded", ""]),
            ("Interpolation", "divTurb_interp", "upwind", "combo",
             ["upwind", "linearUpwind", "linear",
              "limitedLinear", "vanLeer", "MUSCL", "Minmod"]),
            ("Gradient / Coeff", "divTurb_arg", "default", "combo",
             ["default", "grad(k)", "grad(epsilon)", "grad(omega)",
              "0.2", "0.5", "0.75", "1.0"]),
        ],
        "Alpha Schemes": [
            ("Alpha div Scheme", "divAlpha_interp", "vanLeer", "combo",
             ["vanLeer", "vanAlbada", "MUSCL", "Minmod",
              "interfaceCompression", "isoAdvector"]),
            ("cAlpha (compression)", "cAlpha", 1, "int", (0, 4)),
            ("icAlpha (isocurve corr.)", "icAlpha", 0, "int", (0, 4)),
            ("nAlphaCorr", "nAlphaCorr", 2, "int", (1, 10)),
            ("nAlphaSubCycles", "nAlphaSubCycles", 1, "int", (1, 10)),
            ("MULESCorr", "MULESCorr", "yes", "combo", ["yes", "no"]),
        ],
        "Laplacian Schemes": [
            ("Interpolation", "lapInterp", "linear", "combo",
             ["linear", "harmonic", "localMax"]),
            ("snGrad Type", "lapSnGrad", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff (if limited)", "lapLimitCoeff", 0.5,
             "float", (0.0, 1.0)),
        ],
        "snGrad Schemes": [
            ("Default snGrad", "snGradType", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff (if limited)", "snGradLimitCoeff", 0.5,
             "float", (0.0, 1.0)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  fvSolution — PIMPLE with alpha sub-cycling
# ------------------------------------------------------------------ #

FV_SOLUTION = {
    "path": "system/fvSolution",
    "label": "fvSolution",
    "icon": "SP_FileDialogDetailedView",
    "groups": {
        "Alpha Solver": [
            ("Solver", "alphaSolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "alphaSmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "alphaTolerance", "1e-8", "str", None),
            ("Relative Tolerance", "alphaRelTol", "0", "str", None),
        ],
        "Pressure Solver": [
            ("Solver", "pSolver", "GAMG", "combo",
             ["GAMG", "PCG", "PBiCGStab", "smoothSolver"]),
            ("Smoother", "pSmoother", "DIC", "combo",
             ["GaussSeidel", "DIC", "DILU", "symGaussSeidel", "DICGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "pRelTol", "0.01", "str", None),
            ("pFinal Tolerance", "pFinalTol", "1e-8", "str", None),
        ],
        "Velocity Solver": [
            ("Solver", "USolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "USmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "UTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "URelTol", "0.01", "str", None),
        ],
        "Turbulence Solver": [
            ("Solver", "turbSolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "turbSmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "turbTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "turbRelTol", "0.01", "str", None),
        ],
        "PIMPLE Controls": [
            ("Outer Correctors", "nOuterCorrectors", 1, "int", (1, 50)),
            ("Correctors", "nCorrectors", 3, "int", (1, 10)),
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 0,
             "int", (0, 20)),
            ("Algorithm", "algorithm", "PIMPLE", "combo", ["PIMPLE"]),
            ("Momentum Predictor", "momentumPredictor", "no", "combo",
             ["yes", "no"]),
        ],
        "Relaxation Factors": [
            ("U Relaxation", "relaxU", 0.7, "float", (0.0, 1.0)),
            ("p_rgh Relaxation", "relaxP", 0.3, "float", (0.0, 1.0)),
            ("Turbulence Relaxation", "relaxTurb", 0.7, "float", (0.0, 1.0)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  decomposeParDict
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


# ------------------------------------------------------------------ #
#  transportProperties — two-phase
# ------------------------------------------------------------------ #

TRANSPORT_PROPERTIES = {
    "path": "constant/transportProperties",
    "label": "transportProperties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Phase 1 (water)": [
            ("Transport Model", "transportModel_water", "Newtonian", "combo",
             ["Newtonian", "CrossPowerLaw", "BirdCarreau"]),
            ("Kinematic Viscosity (nu) [m²/s]", "nu_water", "1e-06", "str", None),
            ("Density (rho) [kg/m³]", "rho_water", "1000", "str", None),
        ],
        "Phase 2 (air)": [
            ("Transport Model", "transportModel_air", "Newtonian", "combo",
             ["Newtonian", "CrossPowerLaw", "BirdCarreau"]),
            ("Kinematic Viscosity (nu) [m²/s]", "nu_air", "1.48e-05", "str", None),
            ("Density (rho) [kg/m³]", "rho_air", "1", "str", None),
        ],
        "Surface Tension": [
            ("Surface Tension (sigma) [N/m]", "sigma", "0.07", "str", None),
        ],
    },
}


# ------------------------------------------------------------------ #
#  Gravity
# ------------------------------------------------------------------ #

GRAVITY = {
    "path": "constant/g",
    "label": "g (gravity)",
    "icon": "SP_ArrowDown",
    "groups": {
        "Gravity Vector": [
            ("g_x [m/s²]", "gx", 0, "float", (-100, 100)),
            ("g_y [m/s²]", "gy", 0, "float", (-100, 100)),
            ("g_z [m/s²]", "gz", -9.81, "float", (-100, 100)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  turbulenceProperties
# ------------------------------------------------------------------ #

TURBULENCE_PROPERTIES = {
    "path": "constant/turbulenceProperties",
    "label": "turbulenceProperties",
    "icon": "SP_BrowserReload",
    "groups": {
        "Simulation Type": [
            ("Simulation Type", "simulationType", "RAS", "combo",
             ["RAS", "LES", "laminar"]),
        ],
        "RAS Settings|simulationType=RAS": [
            ("RAS Model", "RASModel", "kEpsilon", "combo",
             ["kEpsilon", "kOmegaSST", "realizableKE",
              "SpalartAllmaras", "LRR", "LaunderSharmaKE"]),
            ("Turbulence", "turbulence", "on", "combo", ["on", "off"]),
            ("Print Coefficients", "printCoeffs", "on", "combo",
             ["on", "off"]),
        ],
        "LES Settings|simulationType=LES": [
            ("LES Model", "LESModel", "Smagorinsky", "combo",
             ["Smagorinsky", "kEqn", "dynamicKEqn", "WALE",
              "DeardorffDiffStress", "SpalartAllmarasDES",
              "SpalartAllmarasDDES", "SpalartAllmarasIDDES"]),
            ("LES Delta", "delta", "cubeRootVol", "combo",
             ["cubeRootVol", "vanDriest", "smooth", "Prandtl"]),
            ("Turbulence", "turbulence", "on", "combo", ["on", "off"]),
            ("Print Coefficients", "printCoeffs", "on", "combo",
             ["on", "off"]),
        ],

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
    },
    "info": {
        "field": "RASModel",
        "field_map": {"RAS": "RASModel", "LES": "LESModel"},
        "condition_field": "simulationType",
        "hide_values": ["laminar"],

        "descriptions": {
            "kEpsilon": """<h3>Standard k-\u03b5 Model</h3>
<p>Two-equation model solving for turbulent kinetic energy <i>k</i> and dissipation rate <i>\u03b5</i>.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>\u2202k/\u2202t + \u2207\u00b7(Uk) = \u2207\u00b7[(\u03bd + \u03bd<sub>t</sub>/\u03c3<sub>k</sub>)\u2207k] + P<sub>k</sub> \u2212 \u03b5</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>\u03b5 equation:</td>
<td style='padding: 4px;'>\u2202\u03b5/\u2202t + \u2207\u00b7(U\u03b5) = \u2207\u00b7[(\u03bd + \u03bd<sub>t</sub>/\u03c3<sub>\u03b5</sub>)\u2207\u03b5] + C<sub>1</sub>\u03b5/k\u00b7P<sub>k</sub> \u2212 C<sub>2</sub>\u03b5\u00b2/k</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>\u03bd<sub>t</sub> =</td>
<td style='padding: 4px;'>C<sub>\u03bc</sub> k\u00b2 / \u03b5</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>\u03bc</sub>=0.09 &nbsp; C<sub>1</sub>=1.44 &nbsp; C<sub>2</sub>=1.92 &nbsp; \u03c3<sub>k</sub>=1.0 &nbsp; \u03c3<sub>\u03b5</sub>=1.3
</p>""",

            "kOmegaSST": """<h3>k-\u03c9 SST Model</h3>
<p>Menter's Shear Stress Transport model. Blends k-\u03c9 near walls with k-\u03b5 in the freestream.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>\u2202k/\u2202t + \u2207\u00b7(Uk) = \u2207\u00b7[(\u03bd + \u03c3<sub>k</sub>\u03bd<sub>t</sub>)\u2207k] + P\u0303<sub>k</sub> \u2212 \u03b2*k\u03c9</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>\u03c9 equation:</td>
<td style='padding: 4px;'>\u2202\u03c9/\u2202t + \u2207\u00b7(U\u03c9) = \u2207\u00b7[(\u03bd + \u03c3<sub>\u03c9</sub>\u03bd<sub>t</sub>)\u2207\u03c9] + \u03b3/\u03bd<sub>t</sub>\u00b7P\u0303<sub>k</sub> \u2212 \u03b2\u03c9\u00b2 + CD<sub>k\u03c9</sub></td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>\u03bd<sub>t</sub> =</td>
<td style='padding: 4px;'>a<sub>1</sub>k / max(a<sub>1</sub>\u03c9, SF<sub>2</sub>)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Limiter on \u03bd<sub>t</sub> prevents over-prediction of shear stress in APG flows.<br>
<b>Coefficients:</b> a<sub>1</sub>=0.31 &nbsp; \u03b2*=0.09
</p>""",

            "realizableKE": """<h3>Realizable k-\u03b5 Model</h3>
<p>Shih et al. (1995). Satisfies the mathematical constraint that normal stresses remain positive (realizability).</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>C<sub>\u03bc</sub> =</td>
<td style='padding: 4px;'>Variable \u2014 function of mean strain and rotation rates</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>\u03b5 equation:</td>
<td style='padding: 4px;'>Substantially different from standard k-\u03b5 (derived from mean-square vorticity)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key features:</b> Better for flows with strong streamline curvature, vortices, rotation.<br>
<b>Coefficients:</b> A<sub>0</sub>=4.0 &nbsp; C<sub>2</sub>=1.9 &nbsp; \u03c3<sub>k</sub>=1.0 &nbsp; \u03c3<sub>\u03b5</sub>=1.2
</p>""",

            "SpalartAllmaras": """<h3>Spalart-Allmaras Model</h3>
<p>One-equation model solving for modified turbulent viscosity \u03bd\u0303.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Only 1 transport equation \u2192 cheaper than 2-eq models. Good for external aero.<br>
<b>Note:</b> Only solves for <i>nut</i> \u2014 no k, epsilon, or omega fields needed.
</p>""",

            "LRR": """<h3>Launder-Reece-Rodi (LRR) RSM</h3>
<p>Full Reynolds Stress Model solving 6 transport equations for R<sub>ij</sub> plus \u03b5.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No eddy-viscosity assumption \u2192 captures anisotropy, swirl, streamline curvature.<br>
<b>Cost:</b> 7 transport equations.
</p>""",

            "LaunderSharmaKE": """<h3>Launder-Sharma k-\u03b5 Model</h3>
<p>Low-Reynolds-number variant. Resolves the viscous sublayer without wall functions.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Damping functions handle near-wall behaviour.<br>
<b>Requirement:</b> y\u207a \u2248 1 at first cell \u2014 do NOT use wall functions.
</p>""",

            "Smagorinsky": """<h3>Smagorinsky Model</h3>
<p>Simplest algebraic SGS model. Eddy viscosity proportional to the resolved strain rate.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>k</sub>=0.094 &nbsp; C<sub>e</sub>=1.048
</p>""",

            "kEqn": """<h3>One-Equation Eddy Viscosity (kEqn)</h3>
<p>Solves a transport equation for subgrid-scale kinetic energy k<sub>sgs</sub>.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>k</sub>=0.094 &nbsp; C<sub>e</sub>=1.048
</p>""",

            "dynamicKEqn": """<h3>Dynamic One-Equation Model</h3>
<p>One-equation k<sub>sgs</sub> model with dynamically computed C<sub>k</sub> using the Germano identity.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No need to prescribe C<sub>k</sub> \u2014 adapts to local flow.
</p>""",

            "WALE": """<h3>Wall-Adapting Local Eddy-Viscosity (WALE)</h3>
<p>Naturally gives \u03bd<sub>sgs</sub>\u21920 at walls without damping functions.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key features:</b> Proper wall scaling (\u03bd<sub>sgs</sub> ~ y\u00b3), zero in pure shear.<br>
<b>Coefficients:</b> C<sub>w</sub>=0.325 &nbsp; C<sub>k</sub>=0.094 &nbsp; C<sub>e</sub>=1.048
</p>""",

            "DeardorffDiffStress": """<h3>Deardorff Differential Stress Model</h3>
<p>Full SGS stress model solving transport equations for the SGS stress tensor B<sub>ij</sub>.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No eddy-viscosity assumption at the SGS level.<br>
<b>Cost:</b> 6 additional transport equations.
</p>""",

            "SpalartAllmarasDES": """<h3>Spalart-Allmaras DES</h3>
<p>Detached-Eddy Simulation. Uses SA-RANS near walls, LES in separated regions.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>DES</sub>=0.65<br>
<b>Caution:</b> Can suffer from grid-induced separation (GIS).
</p>""",

            "SpalartAllmarasDDES": """<h3>Spalart-Allmaras DDES</h3>
<p>Delayed DES. Shielding function prevents grid-induced separation.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> f<sub>d</sub> shields boundary layer from LES mode.<br>
<b>Recommended over DES</b> for most applications.
</p>""",

            "SpalartAllmarasIDDES": """<h3>Spalart-Allmaras IDDES</h3>
<p>Improved DDES. Combines DDES with Wall-Modelled LES (WMLES) capability.</p>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Can act as WMLES with turbulent inflow, or as DDES without it.<br>
<b>Best hybrid RANS-LES method</b> for complex separated flows.
</p>""",
        },
    },
}


# ------------------------------------------------------------------ #
#  setFieldsDict — initial phase distribution
# ------------------------------------------------------------------ #

SETFIELDS_DICT = {
    "path": "system/setFieldsDict",
    "label": "setFieldsDict",
    "icon": "SP_DialogApplyButton",
    "groups": {
        "Default Values": [
            ("Default Alpha", "defaultAlpha", 0, "float", (0.0, 1.0)),
        ],
        "Box Region (boxToCell)": [
            ("Use Box Region", "useBox", "true", "combo", ["true", "false"]),
            ("Alpha Value", "boxAlpha", 1, "float", (0.0, 1.0)),
            ("Min X", "boxMinX", -1e6, "float", (-1e9, 1e9)),
            ("Min Y", "boxMinY", -1e6, "float", (-1e9, 1e9)),
            ("Min Z", "boxMinZ", -1e6, "float", (-1e9, 1e9)),
            ("Max X", "boxMaxX", 1e6, "float", (-1e9, 1e9)),
            ("Max Y", "boxMaxY", 0, "float", (-1e9, 1e9)),
            ("Max Z", "boxMaxZ", 1e6, "float", (-1e9, 1e9)),
        ],
        "Cylinder Region (cylinderToCell)": [
            ("Use Cylinder Region", "useCylinder", "false", "combo",
             ["true", "false"]),
            ("Alpha Value", "cylAlpha", 1, "float", (0.0, 1.0)),
            ("Point 1 X", "cylP1X", 0, "float", (-1e9, 1e9)),
            ("Point 1 Y", "cylP1Y", 0, "float", (-1e9, 1e9)),
            ("Point 1 Z", "cylP1Z", 0, "float", (-1e9, 1e9)),
            ("Point 2 X", "cylP2X", 0, "float", (-1e9, 1e9)),
            ("Point 2 Y", "cylP2Y", 1, "float", (-1e9, 1e9)),
            ("Point 2 Z", "cylP2Z", 0, "float", (-1e9, 1e9)),
            ("Radius", "cylRadius", 0.1, "float", (0, 1e6)),
        ],
        "Sphere Region (sphereToCell)": [
            ("Use Sphere Region", "useSphere", "false", "combo",
             ["true", "false"]),
            ("Alpha Value", "sphAlpha", 1, "float", (0.0, 1.0)),
            ("Centre X", "sphCX", 0, "float", (-1e9, 1e9)),
            ("Centre Y", "sphCY", 0, "float", (-1e9, 1e9)),
            ("Centre Z", "sphCZ", 0, "float", (-1e9, 1e9)),
            ("Radius", "sphRadius", 0.1, "float", (0, 1e6)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  Boundary condition defaults (field dicts for the GUI tree)
# ------------------------------------------------------------------ #

BC_P_RGH = {
    "path": "0/p_rgh",
    "label": "p_rgh (pressure - hydrostatic)",
    "icon": "SP_ArrowDown",
    "groups": {
        "p_rgh Field": [
            ("Internal Field [Pa]", "p_rghInternal", 0, "float", (-1e9, 1e9)),
        ],
    },
}

BC_U = {
    "path": "0/U",
    "label": "U (velocity)",
    "icon": "SP_ArrowForward",
    "groups": {
        "Velocity Field": [
            ("Ux [m/s]", "Ux", 0.0, "float", (-1e6, 1e6)),
            ("Uy [m/s]", "Uy", 0.0, "float", (-1e6, 1e6)),
            ("Uz [m/s]", "Uz", 0.0, "float", (-1e6, 1e6)),
        ],
    },
}

BC_ALPHA_WATER = {
    "path": "0/alpha.water",
    "label": "alpha.water (phase fraction)",
    "icon": "SP_MediaVolume",
    "groups": {
        "alpha.water Field": [
            ("Internal Value [0-1]", "alphaWaterInternal", 0, "float",
             (0.0, 1.0)),
        ],
    },
}

BC_K = {
    "path": "0/k",
    "label": "k (turb. kinetic energy)",
    "icon": "SP_MediaVolume",
    "groups": {
        "k Field": [
            ("Internal / Inlet Value [m²/s²]", "kInternal", "0.1",
             "str", None),
        ],
    },
}

BC_EPSILON = {
    "path": "0/epsilon",
    "label": "epsilon (dissipation)",
    "icon": "SP_MediaVolume",
    "groups": {
        "Epsilon Field": [
            ("Internal / Inlet Value [m²/s³]", "epsilonInternal", "0.1",
             "str", None),
        ],
    },
}

BC_OMEGA = {
    "path": "0/omega",
    "label": "omega (specific dissipation)",
    "icon": "SP_MediaVolume",
    "groups": {
        "Omega Field": [
            ("Internal / Inlet Value [1/s]", "omegaInternal", "1.0",
             "str", None),
        ],
    },
}

BC_NUT = {
    "path": "0/nut",
    "label": "nut (turb. viscosity)",
    "icon": "SP_MediaVolume",
    "groups": {
        "nut Field": [
            ("Internal Value [m²/s]", "nutInternal", "0", "str", None),
        ],
    },
}


# ---- Mesh dictionaries ---- #

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
            ("Z min", "zMin", 0.0, "float", (-1e6, 1e6)),
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
            ("Castellated Mesh", "castellatedMesh", "true", "combo",
             ["true", "false"]),
            ("Snap", "snap", "true", "combo", ["true", "false"]),
            ("Add Layers", "addLayers", "true", "combo", ["true", "false"]),
        ],
        "Castellated Mesh Controls": [
            ("Max Local Cells", "maxLocalCells", 100000, "int",
             (1000, 100000000)),
            ("Max Global Cells", "maxGlobalCells", 2000000, "int",
             (10000, 1000000000)),
            ("Min Refinement Cells", "minRefinementCells", 10, "int",
             (0, 10000)),
            ("Cells Between Levels", "nCellsBetweenLevels", 3, "int",
             (1, 20)),
            ("Resolve Feature Angle", "resolveFeatureAngle", 30, "int",
             (0, 180)),
        ],
        "Snap Controls": [
            ("Smooth Patch", "nSmoothPatch", 3, "int", (0, 20)),
            ("Snap Tolerance", "snapTolerance", 2.0, "float", (0.1, 10.0)),
            ("Solve Iterations", "nSolveIter", 100, "int", (1, 1000)),
            ("Relax Iterations", "nRelaxIter", 5, "int", (1, 100)),
            ("Feature Snap Iterations", "nFeatureSnapIter", 10, "int",
             (1, 100)),
            ("Implicit Feature Snap", "implicitFeatureSnap", "true", "combo",
             ["true", "false"]),
        ],
        "Layer Controls": [
            ("Expansion Ratio", "expansionRatio", 1.2, "float", (1.0, 3.0)),
            ("Final Layer Thickness", "finalLayerThickness", 0.5, "float",
             (0.01, 1.0)),
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
            ("Included Angle [°]", "includedAngle", 150, "int", (0, 180)),
        ],
    },
}


# ------------------------------------------------------------------ #
#  API functions
# ------------------------------------------------------------------ #

def get_base_dicts():
    """Return the always-present dictionaries for interFoam."""
    return [
        CONTROL_DICT,
        FV_SCHEMES,
        FV_SOLUTION,
        DECOMPOSE_PAR_DICT,
        TRANSPORT_PROPERTIES,
        TURBULENCE_PROPERTIES,
        GRAVITY,
        SETFIELDS_DICT,
        BLOCK_MESH_DICT,
        BC_P_RGH,
        BC_U,
        BC_ALPHA_WATER,
        BC_K,
        BC_EPSILON,
        BC_OMEGA,
        BC_NUT,
    ]


def get_mesh_dicts():
    """Return mesh-related dictionaries added when STL is imported."""
    return [SNAPPY_HEX_MESH_DICT, SURFACE_FEATURE_EXTRACT_DICT]


def get_turbulence_fields(model_name: str) -> list[str]:
    """Return which BC fields a turbulence model requires."""
    info = TURBULENCE_MODELS.get(model_name, TURBULENCE_MODELS["kEpsilon"])
    return info["fields"]
