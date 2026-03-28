"""
Function object catalog — templates for common OpenFOAM function objects.

Each template defines:
  - type: the OpenFOAM functionObject type
  - description: short description for the GUI
  - fields: [(label, key, default, widget_type, options)]
  - generator: callable(name, settings) -> file content string
"""

FOAM_FUNC_HEADER = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
"""


def _gen_forces(name, s):
    patches = s.get("patches", "wall")
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            forces;
    libs            ("libforces.so");
    writeControl    {s.get('writeControl', 'timeStep')};
    writeInterval   {s.get('writeInterval', 1)};

    patches         ({patches});
    rho             rhoInf;
    rhoInf          {s.get('rhoInf', '1.225')};
    CofR            ({s.get('CofRx', '0')} {s.get('CofRy', '0')} {s.get('CofRz', '0')});
    pitchAxis       ({s.get('pitchX', '0')} {s.get('pitchY', '1')} {s.get('pitchZ', '0')});

    log             yes;
}}
"""


def _gen_force_coeffs(name, s):
    patches = s.get("patches", "wall")
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            forceCoeffs;
    libs            ("libforces.so");
    writeControl    {s.get('writeControl', 'timeStep')};
    writeInterval   {s.get('writeInterval', 1)};

    patches         ({patches});
    rho             rhoInf;
    rhoInf          {s.get('rhoInf', '1.225')};
    CofR            ({s.get('CofRx', '0')} {s.get('CofRy', '0')} {s.get('CofRz', '0')});
    liftDir         ({s.get('liftX', '0')} {s.get('liftY', '0')} {s.get('liftZ', '1')});
    dragDir         ({s.get('dragX', '1')} {s.get('dragY', '0')} {s.get('dragZ', '0')});
    pitchAxis       ({s.get('pitchX', '0')} {s.get('pitchY', '1')} {s.get('pitchZ', '0')});
    magUInf         {s.get('magUInf', '10')};
    lRef            {s.get('lRef', '1')};
    Aref            {s.get('Aref', '1')};

    log             yes;
}}
"""


def _gen_probes(name, s):
    # Build probe points from semicolon-separated list
    points_str = s.get("points", "0 0 0")
    point_lines = []
    for pt in points_str.split(";"):
        pt = pt.strip()
        if pt:
            point_lines.append(f"        ({pt})")
    points_block = "\n".join(point_lines)

    fields_str = s.get("fields", "p U")

    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            probes;
    libs            ("libsampling.so");
    writeControl    {s.get('writeControl', 'timeStep')};
    writeInterval   {s.get('writeInterval', 1)};

    fields          ({fields_str});

    probeLocations
    (
{points_block}
    );
}}
"""


def _gen_field_average(name, s):
    fields_str = s.get("fields", "U p")
    field_entries = []
    for f in fields_str.split():
        f = f.strip()
        if f:
            field_entries.append(f"""        {{
            name        {f}Mean;
            {f}         {f};
            mean        on;
            prime2Mean  {s.get('prime2Mean', 'on')};
            base        {s.get('base', 'time')};
        }}""")
    fields_block = "\n".join(field_entries)

    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            fieldAverage;
    libs            ("libfieldFunctionObjects.so");
    writeControl    {s.get('writeControl', 'writeTime')};
    timeStart       {s.get('timeStart', 0)};

    fields
    (
{fields_block}
    );
}}
"""


def _gen_residuals(name, s):
    fields_str = s.get("fields", "p U k epsilon")
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            residuals;
    libs            ("libutilityFunctionObjects.so");
    writeControl    {s.get('writeControl', 'timeStep')};
    writeInterval   {s.get('writeInterval', 1)};

    fields          ({fields_str});
}}
"""


def _gen_yplus(name, s):
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            yPlus;
    libs            ("libfieldFunctionObjects.so");
    writeControl    {s.get('writeControl', 'writeTime')};

    log             yes;
}}
"""


def _gen_wall_shear_stress(name, s):
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            wallShearStress;
    libs            ("libfieldFunctionObjects.so");
    writeControl    {s.get('writeControl', 'writeTime')};

    log             yes;
}}
"""


def _gen_minmax(name, s):
    fields_str = s.get("fields", "p U T")
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            fieldMinMax;
    libs            ("libfieldFunctionObjects.so");
    writeControl    {s.get('writeControl', 'timeStep')};
    writeInterval   {s.get('writeInterval', 1)};

    mode            magnitude;
    fields          ({fields_str});

    log             yes;
}}
"""


def _gen_surface_sampling(name, s):
    fields_str = s.get("fields", "p U")
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            surfaces;
    libs            ("libsampling.so");
    writeControl    {s.get('writeControl', 'writeTime')};

    surfaceFormat   vtk;
    fields          ({fields_str});

    surfaces
    (
        {s.get('surfaceName', 'slice')}
        {{
            type            cuttingPlane;
            planeType       pointAndNormal;
            point           ({s.get('pointX', '0')} {s.get('pointY', '0')} {s.get('pointZ', '0')});
            normal          ({s.get('normalX', '1')} {s.get('normalY', '0')} {s.get('normalZ', '0')});
            interpolate     true;
        }}
    );
}}
"""


