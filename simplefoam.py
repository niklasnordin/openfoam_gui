"""
Template for simpleFoam solver.
Defines all dictionaries, their default values, and GUI field specifications.

Each field spec is a tuple: (label, key, default, type, options)
  - type: "str", "int", "float", "combo", "bool"
  - options: list for combo, (min, max) for numeric, None otherwise
"""

from __future__ import annotations

SOLVER_NAME = "simpleFoam"
SOLVER_DESCRIPTION = "Steady-state solver for incompressible, turbulent flow (SIMPLE algorithm)"

# Turbulence model choices affect which BC files are generated
TURBULENCE_MODELS = {
    "kEpsilon": {"fields": ["k", "epsilon", "nut"]},
    "kOmegaSST": {"fields": ["k", "omega", "nut"]},
    "realizableKE": {"fields": ["k", "epsilon", "nut"]},
    "SpalartAllmaras": {"fields": ["nut"]},
}

# ------------------------------------------------------------------ #
# Dictionary field definitions for the GUI
# Each dict entry: "dict_path" -> { "group_label": [ field_specs ] }
# ------------------------------------------------------------------ #

CONTROL_DICT = {
    "path": "system/controlDict",
    "label": "controlDict",
    "icon": "SP_FileIcon",
    "groups": {
        "Time Control": [
            ("Application", "application", "simpleFoam", "str", None),
            ("Start From", "startFrom", "startTime", "combo",
             ["startTime", "firstTime", "latestTime"]),
            ("Start Time", "startTime", 0, "float", (0, 1e9)),
            ("Stop At", "stopAt", "endTime", "combo",
             ["endTime", "writeNow", "noWriteNow", "nextWrite"]),
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
              "limitedLinear", "LUST", "vanLeer", "MUSCL", "Minmod",
              "filteredLinear", "skewCorrected linear"]),
            ("Gradient / Coeff", "divU_arg", "grad(U)", "combo",
             ["grad(U)", "default", "grad(k)",
              "0.2", "0.5", "0.75", "1.0"]),
        ],
        "div(phi, turbulence)": [
            ("Bounded", "divTurb_bounded", "bounded", "combo", ["bounded", ""]),
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
             ["GAMG", "PCG", "PBiCGStab", "smoothSolver"]),
            ("Smoother", "pSmoother", "GaussSeidel", "combo",
             ["GaussSeidel", "DIC", "DILU", "symGaussSeidel",
              "DICGaussSeidel"]),
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
        ],
        "Residual Control": [
            ("p Residual", "pResidual", "1e-4", "str", None),
            ("U Residual", "UResidual", "1e-4", "str", None),
            ("Turb. Residual", "turbResidual", "1e-4", "str", None),
        ],
        "Relaxation Factors": [
            ("U Relaxation", "relaxU", 0.7, "float", (0.0, 1.0)),
            ("p Relaxation", "relaxP", 0.3, "float", (0.0, 1.0)),
            ("Turbulence Relaxation", "relaxTurb", 0.7, "float", (0.0, 1.0)),
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
            "kEpsilon": """<h3>Standard k-ε Model</h3>
<p>Two-equation model solving for turbulent kinetic energy <i>k</i> and dissipation rate <i>ε</i>.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>∂k/∂t + ∇·(Uk) = ∇·[(ν + ν<sub>t</sub>/σ<sub>k</sub>)∇k] + P<sub>k</sub> − ε</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ε equation:</td>
<td style='padding: 4px;'>∂ε/∂t + ∇·(Uε) = ∇·[(ν + ν<sub>t</sub>/σ<sub>ε</sub>)∇ε] + C<sub>1</sub>ε/k·P<sub>k</sub> − C<sub>2</sub>ε²/k</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>t</sub> =</td>
<td style='padding: 4px;'>C<sub>μ</sub> k² / ε</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>μ</sub>=0.09 &nbsp; C<sub>1</sub>=1.44 &nbsp; C<sub>2</sub>=1.92 &nbsp; σ<sub>k</sub>=1.0 &nbsp; σ<sub>ε</sub>=1.3
</p>""",

            "kOmegaSST": """<h3>k-ω SST Model</h3>
<p>Menter's Shear Stress Transport model. Blends k-ω near walls with k-ε in the freestream.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>∂k/∂t + ∇·(Uk) = ∇·[(ν + σ<sub>k</sub>ν<sub>t</sub>)∇k] + P̃<sub>k</sub> − β*kω</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ω equation:</td>
<td style='padding: 4px;'>∂ω/∂t + ∇·(Uω) = ∇·[(ν + σ<sub>ω</sub>ν<sub>t</sub>)∇ω] + γ/ν<sub>t</sub>·P̃<sub>k</sub> − βω² + CD<sub>kω</sub></td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>t</sub> =</td>
<td style='padding: 4px;'>a<sub>1</sub>k / max(a<sub>1</sub>ω, SF<sub>2</sub>)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Limiter on ν<sub>t</sub> prevents over-prediction of shear stress in APG flows.<br>
<b>Coefficients:</b> a<sub>1</sub>=0.31 &nbsp; β*=0.09 &nbsp; Blending function F<sub>1</sub> switches between inner (k-ω) and outer (k-ε) sets.
</p>""",

            "realizableKE": """<h3>Realizable k-ε Model</h3>
<p>Shih et al. (1995). Satisfies the mathematical constraint that normal Reynolds stresses must be positive (realizability).</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>∂k/∂t + ∇·(Uk) = ∇·[(ν + ν<sub>t</sub>/σ<sub>k</sub>)∇k] + P<sub>k</sub> − ε</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ε equation:</td>
<td style='padding: 4px;'>∂ε/∂t + ∇·(Uε) = ∇·[(ν + ν<sub>t</sub>/σ<sub>ε</sub>)∇ε] + C<sub>1</sub>Sε − C<sub>2</sub>ε²/(k + √(νε))</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>t</sub> =</td>
<td style='padding: 4px;'>C<sub>μ</sub>(S,Ω) k² / ε &nbsp; (C<sub>μ</sub> is variable)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Variable C<sub>μ</sub> computed from mean strain and rotation rates.<br>
<b>Coefficients:</b> C<sub>2</sub>=1.9 &nbsp; σ<sub>k</sub>=1.0 &nbsp; σ<sub>ε</sub>=1.2
</p>""",

            "SpalartAllmaras": """<h3>Spalart-Allmaras Model</h3>
<p>One-equation model solving for modified turbulent viscosity ν̃. Designed for aerospace flows.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν̃ equation:</td>
<td style='padding: 4px;'>∂ν̃/∂t + ∇·(Uν̃) = c<sub>b1</sub>S̃ν̃ + (1/σ)∇·[(ν + ν̃)∇ν̃] + c<sub>b2</sub>(∇ν̃)² − c<sub>w1</sub>f<sub>w</sub>(ν̃/d)²</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>t</sub> =</td>
<td style='padding: 4px;'>ν̃ f<sub>v1</sub> &nbsp; where f<sub>v1</sub> = χ³/(χ³ + c<sub>v1</sub>³), χ = ν̃/ν</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Only 1 transport equation → cheaper than 2-eq models. Good for attached external aero.<br>
<b>Note:</b> Only solves for <i>nut</i> — no k, epsilon, or omega fields needed.
</p>""",

            "LRR": """<h3>Launder-Reece-Rodi (LRR) RSM</h3>
<p>Full Reynolds Stress Model solving 6 transport equations for the Reynolds stress tensor R<sub>ij</sub> plus ε.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>R<sub>ij</sub> equation:</td>
<td style='padding: 4px;'>∂R<sub>ij</sub>/∂t + ∇·(UR<sub>ij</sub>) = P<sub>ij</sub> + Φ<sub>ij</sub> − ε<sub>ij</sub> + D<sub>ij</sub></td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ε equation:</td>
<td style='padding: 4px;'>∂ε/∂t + ∇·(Uε) = C<sub>ε1</sub>ε/k·P − C<sub>ε2</sub>ε²/k + diffusion</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No eddy-viscosity assumption → captures anisotropy, swirl, streamline curvature.<br>
<b>Cost:</b> 7 transport equations. Use when 2-eq models fail (strong swirl, secondary flows).
</p>""",

            "LaunderSharmaKE": """<h3>Launder-Sharma k-ε Model</h3>
<p>Low-Reynolds-number variant of standard k-ε. Resolves the viscous sublayer without wall functions.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k equation:</td>
<td style='padding: 4px;'>∂k/∂t + ∇·(Uk) = ∇·[(ν + ν<sub>t</sub>/σ<sub>k</sub>)∇k] + P<sub>k</sub> − ε − D</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ε̃ equation:</td>
<td style='padding: 4px;'>∂ε̃/∂t + ∇·(Uε̃) = ∇·[(ν + ν<sub>t</sub>/σ<sub>ε</sub>)∇ε̃] + C<sub>1</sub>ε̃/k·P<sub>k</sub> − C<sub>2</sub>f<sub>2</sub>ε̃²/k + E</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>t</sub> =</td>
<td style='padding: 4px;'>C<sub>μ</sub> f<sub>μ</sub> k² / ε̃</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Damping functions f<sub>μ</sub>, f<sub>2</sub> and extra terms D, E handle near-wall behaviour.<br>
<b>Requirement:</b> y⁺ ≈ 1 at first cell — do NOT use wall functions.
</p>""",

            "Smagorinsky": """<h3>Smagorinsky Model</h3>
<p>The simplest algebraic subgrid-scale model. Eddy viscosity proportional to the resolved strain rate.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>sgs</sub> =</td>
<td style='padding: 4px;'>(C<sub>s</sub>Δ)² |S̄|</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>s</sub>=0.094 (≈ Lilly value 0.17 squared under Ck/Ce formulation)<br>
<b>Ck</b>=0.094 &nbsp; <b>Ce</b>=1.048
</p>""",

            "kEqn": """<h3>One-Equation Eddy Viscosity (kEqn)</h3>
<p>Solves a transport equation for subgrid-scale kinetic energy k<sub>sgs</sub>.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k<sub>sgs</sub> equation:</td>
<td style='padding: 4px;'>∂k<sub>sgs</sub>/∂t + ∇·(Uk<sub>sgs</sub>) = ∇·[(ν + ν<sub>sgs</sub>)∇k<sub>sgs</sub>] + P<sub>sgs</sub> − C<sub>e</sub>k<sub>sgs</sub><sup>3/2</sup>/Δ</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>sgs</sub> =</td>
<td style='padding: 4px;'>C<sub>k</sub>Δ√k<sub>sgs</sub></td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>k</sub>=0.094 &nbsp; C<sub>e</sub>=1.048
</p>""",

            "dynamicKEqn": """<h3>Dynamic One-Equation Model</h3>
<p>One-equation k<sub>sgs</sub> model with dynamically computed C<sub>k</sub> using the Germano identity.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>k<sub>sgs</sub> equation:</td>
<td style='padding: 4px;'>Same as kEqn, but C<sub>k</sub> computed from test-filter level</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>C<sub>k</sub> =</td>
<td style='padding: 4px;'>Dynamic (Germano procedure with Lilly least-squares)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No need to prescribe C<sub>k</sub> — adapts to local flow. Better for transitional flows.<br>
<b>Filter ratio:</b> test filter / grid filter ≈ 2
</p>""",

            "WALE": """<h3>Wall-Adapting Local Eddy-Viscosity (WALE)</h3>
<p>Nicoud &amp; Ducros (1999). Algebraic model that naturally gives ν<sub>sgs</sub>→0 at walls without damping functions.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν<sub>sgs</sub> =</td>
<td style='padding: 4px;'>(C<sub>w</sub>Δ)² (S<sup>d</sup><sub>ij</sub>S<sup>d</sup><sub>ij</sub>)<sup>3/2</sup> / [(S̄<sub>ij</sub>S̄<sub>ij</sub>)<sup>5/2</sup> + (S<sup>d</sup><sub>ij</sub>S<sup>d</sup><sub>ij</sub>)<sup>5/4</sup>]</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key features:</b> Proper wall scaling (ν<sub>sgs</sub> ~ y³), zero in pure shear and solid rotation.<br>
<b>Coefficients:</b> C<sub>w</sub>=0.325 &nbsp; C<sub>k</sub>=0.094 &nbsp; C<sub>e</sub>=1.048
</p>""",

            "DeardorffDiffStress": """<h3>Deardorff Differential Stress Model</h3>
<p>Full subgrid-scale stress model solving transport equations for the SGS stress tensor B<sub>ij</sub>.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>B<sub>ij</sub> equation:</td>
<td style='padding: 4px;'>∂B<sub>ij</sub>/∂t + ∇·(UB<sub>ij</sub>) = Production + Pressure-strain − Dissipation + Diffusion</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> No eddy-viscosity assumption at the SGS level — captures SGS anisotropy.<br>
<b>Cost:</b> 6 additional transport equations. Use for complex wall-bounded flows.
</p>""",

            "SpalartAllmarasDES": """<h3>Spalart-Allmaras DES</h3>
<p>Detached-Eddy Simulation. Uses SA-RANS near walls and switches to LES in separated regions.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>ν̃ equation:</td>
<td style='padding: 4px;'>Same as SA-RANS but with d̃ = min(d, C<sub>DES</sub>Δ)</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Length scale:</td>
<td style='padding: 4px;'>Wall distance d in RANS region, C<sub>DES</sub>Δ in LES region</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Coefficients:</b> C<sub>DES</sub>=0.65<br>
<b>Caution:</b> Original DES can suffer from grid-induced separation (GIS).
</p>""",

            "SpalartAllmarasDDES": """<h3>Spalart-Allmaras DDES</h3>
<p>Delayed Detached-Eddy Simulation. Adds a shielding function to prevent grid-induced separation.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Length scale:</td>
<td style='padding: 4px;'>d̃ = d − f<sub>d</sub>·max(0, d − C<sub>DES</sub>Δ)</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>f<sub>d</sub> =</td>
<td style='padding: 4px;'>1 − tanh[(8r<sub>d</sub>)³] &nbsp; (shields boundary layer from LES)</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> f<sub>d</sub> ≈ 0 in boundary layer → pure RANS; f<sub>d</sub> ≈ 1 away from walls → LES.<br>
<b>Recommended over DES</b> for most applications.
</p>""",

            "SpalartAllmarasIDDES": """<h3>Spalart-Allmaras IDDES</h3>
<p>Improved DDES. Combines DDES with Wall-Modelled LES (WMLES) capability.</p>
<table style='margin: 8px 0; border-collapse: collapse;'>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Length scale:</td>
<td style='padding: 4px;'>Blends between RANS, LES, and WMLES branches</td></tr>
<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>WMLES branch:</td>
<td style='padding: 4px;'>When inflow turbulence is present, resolves wall-layer eddies</td></tr>
</table>
<p style='color: #546E7A; font-size: 11px;'>
<b>Key feature:</b> Can act as WMLES when turbulent inflow is provided, or as DDES without it.<br>
<b>Best hybrid RANS-LES method</b> for complex separated flows with wall effects.
</p>""",
        },
    },
}

