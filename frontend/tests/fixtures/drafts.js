/* Generated fixture -- what a new soil starts as, in the one document the GUI
   (property-sets.js, material-library.js) and the command line (core/model/drafts.py)
   are both held to. See tests/test_draft_parity.py, which writes and compares it, and
   frontend/tests/test-drafts.js, which reads it.

   Not hand-edited. `python tests/test_draft_parity.py --write` rebuilds it.
*/
window.DRAFTS_FIXTURE =
{
  "soil_laws": {
    "2": "GeoLinearElasticPlaneStrain2DLaw",
    "3": "GeoIncrementalLinearElastic3DLaw"
  },
  "soil_defaults": {
    "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
    "YOUNG_MODULUS": 10000000.0,
    "POISSON_RATIO": 0.3,
    "DENSITY_SOLID": 1732.9255861365953,
    "POROSITY": 0.0,
    "PERMEABILITY_XX": 1.1574074074074073e-05,
    "GEO_COHESION": 0.0,
    "GEO_FRICTION_ANGLE": 30.0
  },
  "library": [
    {
      "id": "m1",
      "name": "Fill",
      "color": "#d8c48a",
      "r_inter": 0.7,
      "interface_permeability": "Neutral",
      "variables": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 15000000.0,
        "POISSON_RATIO": 0.3,
        "DENSITY_SOLID": 1732.9255861365953,
        "PERMEABILITY_XX": 1.1574074074074073e-05,
        "POROSITY": 0.0,
        "GEO_COHESION": 1000,
        "GEO_FRICTION_ANGLE": 30.0
      }
    },
    {
      "id": "m2",
      "name": "Sand, loose",
      "color": "#c4a86a",
      "r_inter": 0.7,
      "interface_permeability": "Neutral",
      "variables": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 25000000.0,
        "POISSON_RATIO": 0.28,
        "DENSITY_SOLID": 1834.8623853211009,
        "PERMEABILITY_XX": 1.736111111111111e-05,
        "POROSITY": 0.0,
        "GEO_COHESION": 500,
        "GEO_FRICTION_ANGLE": 32.0
      }
    },
    {
      "id": "m3",
      "name": "Clay, soft",
      "color": "#8fa86b",
      "r_inter": 0.5,
      "interface_permeability": "Impermeable",
      "variables": {
        "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
        "YOUNG_MODULUS": 4000000.0,
        "POISSON_RATIO": 0.35,
        "DENSITY_SOLID": 1529.051987767584,
        "PERMEABILITY_XX": 1.1574074074074074e-09,
        "POROSITY": 0.0,
        "GEO_COHESION": 5000,
        "GEO_FRICTION_ANGLE": 22.0
      }
    },
    {
      "id": "m4",
      "name": "Clay, stiff",
      "color": "#6f8fa8",
      "r_inter": 0.55,
      "interface_permeability": "Impermeable",
      "variables": {
        "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
        "YOUNG_MODULUS": 12000000.0,
        "POISSON_RATIO": 0.33,
        "DENSITY_SOLID": 1783.893985728848,
        "PERMEABILITY_XX": 5.787037037037037e-09,
        "POROSITY": 0.0,
        "GEO_COHESION": 15000,
        "GEO_FRICTION_ANGLE": 25.0
      }
    },
    {
      "id": "m5",
      "name": "Sand, dense",
      "color": "#b08a6a",
      "r_inter": 0.75,
      "interface_permeability": "Neutral",
      "variables": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 45000000.0,
        "POISSON_RATIO": 0.25,
        "DENSITY_SOLID": 1936.7991845056065,
        "PERMEABILITY_XX": 5.787037037037037e-05,
        "POROSITY": 0.0,
        "GEO_COHESION": 0,
        "GEO_FRICTION_ANGLE": 36.0
      }
    },
    {
      "id": "m6",
      "name": "Bedrock",
      "color": "#8d8d99",
      "r_inter": 1.0,
      "interface_permeability": "Impermeable",
      "variables": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 2000000000.0,
        "POISSON_RATIO": 0.2,
        "DENSITY_SOLID": 2446.4831804281343,
        "PERMEABILITY_XX": 0.0,
        "POROSITY": 0.0
      }
    }
  ]
};
