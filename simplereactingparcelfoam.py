"""
Template for simpleReactingParcelFoam solver.
Steady-state compressible turbulent flow with Lagrangian reacting parcels
(spray, coal, biomass combustion) using the SIMPLE algorithm.

Builds on rhoSimpleFoam and adds:
  - constant/reactingCloud1Properties  (parcel configuration)
  - constant/cloudProperties           (cloud list)
  - constant/combustionProperties      (combustion model)

Each field spec: (label, key, default, type, options)
"""

from __future__ import annotations

SOLVER_NAME = "simpleReactingParcelFoam"
SOLVER_DESCRIPTION = (
    "Steady-state compressible solver with Lagrangian reacting parcels "
    "(spray, coal, biomass combustion)"
)

BASE_FIELDS = ["p", "U", "T"]

TURBULENCE_MODELS = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut", "alphat"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut", "alphat"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut", "alphat"]},
    "SpalartAllmaras": {"fields": ["nut", "alphat"]},
}

FIELD_INFO = {
    "p":       {"dim": "[1 -1 -2 0 0 0 0]", "class": "volScalarField",
                "internal": "uniform 101325"},
    "U":       {"dim": "[0 1 -1 0 0 0 0]",  "class": "volVectorField",
                "internal": "uniform (10 0 0)"},
    "T":       {"dim": "[0 0 0 1 0 0 0]",   "class": "volScalarField",
                "internal": "uniform 300"},
    "k":       {"dim": "[0 2 -2 0 0 0 0]",  "class": "volScalarField",
                "internal": "uniform 0.1"},
    "epsilon": {"dim": "[0 2 -3 0 0 0 0]",  "class": "volScalarField",
                "internal": "uniform 0.1"},
    "omega":   {"dim": "[0 0 -1 0 0 0 0]",  "class": "volScalarField",
                "internal": "uniform 1.0"},
    "nut":     {"dim": "[0 2 -1 0 0 0 0]",  "class": "volScalarField",
                "internal": "uniform 0"},
    "alphat":  {"dim": "[1 -1 -1 0 0 0 0]", "class": "volScalarField",
                "internal": "uniform 0"},
}

# ------------------------------------------------------------------ #
#  Dictionary field definitions
# ------------------------------------------------------------------ #

CONTROL_DICT = {
    "path": "system/controlDict",
    "label": "controlDict",
    "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "simpleReactingParcelFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo",
             ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("End Time", "endTime", 1000, "float", (0, 1e9)),
            ("Delta T", "deltaT", 1, "float", (1e-9, 1e6)),
        ],
        "Write Control": [
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "runTime", "adjustableRunTime"]),
            ("Write Interval", "writeInterval", 100, "int", (1, 100000)),
            ("Purge Write", "purgeWrite", 0, "int", (0, 1000)),
            ("Write Format", "writeFormat", "ascii", "combo",
             ["ascii", "binary"]),
            ("Write Precision", "writePrecision", 8, "int", (6, 18)),
        ],
        "Run Control": [
            ("Time Format", "timeFormat", "general", "combo",
             ["general", "fixed", "scientific"]),
            ("Run Time Modifiable", "runTimeModifiable", "true", "combo",
             ["true", "false"]),
        ],
    },
}

