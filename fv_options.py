"""
fvOptions catalog — templates for common OpenFOAM source terms.

Each template defines:
  - type: the OpenFOAM fvOption type
  - description: short description for the GUI
  - fields: [(label, key, default, widget_type, options)]
  - generator: callable(name, settings) -> dict entry string
"""


def _gen_mrf(name, s):
    patches = s.get("nonRotatingPatches", "")
    return f"""    {name}
    {{
        type            MRFSource;
        active          {s.get('active', 'true')};

        MRFSourceCoeffs
        {{
            cellZone        {s.get('cellZone', 'rotatingZone')};
            origin          ({s.get('originX', '0')} {s.get('originY', '0')} {s.get('originZ', '0')});
            axis            ({s.get('axisX', '0')} {s.get('axisY', '0')} {s.get('axisZ', '1')});
            omega           {s.get('omega', '10.47')};  // rad/s
            nonRotatingPatches ({patches});
        }}
    }}"""


def _gen_fixed_temperature(name, s):
    return f"""    {name}
    {{
        type            fixedTemperatureConstraint;
        active          {s.get('active', 'true')};

        fixedTemperatureConstraintCoeffs
        {{
            mode            {s.get('mode', 'uniform')};
            temperature     {s.get('temperature', '300')};
        }}
    }}"""


def _gen_heat_source(name, s):
    return f"""    {name}
    {{
        type            scalarSemiImplicitSource;
        active          {s.get('active', 'true')};

        scalarSemiImplicitSourceCoeffs
        {{
            selectionMode   {s.get('selectionMode', 'cellZone')};
            cellZone        {s.get('cellZone', 'heaterZone')};
            volumeMode      {s.get('volumeMode', 'specific')};
            injectionRateSuSp
            {{
                {s.get('field', 'e')}     ({s.get('Su', '1000')} 0);
            }}
        }}
    }}"""


def _gen_explicit_porosity(name, s):
    return f"""    {name}
    {{
        type            explicitPorositySource;
        active          {s.get('active', 'true')};

        explicitPorositySourceCoeffs
        {{
            selectionMode   cellZone;
            cellZone        {s.get('cellZone', 'porousZone')};
            type            {s.get('porosityType', 'DarcyForchheimer')};

            DarcyForchheimerCoeffs
            {{
                d   d [0 -2 0 0 0 0 0] ({s.get('dx', '1e6')} {s.get('dy', '1e6')} {s.get('dz', '1e6')});
                f   f [0 -1 0 0 0 0 0] ({s.get('fx', '0')} {s.get('fy', '0')} {s.get('fz', '0')});

                coordinateSystem
                {{
                    type    cartesian;
                    origin  (0 0 0);
                    coordinateRotation
                    {{
                        type    axesRotation;
                        e1      (1 0 0);
                        e2      (0 1 0);
                    }}
                }}
            }}
        }}
    }}"""


def _gen_actuator_disk(name, s):
    return f"""    {name}
    {{
        type            actuationDiskSource;
        active          {s.get('active', 'true')};

        actuationDiskSourceCoeffs
        {{
            selectionMode   cellZone;
            cellZone        {s.get('cellZone', 'diskZone')};
            diskDir         ({s.get('diskDirX', '1')} {s.get('diskDirY', '0')} {s.get('diskDirZ', '0')});
            Cp              {s.get('Cp', '0.386')};
            Ct              {s.get('Ct', '0.58')};
            diskArea        {s.get('diskArea', '1.0')};
            upstreamPoint   ({s.get('upX', '-1')} {s.get('upY', '0')} {s.get('upZ', '0')});
        }}
    }}"""


def _gen_mean_velocity_force(name, s):
    return f"""    {name}
    {{
        type            meanVelocityForce;
        active          {s.get('active', 'true')};

        meanVelocityForceCoeffs
        {{
            selectionMode   all;
            fieldName       U;
            Ubar            ({s.get('UbarX', '10')} {s.get('UbarY', '0')} {s.get('UbarZ', '0')});
            relaxation      {s.get('relaxation', '1.0')};
        }}
    }}"""


def _gen_coded_source(name, s):
    return f"""    {name}
    {{
        type            codedSource;
        active          {s.get('active', 'true')};

        codedSourceCoeffs
        {{
            selectionMode   all;
            field           {s.get('field', 'U')};
            codeInclude     #{{}};
            codeCorrect     #{{}};
            codeAddSup
            {{
                // Add your source term code here
                // const vectorField& C = mesh().C();
                // Subtract velocity to create a pressure drop
            }};
        }}
        name            {name};
    }}"""


def _gen_radiation(name, s):
    return f"""    {name}
    {{
        type            radiation;
        active          {s.get('active', 'true')};

        radiationCoeffs
        {{
            radiationModel  {s.get('radiationModel', 'P1')};

            solverFreq      {s.get('solverFreq', '1')};

            absorptionEmissionModel {s.get('absorptionModel', 'constantAbsorptionEmission')};
            constantAbsorptionEmissionCoeffs
            {{
                absorptivity    {s.get('absorptivity', '0.5')};
                emissivity      {s.get('emissivity', '0.5')};
                E               {s.get('E', '0')};
            }}

            scatterModel    none;
            sootModel       none;
        }}
    }}"""


