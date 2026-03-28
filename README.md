# OpenFOAM Case Setup GUI

A desktop application for setting up OpenFOAM CFD cases through a graphical interface. Built with Python and PySide6 (Qt6).

> **⚠️ Work in Progress** — This project is under active development. Features may change, and some functionality is still being refined. Contributions and feedback are welcome.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt6)-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Overview

Setting up an OpenFOAM case involves creating and editing many interconnected dictionary files — controlDict, fvSchemes, fvSolution, boundary conditions, snappyHexMeshDict, and more. This GUI replaces manual text editing with structured forms, live preview, validation, and guided workflows.

The application generates standard OpenFOAM case directories that can be run directly with any OpenFOAM installation (openfoam.org or openfoam.com).

### Key Design Principles

- **Database-driven architecture** — all case data lives in a single `CaseDatabase` object. All widgets read from and write to it. Changes propagate automatically via Qt signals.
- **Non-destructive** — the GUI generates cases; it never modifies your OpenFOAM installation.
- **Round-trip capable** — export a case, then load it back. All 11 solvers pass full round-trip testing with zero warnings.
- **Theme-aware** — full dark/light mode support with customisable colours for every UI element.

---

## Features

### Solvers (11 fully implemented)

| Solver | Type | Algorithm | Key Features |
|--------|------|-----------|--------------|
| simpleFoam | Steady incompressible | SIMPLE | Standard industrial workhorse |
| pimpleFoam | Transient incompressible | PIMPLE | Adjustable timestep, outer correctors |
| pisoFoam | Transient incompressible | PISO | No relaxation, Co < 1 |
| icoFoam | Transient laminar | PISO | No turbulence model |
| rhoSimpleFoam | Steady compressible | SIMPLE | thermophysicalProperties, energy eq. |
| rhoPimpleFoam | Transient compressible | PIMPLE | Adjustable timestep |
| buoyantSimpleFoam | Steady buoyant | SIMPLE | p_rgh, gravity, temperature |
| buoyantPimpleFoam | Transient buoyant | PIMPLE | Natural/mixed convection |
| interFoam | Two-phase VOF | PIMPLE | alpha.water, setFieldsDict, MULES |
| simpleReactingParcelFoam | Steady reacting | SIMPLE | Lagrangian particles, combustion |
| potentialFoam | Potential flow | SIMPLE | Pressure initialisation |

Each solver template includes full turbulence model support (k-ε, k-ω SST, Realizable k-ε, Spalart-Allmaras, LRR, Launder-Sharma, plus LES models), tunable coefficients with descriptions, and appropriate default values.

### Case Setup

- **Structured dictionary editors** — all OpenFOAM dictionaries (controlDict, fvSchemes, fvSolution, blockMeshDict, snappyHexMeshDict, transportProperties, turbulenceProperties, thermophysicalProperties, decomposeParDict) editable through forms with dropdowns, spinboxes, and tooltips
- **Boundary condition editor** — per-patch, per-field BC configuration with role-based defaults (inlet/outlet/wall/symmetry). Supports multi-select batch editing and copy/paste between patches
- **STL import** — load STL geometry files, auto-detect solids, auto-compute blockMesh domain bounds with configurable margin
- **Surface refinement** — per-surface min/max refinement levels, boundary layers, patch types, and surface groups
- **Refinement regions** — box, sphere, and cylinder refinement zones
- **Locations in mesh** — multiple named locations with CSV/file import
- **Function objects** — forces, force coefficients, probes, field averaging, residuals, y+, wall shear stress, min/max, cutting planes, Courant number. Includes 5 preset templates (Aero Coefficients, Flow Monitoring, Wall Analysis, Field Statistics, Cutting Plane)
- **fvOptions** — MRF, explicit porosity (with porous media database), heat sources, actuator disks, mean velocity forcing, temperature constraints, radiation, coded sources
- **blockMesh grading** — per-direction expansion ratios for non-uniform cell distributions
- **setFieldsDict** — box, cylinder, and sphere regions for VOF phase initialisation

### Workflow & Usability

