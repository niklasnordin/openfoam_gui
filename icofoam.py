"""
Template for icoFoam solver.
Transient solver for incompressible, laminar flow.

Key characteristics:
  - Laminar only — no turbulence model selection
  - PISO algorithm with pressure correctors
  - Kinematic pressure p [m²/s²] (divided by density)
  - Fixed time step (no adjustable time stepping)
  - transportProperties with just nu

Each field spec: (label, key, default, type, options)
"""

from __future__ import annotations

SOLVER_NAME = "icoFoam"
SOLVER_DESCRIPTION = "Transient solver for incompressible, laminar flow"

# No turbulence — laminar only
BASE_FIELDS = ["p", "U"]
TURBULENCE_MODELS = {}

FIELD_INFO = {
    "p": {"dim": "[0 2 -2 0 0 0 0]", "class": "volScalarField",
          "internal": "uniform 0"},
    "U": {"dim": "[0 1 -1 0 0 0 0]", "class": "volVectorField",
          "internal": "uniform (0 0 0)"},
}


# ------------------------------------------------------------------ #
#  controlDict — transient, fixed time step
# ------------------------------------------------------------------ #

CONTROL_DICT = {
    "path": "system/controlDict",
    "label": "controlDict",
    "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "icoFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo",
             ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo",
             ["endTime", "writeNow", "noWriteNow", "nextWrite"]),
            ("End Time", "endTime", 0.5, "float", (0, 1e9)),
            ("Delta T", "deltaT", 0.005, "float", (1e-12, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "runTime", "cpuTime", "clockTime"]),
            ("Write Interval", "writeInterval", 20, "int", (1, 100000)),
            ("Purge Write", "purgeWrite", 0, "int", (0, 1000)),
            ("Write Format", "writeFormat", "ascii", "combo",
             ["ascii", "binary"]),
            ("Write Precision", "writePrecision", 6, "int", (1, 20)),
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
#  fvSchemes — transient, simple Gauss linear for laminar
# ------------------------------------------------------------------ #

FV_SCHEMES = {
    "path": "system/fvSchemes",
    "label": "fvSchemes",
    "icon": "SP_FileDialogContentsView",
    "groups": {
        "Time Schemes": [
            ("ddt Scheme", "ddtScheme", "Euler", "combo",
             ["Euler", "backward", "CrankNicolson"]),
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
            ("Limiter Coefficient", "gradLimitCoeff", 1.0,
             "float", (0.0, 1.0)),
            ("grad(U) Method", "gradU_method", "Gauss", "combo",
             ["Gauss", "cellLimited Gauss", "faceLimited Gauss",
              "leastSquares"]),
            ("grad(U) Interpolation", "gradU_interp", "linear", "combo",
             ["linear", "pointLinear", "leastSquares"]),
            ("grad(U) Limiter Coeff", "gradU_coeff", 1.0,
             "float", (0.0, 1.0)),
        ],
        "div(phi,U)": [
            ("Bounded", "divU_bounded", "", "combo", ["bounded", ""]),
            ("Interpolation", "divU_interp", "linear", "combo",
             ["upwind", "linearUpwind", "linearUpwindV", "linear",
              "limitedLinear", "LUST", "vanLeer"]),
            ("Gradient / Coeff", "divU_arg", "default", "combo",
             ["grad(U)", "default", "0.2", "0.5", "0.75", "1.0"]),
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
#  fvSolution — PISO algorithm
# ------------------------------------------------------------------ #

FV_SOLUTION = {
    "path": "system/fvSolution",
    "label": "fvSolution",
    "icon": "SP_FileDialogDetailedView",
    "groups": {
        "Pressure Solver": [
            ("Solver", "pSolver", "PCG", "combo",
             ["PCG", "GAMG", "PBiCGStab", "smoothSolver"]),
            ("Preconditioner", "pSmoother", "DIC", "combo",
             ["DIC", "GaussSeidel", "DILU", "symGaussSeidel",
              "DICGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-6", "str", None),
            ("Relative Tolerance", "pRelTol", "0.01", "str", None),
            ("pFinal Tolerance", "pFinalTol", "1e-6", "str", None),
        ],
        "Velocity Solver": [
            ("Solver", "USolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "USmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "UTolerance", "1e-5", "str", None),
            ("Relative Tolerance", "URelTol", "0", "str", None),
        ],
        "PISO Controls": [
            ("Correctors", "nCorrectors", 2, "int", (1, 10)),
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 0,
             "int", (0, 20)),
            ("Algorithm", "algorithm", "PISO", "combo", ["PISO"]),
            ("pRefCell", "pRefCell", 0, "int", (0, 1000000)),
            ("pRefValue", "pRefValue", 0, "float", (-1e9, 1e9)),
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
#  transportProperties — single-phase, nu only
# ------------------------------------------------------------------ #

TRANSPORT_PROPERTIES = {
    "path": "constant/transportProperties",
    "label": "transportProperties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Fluid Properties": [
            ("Transport Model", "transportModel", "Newtonian", "combo",
             ["Newtonian", "CrossPowerLaw", "BirdCarreau",
              "HerschelBulkley"]),
            ("Kinematic Viscosity (nu) [m²/s]", "nu", "0.01", "str", None),
        ],
    },
}


# ------------------------------------------------------------------ #
#  Boundary condition defaults
# ------------------------------------------------------------------ #

BC_P = {
    "path": "0/p",
    "label": "p (pressure)",
    "icon": "SP_ArrowDown",
    "groups": {
        "Pressure Field": [
            ("Internal Field [m²/s²]", "pInternal", 0, "float",
             (-1e9, 1e9)),
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


# ---- Mesh dictionaries ---- #

BLOCK_MESH_DICT = {
    "path": "system/blockMeshDict",
    "label": "blockMeshDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Domain Size": [
            ("X min", "xMin", 0.0, "float", (-1e6, 1e6)),
            ("X max", "xMax", 1.0, "float", (-1e6, 1e6)),
            ("Y min", "yMin", 0.0, "float", (-1e6, 1e6)),
            ("Y max", "yMax", 1.0, "float", (-1e6, 1e6)),
            ("Z min", "zMin", 0.0, "float", (-1e6, 1e6)),
            ("Z max", "zMax", 0.1, "float", (-1e6, 1e6)),
        ],
        "Cell Counts": [
            ("Cells X", "cellsX", 20, "int", (1, 10000)),
            ("Cells Y", "cellsY", 20, "int", (1, 10000)),
            ("Cells Z", "cellsZ", 1, "int", (1, 10000)),
            ("Cell Size [m]", "cellSize", 0.05, "float", (1e-6, 100.0)),
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
            ("Add Layers", "addLayers", "true", "combo",
             ["true", "false"]),
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
    """Return the always-present dictionaries for icoFoam."""
    return [
        CONTROL_DICT,
        FV_SCHEMES,
        FV_SOLUTION,
        DECOMPOSE_PAR_DICT,
        TRANSPORT_PROPERTIES,
        BLOCK_MESH_DICT,
        BC_P,
        BC_U,
    ]


def get_mesh_dicts():
    """Return mesh-related dictionaries added when STL is imported."""
    return [SNAPPY_HEX_MESH_DICT, SURFACE_FEATURE_EXTRACT_DICT]


def get_turbulence_fields(model_name: str) -> list[str]:
    """icoFoam is laminar — no turbulence fields."""
    return []