FV_SCHEMES = {
    "path": "system/fvSchemes",
    "label": "fvSchemes",
    "icon": "SP_FileDialogContentsView",
    "groups": {
        "Time Schemes": [
            ("ddt Scheme", "ddtScheme", "steadyState", "combo",
             ["steadyState", "Euler", "backward", "localEuler", "CrankNicolson"]),
            ("CrankNicolson Coeff (0=Euler, 1=pure CN)", "ddtCoeff", 0.9, "float", (0.0, 1.0)),
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
            ("Bounded", "divU_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divU_interp", "linearUpwind", "combo",
             ["upwind", "linearUpwind", "linearUpwindV", "linear",
              "limitedLinear", "LUST", "vanLeer", "MUSCL", "Minmod"]),
            ("Gradient / Coeff", "divU_arg", "grad(U)", "combo",
             ["grad(U)", "default", "0.5", "1.0"]),
        ],
        "div(phi, turbulence)": [
            ("Bounded", "divTurb_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divTurb_interp", "upwind", "combo",
             ["upwind", "linearUpwind", "linear", "limitedLinear", "vanLeer"]),
            ("Gradient / Coeff", "divTurb_arg", "default", "combo",
             ["default", "grad(k)", "grad(epsilon)", "grad(omega)", "0.5", "1.0"]),
        ],
        "div(phi, energy)": [
            ("Bounded", "divE_bounded", "bounded", "combo", ["bounded", ""]),
            ("Interpolation", "divE_interp", "upwind", "combo",
             ["upwind", "linearUpwind", "linear", "limitedLinear", "vanLeer"]),
            ("Gradient / Coeff", "divE_arg", "", "combo",
             ["", "default", "0.5", "1.0"]),
        ],
        "Laplacian Schemes": [
            ("Interpolation", "lapInterp", "linear", "combo",
             ["linear", "harmonic", "localMax"]),
            ("snGrad Type", "lapSnGrad", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff (if limited)", "lapLimitCoeff", 0.5, "float", (0.0, 1.0)),
        ],
        "snGrad Schemes": [
            ("Default snGrad", "snGradType", "corrected", "combo",
             ["corrected", "orthogonal", "uncorrected", "limited"]),
            ("Limited Coeff (if limited)", "snGradLimitCoeff", 0.5, "float", (0.0, 1.0)),
        ],
    },
}

FV_SOLUTION = {
    "path": "system/fvSolution",
    "label": "fvSolution",
    "icon": "SP_FileDialogDetailedView",
    "groups": {
        "Pressure Solver": [
            ("Solver", "pSolver", "GAMG", "combo",
             ["GAMG", "PCG", "smoothSolver", "PBiCGStab"]),
            ("Smoother", "pSmoother", "GaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DICGaussSeidel"]),
            ("Tolerance", "pTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "pRelTol", "0.01", "str", None),
        ],
        "Velocity Solver": [
            ("Solver", "USolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "USmoother", "GaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "UTolerance", "1e-8", "str", None),
            ("Relative Tolerance", "URelTol", "0.1", "str", None),
        ],
        "Energy Solver": [
            ("Solver", "eSolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "eSmoother", "symGaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "eTolerance", "1e-7", "str", None),
            ("Relative Tolerance", "eRelTol", "0.1", "str", None),
        ],
        "Turbulence Solver": [
            ("Solver", "turbSolver", "smoothSolver", "combo",
             ["smoothSolver", "PBiCGStab", "GAMG"]),
            ("Smoother", "turbSmoother", "GaussSeidel", "combo",
             ["GaussSeidel", "symGaussSeidel", "DILU"]),
            ("Tolerance", "turbTolerance", "1e-8", "str", None),
            ("Relative Tolerance", "turbRelTol", "0.1", "str", None),
        ],
        "SIMPLE Controls": [
            ("Non-Orthogonal Correctors", "nNonOrthogonalCorrectors", 1, "int", (0, 20)),
            ("Consistent", "consistent", "yes", "combo", ["yes", "no"]),
            ("Algorithm", "algorithm", "SIMPLE", "str", None),
        ],
        "Residual Control": [
            ("p Residual", "pResidual", "1e-4", "str", None),
            ("U Residual", "UResidual", "1e-4", "str", None),
            ("Energy Residual", "eResidual", "1e-4", "str", None),
            ("Turb. Residual", "turbResidual", "1e-4", "str", None),
        ],
        "Relaxation Factors": [
            ("U Relaxation", "relaxU", 0.7, "float", (0.0, 1.0)),
            ("p Relaxation", "relaxP", 0.3, "float", (0.0, 1.0)),
            ("Energy Relaxation", "relaxE", 0.5, "float", (0.0, 1.0)),
            ("Turbulence Relaxation", "relaxTurb", 0.7, "float", (0.0, 1.0)),
            ("Density Relaxation", "relaxRho", 0.5, "float", (0.0, 1.0)),
        ],
    },
}

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
            ("Mixture", "mixture", "pureMixture", "combo",
             ["pureMixture", "homogeneousMixture", "reactingMixture",
              "singleStepReactingMixture"]),
            ("Transport", "transport", "sutherland", "combo",
             ["sutherland", "const", "polynomial"]),
            ("Thermo", "thermo", "hConst", "combo",
             ["hConst", "janaf", "hPolynomial"]),
            ("Equation of State", "equationOfState", "perfectGas", "combo",
             ["perfectGas", "incompressiblePerfectGas", "rhoConst"]),
            ("Specie", "specie", "specie", "str", None),
            ("Energy", "energy", "sensibleEnthalpy", "combo",
             ["sensibleEnthalpy", "sensibleInternalEnergy"]),
        ],
        "Mixture Properties": [
            ("Molecular Weight [g/mol]", "molWeight", "28.96", "str", None),
            ("Cp [J/(kg·K)]", "Cp", "1004.5", "str", None),
            ("Hf [J/kg]", "Hf", "0", "str", None),
        ],
        "Sutherland Transport": [
            ("As [kg/(m·s·K^0.5)]", "As", "1.458e-06", "str", None),
            ("Ts [K]", "Ts", "110.4", "str", None),
        ],
    },
}

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
            ("Print Coefficients", "printCoeffs", "on", "combo", ["on", "off"]),
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
            ("betaStar", "sst_betaStar", 0.09, "float", (0.0, 1.0)),
            ("a1", "sst_a1", 0.31, "float", (0.0, 1.0)),
        ],
    },
    "info": {
        "field": "RASModel",
        "field_map": {"RAS": "RASModel"},
        "condition_field": "simulationType",
        "hide_values": ["laminar", "LES"],
        "descriptions": {
            "kEpsilon": "<h3>Standard k-ε</h3><p>Two-equation model: ν<sub>t</sub> = C<sub>μ</sub>k²/ε</p>",
            "kOmegaSST": "<h3>k-ω SST</h3><p>Menter SST: blends k-ω (wall) with k-ε (freestream)</p>",
            "realizableKE": "<h3>Realizable k-ε</h3><p>Variable C<sub>μ</sub>, better for separated flows</p>",
            "SpalartAllmaras": "<h3>Spalart-Allmaras</h3><p>One-equation model for ν̃</p>",
            "LRR": "<h3>LRR RSM</h3><p>Full Reynolds stress transport (7 equations)</p>",
            "LaunderSharmaKE": "<h3>Launder-Sharma k-ε</h3><p>Low-Re, resolves viscous sublayer (y⁺≈1)</p>",
        },
    },
}