- **Guided workflow bar** — 6-step progress indicator (Solver → Mesh → BCs → Numerics → Run → Export) with live validation status on each step
- **Case dashboard** — at-a-glance summary showing solver, mesh stats, patch roles, numerics, time settings, and validation status. Clickable cards navigate to the relevant editor
- **Inline validation markers** — tree items and workflow steps show ✗/⚠ icons in real-time as you edit. 8 check categories: patches, BCs, locations, relaxation, time settings, mesh settings, STL refinement, CFL estimate
- **Scenario presets** — 9 ready-to-use configurations (External Aero, Pipe Flow, Vortex Shedding, Laminar Channel, Dam Break, Natural Convection, Compressible Duct, etc.) that set solver + turbulence model + optimised numerics in one click
- **Best practice guidelines** — built-in reference for mesh quality, y+ selection, turbulence models, steady/transient numerics, boundary conditions, buoyant flows, VOF, and parallel decomposition
- **Live file preview** — syntax-highlighted OpenFOAM dictionary preview that updates as you edit, with configurable colours
- **Config save/load** — save entire case configuration as JSON, load it back later
- **Case reader** — load an existing OpenFOAM case directory into the GUI for modification
- **Recent files** — quick access to last 10 configs/cases
- **Keyboard shortcuts** — Ctrl+S (save), Ctrl+O (load), Ctrl+E (export), Ctrl+Shift+O (load case), Ctrl+Shift+V (validate)
- **Search/filter** — filter patches and surfaces by name when working with complex geometries

### Calculators (6 tabs)

| Calculator | Purpose |
|------------|---------|
| **Turbulence Inlet** | Compute k, ε, ω, ν_t from velocity, intensity, and length scale |
| **y+ Estimator** | First cell height for target y+ with table for common values |
| **Layer Thickness** | Boundary layer stack heights for snappyHexMesh addLayers |
| **Dimensionless Numbers** | Re, Pr, Gr, Ra, Ma, Ri, Pe with flow regime classification and solver suggestions |
| **Unit Converter** | 10 unit groups: pressure, velocity, length, temperature, density, viscosity, thermal conductivity, mass flow, force |
| **Pipe Flow** | Darcy-Weisbach pressure drop, friction factor, flow rate, entry length |

### Analysis Tools

- **Residual plotter** — parse OpenFOAM log files and plot convergence history (log scale, per-field checkboxes, 5s auto-refresh for live monitoring)
- **Config diff** — compare current settings against a saved config or exported case, with colour-coded diff table
- **Case comparison** — load two exported cases and diff their dictionaries side by side
- **STL viewer** — 3D visualisation of loaded STL geometry (requires numpy)

### Customisation

- **Dark mode** — full VS Code-inspired dark theme with one-click toggle
- **Custom colours** — 27 colour keys covering every UI element (tree panel, editor, preview, toolbar, buttons, syntax highlighting)
- **Font settings** — configurable UI and monospace font families and sizes
- **Custom solver templates** — create new solver configurations from built-in templates via a visual editor. Saved as JSON, appears in the solver dropdown
- **Porous media database** — save and reuse Darcy-Forchheimer coefficients across cases
- **OpenFOAM version support** — openfoam.org (6–11) and openfoam.com (v1912–v2412) with version-specific keyword handling

---

## Installation

### Requirements

- Python 3.9 or later
- PySide6 (Qt6 bindings)
- numpy (optional, for STL viewer)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/openfoam-gui.git
cd openfoam-gui

# Install dependencies
pip install PySide6 numpy

