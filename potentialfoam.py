"""
Template for potentialFoam solver.
Potential flow solver for initialising the pressure field.

Solves a Laplacian equation for p and derives U from the pressure gradient.
Laminar only, steady-state, no turbulence. Typically run once before the
main solver to provide a better initial p field.
"""
from __future__ import annotations
from shared_dicts import *

SOLVER_NAME = "potentialFoam"
SOLVER_DESCRIPTION = "Potential flow initialisation (Laplacian for p)"
BASE_FIELDS = ["p", "U"]
TURBULENCE_MODELS = {}
FIELD_INFO = {
    "p": {"dim": "[0 2 -2 0 0 0 0]", "class": "volScalarField", "internal": "uniform 0"},
    "U": {"dim": "[0 1 -1 0 0 0 0]", "class": "volVectorField", "internal": "uniform (10 0 0)"},
}

CONTROL_DICT = {
    "path": "system/controlDict", "label": "controlDict", "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "potentialFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo", ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo", ["endTime", "writeNow"]),
            ("End Time", "endTime", 1, "float", (0, 1e9)),
            ("Delta T", "deltaT", 1, "float", (1e-9, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "runTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
            ("Write Format", "writeFormat", "ascii", "combo", ["ascii", "binary"]),
            ("Write Precision", "writePrecision", 8, "int", (1, 20)),
        ],
    },
}
FV_SCHEMES = {
    "path": "system/fvSchemes", "label": "fvSchemes", "icon": "SP_FileDialogContentsView",
    "groups": {
        "Time Schemes": [
            ("ddt Scheme", "ddtScheme", "steadyState", "combo", ["steadyState"]),
        ],
        "Gradient Schemes": [
            ("Default Method", "gradMethod", "Gauss", "combo", ["Gauss", "leastSquares"]),
            ("Default Interpolation", "gradInterp", "linear", "combo", ["linear"]),
            ("Default Limiter", "gradLimiter", "none", "combo", ["none", "cellLimited"]),
            ("Limiter Coefficient", "gradLimitCoeff", 1.0, "float", (0.0, 1.0)),
            ("grad(U) Method", "gradU_method", "Gauss", "combo", ["Gauss", "leastSquares"]),
            ("grad(U) Interpolation", "gradU_interp", "linear", "combo", ["linear"]),
            ("grad(U) Limiter Coeff", "gradU_coeff", 1.0, "float", (0.0, 1.0)),
        ],
        "div(phi,U)": [
            ("Interpolation", "divU_interp", "linear", "combo", ["linear", "upwind"]),
            ("Bounded", "divU_bounded", "", "combo", [""]),
            ("Gradient / Coeff", "divU_arg", "default", "combo", ["default"]),
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
            ("Solver", "pSolver", "PCG", "combo", ["PCG", "GAMG", "PBiCGStab", "smoothSolver"]),
            ("Preconditioner", "pSmoother", "DIC", "combo",
             ["DIC", "GaussSeidel", "symGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "pRelTol", "0.01", "str", None),
        ],
        "SIMPLE Controls": [
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 10, "int", (0, 50)),
            ("Consistent", "consistent", "yes", "combo", ["yes", "no"]),
            ("Algorithm", "algorithm", "SIMPLE", "combo", ["SIMPLE"]),
        ],
    },
}

def get_base_dicts():
    return [CONTROL_DICT, FV_SCHEMES, FV_SOLUTION, DECOMPOSE_PAR_DICT,
            BLOCK_MESH_DICT, bc_p(), bc_u()]
def get_mesh_dicts():
    return [SNAPPY_HEX_MESH_DICT, SURFACE_FEATURE_EXTRACT_DICT]
def get_turbulence_fields(model_name):
    return []