# ------------------------------------------------------------------ #
#  Combustion properties
# ------------------------------------------------------------------ #

COMBUSTION_PROPERTIES = {
    "path": "constant/combustionProperties",
    "label": "combustionProperties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Combustion Model": [
            ("Combustion Model", "combustionModel", "none", "combo",
             ["none", "PaSR", "EDC", "laminar",
              "infinitelyFastChemistry", "noCombustion"]),
            ("Active", "active", "true", "combo", ["true", "false"]),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Cloud properties (Lagrangian parcel configuration)
# ------------------------------------------------------------------ #

CLOUD_PROPERTIES = {
    "path": "constant/cloudProperties",
    "label": "cloudProperties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Cloud Configuration": [
            ("Cloud Type", "type", "reactingCloud", "combo",
             ["reactingCloud", "coalCloud", "sprayCloud",
              "basicKinematicCloud", "thermoCloud"]),
        ],
    },
}

REACTING_CLOUD_PROPERTIES = {
    "path": "constant/reactingCloud1Properties",
    "label": "reactingCloud1Properties",
    "icon": "SP_DriveNetIcon",
    "groups": {
        "Solution": [
            ("Active", "cloudActive", "true", "combo", ["true", "false"]),
            ("Coupled", "coupled", "true", "combo", ["true", "false"]),
            ("Transient", "transient", "false", "combo", ["true", "false"]),
            ("Cell Value Source Correction",
             "cellValueSourceCorrection", "on", "combo", ["on", "off"]),
            ("Max Track Time", "maxTrackTime", 1.0, "float", (0.0, 1e6)),
            ("Max Co", "cloudMaxCo", 0.3, "float", (0.01, 10.0)),
        ],
        "Constant Properties": [
            ("rho0 [kg/m³]", "parcelRho0", 1000.0, "float", (0.01, 10000.0)),
            ("T0 [K]", "parcelT0", 300.0, "float", (1.0, 5000.0)),
            ("Cp0 [J/(kg·K)]", "parcelCp0", 4187.0, "float", (1.0, 50000.0)),
            ("Young's Modulus [Pa]", "youngsModulus", 0.0, "float", (0.0, 1e12)),
            ("Poisson's Ratio", "poissonsRatio", 0.0, "float", (0.0, 0.5)),
        ],
        "Sub-Models": [
            ("Injection Model", "injectionModel", "coneNozzleInjection", "combo",
             ["coneNozzleInjection", "patchInjection", "cellZoneInjection",
              "fieldActivatedInjection", "manualInjection",
              "patchFlowRateInjection", "noInjection"]),
            ("Dispersion Model", "dispersionModel", "stochasticDispersionRAS", "combo",
             ["stochasticDispersionRAS", "gradientDispersionRAS", "none"]),
            ("Patch Interaction", "patchInteractionModel", "standardWallInteraction", "combo",
             ["standardWallInteraction", "localInteraction",
              "rebound", "stick", "escape", "none"]),
            ("Surface Film Model", "surfaceFilmModel", "none", "combo",
             ["none", "thermoSurfaceFilm"]),
            ("Heat Transfer", "heatTransferModel", "RanzMarshall", "combo",
             ["RanzMarshall", "none"]),
            ("Composition Model", "compositionModel", "singleMixtureFraction", "combo",
             ["singleMixtureFraction", "singlePhaseMixture", "none"]),
            ("Phase Change Model", "phaseChangeModel", "liquidEvaporation", "combo",
             ["liquidEvaporation", "liquidEvaporationBoil", "none"]),
            ("Drag Model", "dragModel", "sphereDrag", "combo",
             ["sphereDrag", "WenYuDrag", "ErgunWenYuDrag",
              "distortedSphereDrag", "nonSphereDrag", "SchillerNaumannDrag"]),
            ("Stochastic Collision", "stochasticCollisionModel", "none", "combo",
             ["none", "ORourkeCollision"]),
            ("Radiation Model (cloud)", "cloudRadiationModel", "none", "combo",
             ["none", "P1"]),
        ],
        "Injection Settings": [
            ("SOI (Start of Injection)", "SOI", 0.0, "float", (0.0, 1e9)),
            ("Mass Total [kg]", "massTotal", 0.001, "float", (0.0, 1e6)),
            ("Parcel Basis", "parcelBasisType", "mass", "combo",
             ["mass", "number", "fixed"]),
            ("nParticle (if fixed)", "nParticle", 1, "int", (1, 1000000)),
            ("Duration [s]", "duration", 1e6, "float", (0.0, 1e9)),
            ("Parcels Per Second", "parcelsPerSecond", 1000, "int", (1, 1000000)),
        ],
        "Cone Nozzle Settings|injectionModel=coneNozzleInjection": [
            ("Position X", "injPosX", "0", "str", None),
            ("Position Y", "injPosY", "0", "str", None),
            ("Position Z", "injPosZ", "0", "str", None),
            ("Direction X", "injDirX", "1", "str", None),
            ("Direction Y", "injDirY", "0", "str", None),
            ("Direction Z", "injDirZ", "0", "str", None),
            ("Outer Cone Angle [deg]", "outerConeAngle", 10.0, "float", (0.0, 90.0)),
            ("Inner Cone Angle [deg]", "innerConeAngle", 0.0, "float", (0.0, 90.0)),
            ("Injection Method", "injectionMethod", "disc", "combo",
             ["disc", "point"]),
            ("Flow Type", "flowType", "flowRateAndDischarge", "combo",
             ["flowRateAndDischarge", "pressureDrivenVelocity",
              "constantVelocity"]),
            ("Discharge Coeff (Cd)", "Cd", 0.9, "float", (0.0, 1.0)),
            ("Outer Diameter [m]", "outerDiameter", 0.001, "float", (0.0, 1.0)),
        ],
        "Patch Injection Settings|injectionModel=patchInjection": [
            ("Patch Name", "injPatch", "inlet", "str", None),
            ("U0 [m/s]", "injU0", "10", "str", None),
        ],
        "Size Distribution": [
            ("Distribution Type", "sizeDistribution", "RosinRammler", "combo",
             ["RosinRammler", "fixedValue", "general", "normal", "uniform"]),
            ("Min Diameter [m]", "dMin", "1e-6", "str", None),
            ("Max Diameter [m]", "dMax", "1e-3", "str", None),
            ("d (characteristic) [m]", "dChar", "5e-5", "str", None),
            ("n (spread parameter)", "nRR", "3", "str", None),
        ],
        "Wall Interaction Settings": [
            ("Type (wall)", "wallType", "rebound", "combo",
             ["rebound", "stick", "escape"]),
            ("e (restitution)", "wallE", 1.0, "float", (0.0, 1.0)),
            ("mu (friction)", "wallMu", 0.0, "float", (0.0, 1.0)),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Boundary condition templates for p, U, T, turb
# ------------------------------------------------------------------ #

BC_P = {
    "path": "0/p",
    "label": "p (pressure)",
    "icon": "SP_ArrowDown",
    "groups": {
        "Internal Field": [
            ("Internal Pressure [Pa]", "pInternal", "101325", "str", None),
        ],
    },
}

BC_U = {
    "path": "0/U",
    "label": "U (velocity)",
    "icon": "SP_ArrowRight",
    "groups": {
        "Internal Field": [
            ("Ux [m/s]", "Ux", 10.0, "float", (-1e4, 1e4)),
            ("Uy [m/s]", "Uy", 0.0, "float", (-1e4, 1e4)),
            ("Uz [m/s]", "Uz", 0.0, "float", (-1e4, 1e4)),
        ],
    },
}

BC_T = {
    "path": "0/T",
    "label": "T (temperature)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal Temperature [K]", "TInternal", "300", "str", None),
        ],
    },
}

BC_K = {
    "path": "0/k",
    "label": "k (turb. kinetic energy)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal k [m²/s²]", "kInternal", "0.1", "str", None),
        ],
    },
}

