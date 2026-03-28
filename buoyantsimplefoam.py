"""
Template for buoyantSimpleFoam solver.
Steady-state buoyant, compressible, turbulent flow (SIMPLE algorithm).

Uses p_rgh (pressure minus hydrostatic), gravity, and thermophysicalProperties.
"""
from __future__ import annotations
from shared_dicts import *

SOLVER_NAME = "buoyantSimpleFoam"
SOLVER_DESCRIPTION = "Steady-state buoyant, compressible, turbulent flow (SIMPLE)"
BASE_FIELDS = ["p_rgh", "U", "T"]
TURBULENCE_MODELS = TURB_MODELS_COMP
FIELD_INFO = {
    "p_rgh":   {"dim": "[1 -1 -2 0 0 0 0]", "class": "volScalarField", "internal": "uniform 0"},
    "U":       {"dim": "[0 1 -1 0 0 0 0]",  "class": "volVectorField", "internal": "uniform (0 0 0)"},
    "T":       {"dim": "[0 0 0 1 0 0 0]",   "class": "volScalarField", "internal": "uniform 300"},
    "k":       {"dim": "[0 2 -2 0 0 0 0]",  "class": "volScalarField", "internal": "uniform 0.1"},
    "epsilon": {"dim": "[0 2 -3 0 0 0 0]",  "class": "volScalarField", "internal": "uniform 0.1"},
    "omega":   {"dim": "[0 0 -1 0 0 0 0]",  "class": "volScalarField", "internal": "uniform 1.0"},
    "nut":     {"dim": "[0 2 -1 0 0 0 0]",  "class": "volScalarField", "internal": "uniform 0"},
    "alphat":  {"dim": "[1 -1 -1 0 0 0 0]", "class": "volScalarField", "internal": "uniform 0"},
}