def _gen_courant_no(name, s):
    return f"""{FOAM_FUNC_HEADER}
{name}
{{
    type            CourantNo;
    libs            ("libfieldFunctionObjects.so");
    writeControl    {s.get('writeControl', 'writeTime')};

    log             yes;
}}
"""


# ------------------------------------------------------------------ #
#  Master catalog
# ------------------------------------------------------------------ #

FUNCTION_OBJECT_CATALOG = {
    "forces": {
        "description": "Compute forces and moments on patches",
        "fields": [
            ("Patches (space-separated)", "patches", "wall", "str", None),
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "writeTime", "runTime", "adjustableRunTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
            ("Rho Inf [kg/m³]", "rhoInf", "1.225", "str", None),
            ("Centre of Rotation X", "CofRx", "0", "str", None),
            ("Centre of Rotation Y", "CofRy", "0", "str", None),
            ("Centre of Rotation Z", "CofRz", "0", "str", None),
            ("Pitch Axis X", "pitchX", "0", "str", None),
            ("Pitch Axis Y", "pitchY", "1", "str", None),
            ("Pitch Axis Z", "pitchZ", "0", "str", None),
        ],
        "generator": _gen_forces,
    },
    "forceCoeffs": {
        "description": "Compute Cd, Cl, Cm coefficients",
        "fields": [
            ("Patches (space-separated)", "patches", "wall", "str", None),
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "writeTime", "runTime", "adjustableRunTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
            ("Rho Inf [kg/m³]", "rhoInf", "1.225", "str", None),
            ("Freestream Velocity [m/s]", "magUInf", "10", "str", None),
            ("Reference Length [m]", "lRef", "1", "str", None),
            ("Reference Area [m²]", "Aref", "1", "str", None),
            ("Centre of Rotation X", "CofRx", "0", "str", None),
            ("Centre of Rotation Y", "CofRy", "0", "str", None),
            ("Centre of Rotation Z", "CofRz", "0", "str", None),
            ("Lift Direction X", "liftX", "0", "str", None),
            ("Lift Direction Y", "liftY", "0", "str", None),
            ("Lift Direction Z", "liftZ", "1", "str", None),
            ("Drag Direction X", "dragX", "1", "str", None),
            ("Drag Direction Y", "dragY", "0", "str", None),
            ("Drag Direction Z", "dragZ", "0", "str", None),
            ("Pitch Axis X", "pitchX", "0", "str", None),
            ("Pitch Axis Y", "pitchY", "1", "str", None),
            ("Pitch Axis Z", "pitchZ", "0", "str", None),
        ],
        "generator": _gen_force_coeffs,
    },
    "probes": {
        "description": "Sample fields at specified locations",
        "fields": [
            ("Fields (space-separated)", "fields", "p U", "str", None),
            ("Probe Points (x y z; per point)", "points", "0 0 0; 1 0 0", "str", None),
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "writeTime", "runTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
        ],
        "generator": _gen_probes,
    },
    "fieldAverage": {
        "description": "Time-averaged fields (UMean, pMean, etc.)",
        "fields": [
            ("Fields to Average (space-separated)", "fields", "U p", "str", None),
            ("Compute Prime² Mean", "prime2Mean", "on", "combo", ["on", "off"]),
            ("Base", "base", "time", "combo", ["time", "iteration"]),
            ("Write Control", "writeControl", "writeTime", "combo",
             ["writeTime", "timeStep", "runTime"]),
            ("Time Start", "timeStart", 0, "float", (0, 1e9)),
        ],
        "generator": _gen_field_average,
    },
    "residuals": {
        "description": "Write residuals to file for plotting",
        "fields": [
            ("Fields (space-separated)", "fields", "p U k epsilon", "str", None),
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "writeTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
        ],
        "generator": _gen_residuals,
    },
    "yPlus": {
        "description": "Compute y+ on wall patches",
        "fields": [
            ("Write Control", "writeControl", "writeTime", "combo",
             ["writeTime", "timeStep"]),
        ],
        "generator": _gen_yplus,
    },
    "wallShearStress": {
        "description": "Compute wall shear stress field",
        "fields": [
            ("Write Control", "writeControl", "writeTime", "combo",
             ["writeTime", "timeStep"]),
        ],
        "generator": _gen_wall_shear_stress,
    },
    "fieldMinMax": {
        "description": "Log min/max of fields each time step",
        "fields": [
            ("Fields (space-separated)", "fields", "p U T", "str", None),
            ("Write Control", "writeControl", "timeStep", "combo",
             ["timeStep", "writeTime"]),
            ("Write Interval", "writeInterval", 1, "int", (1, 100000)),
        ],
        "generator": _gen_minmax,
    },
    "surfaces": {
        "description": "Sample fields on a cutting plane (VTK output)",
        "fields": [
            ("Fields (space-separated)", "fields", "p U", "str", None),
            ("Surface Name", "surfaceName", "slice", "str", None),
            ("Point X", "pointX", "0", "str", None),
            ("Point Y", "pointY", "0", "str", None),
            ("Point Z", "pointZ", "0", "str", None),
            ("Normal X", "normalX", "1", "str", None),
            ("Normal Y", "normalY", "0", "str", None),
            ("Normal Z", "normalZ", "0", "str", None),
            ("Write Control", "writeControl", "writeTime", "combo",
             ["writeTime", "timeStep"]),
        ],
        "generator": _gen_surface_sampling,
    },
    "CourantNo": {
        "description": "Compute and write Courant number field",
        "fields": [
            ("Write Control", "writeControl", "writeTime", "combo",
             ["writeTime", "timeStep"]),
        ],
        "generator": _gen_courant_no,
    },
}

