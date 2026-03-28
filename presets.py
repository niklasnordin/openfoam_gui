"""
Case presets — ready-to-use scenario configurations with best-practice settings.

Each preset specifies a solver, turbulence model, and optimised default values
for numerics, mesh, and time control. Applying a preset switches solver and
overwrites the relevant dict values — STL / patches are preserved.

Best practice guidelines are attached to each preset and can also be displayed
independently.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QSplitter, QFrame,
    QMessageBox, QGroupBox, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt, Signal


# ================================================================== #
#  Best practice guidelines (reusable text blocks)
# ================================================================== #

GUIDELINES = {
    "mesh_quality": """<h3>Mesh Quality</h3>
<p><b>Non-orthogonality:</b> Keep max non-orthogonality below 65°. Above 70° use
<code>limited corrected</code> snGrad/laplacian schemes. Above 80° expect poor
convergence — re-mesh instead.</p>
<p><b>Aspect ratio:</b> Keep below 20:1 in critical regions. First layer cells
near walls can be higher (up to 100:1 is acceptable for attached BL).</p>
<p><b>Skewness:</b> Max skewness below 4 is good. Above 4 causes numerical
diffusion; above 10 will likely diverge.</p>
<p><b>Cell count:</b> Start with a coarse mesh (500k–2M cells) to verify the
setup converges, then refine. Double resolution in each direction = 8× cells.</p>""",

    "y_plus": """<h3>y+ and Near-Wall Treatment</h3>
<p><b>Wall functions (y+ = 30–300):</b> Use <code>kqRWallFunction</code> /
<code>epsilonWallFunction</code> / <code>omegaWallFunction</code>. Fastest option.
Good for external aero and industrial flows where wall gradients aren't critical.</p>
<p><b>Wall-resolved (y+ &lt; 1):</b> Use <code>fixedValue 0</code> for k,
<code>omegaWallFunction</code> for ω (it adapts), <code>nutLowReWallFunction</code>.
Required for heat transfer, transition, and separation prediction.</p>
<p><b>Enhanced wall treatment (y+ = 1–30):</b> k-ω SST handles this range
automatically — it blends between wall functions and wall-resolved. Safest choice
when y+ varies across the domain.</p>
<p><b>Tip:</b> Use the y+ Estimator (Calculators tab) to compute Δy for your
target y+ before meshing.</p>""",

    "turbulence_models": """<h3>Turbulence Model Selection</h3>
<p><b>k-ω SST</b> — Best general-purpose model. Works for most industrial flows,
handles separation reasonably well, and adapts to wall treatment. <i>Default
recommendation for almost all cases.</i></p>
<p><b>k-ε (standard/realizable)</b> — Good for fully turbulent flows away from
walls. Overpredicts turbulence in separated regions. Realizable variant is better
for swirl and recirculation.</p>
<p><b>Spalart-Allmaras</b> — One-equation model, fast. Good for external
aerodynamics with attached boundary layers. Poor for separated flows.</p>
<p><b>LES/DES/DDES</b> — Resolves large eddies, models small ones. Much more
expensive (fine mesh + small Δt). Use only when RANS fails to capture the
physics (e.g. bluff body wake, combustion, acoustics).</p>""",

    "numerics_steady": """<h3>Steady-State Numerics (SIMPLE)</h3>
<p><b>Relaxation factors:</b> Start with U=0.7, p=0.3, turb=0.7. If diverging,
reduce to U=0.5, p=0.2. Never set p > 0.5 in SIMPLE.</p>
<p><b>Residuals:</b> Monitor all residuals. Converged typically means all below
1e-4, with continuity below 1e-5. Force/moment monitors plateauing is a better
convergence indicator.</p>
<p><b>Schemes:</b> Start with first-order (<code>upwind</code>) to establish
flow pattern, then switch to second-order (<code>linearUpwind</code>) for
accuracy. <code>bounded Gauss linearUpwind grad(U)</code> is a safe default.</p>
<p><b>Consistent SIMPLE:</b> Enable <code>consistent yes</code> (SIMPLEC) for
faster convergence. Allows higher relaxation factors (U=0.9, p=0.5).</p>""",

    "numerics_transient": """<h3>Transient Numerics (PIMPLE/PISO)</h3>
