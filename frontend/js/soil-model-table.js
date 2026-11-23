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
    "mohr_coulomb",
    "udsm"
  ],
  "other": "other",
  "flowing": [
    "FULLY_COUPLED"
  ],
  "udsm": {
    "model": "udsm",
    "variables": [
      "UDSM_NAME",
      "UDSM_NUMBER",
      "IS_FORTRAN_UDSM",
      "UMAT_PARAMETERS",
      "INDEX_OF_UMAT_C_PARAMETER",
      "INDEX_OF_UMAT_PHI_PARAMETER"
    ],
    "required": [
      "UDSM_NAME",
      "UDSM_NUMBER",
      "UMAT_PARAMETERS"
    ]
  },
  "unsaturated": [
    "SaturatedBelowPhreaticLevelLaw",
    "VanGenuchtenLaw"
  ],
  "blank": {
    "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
    "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
    "SATURATED_SATURATION": 1.0,
    "RESIDUAL_SATURATION": 1e-10
  },
  "palette": [
    "#d8c48a",
    "#8fa86b",
    "#6f8fa8",
    "#c4785a",
    "#9a80b0",
    "#5fa89f",
    "#b08a6a",
    "#b0606f",
    "#7f9f3f",
    "#4f6f9f",
    "#d89a4a",
    "#8d8d99"
  ],
  "vectors": [
    "GEO_COHESION_FUNCTION_COEFFICIENTS",
    "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS",
    "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS"
  ],
  "constants": {
    "WATER_SPECIFIC_WEIGHT": 10000.0,
    "WATER_BULK_MODULUS": 2200000000.0,
    "WATER_VISCOSITY": 0.001,
    "BULK_MODULUS_SOLID": 10000000000.0,
    "PERMEABILITY": 1.1574074074074074e-12,
    "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
    "VAN_GENUCHTEN_GL": 1.25
  },
  "computed": {
    "UNIT_WEIGHT_DRY": {
      "label": "Unit weight, dry",
      "quantity": "specific weight",
      "group": "Weight"
    },
    "UNIT_WEIGHT_SATURATED": {
      "label": "Unit weight, saturated",
      "quantity": "specific weight",
      "group": "Weight"
    },
    "HYDRAULIC_CONDUCTIVITY_XX": {
      "label": "Darcy permeability xx",
      "quantity": "velocity",
      "group": "Flow"
    },
    "HYDRAULIC_CONDUCTIVITY_YY": {
      "label": "Darcy permeability yy",
      "quantity": "velocity",
      "group": "Flow"
    }
  },
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
              "label": "Drainage type",
              "default": "CONSTANT_PW_FIELD",
              "choices": [
                "CONSTANT_PW_FIELD",
                "FULLY_COUPLED"
              ],
              "choice_text": {
                "CONSTANT_PW_FIELD": {
                  "label": "Mechanical only",
                  "note": "Solves displacements with prescribed pore pressures"
                },
                "FULLY_COUPLED": {
                  "label": "Fully coupled",
                  "note": "Solves pore pressures and displacements coupled with a UPw formulation"
                }
              },
              "absent": "CONSTANT_PW_FIELD"
            }
          ]
        },
        {
          "title": "Stiffness",
          "parameters": [
            {
              "name": "YOUNG_MODULUS",
              "label": "Young's modulus",
              "default": 10000000.0,
              "required": true
            },
            {
              "name": "POISSON_RATIO",
              "label": "Poisson's ratio",
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
              "label": "Density of the solid",
              "default": 1732.9255861365953,
              "required": true
            },
            {
              "name": "POROSITY",
              "label": "Porosity",
              "default": 0.0,
              "required": true
            }
          ]
        },
        {
          "title": "Saturation",
          "parameters": [
            {
              "name": "RETENTION_LAW",
              "label": "Retention law",
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
              "label": "Saturated saturation",
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
              "label": "Residual saturation",
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
              "name": "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
              "label": "Air entry pressure",
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
              "label": "Pore size distribution index g_n",
              "default": 1.377,
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
          "title": "Flow",
          "parameters": [
            {
              "name": "PERMEABILITY_XX",
              "label": "Intrinsic permeability xx",
              "default": 1.1574074074074074e-12,
              "flow": true
            },
            {
              "name": "PERMEABILITY_YY",
              "label": "Intrinsic permeability yy",
              "flow": true
            },
            {
              "name": "MINIMUM_RELATIVE_PERMEABILITY",
              "label": "Minimum relative permeability",
              "default": 0.0001,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            },
            {
              "name": "VAN_GENUCHTEN_GL",
              "label": "Relative permeability exponent g_l",
              "default": 1.25,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            }
          ]
        },
        {
          "title": "Grain-water interaction",
          "parameters": [
            {
              "name": "BULK_MODULUS_SOLID",
              "label": "Bulk modulus of the grains",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
                ]
              }
            },
            {
              "name": "BIOT_COEFFICIENT",
              "label": "Biot coefficient",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
                ]
              }
            }
          ]
        },
        {
          "title": "Initial stresses",
          "parameters": [
            {
              "name": "K0_NC",
              "label": "K0, normally consolidated"
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
              "label": "Drainage type",
              "default": "CONSTANT_PW_FIELD",
              "choices": [
                "CONSTANT_PW_FIELD",
                "FULLY_COUPLED"
              ],
              "choice_text": {
                "CONSTANT_PW_FIELD": {
                  "label": "Mechanical only",
                  "note": "Solves displacements with prescribed pore pressures"
                },
                "FULLY_COUPLED": {
                  "label": "Fully coupled",
                  "note": "Solves pore pressures and displacements coupled with a UPw formulation"
                }
              },
              "absent": "CONSTANT_PW_FIELD"
            }
          ]
        },
        {
          "title": "Stiffness",
          "parameters": [
            {
              "name": "YOUNG_MODULUS",
              "label": "Young's modulus",
              "default": 10000000.0,
              "required": true
            },
            {
              "name": "POISSON_RATIO",
              "label": "Poisson's ratio",
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
              "label": "Density of the solid",
              "default": 1732.9255861365953,
              "required": true
            },
            {
              "name": "POROSITY",
              "label": "Porosity",
              "default": 0.0,
              "required": true
            }
          ]
        },
        {
          "title": "Saturation",
          "parameters": [
            {
              "name": "RETENTION_LAW",
              "label": "Retention law",
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
              "label": "Saturated saturation",
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
              "label": "Residual saturation",
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
              "name": "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
              "label": "Air entry pressure",
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
              "label": "Pore size distribution index g_n",
              "default": 1.377,
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
          "title": "Flow",
          "parameters": [
            {
              "name": "PERMEABILITY_XX",
              "label": "Intrinsic permeability xx",
              "default": 1.1574074074074074e-12,
              "flow": true
            },
            {
              "name": "PERMEABILITY_YY",
              "label": "Intrinsic permeability yy",
              "flow": true
            },
            {
              "name": "MINIMUM_RELATIVE_PERMEABILITY",
              "label": "Minimum relative permeability",
              "default": 0.0001,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            },
            {
              "name": "VAN_GENUCHTEN_GL",
              "label": "Relative permeability exponent g_l",
              "default": 1.25,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            }
          ]
        },
        {
          "title": "Grain-water interaction",
          "parameters": [
            {
              "name": "BULK_MODULUS_SOLID",
              "label": "Bulk modulus of the grains",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
                ]
              }
            },
            {
              "name": "BIOT_COEFFICIENT",
              "label": "Biot coefficient",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
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
              "label": "Cohesion",
              "default": 1000.0,
              "required": true
            },
            {
              "name": "GEO_FRICTION_ANGLE",
              "label": "Friction angle",
              "default": 30.0,
              "required": true
            },
            {
              "name": "GEO_DILATANCY_ANGLE",
              "label": "Dilatancy angle",
              "default": 0.0,
              "required": true
            },
            {
              "name": "GEO_ENABLE_TENSION_CUT_OFF",
              "label": "Tension cut-off",
              "default": false,
              "flag": true,
              "absent": false
            },
            {
              "name": "GEO_TENSILE_STRENGTH",
              "label": "Tensile strength",
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
          "title": "Hardening",
          "parameters": [
            {
              "name": "GEO_COULOMB_HARDENING_TYPE",
              "label": "Hardening",
              "choices": [
                "None",
                "Linear"
              ],
              "absent": "None"
            },
            {
              "name": "GEO_COHESION_FUNCTION_COEFFICIENTS",
              "label": "Cohesion slope",
              "default": 0.0,
              "when": {
                "name": "GEO_COULOMB_HARDENING_TYPE",
                "values": [
                  "Linear"
                ]
              }
            },
            {
              "name": "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS",
              "label": "Friction angle slope",
              "default": 0.0,
              "when": {
                "name": "GEO_COULOMB_HARDENING_TYPE",
                "values": [
                  "Linear"
                ]
              }
            },
            {
              "name": "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS",
              "label": "Dilatancy angle slope",
              "default": 0.0,
              "when": {
                "name": "GEO_COULOMB_HARDENING_TYPE",
                "values": [
                  "Linear"
                ]
              }
            }
          ]
        },
        {
          "title": "Initial stresses",
          "parameters": [
            {
              "name": "K0_NC",
              "label": "K0, normally consolidated"
            }
          ]
        }
      ]
    },
    "udsm": {
      "label": "User-defined (UDSM)",
      "laws": {
        "2": "SmallStrainUDSM2DPlaneStrainLaw",
        "3": "SmallStrainUDSM3DLaw"
      },
      "old_laws": {},
      "groups": [
        {
          "title": "Drainage",
          "parameters": [
            {
              "name": "GEO_DRAINAGE_TYPE",
              "label": "Drainage type",
              "default": "CONSTANT_PW_FIELD",
              "choices": [
                "CONSTANT_PW_FIELD",
                "FULLY_COUPLED"
              ],
              "choice_text": {
                "CONSTANT_PW_FIELD": {
                  "label": "Mechanical only",
                  "note": "Solves displacements with prescribed pore pressures"
                },
                "FULLY_COUPLED": {
                  "label": "Fully coupled",
                  "note": "Solves pore pressures and displacements coupled with a UPw formulation"
                }
              },
              "absent": "CONSTANT_PW_FIELD"
            }
          ]
        },
        {
          "title": "Weight",
          "parameters": [
            {
              "name": "DENSITY_SOLID",
              "label": "Density of the solid",
              "default": 1732.9255861365953,
              "required": true
            },
            {
              "name": "POROSITY",
              "label": "Porosity",
              "default": 0.0,
              "required": true
            }
          ]
        },
        {
          "title": "Saturation",
          "parameters": [
            {
              "name": "RETENTION_LAW",
              "label": "Retention law",
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
              "label": "Saturated saturation",
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
              "label": "Residual saturation",
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
              "name": "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
              "label": "Air entry pressure",
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
              "label": "Pore size distribution index g_n",
              "default": 1.377,
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
          "title": "Flow",
          "parameters": [
            {
              "name": "PERMEABILITY_XX",
              "label": "Intrinsic permeability xx",
              "default": 1.1574074074074074e-12,
              "flow": true
            },
            {
              "name": "PERMEABILITY_YY",
              "label": "Intrinsic permeability yy",
              "flow": true
            },
            {
              "name": "MINIMUM_RELATIVE_PERMEABILITY",
              "label": "Minimum relative permeability",
              "default": 0.0001,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "SaturatedBelowPhreaticLevelLaw",
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            },
            {
              "name": "VAN_GENUCHTEN_GL",
              "label": "Relative permeability exponent g_l",
              "default": 1.25,
              "when": {
                "name": "RETENTION_LAW",
                "values": [
                  "VanGenuchtenLaw"
                ]
              },
              "flow": true
            }
          ]
        },
        {
          "title": "Grain-water interaction",
          "parameters": [
            {
              "name": "BULK_MODULUS_SOLID",
              "label": "Bulk modulus of the grains",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
                ]
              }
            },
            {
              "name": "BIOT_COEFFICIENT",
              "label": "Biot coefficient",
              "when": {
                "name": "GEO_DRAINAGE_TYPE",
                "values": [
                  "FULLY_COUPLED"
                ]
              }
            }
          ]
        },
        {
          "title": "Initial stresses",
          "parameters": [
            {
              "name": "K0_NC",
              "label": "K0, normally consolidated"
            }
          ]
        }
      ]
    }
  }
};
