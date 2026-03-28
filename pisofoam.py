"""
Template for pisoFoam solver.
Transient solver for incompressible, turbulent flow using the PISO algorithm.

Key characteristics:
  - Transient with fixed or adjustable time step
  - PISO algorithm: pressure correctors, no outer correctors
  - No relaxation factors (fully transient)
  - pFinal solver entry for final corrector
  - Kinematic pressure p [m²/s²]

Each field spec: (label, key, default, type, options)
"""

from __future__ import annotations

SOLVER_NAME = "pisoFoam"
SOLVER_DESCRIPTION = "Transient solver for incompressible, turbulent flow (PISO algorithm)"

TURBULENCE_MODELS = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut"]},
    "SpalartAllmaras": {"fields": ["nut"]},
}


# ------------------------------------------------------------------ #
#  controlDict — transient
# ------------------------------------------------------------------ #

CONTROL_DICT = {
    "path": "system/controlDict",
    "label": "controlDict",
    "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "pisoFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo",
             ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo",
             ["endTime", "writeNow", "noWriteNow", "nextWrite"]),
            ("End Time", "endTime", 1.0, "float", (0, 1e9)),
            ("Delta T", "deltaT", 1e-4, "float", (1e-12, 1e6)),
        ],
        "Adjustable Time Step": [
            ("Adjustable Time Step", "adjustTimeStep", "yes", "combo",
             ["yes", "no"]),
            ("Max Courant Number", "maxCo", 0.5, "float", (0.01, 100.0)),
            ("Max Delta T", "maxDeltaT", 1.0, "float", (1e-12, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "adjustableRunTime", "combo",
             ["timeStep", "runTime", "adjustableRunTime", "cpuTime",
              "clockTime"]),
            ("Write Interval", "writeInterval", 0.1, "float",
             (1e-12, 1e9)),
            ("Purge Write", "purgeWrite", 0, "int", (0, 1000)),
            ("Write Format", "writeFormat", "ascii", "combo",
             ["ascii", "binary"]),
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
#  fvSchemes — transient
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
            ("Limiter Coefficient", "gradLimitCoeff", 1.0,
             "float", (0.0, 1.0)),
            ("grad(U) Method", "gradU_method", "cellLimited Gauss", "combo",
             ["Gauss", "cellLimited Gauss", "faceLimited Gauss",
              "leastSquares"]),
            ("grad(U) Interpolation", "gradU_interp", "linear", "combo",
             ["linear", "pointLinear", "leastSquares"]),
            ("grad(U) Limiter Coeff", "gradU_coeff", 1.0,
             "float", (0.0, 1.0)),
        ],
        "div(phi,U)": [
            ("Bounded", "divU_bounded", "", "combo", ["bounded", ""]),
            ("Interpolation", "divU_interp", "linearUpwindV", "combo",
             ["upwind", "linearUpwind", "linearUpwindV", "linear",
              "limitedLinear", "LUST", "vanLeer", "MUSCL", "Minmod"]),
            ("Gradient / Coeff", "divU_arg", "grad(U)", "combo",
             ["grad(U)", "default", "grad(k)",
              "0.2", "0.5", "0.75", "1.0"]),
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
#  fvSolution — PISO algorithm (no outer correctors, no relaxation)
# ------------------------------------------------------------------ #

FV_SOLUTION = {
    "path": "system/fvSolution",
    "label": "fvSolution",
    "icon": "SP_FileDialogDetailedView",
    "groups": {
        "Pressure Solver": [
            ("Solver", "pSolver", "GAMG", "combo",
             ["GAMG", "PCG", "PBiCGStab", "smoothSolver"]),
            ("Smoother", "pSmoother", "GaussSeidel", "combo",
             ["GaussSeidel", "DIC", "DILU", "symGaussSeidel",
              "DICGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-6", "str", None),
            ("Relative Tolerance", "pRelTol", "0.05", "str", None),
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
        "Turbulence Solver": [
            ("Solver", "turbSolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "turbSmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "turbTolerance", "1e-5", "str", None),
            ("Relative Tolerance", "turbRelTol", "0", "str", None),
        ],
        "PISO Controls": [
            ("Correctors", "nCorrectors", 2, "int", (1, 10)),
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 1,
             "int", (0, 20)),
            ("Algorithm", "algorithm", "PISO", "combo", ["PISO"]),
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
#  transportProperties
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
            ("Kinematic Viscosity (nu) [m²/s]", "nu", "1e-06", "str", None),
        ],
    },
}


# ------------------------------------------------------------------ #
#  turbulenceProperties — full RAS / LES / laminar support
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
            "kEpsilon": "<h3>Standard k-\u03b5</h3><p>C\u03bc=0.09, C1=1.44, C2=1.92</p>",
            "kOmegaSST": "<h3>k-\u03c9 SST</h3><p>Menter's blended model. Best general-purpose choice.</p>",
            "realizableKE": "<h3>Realizable k-\u03b5</h3><p>Variable C\u03bc. Better for swirl/curvature.</p>",
            "SpalartAllmaras": "<h3>Spalart-Allmaras</h3><p>One-equation model. Good for external aero.</p>",
            "LRR": "<h3>LRR Reynolds Stress</h3><p>7 equations. Captures anisotropy.</p>",
            "LaunderSharmaKE": "<h3>Launder-Sharma k-\u03b5</h3><p>Low-Re variant, resolves viscous sublayer (y+\u22481).</p>",
            "Smagorinsky": "<h3>Smagorinsky</h3><p>Algebraic SGS. Ck=0.094, Ce=1.048.</p>",
            "kEqn": "<h3>kEqn</h3><p>One-equation SGS transport model.</p>",
            "dynamicKEqn": "<h3>Dynamic kEqn</h3><p>Dynamic Ck via Germano identity.</p>",
            "WALE": "<h3>WALE</h3><p>Proper wall scaling, no damping functions.</p>",
            "DeardorffDiffStress": "<h3>Deardorff</h3><p>Full SGS stress model (6 extra eqs).</p>",
            "SpalartAllmarasDES": "<h3>SA-DES</h3><p>RANS near walls, LES in separated regions.</p>",
            "SpalartAllmarasDDES": "<h3>SA-DDES</h3><p>Delayed DES. Shields boundary layer from LES.</p>",
            "SpalartAllmarasIDDES": "<h3>SA-IDDES</h3><p>Improved DDES + WMLES capability.</p>",
        },
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
            ("Ux [m/s]", "Ux", 10.0, "float", (-1e6, 1e6)),
            ("Uy [m/s]", "Uy", 0.0, "float", (-1e6, 1e6)),
            ("Uz [m/s]", "Uz", 0.0, "float", (-1e6, 1e6)),
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
    """Return the always-present dictionaries for pisoFoam."""
    return [
        CONTROL_DICT,
        FV_SCHEMES,
        FV_SOLUTION,
        DECOMPOSE_PAR_DICT,
        TRANSPORT_PROPERTIES,
        TURBULENCE_PROPERTIES,
        BLOCK_MESH_DICT,
        BC_P,
        BC_U,
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