# ---- Boundary conditions ---- #

BC_P = {
    "path": "0/p",
    "label": "p (pressure)",
    "icon": "SP_ArrowDown",
    "groups": {
        "Pressure Field": [
            ("Internal Field [m²/s²]", "pInternal", 0, "float", (-1e9, 1e9)),
            ("Outlet Value [m²/s²]", "pOutlet", 0, "float", (-1e9, 1e9)),
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
            ("Internal / Inlet Value [m²/s²]", "kInternal", "0.1", "str", None),
        ],
    },
}

BC_EPSILON = {
    "path": "0/epsilon",
    "label": "epsilon (dissipation)",
    "icon": "SP_MediaVolume",
    "groups": {
        "Epsilon Field": [
            ("Internal / Inlet Value [m²/s³]", "epsilonInternal", "0.1", "str", None),
        ],
    },
}

BC_OMEGA = {
    "path": "0/omega",
    "label": "omega (specific dissipation)",
    "icon": "SP_MediaVolume",
    "groups": {
        "Omega Field": [
            ("Internal / Inlet Value [1/s]", "omegaInternal", "1.0", "str", None),
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

# ---- Mesh dictionaries (conditionally included) ---- #

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
            ("Implicit Feature Snap", "implicitFeatureSnap", "true", "combo",
             ["true", "false"]),
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
            ("Included Angle [°]", "includedAngle", 150, "int", (0, 180)),
        ],
    },
}


def get_base_dicts():
    """Return the always-present dictionaries for simpleFoam."""
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
