"""
Boundary condition type definitions for simpleFoam.

Each field (p, U, k, epsilon, omega, nut) has a set of available BC types.
Each BC type defines its OpenFOAM 'type' keyword and what additional
parameters the user can set.

Structure:
  BC_TYPES[field_name] = {
      "display_name": {
          "type": "openfoam_type_keyword",
          "params": [ (label, key, default, widget_type), ... ],
          "code": callable(patch_name, params) -> str   # optional override
      }
  }
"""


def _uniform_value(val):
    """Format a value for 'uniform' keyword."""
    if isinstance(val, (list, tuple)):
        return f"uniform ({' '.join(str(v) for v in val)})"
    return f"uniform {val}"


# ------------------------------------------------------------------ #
#  Pressure (p) boundary conditions
# ------------------------------------------------------------------ #
BC_TYPES_P = {
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "fixedValue": {
        "type": "fixedValue",
        "params": [
            ("Value [m²/s²]", "value", "0", "str"),
        ],
    },
    "totalPressure": {
        "type": "totalPressure",
        "params": [
            ("p0 [m²/s²]", "p0", "0", "str"),
            ("gamma", "gamma", "1", "str"),
        ],
    },
    "fixedFluxPressure": {
        "type": "fixedFluxPressure",
        "params": [
            ("Value [m²/s²]", "value", "0", "str"),
        ],
    },
    "freestreamPressure": {
        "type": "freestreamPressure",
        "params": [
            ("Freestream Value [m²/s²]", "freestreamValue", "0", "str"),
        ],
    },
    "fixedMean": {
        "type": "fixedMean",
        "params": [
            ("Mean Value [m²/s²]", "meanValue", "0", "str"),
            ("Value [m²/s²]", "value", "0", "str"),
        ],
    },
    "uniformTotalPressure": {
        "type": "uniformTotalPressure",
        "params": [
            ("p0", "p0", "0", "str"),
            ("gamma", "gamma", "1", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Velocity (U) boundary conditions
# ------------------------------------------------------------------ #
BC_TYPES_U = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [
            ("Ux [m/s]", "Ux", "10", "str"),
            ("Uy [m/s]", "Uy", "0", "str"),
            ("Uz [m/s]", "Uz", "0", "str"),
        ],
        "value_fmt": "vector",
    },
    "noSlip": {
        "type": "noSlip",
        "params": [],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Ux", "inletUx", "0", "str"),
            ("Inlet Uy", "inletUy", "0", "str"),
            ("Inlet Uz", "inletUz", "0", "str"),
            ("Value Ux", "Ux", "0", "str"),
            ("Value Uy", "Uy", "0", "str"),
            ("Value Uz", "Uz", "0", "str"),
        ],
        "value_fmt": "vector_inlet_outlet",
    },
    "flowRateInletVelocity": {
        "type": "flowRateInletVelocity",
        "params": [
            ("Flow Rate Mode", "flowRateMode", "volumetricFlowRate", "combo",
             ["volumetricFlowRate", "massFlowRate"]),
            ("Volumetric Flow Rate [m³/s]", "volumetricFlowRate", "0.001", "str", None),
            ("Mass Flow Rate [kg/s]", "massFlowRate", "0.1", "str", None),
            ("Density (rho) [kg/m³]", "rhoInlet", "1.0", "str", None,
             {"incompressible_only": True}),
        ],
        "value_fmt": "flow_rate_inlet",
    },
    "surfaceNormalFixedValue": {
        "type": "surfaceNormalFixedValue",
        "params": [
            ("Ref. Value (negative = into domain)", "refValue", "-10", "str"),
        ],
        "value_fmt": "surface_normal",
    },
    "pressureInletVelocity": {
        "type": "pressureInletVelocity",
        "params": [
            ("Value Ux", "Ux", "0", "str"),
            ("Value Uy", "Uy", "0", "str"),
            ("Value Uz", "Uz", "0", "str"),
        ],
        "value_fmt": "vector",
    },
    "slip": {
        "type": "slip",
        "params": [],
    },
    "movingWallVelocity": {
        "type": "movingWallVelocity",
        "params": [
            ("Value Ux", "Ux", "0", "str"),
            ("Value Uy", "Uy", "0", "str"),
            ("Value Uz", "Uz", "0", "str"),
        ],
        "value_fmt": "vector",
    },
    "pressureInletOutletVelocity": {
        "type": "pressureInletOutletVelocity",
        "params": [
            ("Value Ux", "Ux", "0", "str"),
            ("Value Uy", "Uy", "0", "str"),
            ("Value Uz", "Uz", "0", "str"),
        ],
        "value_fmt": "vector",
    },
    "freestream": {
        "type": "freestream",
        "params": [
            ("Freestream Ux", "Ux", "10", "str"),
            ("Freestream Uy", "Uy", "0", "str"),
            ("Freestream Uz", "Uz", "0", "str"),
        ],
        "value_fmt": "freestream_vector",
    },
    "atmBoundaryLayerInletVelocity": {
        "type": "atmBoundaryLayerInletVelocity",
        "params": [
            ("Uref [m/s]", "Uref", "10", "str"),
            ("Zref [m]", "Zref", "10", "str"),
            ("z0 (roughness) [m]", "z0", "0.1", "str"),
            ("flow Dir X", "flowDirX", "1", "str"),
            ("flow Dir Y", "flowDirY", "0", "str"),
            ("flow Dir Z", "flowDirZ", "0", "str"),
            ("zDir X", "zDirX", "0", "str"),
            ("zDir Y", "zDirY", "0", "str"),
            ("zDir Z", "zDirZ", "1", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Turbulent kinetic energy (k)
# ------------------------------------------------------------------ #
BC_TYPES_K = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [m²/s²]", "value", "0.1", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "kqRWallFunction": {
        "type": "kqRWallFunction",
        "params": [("Value [m²/s²]", "value", "0.1", "str")],
    },
    "turbulentIntensityKineticEnergyInlet": {
        "type": "turbulentIntensityKineticEnergyInlet",
        "params": [("Intensity", "intensity", "0.05", "str")],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Value [m²/s²]", "inletValue", "0.1", "str"),
            ("Value [m²/s²]", "value", "0.1", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Epsilon
# ------------------------------------------------------------------ #
BC_TYPES_EPSILON = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [m²/s³]", "value", "0.1", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "epsilonWallFunction": {
        "type": "epsilonWallFunction",
        "params": [("Value [m²/s³]", "value", "0.1", "str")],
    },
    "turbulentMixingLengthDissipationRateInlet": {
        "type": "turbulentMixingLengthDissipationRateInlet",
        "params": [("Mixing Length [m]", "mixingLength", "0.01", "str")],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Value [m²/s³]", "inletValue", "0.1", "str"),
            ("Value [m²/s³]", "value", "0.1", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Omega
# ------------------------------------------------------------------ #
BC_TYPES_OMEGA = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [1/s]", "value", "1.0", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "omegaWallFunction": {
        "type": "omegaWallFunction",
        "params": [("Value [1/s]", "value", "1.0", "str")],
    },
    "turbulentMixingLengthFrequencyInlet": {
        "type": "turbulentMixingLengthFrequencyInlet",
        "params": [("Mixing Length [m]", "mixingLength", "0.01", "str")],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Value [1/s]", "inletValue", "1.0", "str"),
            ("Value [1/s]", "value", "1.0", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  nut (turbulent viscosity)
# ------------------------------------------------------------------ #
BC_TYPES_NUT = {
    "calculated": {
        "type": "calculated",
        "params": [("Value [m²/s]", "value", "0", "str")],
    },
    "nutkWallFunction": {
        "type": "nutkWallFunction",
        "params": [("Value [m²/s]", "value", "0", "str")],
    },
    "nutUSpaldingWallFunction": {
        "type": "nutUSpaldingWallFunction",
        "params": [("Value [m²/s]", "value", "0", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
}


# ------------------------------------------------------------------ #
#  Temperature (T)
# ------------------------------------------------------------------ #
BC_TYPES_T = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [K]", "value", "300", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Value [K]", "inletValue", "300", "str"),
            ("Value [K]", "value", "300", "str"),
        ],
    },
    "fixedGradient": {
        "type": "fixedGradient",
        "params": [("Gradient [K/m]", "gradient", "0", "str")],
    },
    "totalTemperature": {
        "type": "totalTemperature",
        "params": [
            ("T0 [K]", "T0", "300", "str"),
            ("gamma", "gamma", "1.4", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  alphat (turbulent thermal diffusivity)
# ------------------------------------------------------------------ #
BC_TYPES_ALPHAT = {
    "calculated": {
        "type": "calculated",
        "params": [("Value [kg/(m·s)]", "value", "0", "str")],
    },
    "compressible::alphatWallFunction": {
        "type": "compressible::alphatWallFunction",
        "params": [
            ("Value [kg/(m·s)]", "value", "0", "str"),
            ("Prt", "Prt", "0.85", "str"),
        ],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
}

# ------------------------------------------------------------------ #
#  p_rgh (pressure minus hydrostatic — interFoam)
# ------------------------------------------------------------------ #
BC_TYPES_P_RGH = {
    "fixedFluxPressure": {
        "type": "fixedFluxPressure",
        "params": [("Value [Pa]", "value", "0", "str")],
    },
    "totalPressure": {
        "type": "totalPressure",
        "params": [
            ("p0 [Pa]", "p0", "0", "str"),
            ("gamma", "gamma", "1", "str"),
        ],
    },
    "prghTotalPressure": {
        "type": "prghTotalPressure",
        "params": [
            ("p [Pa]", "p", "0", "str"),
        ],
    },
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [Pa]", "value", "0", "str")],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
}

# ------------------------------------------------------------------ #
#  alpha.water (VOF phase fraction — interFoam)
# ------------------------------------------------------------------ #
BC_TYPES_ALPHA_WATER = {
    "fixedValue": {
        "type": "fixedValue",
        "params": [("Value [0-1]", "value", "1", "str")],
    },
    "inletOutlet": {
        "type": "inletOutlet",
        "params": [
            ("Inlet Value", "inletValue", "1", "str"),
            ("Value", "value", "1", "str"),
        ],
    },
    "zeroGradient": {
        "type": "zeroGradient",
        "params": [],
    },
    "alphaContactAngle": {
        "type": "alphaContactAngle",
        "params": [
            ("Contact Angle [°]", "theta0", "90", "str"),
            ("Dynamic Advancing [°]", "thetaA", "90", "str"),
            ("Dynamic Receding [°]", "thetaR", "90", "str"),
            ("Velocity Scale [m/s]", "uTheta", "1", "str"),
            ("Value", "value", "0", "str"),
        ],
    },
}

# ------------------------------------------------------------------ #
#  Master map: field name -> BC types dict
# ------------------------------------------------------------------ #
ALL_BC_TYPES = {
    "p": BC_TYPES_P,
    "p_rgh": BC_TYPES_P_RGH,
    "U": BC_TYPES_U,
    "T": BC_TYPES_T,
    "alpha.water": BC_TYPES_ALPHA_WATER,
    "k": BC_TYPES_K,
    "epsilon": BC_TYPES_EPSILON,
    "omega": BC_TYPES_OMEGA,
    "nut": BC_TYPES_NUT,
    "alphat": BC_TYPES_ALPHAT,
}


# ------------------------------------------------------------------ #
#  Default BC assignments per patch role
# ------------------------------------------------------------------ #
DEFAULT_PATCH_BCS = {
    "inlet": {
        "p": ("zeroGradient", {}),
        "p_rgh": ("fixedFluxPressure", {"value": "0"}),
        "U": ("fixedValue", {"Ux": "10", "Uy": "0", "Uz": "0"}),
        "T": ("fixedValue", {"value": "300"}),
        "alpha.water": ("fixedValue", {"value": "1"}),
        "k": ("fixedValue", {"value": "0.1"}),
        "epsilon": ("fixedValue", {"value": "0.1"}),
        "omega": ("fixedValue", {"value": "1.0"}),
        "nut": ("calculated", {"value": "0"}),
        "alphat": ("calculated", {"value": "0"}),
    },
    "outlet": {
        "p": ("fixedValue", {"value": "0"}),
        "p_rgh": ("totalPressure", {"p0": "0", "gamma": "1"}),
        "U": ("zeroGradient", {}),
        "T": ("zeroGradient", {}),
        "alpha.water": ("inletOutlet", {"inletValue": "0", "value": "0"}),
        "k": ("zeroGradient", {}),
        "epsilon": ("zeroGradient", {}),
        "omega": ("zeroGradient", {}),
        "nut": ("calculated", {"value": "0"}),
        "alphat": ("calculated", {"value": "0"}),
    },
    "wall": {
        "p": ("zeroGradient", {}),
        "p_rgh": ("fixedFluxPressure", {"value": "0"}),
        "U": ("noSlip", {}),
        "T": ("zeroGradient", {}),
        "alpha.water": ("zeroGradient", {}),
        "k": ("kqRWallFunction", {"value": "0.1"}),
        "epsilon": ("epsilonWallFunction", {"value": "0.1"}),
        "omega": ("omegaWallFunction", {"value": "1.0"}),
        "nut": ("nutkWallFunction", {"value": "0"}),
        "alphat": ("compressible::alphatWallFunction", {"value": "0", "Prt": "0.85"}),
    },
    "symmetry": {
        "p": ("zeroGradient", {}),
        "p_rgh": ("fixedFluxPressure", {"value": "0"}),
        "U": ("slip", {}),
        "T": ("zeroGradient", {}),
        "alpha.water": ("zeroGradient", {}),
        "k": ("zeroGradient", {}),
        "epsilon": ("zeroGradient", {}),
        "omega": ("zeroGradient", {}),
        "nut": ("zeroGradient", {}),
        "alphat": ("zeroGradient", {}),
    },
}


def format_bc_block(patch_name: str, field: str, bc_name: str, params: dict) -> str:
    """Generate the OpenFOAM boundary condition block for one patch/field combo."""
    bc_def = ALL_BC_TYPES.get(field, {}).get(bc_name)
    if not bc_def:
        return f"    {patch_name}\n    {{\n        type    {bc_name};\n    }}"

    lines = [f"    {patch_name}", "    {", f"        type            {bc_def['type']};"]

    value_fmt = bc_def.get("value_fmt", "")

    if value_fmt == "vector":
        ux = params.get("Ux", "0")
        uy = params.get("Uy", "0")
        uz = params.get("Uz", "0")
        lines.append(f"        value           uniform ({ux} {uy} {uz});")
    elif value_fmt == "freestream_vector":
        ux = params.get("Ux", "0")
        uy = params.get("Uy", "0")
        uz = params.get("Uz", "0")
        lines.append(f"        freestreamValue uniform ({ux} {uy} {uz});")
    elif value_fmt == "vector_inlet_outlet":
        iux = params.get("inletUx", "0")
        iuy = params.get("inletUy", "0")
        iuz = params.get("inletUz", "0")
        ux = params.get("Ux", "0")
        uy = params.get("Uy", "0")
        uz = params.get("Uz", "0")
        lines.append(f"        inletValue      uniform ({iux} {iuy} {iuz});")
        lines.append(f"        value           uniform ({ux} {uy} {uz});")
    elif value_fmt == "surface_normal":
        ref = params.get("refValue", "-10")
        lines.append(f"        refValue        uniform {ref};")
    elif value_fmt == "flow_rate_inlet":
        mode = params.get("flowRateMode", "volumetricFlowRate")
        if mode == "massFlowRate":
            val = params.get("massFlowRate", "0.1")
            lines.append(f"        massFlowRate    {val};")
            # rhoInlet only for incompressible solvers — only output if present
            if "rhoInlet" in params:
                lines.append(f"        rhoInlet        {params['rhoInlet']};")
        else:
            val = params.get("volumetricFlowRate", "0.001")
            lines.append(f"        volumetricFlowRate {val};")
    else:
        # Standard scalar params — handle each key
        for label, key, default, _wtype in bc_def.get("params", []):
            val = params.get(key, default)
            if key == "value":
                lines.append(f"        value           uniform {val};")
            elif key == "inletValue":
                lines.append(f"        inletValue      uniform {val};")
            elif key == "p0":
                lines.append(f"        p0              uniform {val};")
            elif key == "freestreamValue":
                lines.append(f"        freestreamValue uniform {val};")
            elif key == "intensity":
                lines.append(f"        intensity       {val};")
            elif key == "mixingLength":
                lines.append(f"        mixingLength    {val};")
            elif key == "gamma":
                lines.append(f"        gamma           {val};")
            elif key == "Prt":
                lines.append(f"        Prt             {val};")
            elif key == "T0":
                lines.append(f"        T0              uniform {val};")
            elif key == "gradient":
                lines.append(f"        gradient        uniform {val};")
            elif key == "volumetricFlowRate":
                lines.append(f"        volumetricFlowRate {val};")
            elif key == "meanValue":
                lines.append(f"        meanValue       uniform {val};")
            elif key == "Uref":
                lines.append(f"        Uref            {val};")
            elif key == "Zref":
                lines.append(f"        Zref            {val};")
            elif key == "z0":
                fdir = f"({params.get('flowDirX','1')} {params.get('flowDirY','0')} {params.get('flowDirZ','0')})"
                zdir = f"({params.get('zDirX','0')} {params.get('zDirY','0')} {params.get('zDirZ','1')})"
                lines.append(f"        z0              uniform {val};")
                lines.append(f"        flowDir         {fdir};")
                lines.append(f"        zDir            {zdir};")
            elif key in ("flowDirX", "flowDirY", "flowDirZ",
                         "zDirX", "zDirY", "zDirZ"):
                pass  # Handled as part of z0 above
            elif key == "refValue":
                lines.append(f"        refValue        uniform {val};")

    lines.append("    }")
    return "\n".join(lines)