# ------------------------------------------------------------------ #
#  Function object preset templates
# ------------------------------------------------------------------ #

FUNC_OBJECT_PRESETS = {
    "Aero Force Coefficients (Cd/Cl/Cm)": {
        "description": "Standard aerodynamic coefficient setup for external flows. "
                       "Includes force coefficients with lift/drag directions and "
                       "reference values.",
        "objects": {
            "aeroCoeffs": {
                "type": "forceCoeffs",
                "params": {
                    "patches": "wall",
                    "writeControl": "timeStep",
                    "writeInterval": 1,
                    "rhoInf": "1.225",
                    "magUInf": "10",
                    "lRef": "1",
                    "Aref": "1",
                    "CofRx": "0", "CofRy": "0", "CofRz": "0",
                    "liftX": "0", "liftY": "0", "liftZ": "1",
                    "dragX": "1", "dragY": "0", "dragZ": "0",
                    "pitchX": "0", "pitchY": "1", "pitchZ": "0",
                },
            },
        },
    },
    "Flow Monitoring (probes + residuals)": {
        "description": "Monitor flow at key points and track residual convergence. "
                       "Good starting set for any simulation.",
        "objects": {
            "flowProbes": {
                "type": "probes",
                "params": {
                    "fields": "p U",
                    "points": "0 0 0; 1 0 0; 2 0 0",
                    "writeControl": "timeStep",
                    "writeInterval": 10,
                },
            },
            "solverResiduals": {
                "type": "residuals",
                "params": {
                    "fields": "p U k epsilon omega",
                    "writeControl": "timeStep",
                    "writeInterval": 1,
                },
            },
        },
    },
    "Wall Analysis (y+, shear stress, forces)": {
        "description": "Complete wall diagnostics: y+ field for mesh quality check, "
                       "wall shear stress for flow analysis, and integrated forces.",
        "objects": {
            "yPlusField": {
                "type": "yPlus",
                "params": {"writeControl": "writeTime"},
            },
            "wallShear": {
                "type": "wallShearStress",
                "params": {"writeControl": "writeTime"},
            },
            "wallForces": {
                "type": "forces",
                "params": {
                    "patches": "wall",
                    "writeControl": "timeStep",
                    "writeInterval": 1,
                    "rhoInf": "1.225",
                    "CofRx": "0", "CofRy": "0", "CofRz": "0",
                    "pitchX": "0", "pitchY": "1", "pitchZ": "0",
                },
            },
        },
    },
    "Field Statistics (min/max + average)": {
        "description": "Track field extremes and compute time-averaged fields. "
                       "Useful for steady-state convergence check and transient statistics.",
        "objects": {
            "fieldMinMax": {
                "type": "fieldMinMax",
                "params": {
                    "fields": "p U T",
                    "writeControl": "timeStep",
                    "writeInterval": 1,
                },
            },
            "fieldMeans": {
                "type": "fieldAverage",
                "params": {
                    "fields": "U p",
                    "prime2Mean": "on",
                    "base": "time",
                    "writeControl": "writeTime",
                    "timeStart": 0,
                },
            },
        },
    },
    "Cutting Plane + Courant Number": {
        "description": "Sample fields on a mid-plane slice (VTK output) and "
                       "compute the Courant number field for timestep verification.",
        "objects": {
            "midPlane": {
                "type": "surfaces",
                "params": {
                    "fields": "p U",
                    "surfaceName": "midPlane",
                    "pointX": "0", "pointY": "0", "pointZ": "0",
                    "normalX": "0", "normalY": "0", "normalZ": "1",
                    "writeControl": "writeTime",
                },
            },
            "courantField": {
                "type": "CourantNo",
                "params": {"writeControl": "writeTime"},
            },
        },
    },
}