<p><b>CFL number:</b> For PISO, keep Co &lt; 1 (typically 0.5). For PIMPLE with
outer correctors, Co can be higher (up to 5–10 with nOuterCorrectors=3+).</p>
<p><b>Time schemes:</b> <code>Euler</code> is first-order, robust, good for
startup. <code>backward</code> is second-order but can oscillate.
<code>CrankNicolson 0.9</code> is a good compromise (blended 2nd order).</p>
<p><b>PISO vs PIMPLE:</b> PISO is cheaper per step (no outer correctors) but
needs Co &lt; 1. PIMPLE with nOuterCorrectors ≥ 2 allows larger timesteps at
the cost of more work per step. Use PIMPLE for most cases.</p>
<p><b>adjustableTimeStep:</b> Enable this with a target maxCo. Saves compute
time by using larger Δt when flow allows it.</p>""",

    "boundary_conditions": """<h3>Boundary Condition Best Practices</h3>
<p><b>Inlet:</b> Use <code>fixedValue</code> for U, <code>zeroGradient</code>
for p. Set k and ε/ω from turbulence intensity (use Calculators tab). Typical
intensity: 1% for clean wind tunnels, 5% for industrial flows, 10%+ for
engine intakes.</p>
<p><b>Outlet:</b> Use <code>fixedValue 0</code> for p, <code>zeroGradient</code>
or <code>inletOutlet</code> for U. <code>inletOutlet</code> prevents backflow
instability — always prefer it over <code>zeroGradient</code> for U at outlets.</p>
<p><b>Walls:</b> <code>noSlip</code> for U (or <code>fixedValue uniform (0 0 0)</code>).
Choose wall functions based on y+ (see y+ guidelines).</p>
<p><b>Symmetry:</b> Use <code>symmetry</code> type for all fields. Only valid
when the flow is truly symmetric about the plane.</p>""",

    "buoyant_flows": """<h3>Buoyant / Natural Convection Flows</h3>
<p><b>Solver:</b> Use buoyantSimpleFoam (steady) or buoyantPimpleFoam (transient).
These solve for p_rgh (pressure minus hydrostatic) and include gravity.</p>
<p><b>Gravity:</b> Set g = (0, 0, -9.81) for Z-up convention or
g = (0, -9.81, 0) for Y-up.</p>
<p><b>Boussinesq vs compressible:</b> For small ΔT (&lt; 30K), Boussinesq
approximation is sufficient. For large ΔT or high-speed flows, use full
compressible (heRhoThermo).</p>
<p><b>Convergence:</b> Buoyant flows converge slowly. Use under-relaxation 0.3–0.5
for temperature. Monitor Nusselt number or heat flux as convergence indicator.</p>""",

    "vof_multiphase": """<h3>Volume of Fluid (VOF) — interFoam</h3>
<p><b>CFL:</b> Keep both Co and alpha Co below 1 (maxAlphaCo=1). The interface
sharpness depends on the alpha CFL number.</p>
<p><b>Schemes:</b> Use <code>vanLeer</code> or <code>vanAlbada</code> for alpha
divergence. Avoid <code>upwind</code> (too diffusive) and <code>linear</code>
(unbounded, will break phase fraction).</p>
<p><b>setFieldsDict:</b> Initialise alpha carefully. Use boxToCell,
cylinderToCell, or sphereToCell to define the initial phase distribution.</p>
<p><b>Mesh:</b> Refine the interface region. At least 4–8 cells across the
interface thickness for accurate capture. Use refinement regions or
adaptive mesh refinement (AMR).</p>""",

    "parallel": """<h3>Parallel Decomposition</h3>