BC_EPSILON = {
    "path": "0/epsilon",
    "label": "epsilon (dissipation)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal ε [m²/s³]", "epsilonInternal", "0.1", "str", None),
        ],
    },
}

BC_OMEGA = {
    "path": "0/omega",
    "label": "omega (specific dissipation)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal ω [1/s]", "omegaInternal", "1.0", "str", None),
        ],
    },
}

BC_NUT = {
    "path": "0/nut",
    "label": "nut (turb. viscosity)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal νt [m²/s]", "nutInternal", "0", "str", None),
        ],
    },
}

BC_ALPHAT = {
    "path": "0/alphat",
    "label": "alphat (turb. thermal diffusivity)",
    "icon": "SP_ArrowUp",
    "groups": {
        "Internal Field": [
            ("Internal αt [kg/(m·s)]", "alphatInternal", "0", "str", None),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Mesh dictionaries
# ------------------------------------------------------------------ #

BLOCK_MESH_DICT = {
    "path": "system/blockMeshDict",
    "label": "blockMeshDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Domain Bounds": [
            ("X min", "xMin", -5.0, "float", (-1e6, 1e6)),
            ("X max", "xMax", 15.0, "float", (-1e6, 1e6)),
            ("Y min", "yMin", -5.0, "float", (-1e6, 1e6)),
            ("Y max", "yMax", 5.0, "float", (-1e6, 1e6)),
            ("Z min", "zMin", -5.0, "float", (-1e6, 1e6)),
            ("Z max", "zMax", 5.0, "float", (-1e6, 1e6)),
        ],
        "STL Margin": [
            ("Domain Margin [%]", "domainMargin", 50.0, "float", (0.0, 500.0)),
        ],
        "Cell Size": [
            ("Cell Size [m]", "cellSize", 0.008, "float", (1e-6, 100.0)),
        ],
        "Cell Count": [
            ("Cells X", "nCellsX", 20, "int", (1, 10000)),
            ("Cells Y", "nCellsY", 10, "int", (1, 10000)),
            ("Cells Z", "nCellsZ", 10, "int", (1, 10000)),
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
            ("Max Local Cells", "maxLocalCells", 100000, "int", (1000, 10000000)),
            ("Max Global Cells", "maxGlobalCells", 2000000, "int", (10000, 100000000)),
            ("Resolve Feature Angle", "resolveFeatureAngle", 30, "int", (0, 180)),
            ("Cells Between Levels", "nCellsBetweenLevels", 3, "int", (1, 20)),
        ],
        "Snap Controls": [
            ("Smooth Patch Iterations", "nSmoothPatch", 3, "int", (0, 20)),
            ("Snap Tolerance", "snapTolerance", 2.0, "float", (0.1, 10.0)),
            ("Feature Snap Iterations", "nFeatureSnapIter", 10, "int", (0, 50)),
        ],
        "Layer Controls": [
            ("Expansion Ratio", "expansionRatio", 1.2, "float", (1.0, 3.0)),
            ("Final Layer Thickness", "finalLayerThickness", 0.5, "float", (0.01, 2.0)),
            ("Min Thickness", "minThickness", 0.1, "float", (0.001, 1.0)),
            ("Feature Angle", "featureAngle", 130, "int", (0, 360)),
        ],
        "Mesh Quality": [
            ("Max Non-Orthogonality", "maxNonOrtho", 65, "int", (20, 90)),
            ("Max Concave", "maxConcave", 80, "int", (20, 180)),
        ],
    },
}

SURFACE_FEATURE_EXTRACT_DICT = {
    "path": "system/surfaceFeatureExtractDict",
    "label": "surfaceFeatureExtractDict",
    "icon": "SP_DialogResetButton",
    "groups": {
        "Feature Extraction": [
            ("Included Angle", "includedAngle", 150, "int", (0, 180)),
        ],
    },
}

# ------------------------------------------------------------------ #
#  API functions
# ------------------------------------------------------------------ #

def get_base_dicts():
    return [
        CONTROL_DICT,
        FV_SCHEMES,
        FV_SOLUTION,
        DECOMPOSE_PAR_DICT,
        THERMOPHYSICAL_PROPERTIES,
        TURBULENCE_PROPERTIES,
        COMBUSTION_PROPERTIES,
        CLOUD_PROPERTIES,
        REACTING_CLOUD_PROPERTIES,
        BLOCK_MESH_DICT,
        BC_P, BC_U, BC_T,
        BC_K, BC_EPSILON, BC_OMEGA, BC_NUT, BC_ALPHAT,
    ]


def get_mesh_dicts():
    return [SNAPPY_HEX_MESH_DICT, SURFACE_FEATURE_EXTRACT_DICT]


def get_turbulence_fields(model_name: str) -> list[str]:
    return TURBULENCE_MODELS.get(model_name, {}).get("fields", [])