def _gen_limiting(name, s):
    return f"""    {name}
    {{
        type            limitTemperature;
        active          {s.get('active', 'true')};

        limitTemperatureCoeffs
        {{
            selectionMode   all;
            min             {s.get('Tmin', '200')};
            max             {s.get('Tmax', '500')};
        }}
    }}"""


# ------------------------------------------------------------------ #
#  Master catalog
# ------------------------------------------------------------------ #

FV_OPTIONS_CATALOG = {
    "MRFSource": {
        "description": "Multiple Reference Frame (rotating zone)",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Cell Zone", "cellZone", "rotatingZone", "str", None),
            ("Origin X", "originX", "0", "str", None),
            ("Origin Y", "originY", "0", "str", None),
            ("Origin Z", "originZ", "0", "str", None),
            ("Axis X", "axisX", "0", "str", None),
            ("Axis Y", "axisY", "0", "str", None),
            ("Axis Z", "axisZ", "1", "str", None),
            ("Omega [rad/s]", "omega", "10.47", "str", None),
            ("Non-Rotating Patches", "nonRotatingPatches", "", "str", None),
        ],
        "generator": _gen_mrf,
    },
    "explicitPorositySource": {
        "description": "Darcy-Forchheimer porous zone",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Cell Zone", "cellZone", "porousZone", "str", None),
            ("Porosity Type", "porosityType", "DarcyForchheimer", "combo",
             ["DarcyForchheimer", "powerLaw"]),
            ("d coefficients X [1/m²]", "dx", "1e6", "str", None),
            ("d coefficients Y [1/m²]", "dy", "1e6", "str", None),
            ("d coefficients Z [1/m²]", "dz", "1e6", "str", None),
            ("f coefficients X [1/m]", "fx", "0", "str", None),
            ("f coefficients Y [1/m]", "fy", "0", "str", None),
            ("f coefficients Z [1/m]", "fz", "0", "str", None),
        ],
        "generator": _gen_explicit_porosity,
    },
    "scalarSemiImplicitSource": {
        "description": "Volumetric heat / scalar source",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Selection Mode", "selectionMode", "cellZone", "combo",
             ["cellZone", "all", "points"]),
            ("Cell Zone", "cellZone", "heaterZone", "str", None),
            ("Volume Mode", "volumeMode", "specific", "combo",
             ["specific", "absolute"]),
            ("Field", "field", "e", "combo", ["e", "h", "T"]),
            ("Source Value Su [W/m³ or W]", "Su", "1000", "str", None),
        ],
        "generator": _gen_heat_source,
    },
    "fixedTemperatureConstraint": {
        "description": "Fix temperature in a zone",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Mode", "mode", "uniform", "combo", ["uniform", "lookup"]),
            ("Temperature [K]", "temperature", "300", "str", None),
        ],
        "generator": _gen_fixed_temperature,
    },
    "actuationDiskSource": {
        "description": "Actuator disk model for propellers / turbines",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Cell Zone", "cellZone", "diskZone", "str", None),
            ("Disk Direction X", "diskDirX", "1", "str", None),
            ("Disk Direction Y", "diskDirY", "0", "str", None),
            ("Disk Direction Z", "diskDirZ", "0", "str", None),
            ("Power Coeff Cp", "Cp", "0.386", "str", None),
            ("Thrust Coeff Ct", "Ct", "0.58", "str", None),
            ("Disk Area [m²]", "diskArea", "1.0", "str", None),
            ("Upstream Point X", "upX", "-1", "str", None),
            ("Upstream Point Y", "upY", "0", "str", None),
            ("Upstream Point Z", "upZ", "0", "str", None),
        ],
        "generator": _gen_actuator_disk,
    },
    "meanVelocityForce": {
        "description": "Force flow to match a target mean velocity (periodic flows)",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Ubar X [m/s]", "UbarX", "10", "str", None),
            ("Ubar Y [m/s]", "UbarY", "0", "str", None),
            ("Ubar Z [m/s]", "UbarZ", "0", "str", None),
            ("Relaxation", "relaxation", "1.0", "str", None),
        ],
        "generator": _gen_mean_velocity_force,
    },
    "limitTemperature": {
        "description": "Clamp temperature between min and max",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Min Temperature [K]", "Tmin", "200", "str", None),
            ("Max Temperature [K]", "Tmax", "500", "str", None),
        ],
        "generator": _gen_limiting,
    },
    "radiation": {
        "description": "Radiation source term (P1, fvDOM, etc.)",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Radiation Model", "radiationModel", "P1", "combo",
             ["P1", "fvDOM", "viewFactor", "opaqueSolid", "none"]),
            ("Solver Frequency", "solverFreq", "1", "int", (1, 100)),
            ("Absorption Model", "absorptionModel", "constantAbsorptionEmission", "combo",
             ["constantAbsorptionEmission", "greyMeanAbsorptionEmission",
              "wideBandAbsorptionEmission"]),
            ("Absorptivity", "absorptivity", "0.5", "str", None),
            ("Emissivity", "emissivity", "0.5", "str", None),
        ],
        "generator": _gen_radiation,
    },
    "codedSource": {
        "description": "User-coded source term (C++)",
        "fields": [
            ("Active", "active", "true", "combo", ["true", "false"]),
            ("Field", "field", "U", "combo", ["U", "p", "T", "k", "epsilon", "omega"]),
        ],
        "generator": _gen_coded_source,
    },
}