<p><b>scotch:</b> Automatic graph-based decomposition. Best default choice —
minimises inter-processor communication with no user input.</p>
<p><b>hierarchical:</b> Geometric cuts along X/Y/Z. Good for structured meshes
or when you want to control the decomposition shape.</p>
<p><b>Cells per core:</b> Aim for 50k–200k cells per core. Below 10k, the
communication overhead dominates. Above 500k, you're not using enough cores.</p>
<p><b>Tip:</b> Always run decomposePar and then checkMesh -allTopology to verify
the decomposition before launching the solver.</p>""",
}


# ================================================================== #
#  Preset definitions
# ================================================================== #

PRESETS: list[dict[str, Any]] = [
    {
        "name": "External Aerodynamics",
        "category": "Incompressible",
        "description": "Steady-state external flow (vehicles, buildings, wings). "
                       "k-ω SST with wall functions, second-order schemes.",
        "solver": "simpleFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["turbulence_models", "y_plus", "numerics_steady",
                       "boundary_conditions", "mesh_quality"],
        "values": {
            "system/controlDict": {
                "endTime": 2000, "deltaT": 1, "writeInterval": 200,
            },
            "system/fvSchemes": {
                "ddtScheme": "steadyState",
                "gradLimiter": "cellLimited", "gradLimitCoeff": 1.0,
                "gradU_method": "cellLimited Gauss",
                "divU_bounded": "bounded", "divU_interp": "linearUpwind",
                "divU_arg": "grad(U)",
                "divTurb_bounded": "bounded", "divTurb_interp": "linearUpwind",
                "divTurb_arg": "default",
            },
            "system/fvSolution": {
                "relaxU": 0.7, "relaxP": 0.3, "relaxTurb": 0.7,
                "consistent": "yes",
                "nNonOrthogonalCorrectors": 1,
            },
            "constant/transportProperties": {
                "nu": "1.5e-05",
            },
        },
    },
    {
        "name": "Internal Pipe Flow",
        "category": "Incompressible",
        "description": "Steady-state internal flow in ducts/pipes. "
                       "k-ε with standard wall functions, moderate relaxation.",
        "solver": "simpleFoam",
        "turb_model": "kEpsilon",
        "guidelines": ["turbulence_models", "y_plus", "numerics_steady",
                       "boundary_conditions", "parallel"],
        "values": {
            "system/controlDict": {
                "endTime": 3000, "deltaT": 1, "writeInterval": 500,
            },
            "system/fvSchemes": {
                "ddtScheme": "steadyState",
                "divU_bounded": "bounded", "divU_interp": "linearUpwind",
                "divU_arg": "grad(U)",
            },
            "system/fvSolution": {
                "relaxU": 0.7, "relaxP": 0.3, "relaxTurb": 0.7,
                "consistent": "yes",
            },
        },
    },
    {
        "name": "Transient Vortex Shedding",
        "category": "Incompressible",
        "description": "Transient bluff-body flow (cylinders, buildings). "
                       "PIMPLE with k-ω SST, CrankNicolson time scheme.",
        "solver": "pimpleFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["turbulence_models", "numerics_transient",
                       "boundary_conditions", "mesh_quality"],
        "values": {
            "system/controlDict": {
                "endTime": 10.0, "deltaT": 0.001,
                "adjustTimeStep": "yes", "maxCo": 1.0,
                "writeControl": "adjustableRunTime", "writeInterval": 0.5,
            },
            "system/fvSchemes": {
                "ddtScheme": "CrankNicolson", "ddtCoeff": 0.9,
                "divU_bounded": "bounded", "divU_interp": "linearUpwindV",
                "divU_arg": "grad(U)",
            },
            "system/fvSolution": {
                "nOuterCorrectors": 2, "nCorrectors": 1,
                "relaxU": 0.7, "relaxP": 0.3, "relaxTurb": 0.7,
            },
        },
    },
    {
        "name": "Laminar Channel Flow",
        "category": "Incompressible",
        "description": "Low-Re laminar flow (Re < 2300). "
                       "icoFoam with PISO, fixed timestep.",
        "solver": "icoFoam",
        "turb_model": "",
        "guidelines": ["numerics_transient", "boundary_conditions"],
        "values": {
            "system/controlDict": {
                "endTime": 2.0, "deltaT": 0.005,
                "writeControl": "timeStep", "writeInterval": 50,
            },
            "system/fvSchemes": {
                "ddtScheme": "Euler",
                "divU_interp": "linear",
            },
            "system/fvSolution": {
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 0,
                "pRefCell": 0, "pRefValue": 0,
            },
            "constant/transportProperties": {
                "nu": "0.01",
            },
        },
    },
    {
        "name": "Free Surface (Dam Break)",
        "category": "Multiphase",
        "description": "Two-phase VOF with interFoam. "
                       "Water/air interface with gravity.",
        "solver": "interFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["vof_multiphase", "numerics_transient", "mesh_quality"],
        "values": {
            "system/controlDict": {
                "endTime": 1.0, "deltaT": 0.0001,
                "adjustTimeStep": "yes", "maxCo": 0.5,
                "writeControl": "adjustableRunTime", "writeInterval": 0.05,
            },
            "system/fvSchemes": {
                "ddtScheme": "Euler",
            },
        },
    },
    {
        "name": "Natural Convection (Steady)",
        "category": "Heat Transfer",
        "description": "Buoyancy-driven steady flow. "
                       "buoyantSimpleFoam with k-ω SST.",
        "solver": "buoyantSimpleFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["buoyant_flows", "turbulence_models",
                       "numerics_steady", "boundary_conditions"],
        "values": {
            "system/controlDict": {
                "endTime": 5000, "deltaT": 1, "writeInterval": 500,
            },
            "system/fvSolution": {
                "relaxU": 0.5, "relaxP": 0.2, "relaxTurb": 0.5,
                "relaxE": 0.3,
            },
        },
    },
    {
        "name": "Natural Convection (Transient)",
        "category": "Heat Transfer",
        "description": "Transient buoyancy-driven flow. "
                       "buoyantPimpleFoam with k-ω SST.",
        "solver": "buoyantPimpleFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["buoyant_flows", "turbulence_models",
                       "numerics_transient", "boundary_conditions"],
        "values": {
            "system/controlDict": {
                "endTime": 100.0, "deltaT": 0.01,
                "adjustTimeStep": "yes", "maxCo": 0.5,
                "writeControl": "adjustableRunTime", "writeInterval": 5.0,
            },
            "system/fvSolution": {
                "nOuterCorrectors": 2,
                "relaxU": 0.7, "relaxP": 0.3, "relaxTurb": 0.5,
                "relaxE": 0.5,
            },
        },
    },
    {
        "name": "Compressible Duct Flow",
        "category": "Compressible",
        "description": "Steady compressible flow with heat transfer. "
                       "rhoSimpleFoam with k-ω SST.",
        "solver": "rhoSimpleFoam",
        "turb_model": "kOmegaSST",
        "guidelines": ["turbulence_models", "numerics_steady",
                       "boundary_conditions", "mesh_quality"],
        "values": {
            "system/controlDict": {
                "endTime": 5000, "deltaT": 1, "writeInterval": 500,
            },
            "system/fvSolution": {
                "relaxU": 0.5, "relaxP": 0.2, "relaxTurb": 0.5,
                "relaxE": 0.3, "relaxRho": 0.5,
            },
        },
    },
    {
        "name": "Potential Flow Initialisation",
        "category": "Utility",
        "description": "Quick potential flow solve to initialise pressure. "
                       "Run before the main solver for faster convergence.",
        "solver": "potentialFoam",
        "turb_model": "",
        "guidelines": ["mesh_quality", "parallel"],
        "values": {
            "system/controlDict": {
                "endTime": 1, "deltaT": 1,
            },
            "system/fvSolution": {
                "nNonOrthogonalCorrectors": 10,
            },
        },
    },
]


# ================================================================== #
#  Apply preset to database
# ================================================================== #

def apply_preset(preset: dict, db, solver_registry: list) -> str | None:
    """Apply a preset configuration to the database.

    Args:
        preset: one of the PRESETS dicts
        db: CaseDatabase instance
        solver_registry: SOLVER_REGISTRY list from main.py

    Returns:
        error message string, or None on success
    """
    solver_name = preset["solver"]
    turb_model = preset.get("turb_model", "")

    # Find template
    template = None
    for name, _desc, tmpl in solver_registry:
        if name == solver_name and tmpl:
            template = tmpl
            break

    if template is None:
        return f"Solver '{solver_name}' not available."

    # Switch solver
    db.template = template
    db.solver = solver_name
    db.reset()
    db._recompute_active_fields()

    # Set turbulence model
    if turb_model and hasattr(template, 'TURBULENCE_MODELS'):
        if turb_model in template.TURBULENCE_MODELS:
            db.turbulence_model = turb_model
            db.set_dict_value("constant/turbulenceProperties",
                              "RASModel", turb_model)

    # Apply dict values
    for dict_path, values in preset.get("values", {}).items():
        for key, val in values.items():
            db.set_dict_value(dict_path, key, val)

    return None


# ================================================================== #
#  Preset browser dialog
# ================================================================== #

class PresetDialog(QDialog):
    """Dialog for browsing and applying case presets."""

    preset_applied = Signal()

    def __init__(self, db, solver_registry: list, parent=None):
        super().__init__(parent)
        self.db = db
        self._solver_registry = solver_registry
        self.setWindowTitle("Case Presets — Scenario Configurations")
        self.setMinimumSize(850, 550)
        self.resize(950, 600)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Select a preset to apply optimised settings for your scenario.</b>"
            "<br><span style='font-size:11px;'>"
            "This will switch the solver and overwrite numerics/time settings. "
            "STL files, patches, and surface refinement are preserved.</span>"
        ))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: preset list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._preset_list = QListWidget()
        self._current_category = ""
        for preset in PRESETS:
            cat = preset.get("category", "")
            if cat != self._current_category:
                header = QListWidgetItem(f"— {cat} —")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self._preset_list.addItem(header)
                self._current_category = cat
            item = QListWidgetItem(f"  {preset['name']}")
            item.setData(Qt.ItemDataRole.UserRole, preset)
            self._preset_list.addItem(item)

        self._preset_list.currentItemChanged.connect(self._on_preset_selected)
        ll.addWidget(self._preset_list)
        splitter.addWidget(left)

        # Right: details + guidelines
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._detail_view = QTextEdit()
        self._detail_view.setReadOnly(True)
        rl.addWidget(self._detail_view)

        splitter.addWidget(right)
        splitter.setSizes([280, 570])
        layout.addWidget(splitter)

        # Buttons
        btn_row = QHBoxLayout()

        btn_guidelines = QPushButton("View All Guidelines…")
        btn_guidelines.setObjectName("secondary")
        btn_guidelines.clicked.connect(self._show_all_guidelines)
        btn_row.addWidget(btn_guidelines)

        btn_row.addStretch()

        btn_apply = QPushButton("Apply Preset")
        btn_apply.setMinimumHeight(36)
        btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(btn_apply)

        btn_close = QPushButton("Close")
        btn_close.setObjectName("secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_preset_selected(self, current, _previous=None):
        if not current:
            return
        preset = current.data(Qt.ItemDataRole.UserRole)
        if not preset:
            self._detail_view.clear()
            return

        html = []
        html.append(f"<h2>{preset['name']}</h2>")
        html.append(f"<p>{preset['description']}</p>")
        html.append(f"<p><b>Solver:</b> {preset['solver']}")
        if preset.get("turb_model"):
            html.append(f" &nbsp;|&nbsp; <b>Turbulence:</b> {preset['turb_model']}")
        html.append("</p>")

        # Show key settings
        html.append("<h3>Settings Applied</h3>")
        for dict_path, values in preset.get("values", {}).items():
            html.append(f"<p><b>{dict_path}:</b></p><ul>")
            for k, v in values.items():
                html.append(f"<li>{k} = {v}</li>")
            html.append("</ul>")

        # Guidelines
        guideline_keys = preset.get("guidelines", [])
        if guideline_keys:
            html.append("<hr>")
            html.append("<h2>Best Practice Guidelines</h2>")
            for gk in guideline_keys:
                text = GUIDELINES.get(gk, "")
                if text:
                    html.append(text)

        self._detail_view.setHtml("".join(html))

    def _apply(self):
        item = self._preset_list.currentItem()
        if not item:
            QMessageBox.information(self, "Select Preset",
                                    "Please select a preset first.")
            return
        preset = item.data(Qt.ItemDataRole.UserRole)
        if not preset:
            return

        reply = QMessageBox.question(
            self, "Apply Preset",
            f"Apply '{preset['name']}'?\n\n"
            f"This will switch to {preset['solver']} and overwrite "
            "numerics and time settings.\n"
            "STL files and surface refinement are preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        err = apply_preset(preset, self.db, self._solver_registry)
        if err:
            QMessageBox.warning(self, "Preset Error", err)
        else:
            QMessageBox.information(
                self, "Preset Applied",
                f"'{preset['name']}' applied successfully.\n\n"
                f"Solver: {preset['solver']}\n"
                f"Turbulence: {preset.get('turb_model', 'laminar')}")
            self.preset_applied.emit()

    def _show_all_guidelines(self):
        """Show all guidelines in the detail view."""
        html = ["<h1>OpenFOAM Best Practice Guidelines</h1>"]
        for key in ["mesh_quality", "y_plus", "turbulence_models",
                     "numerics_steady", "numerics_transient",
                     "boundary_conditions", "buoyant_flows",
                     "vof_multiphase", "parallel"]:
            text = GUIDELINES.get(key, "")
            if text:
                html.append(text)
                html.append("<hr>")
        self._detail_view.setHtml("".join(html))
