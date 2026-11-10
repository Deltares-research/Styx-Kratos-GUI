/* Generated from core/model/units.py -- the unit systems a project can be in, each
   quantity's dimension (mass, length, time) and label, and the quantity of every Kratos
   variable the application knows. Read by frontend/js/units.js.

   Not hand-edited: `python tests/test_unit_table.py --write` rebuilds it, and
   tests/test_unit_table.py fails when it is stale.
*/
window.App = window.App || {};
App.UNIT_TABLE =
{
  "default": "SI",
  "gravity": 9.81,
  "systems": {
    "SI": {
      "title": "SI (N, m, kg, s)",
      "mass": 1.0,
      "length": 1.0,
      "time": 1.0
    },
    "kN": {
      "title": "kN, m, t, s",
      "mass": 1000.0,
      "length": 1.0,
      "time": 1.0
    }
  },
  "quantities": {
    "stress": {
      "dimension": [
        1,
        -1,
        -2
      ],
      "labels": {
        "SI": "Pa",
        "kN": "kPa"
      }
    },
    "force": {
      "dimension": [
        1,
        1,
        -2
      ],
      "labels": {
        "SI": "N",
        "kN": "kN"
      }
    },
    "line force": {
      "dimension": [
        1,
        0,
        -2
      ],
      "labels": {
        "SI": "N/m",
        "kN": "kN/m"
      }
    },
    "moment per length": {
      "dimension": [
        1,
        1,
        -2
      ],
      "labels": {
        "SI": "N·m/m",
        "kN": "kN·m/m"
      }
    },
    "density": {
      "dimension": [
        1,
        -3,
        0
      ],
      "labels": {
        "SI": "kg/m³",
        "kN": "t/m³"
      }
    },
    "specific weight": {
      "dimension": [
        1,
        -2,
        -2
      ],
      "labels": {
        "SI": "N/m³",
        "kN": "kN/m³"
      }
    },
    "stiffness per area": {
      "dimension": [
        1,
        -2,
        -2
      ],
      "labels": {
        "SI": "N/m³",
        "kN": "kN/m³"
      }
    },
    "viscosity": {
      "dimension": [
        1,
        -1,
        -1
      ],
      "labels": {
        "SI": "Pa·s",
        "kN": "kPa·s"
      }
    },
    "permeability": {
      "dimension": [
        0,
        2,
        0
      ],
      "labels": {
        "SI": "m²",
        "kN": "m²"
      }
    },
    "area": {
      "dimension": [
        0,
        2,
        0
      ],
      "labels": {
        "SI": "m²",
        "kN": "m²"
      }
    },
    "second moment of area": {
      "dimension": [
        0,
        4,
        0
      ],
      "labels": {
        "SI": "m⁴",
        "kN": "m⁴"
      }
    },
    "length": {
      "dimension": [
        0,
        1,
        0
      ],
      "labels": {
        "SI": "m",
        "kN": "m"
      }
    },
    "acceleration": {
      "dimension": [
        0,
        1,
        -2
      ],
      "labels": {
        "SI": "m/s²",
        "kN": "m/s²"
      }
    },
    "velocity": {
      "dimension": [
        0,
        1,
        -1
      ],
      "labels": {
        "SI": "m/s",
        "kN": "m/s"
      }
    },
    "flow rate per metre": {
      "dimension": [
        0,
        2,
        -1
      ],
      "labels": {
        "SI": "m³/s/m",
        "kN": "m³/s/m"
      }
    },
    "dimensionless": {
      "dimension": [
        0,
        0,
        0
      ],
      "labels": {
        "SI": "",
        "kN": ""
      }
    },
    "angle": {
      "dimension": [
        0,
        0,
        0
      ],
      "labels": {
        "SI": "°",
        "kN": "°"
      }
    },
    "angle in radians": {
      "dimension": [
        0,
        0,
        0
      ],
      "labels": {
        "SI": "rad",
        "kN": "rad"
      }
    }
  },
  "variables": {
    "YOUNG_MODULUS": "stress",
    "POISSON_RATIO": "dimensionless",
    "GEO_POISSON_UNDRAINED": "dimensionless",
    "DENSITY_SOLID": "density",
    "DENSITY_WATER": "density",
    "POROSITY": "dimensionless",
    "BULK_MODULUS_SOLID": "stress",
    "BULK_MODULUS_FLUID": "stress",
    "DYNAMIC_VISCOSITY": "viscosity",
    "BIOT_COEFFICIENT": "dimensionless",
    "PERMEABILITY_XX": "permeability",
    "PERMEABILITY_YY": "permeability",
    "PERMEABILITY_ZZ": "permeability",
    "PERMEABILITY_XY": "permeability",
    "PERMEABILITY_YZ": "permeability",
    "PERMEABILITY_ZX": "permeability",
    "GEO_COHESION": "stress",
    "GEO_FRICTION_ANGLE": "angle",
    "GEO_DILATANCY_ANGLE": "angle",
    "GEO_TENSILE_STRENGTH": "stress",
    "GEO_COHESION_FUNCTION_COEFFICIENTS": "stress",
    "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS": "angle in radians",
    "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS": "angle in radians",
    "K0_NC": "dimensionless",
    "K0_MAIN_DIRECTION": "dimensionless",
    "K0_VALUE_XX": "dimensionless",
    "K0_VALUE_YY": "dimensionless",
    "K0_VALUE_ZZ": "dimensionless",
    "OCR": "dimensionless",
    "POISSON_UNLOADING_RELOADING": "dimensionless",
    "SATURATED_SATURATION": "dimensionless",
    "RESIDUAL_SATURATION": "dimensionless",
    "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": "stress",
    "VAN_GENUCHTEN_GN": "dimensionless",
    "VAN_GENUCHTEN_GL": "dimensionless",
    "MINIMUM_RELATIVE_PERMEABILITY": "dimensionless",
    "PERMEABILITY_CHANGE_INVERSE_FACTOR": "dimensionless",
    "INTERFACE_NORMAL_STIFFNESS": "stiffness per area",
    "INTERFACE_SHEAR_STIFFNESS": "stiffness per area",
    "DENSITY": "density",
    "CROSS_AREA": "area",
    "AREA_EFFECTIVE_Y": "area",
    "AREA_EFFECTIVE_Z": "area",
    "I33": "second moment of area",
    "I22": "second moment of area",
    "TORSIONAL_INERTIA": "second moment of area",
    "THICKNESS": "length",
    "THICKNESS_EFFECTIVE_Y": "length",
    "THICKNESS_EFFECTIVE_Z": "length",
    "TRUSS_PRESTRESS_PK2": "stress"
  }
};
