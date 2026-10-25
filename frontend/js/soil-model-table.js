/* Generated from core/model/soil_models.py -- the soil models a material can be: each
   one's law per dimension, its older law names, and the parameters the material window
   lists for it, in groups, with their SI defaults, choices and when each is shown. Read
   by frontend/js/soil-models.js.

   Not hand-edited: `python tests/test_soil_model_table.py --write` rebuilds it, and
   tests/test_soil_model_table.py fails when it is stale.
*/
window.App = window.App || {};
App.SOIL_MODEL_TABLE =
{
  "order": [
    "linear_elastic",
    "mohr_coulomb"
  ],
  "other": "other",
  "models": {
    "linear_elastic": {
      "label": "Linear elastic",
      "laws": {
        "2": "GeoLinearElasticPlaneStrain2DLaw",
        "3": "GeoIncrementalLinearElastic3DLaw"
      },
      "old_laws": {},
      "groups": [
        {
          "title": "Drainage",
          "parameters": [
            {
              "name": "GEO_DRAINAGE_TYPE",
              "default": "CONSTANT_PW_FIELD",
              "choices": [
                "CONSTANT_PW_FIELD",
                "FULLY_COUPLED",
                "DRAINED",
                "UNDRAINED"
              ],
              "absent": "CONSTANT_PW_FIELD"
            },
            {
              "name": "GEO_POISSON_UNDRAINED",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "UNDRAINED"
                ]
              }
            }
          ]
        },
        {
          "title": "Stiffness",
          "parameters": [
            {
              "name": "YOUNG_MODULUS",
              "default": 10000000.0,
              "required": true
            },
            {
              "name": "POISSON_RATIO",
              "default": 0.3,
              "required": true
            }
          ]
        },
        {
          "title": "Weight",
          "parameters": [
            {
              "name": "DENSITY_SOLID",
              "default": 1732.9255861365953,
              "required": true
            },
            {
              "name": "DENSITY_WATER"
            },
            {
              "name": "POROSITY",
              "default": 0.0
            }
          ]
        },
        {
          "title": "Flow",
          "parameters": [
            {
              "name": "PERMEABILITY_XX",
              "default": 1.1574074074074073e-05
            },
            {
              "name": "PERMEABILITY_YY"
            },
            {
              "name": "RETENTION_LAW",
              "choices": [
                "SaturatedLaw",
                "SaturatedBelowPhreaticLevelLaw",
                "VanGenuchtenLaw"
              ],
              "absent": "SaturatedLaw"
            },
            {
              "name": "SATURATED_SATURATION",
              "default": 1.0,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "RESIDUAL_SATURATION",
              "default": 1e-10,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "MINIMUM_RELATIVE_PERMEABILITY",
              "default": 0.0001,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
              "default": 2611.0,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_GN",
              "default": 1.377,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_GL",
              "default": 1.25,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            }
          ]
        },
        {
          "title": "Strength",
          "parameters": [
            {
              "name": "GEO_COHESION",
              "default": 0.0
            },
            {
              "name": "GEO_FRICTION_ANGLE",
              "default": 30.0
            }
          ]
        },
        {
          "title": "Pore fluid",
          "parameters": [
            {
              "name": "BULK_MODULUS_SOLID"
            },
            {
              "name": "BULK_MODULUS_FLUID"
            },
            {
              "name": "BIOT_COEFFICIENT"
            }
          ]
        },
        {
          "title": "Initial stresses",
          "parameters": [
            {
              "name": "K0_NC"
            }
          ]
        }
      ]
    },
    "mohr_coulomb": {
      "label": "Mohr-Coulomb",
      "laws": {
        "2": "GeoMohrCoulombLawPlaneStrain",
        "3": "GeoMohrCoulombLaw3D"
      },
      "old_laws": {
        "GeoMohrCoulombWithTensionCutOff2D": 2,
        "GeoMohrCoulombWithTensionCutOff3D": 3
      },
      "groups": [
        {
          "title": "Drainage",
          "parameters": [
            {
              "name": "GEO_DRAINAGE_TYPE",
              "default": "CONSTANT_PW_FIELD",
              "choices": [
                "CONSTANT_PW_FIELD",
                "FULLY_COUPLED",
                "DRAINED",
                "UNDRAINED"
              ],
              "absent": "CONSTANT_PW_FIELD"
            },
            {
              "name": "GEO_POISSON_UNDRAINED",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "UNDRAINED"
                ]
              }
            }
          ]
        },
        {
          "title": "Stiffness",
          "parameters": [
            {
              "name": "YOUNG_MODULUS",
              "default": 10000000.0,
              "required": true
            },
            {
              "name": "POISSON_RATIO",
              "default": 0.3,
              "required": true
            }
          ]
        },
        {
          "title": "Weight",
          "parameters": [
            {
              "name": "DENSITY_SOLID",
              "default": 1732.9255861365953,
              "required": true
            },
            {
              "name": "DENSITY_WATER"
            },
            {
              "name": "POROSITY",
              "default": 0.0
            }
          ]
        },
        {
          "title": "Flow",
          "parameters": [
            {
              "name": "PERMEABILITY_XX",
              "default": 1.1574074074074073e-05
            },
            {
              "name": "PERMEABILITY_YY"
            },
            {
              "name": "RETENTION_LAW",
              "default": "SaturatedBelowPhreaticLevelLaw",
              "choices": [
                "SaturatedLaw",
                "SaturatedBelowPhreaticLevelLaw",
                "VanGenuchtenLaw"
              ],
              "absent": "SaturatedLaw"
            },
            {
              "name": "SATURATED_SATURATION",
              "default": 1.0,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "RESIDUAL_SATURATION",
              "default": 1e-10,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "MINIMUM_RELATIVE_PERMEABILITY",
              "default": 0.0001,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
              "default": 2611.0,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_GN",
              "default": 1.377,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            },
            {
              "name": "VAN_GENUCHTEN_GL",
              "default": 1.25,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              }
            }
          ]
        },
        {
          "title": "Strength",
          "parameters": [
            {
              "name": "GEO_COHESION",
              "default": 1000.0,
              "required": true
            },
            {
              "name": "GEO_FRICTION_ANGLE",
              "default": 30.0,
              "required": true
            },
            {
              "name": "GEO_DILATANCY_ANGLE",
              "default": 0.0,
              "required": true
            },
            {
              "name": "GEO_ENABLE_TENSION_CUT_OFF",
              "default": false,
              "flag": true,
              "absent": false
            },
            {
              "name": "GEO_TENSILE_STRENGTH",
              "default": 0.0,
              "required": true,
              "when": {
                "name": "GEO_ENABLE_TENSION_CUT_OFF",
                "values": [
                  true
                ]
              }
            }
          ]
        },
        {
          "title": "Pore fluid",
          "parameters": [
            {
              "name": "BULK_MODULUS_SOLID"
            },
            {
              "name": "BULK_MODULUS_FLUID"
            },
            {
              "name": "BIOT_COEFFICIENT"
            }
          ]
        },
        {
          "title": "Initial stresses",
          "parameters": [
            {
              "name": "K0_NC"
            }
          ]
        }
      ]
    }
  }
};