CONTROL_DICT = {
    "path": "system/controlDict", "label": "controlDict", "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "buoyantSimpleFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo", ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo", ["endTime", "writeNow", "noWriteNow", "nextWrite"]),
            ("End Time", "endTime", 1000, "float", (0, 1e9)),
            ("Delta T", "deltaT", 1, "float", (1e-9, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "runTime", "adjustableRunTime", "cpuTime", "clockTime"]),
            ("Write Interval", "writeInterval", 100, "int", (1, 100000)),
            ("Purge Write", "purgeWrite", 0, "int", (0, 1000)),
            ("Write Format", "writeFormat", "ascii", "combo", ["ascii", "binary"]),
            ("Write Precision", "writePrecision", 8, "int", (1, 20)),
            ("Write Compression", "writeCompression", "off", "combo", ["off", "on"]),
        ],
    },
}
FV_SCHEMES = {
    "path": "system/fvSchemes", "label": "fvSchemes", "icon": "SP_FileDialogContentsView",
    "groups": {
        "Time Schemes": [("ddt Scheme", "ddtScheme", "steadyState", "combo",
            ["steadyState", "Euler", "backward", "localEuler", "CrankNicolson"])],
        "Gradient Schemes": [
            ("Default Method", "gradMethod", "Gauss", "combo", ["Gauss", "leastSquares"]),
            ("Default Interpolation", "gradInterp", "linear", "combo", ["linear", "pointLinear"]),
            ("Default Limiter", "gradLimiter", "none", "combo", ["none", "cellLimited", "faceLimited"]),
            ("Limiter Coefficient", "gradLimitCoeff", 1.0, "float", (0.0, 1.0)),
            ("grad(U) Method", "gradU_method", "cellLimited Gauss", "combo",
             ["Gauss", "cellLimited Gauss", "faceLimited Gauss", "leastSquares"]),
            ("grad(U) Interpolation", "gradU_interp", "linear", "combo", ["linear", "pointLinear"]),
            ("grad(U) Limiter Coeff", "gradU_coeff", 1.0, "float", (0.0, 1.0)),
        ],
        "div(phi,U)": [
            ("Bounded", "divU_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divU_interp", "linearUpwind", "combo",
             ["upwind", "linearUpwind", "linearUpwindV", "linear", "limitedLinear", "vanLeer"]),
            ("Gradient / Coeff", "divU_arg", "grad(U)", "combo",
             ["grad(U)", "default", "0.2", "0.5", "0.75", "1.0"]),
        ],
        "div(phi, turbulence)": [
            ("Bounded", "divTurb_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divTurb_interp", "upwind", "combo",
             ["upwind", "linearUpwind", "linear", "limitedLinear", "vanLeer"]),
            ("Gradient / Coeff", "divTurb_arg", "default", "combo",
             ["default", "grad(k)", "0.5", "1.0"]),
        ],
        "div(phi,e) — Energy": [
            ("Bounded", "divE_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divE_interp", "upwind", "combo",
             ["upwind", "linearUpwind", "linear", "limitedLinear"]),
            ("Gradient / Coeff", "divE_arg", "default", "combo", ["default", "0.5", "1.0"]),
        ],
        "Laplacian Schemes": [
            ("Interpolation", "lapInterp", "linear", "combo", ["linear", "harmonic"]),
            ("snGrad Type", "lapSnGrad", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff", "lapLimitCoeff", 0.5, "float", (0.0, 1.0)),
        ],
        "snGrad Schemes": [
            ("Default snGrad", "snGradType", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff", "snGradLimitCoeff", 0.5, "float", (0.0, 1.0)),
        ],
    },
}
FV_SOLUTION = {
    "path": "system/fvSolution", "label": "fvSolution", "icon": "SP_FileDialogDetailedView",
    "groups": {
        "Pressure Solver": [
            ("Solver", "pSolver", "GAMG", "combo", ["GAMG", "PCG", "PBiCGStab", "smoothSolver"]),
            ("Smoother", "pSmoother", "GaussSeidel", "combo", ["GaussSeidel", "DIC", "symGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "pRelTol", "0.01", "str", None),
        ],
        "Velocity Solver": [
            ("Solver", "USolver", "smoothSolver", "combo", ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "USmoother", "GaussSeidel", "combo", ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "UTolerance", "1e-8", "str", None),
            ("Relative Tolerance", "URelTol", "0.1", "str", None),
        ],
        "Energy Solver": [
            ("Solver", "eSolver", "smoothSolver", "combo", ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "eSmoother", "symGaussSeidel", "combo", ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "eTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "eRelTol", "0.1", "str", None),
        ],
        "Turbulence Solver": [
            ("Solver", "turbSolver", "smoothSolver", "combo", ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "turbSmoother", "GaussSeidel", "combo", ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "turbTolerance", "1e-8", "str", None),
            ("Relative Tolerance", "turbRelTol", "0.1", "str", None),
        ],
        "SIMPLE Controls": [
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 1, "int", (0, 20)),
            ("Consistent", "consistent", "yes", "combo", ["yes", "no"]),
            ("Algorithm", "algorithm", "SIMPLE", "combo", ["SIMPLE"]),
        ],
        "Residual Control": [
            ("p_rgh Residual", "pResidual", "1e-4", "str", None),
            ("U Residual", "UResidual", "1e-4", "str", None),
            ("e Residual", "eResidual", "1e-4", "str", None),
            ("Turb. Residual", "turbResidual", "1e-4", "str", None),
        ],
        "Relaxation Factors": [
            ("U", "relaxU", 0.7, "float", (0.0, 1.0)),
            ("p_rgh", "relaxP", 0.3, "float", (0.0, 1.0)),
            ("e / h", "relaxE", 0.5, "float", (0.0, 1.0)),
            ("Turbulence", "relaxTurb", 0.7, "float", (0.0, 1.0)),
            ("rho", "relaxRho", 1.0, "float", (0.0, 1.0)),
        ],
    },
}
TURBULENCE_PROPERTIES = make_turb_properties_dict()

def get_base_dicts():
    return [CONTROL_DICT, FV_SCHEMES, FV_SOLUTION, DECOMPOSE_PAR_DICT,
            THERMOPHYSICAL_PROPERTIES, TURBULENCE_PROPERTIES, GRAVITY,
            BLOCK_MESH_DICT,
            bc_p_rgh(), bc_u(0.0), bc_t(), BC_K, BC_EPSILON, BC_OMEGA, BC_NUT, BC_ALPHAT]
def get_mesh_dicts():
    return [SNAPPY_HEX_MESH_DICT, SURFACE_FEATURE_EXTRACT_DICT]
def get_turbulence_fields(model_name):
    return TURBULENCE_MODELS.get(model_name, TURBULENCE_MODELS["kEpsilon"])["fields"]