# Run
python main.py
```

### First Run

On first startup, the application will:
1. Create `~/.openfoam_gui_settings.json` (colour/font preferences)
2. Export built-in solver templates to `~/.openfoam_gui_templates/builtins/`
3. Show the simpleFoam solver with default settings

---

## Usage

### Quick Start

1. **Select a solver** from the dropdown (top-left) or use **🚀 Presets** for a scenario-based starting point
2. **Load STL geometry** via the STL tab (right panel) — blockMesh bounds auto-compute
3. **Configure surface refinement** — set min/max levels and boundary layers per surface
4. **Set boundary conditions** — click "Patch BC Editor" in the tree, assign roles and BCs per patch
5. **Adjust numerics** — fvSchemes (discretisation), fvSolution (solver settings, relaxation)
6. **Configure time control** — controlDict (deltaT, endTime, write settings)
7. **Validate** — click ✓ Validate or press Ctrl+Shift+V
8. **Export** — click Export Case, choose a directory and case name

### Workflow Bar

The step bar at the top provides guided navigation:

```
[1 Solver] → [2 Mesh] → [3 BCs] → [4 Numerics] → [5 Run] → [6 Export]
```

Each step shows a status indicator:
- ✓ (green) — configured correctly
- ! (orange) — warnings (non-critical)
- ✗ (red) — errors that should be fixed

Click any step to jump to the relevant editor.

### Presets

Use **🚀 Presets** for pre-configured scenarios. Each preset sets the solver, turbulence model, and optimised default values. Includes best practice guidelines explaining the rationale behind the settings.

### Config Management

- **Save Config** (Ctrl+S) — saves all settings as a JSON file
- **Load Config** (Ctrl+O) — restores a saved configuration
- **Load Case** (Ctrl+Shift+O) — reads an existing OpenFOAM case directory
- **Diff** — compare current settings against a saved config or case
- **Compare** — diff two exported case directories

---

## Project Structure

```
of_gui/
├── main.py                    # Main window, toolbar, tree, layout
├── case_db.py                 # CaseDatabase — central data store
├── case_manager.py            # CaseWriter — generates OpenFOAM files
├── case_reader.py             # CaseReader — reads existing cases
├── of_version.py              # OpenFOAM version handling (org/com)
│
├── dict_editor.py             # Generic dictionary editor widget
├── patch_editor.py            # Boundary condition editor
├── surface_editor.py          # Surface refinement editor
├── stl_manager.py             # STL file import/management
├── stl_viewer.py              # 3D STL viewer (numpy)
├── preview.py                 # Syntax-highlighted file preview
├── func_editor.py             # Function object editor
├── fvoptions_editor.py        # fvOptions editor + porous DB
├── refregion_editor.py        # Refinement region editor
├── locations_editor.py        # Locations in mesh editor
│
├── simplefoam.py              # Solver template: simpleFoam
├── pimplefoam.py              # Solver template: pimpleFoam
├── pisofoam.py                # Solver template: pisoFoam
├── icofoam.py                 # Solver template: icoFoam
├── rhosimplefoam.py           # Solver template: rhoSimpleFoam
├── rhopimplefoam.py           # Solver template: rhoPimpleFoam
├── buoyantsimplefoam.py       # Solver template: buoyantSimpleFoam
├── buoyantpimplefoam.py       # Solver template: buoyantPimpleFoam
├── interfoam.py               # Solver template: interFoam
├── simplereactingparcelfoam.py# Solver template: simpleReactingParcelFoam
├── potentialfoam.py           # Solver template: potentialFoam
├── shared_dicts.py            # Shared turbulence/mesh/BC definitions
│
├── bc_types.py                # Boundary condition type definitions
├── func_objects.py            # Function object catalog + presets
├── fv_options.py              # fvOptions catalog
├── porous_db.py               # Porous media parameter database
│
├── app_settings.py            # Settings management + stylesheet
├── settings_dialog.py         # Settings dialog (colours, fonts)
├── custom_template.py         # Custom solver template system
├── template_editor.py         # Template editor dialog
│
├── calculators.py             # CFD calculators (6 tabs)
├── case_validator.py          # Case validation engine
├── case_compare.py            # Config diff + case comparison
├── residual_plotter.py        # Log file residual plotter
├── workflow.py                # Workflow bar + case dashboard
├── presets.py                 # Scenario presets + best practices
│
└── requirements.txt           # Python dependencies
```

41 Python files, ~21,000 lines of code.

---

## Screenshots

*Screenshots coming soon — the application supports both light and dark themes.*

---

## Roadmap

Planned features (not yet implemented):

- [ ] Drag-and-drop STL onto main window
- [ ] Undo/redo (QUndoStack)
- [ ] checkMesh result parser
- [ ] SLURM/PBS job submission script generator
- [ ] Refinement region visualiser in 3D viewer
- [ ] Parameter sweep generator
- [ ] Allrun script visual editor
- [ ] Export single dictionary to clipboard
- [ ] Case notes / annotations

---

## Contributing

This is a work in progress. If you'd like to contribute:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Bug reports and feature requests are welcome via GitHub Issues.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [OpenFOAM](https://openfoam.org/) — The Open Source CFD Toolbox
- [PySide6](https://doc.qt.io/qtforpython-6/) — Qt for Python
- Built with assistance from [Claude](https://claude.ai) (Anthropic)
