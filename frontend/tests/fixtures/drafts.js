/* Generated fixture -- what a new soil or structure starts as, in the one document
   the GUI (property-sets.js, material-library.js, beams.js, anchors.js, interfaces.js,
   loads.js, normal-loads.js) and the command line (core/model/drafts.py) are both held
   to. See tests/test_draft_parity.py, which writes and compares it, and
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
  "soil_models": {
    "defaults": {
      "linear_elastic": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 10000000.0,
        "POISSON_RATIO": 0.3,
        "DENSITY_SOLID": 1732.9255861365953,
        "POROSITY": 0.0,
        "PERMEABILITY_XX": 1.1574074074074073e-05,
        "GEO_COHESION": 0.0,
        "GEO_FRICTION_ANGLE": 30.0
      },
      "mohr_coulomb": {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        "YOUNG_MODULUS": 10000000.0,
        "POISSON_RATIO": 0.3,
        "DENSITY_SOLID": 1732.9255861365953,
        "POROSITY": 0.0,
        "PERMEABILITY_XX": 1.1574074074074073e-05,
        "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
        "SATURATED_SATURATION": 1.0,
        "RESIDUAL_SATURATION": 1e-10,
        "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
        "GEO_COHESION": 1000.0,
        "GEO_FRICTION_ANGLE": 30.0,
        "GEO_DILATANCY_ANGLE": 0.0,
        "GEO_ENABLE_TENSION_CUT_OFF": false
      }
    },
    "fill": [
      {
        "title": "a new Mohr-Coulomb soil",
        "before_law": null,
        "before": {},
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {},
        "system": "SI",
        "skip": [],
        "filled": [
          "GEO_DRAINAGE_TYPE",
          "YOUNG_MODULUS",
          "POISSON_RATIO",
          "DENSITY_SOLID",
          "POROSITY",
          "PERMEABILITY_XX",
          "RETENTION_LAW",
          "SATURATED_SATURATION",
          "RESIDUAL_SATURATION",
          "MINIMUM_RELATIVE_PERMEABILITY",
          "GEO_COHESION",
          "GEO_FRICTION_ANGLE",
          "GEO_DILATANCY_ANGLE",
          "GEO_ENABLE_TENSION_CUT_OFF"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "note": "Filled in from the Mohr-Coulomb defaults: GEO_DRAINAGE_TYPE, YOUNG_MODULUS, POISSON_RATIO, DENSITY_SOLID, POROSITY, PERMEABILITY_XX, RETENTION_LAW, SATURATED_SATURATION, RESIDUAL_SATURATION, MINIMUM_RELATIVE_PERMEABILITY, GEO_COHESION, GEO_FRICTION_ANGLE, GEO_DILATANCY_ANGLE, GEO_ENABLE_TENSION_CUT_OFF."
      },
      {
        "title": "an elastic soil made Mohr-Coulomb keeps its cohesion",
        "before_law": "GeoLinearElasticPlaneStrain2DLaw",
        "before": {
          "GEO_COHESION": 5.0,
          "YOUNG_MODULUS": 20000.0
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {},
        "system": "kN",
        "skip": [],
        "filled": [
          "GEO_DRAINAGE_TYPE",
          "POISSON_RATIO",
          "DENSITY_SOLID",
          "POROSITY",
          "PERMEABILITY_XX",
          "RETENTION_LAW",
          "SATURATED_SATURATION",
          "RESIDUAL_SATURATION",
          "MINIMUM_RELATIVE_PERMEABILITY",
          "GEO_FRICTION_ANGLE",
          "GEO_DILATANCY_ANGLE",
          "GEO_ENABLE_TENSION_CUT_OFF"
        ],
        "after": {
          "GEO_COHESION": 5.0,
          "YOUNG_MODULUS": 20000.0,
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "note": "Filled in from the Mohr-Coulomb defaults: GEO_DRAINAGE_TYPE, POISSON_RATIO, DENSITY_SOLID, POROSITY, PERMEABILITY_XX, RETENTION_LAW, SATURATED_SATURATION, RESIDUAL_SATURATION, MINIMUM_RELATIVE_PERMEABILITY, GEO_FRICTION_ANGLE, GEO_DILATANCY_ANGLE, GEO_ENABLE_TENSION_CUT_OFF."
      },
      {
        "title": "a Van Genuchten law brings its parameters",
        "before_law": "GeoMohrCoulombLawPlaneStrain",
        "before": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {
          "RETENTION_LAW": "VanGenuchtenLaw"
        },
        "system": "kN",
        "skip": [],
        "filled": [
          "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
          "VAN_GENUCHTEN_GN",
          "VAN_GENUCHTEN_GL"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "VanGenuchtenLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false,
          "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2.611,
          "VAN_GENUCHTEN_GN": 1.377,
          "VAN_GENUCHTEN_GL": 1.25
        },
        "note": "Filled in from the Mohr-Coulomb defaults: VAN_GENUCHTEN_AIR_ENTRY_PRESSURE, VAN_GENUCHTEN_GN, VAN_GENUCHTEN_GL."
      },
      {
        "title": "a Van Genuchten parameter left out on purpose",
        "before_law": "GeoMohrCoulombLawPlaneStrain",
        "before": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {
          "RETENTION_LAW": "VanGenuchtenLaw"
        },
        "system": "kN",
        "skip": [
          "VAN_GENUCHTEN_GN"
        ],
        "filled": [
          "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE",
          "VAN_GENUCHTEN_GL"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "VanGenuchtenLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false,
          "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2.611,
          "VAN_GENUCHTEN_GL": 1.25
        },
        "note": "Filled in from the Mohr-Coulomb defaults: VAN_GENUCHTEN_AIR_ENTRY_PRESSURE, VAN_GENUCHTEN_GL."
      },
      {
        "title": "the tension cut-off brings its tensile strength",
        "before_law": "GeoMohrCoulombLawPlaneStrain",
        "before": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {
          "GEO_ENABLE_TENSION_CUT_OFF": true
        },
        "system": "kN",
        "skip": [],
        "filled": [
          "GEO_TENSILE_STRENGTH"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": true,
          "GEO_TENSILE_STRENGTH": 0.0
        },
        "note": "Filled in from the Mohr-Coulomb defaults: GEO_TENSILE_STRENGTH."
      },
      {
        "title": "a listed variable left out stays out",
        "before_law": "GeoMohrCoulombLawPlaneStrain",
        "before": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {
          "YOUNG_MODULUS": 30000.0
        },
        "system": "kN",
        "skip": [],
        "filled": [],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 30000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "note": null
      },
      {
        "title": "a required variable left out comes back",
        "before_law": "GeoMohrCoulombLawPlaneStrain",
        "before": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "after_law": "GeoMohrCoulombLawPlaneStrain",
        "changes": {},
        "system": "kN",
        "skip": [],
        "filled": [
          "GEO_DILATANCY_ANGLE"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1.7329255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false,
          "GEO_DILATANCY_ANGLE": 0.0
        },
        "note": "Filled in from the Mohr-Coulomb defaults: GEO_DILATANCY_ANGLE."
      },
      {
        "title": "another law fills nothing",
        "before_law": "GeoLinearElasticPlaneStrain2DLaw",
        "before": {
          "YOUNG_MODULUS": 1.0
        },
        "after_law": "SmallStrainUDSM2DPlaneStrainLaw",
        "changes": {},
        "system": "SI",
        "skip": [],
        "filled": [],
        "after": {
          "YOUNG_MODULUS": 1.0
        },
        "note": null
      },
      {
        "title": "an old Mohr-Coulomb name is Mohr-Coulomb",
        "before_law": null,
        "before": {},
        "after_law": "GeoMohrCoulombWithTensionCutOff2D",
        "changes": {},
        "system": "SI",
        "skip": [],
        "filled": [
          "GEO_DRAINAGE_TYPE",
          "YOUNG_MODULUS",
          "POISSON_RATIO",
          "DENSITY_SOLID",
          "POROSITY",
          "PERMEABILITY_XX",
          "RETENTION_LAW",
          "SATURATED_SATURATION",
          "RESIDUAL_SATURATION",
          "MINIMUM_RELATIVE_PERMEABILITY",
          "GEO_COHESION",
          "GEO_FRICTION_ANGLE",
          "GEO_DILATANCY_ANGLE",
          "GEO_ENABLE_TENSION_CUT_OFF"
        ],
        "after": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "note": "Filled in from the Mohr-Coulomb defaults: GEO_DRAINAGE_TYPE, YOUNG_MODULUS, POISSON_RATIO, DENSITY_SOLID, POROSITY, PERMEABILITY_XX, RETENTION_LAW, SATURATED_SATURATION, RESIDUAL_SATURATION, MINIMUM_RELATIVE_PERMEABILITY, GEO_COHESION, GEO_FRICTION_ANGLE, GEO_DILATANCY_ANGLE, GEO_ENABLE_TENSION_CUT_OFF."
      }
    ],
    "problem": [
      {
        "title": "a default Mohr-Coulomb soil",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "problem": null
      },
      {
        "title": "dilatancy above friction",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 35.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "problem": "GEO_DILATANCY_ANGLE cannot be larger than GEO_FRICTION_ANGLE."
      },
      {
        "title": "friction at 90 degrees",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 90.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "problem": "GEO_FRICTION_ANGLE must be below 90 degrees."
      },
      {
        "title": "tensile strength above the apex",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": true,
          "GEO_TENSILE_STRENGTH": 5000.0
        },
        "problem": "GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / tan(GEO_FRICTION_ANGLE) = 1732.05."
      },
      {
        "title": "tensile strength above the apex, a large one",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 2000000.0,
          "GEO_FRICTION_ANGLE": 25.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": true,
          "GEO_TENSILE_STRENGTH": 10000000.0
        },
        "problem": "GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / tan(GEO_FRICTION_ANGLE) = 4.28901e+06."
      },
      {
        "title": "tensile strength above the apex, a small one",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 2e-05,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": true,
          "GEO_TENSILE_STRENGTH": 1.0
        },
        "problem": "GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / tan(GEO_FRICTION_ANGLE) = 3.4641e-05."
      },
      {
        "title": "a tensile strength with the cut-off off is not read",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false,
          "GEO_TENSILE_STRENGTH": 5000.0
        },
        "problem": null
      },
      {
        "title": "a tensile strength with no cut-off flag switches it on",
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 0.0,
          "GEO_TENSILE_STRENGTH": 5000.0
        },
        "problem": "GEO_TENSILE_STRENGTH cannot be larger than GEO_COHESION / tan(GEO_FRICTION_ANGLE) = 1732.05."
      },
      {
        "title": "an elastic soil is not held to it",
        "law": "GeoLinearElasticPlaneStrain2DLaw",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 10000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.0,
          "PERMEABILITY_XX": 1.1574074074074073e-05,
          "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
          "SATURATED_SATURATION": 1.0,
          "RESIDUAL_SATURATION": 1e-10,
          "MINIMUM_RELATIVE_PERMEABILITY": 0.0001,
          "GEO_COHESION": 1000.0,
          "GEO_FRICTION_ANGLE": 30.0,
          "GEO_DILATANCY_ANGLE": 35.0,
          "GEO_ENABLE_TENSION_CUT_OFF": false
        },
        "problem": null
      }
    ],
    "required": [
      {
        "law": "GeoLinearElasticPlaneStrain2DLaw",
        "variables": {},
        "required": [
          "YOUNG_MODULUS",
          "POISSON_RATIO",
          "DENSITY_SOLID"
        ]
      },
      {
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {},
        "required": [
          "YOUNG_MODULUS",
          "POISSON_RATIO",
          "DENSITY_SOLID",
          "GEO_COHESION",
          "GEO_FRICTION_ANGLE",
          "GEO_DILATANCY_ANGLE"
        ]
      },
      {
        "law": "GeoMohrCoulombLawPlaneStrain",
        "variables": {
          "GEO_ENABLE_TENSION_CUT_OFF": true
        },
        "required": [
          "YOUNG_MODULUS",
          "POISSON_RATIO",
          "DENSITY_SOLID",
          "GEO_COHESION",
          "GEO_FRICTION_ANGLE",
          "GEO_DILATANCY_ANGLE",
          "GEO_TENSILE_STRENGTH"
        ]
      },
      {
        "law": "SmallStrainUDSM2DPlaneStrainLaw",
        "variables": {},
        "required": []
      }
    ],
    "law_in": [
      {
        "law": "GeoLinearElasticPlaneStrain2DLaw",
        "dimension": 2,
        "result": "GeoLinearElasticPlaneStrain2DLaw"
      },
      {
        "law": "GeoLinearElasticPlaneStrain2DLaw",
        "dimension": 3,
        "result": "GeoIncrementalLinearElastic3DLaw"
      },
      {
        "law": "GeoMohrCoulombLawPlaneStrain",
        "dimension": 2,
        "result": "GeoMohrCoulombLawPlaneStrain"
      },
      {
        "law": "GeoMohrCoulombLawPlaneStrain",
        "dimension": 3,
        "result": "GeoMohrCoulombLaw3D"
      },
      {
        "law": "GeoMohrCoulombWithTensionCutOff2D",
        "dimension": 2,
        "result": "GeoMohrCoulombLawPlaneStrain"
      },
      {
        "law": "GeoMohrCoulombWithTensionCutOff2D",
        "dimension": 3,
        "result": "GeoMohrCoulombLaw3D"
      },
      {
        "law": "GeoMohrCoulombWithTensionCutOff3D",
        "dimension": 2,
        "result": "GeoMohrCoulombLawPlaneStrain"
      },
      {
        "law": "GeoMohrCoulombWithTensionCutOff3D",
        "dimension": 3,
        "result": "GeoMohrCoulombLaw3D"
      },
      {
        "law": "SmallStrainUDSM2DPlaneStrainLaw",
        "dimension": 2,
        "result": "SmallStrainUDSM2DPlaneStrainLaw"
      },
      {
        "law": "SmallStrainUDSM2DPlaneStrainLaw",
        "dimension": 3,
        "result": "SmallStrainUDSM2DPlaneStrainLaw"
      }
    ]
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
  ],
  "projects": {
    "section": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 2,
      "unit_system": "SI",
      "section_offset": 12.5,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        },
        {
          "id": "load_2d",
          "name": "LineLoad_1",
          "kind": "line",
          "x0": 1.0,
          "x1": 10.0,
          "y": 0.0,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": "load"
        }
      ],
      "beam_sections": [],
      "panel_sections": [],
      "beams": [],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "section_kn": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 2,
      "unit_system": "kN",
      "section_offset": 12.5,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1.7329255861365953,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1.8348623853211008,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.5,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1.529051987767584,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1.783893985728848,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1.9367991845056065,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2.4464831804281344,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        },
        {
          "id": "load_2d",
          "name": "LineLoad_1",
          "kind": "line",
          "x0": 1.0,
          "x1": 10.0,
          "y": 0.0,
          "thickness": 0.25,
          "components": [
            0.0,
            -20.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": "load"
        }
      ],
      "beam_sections": [],
      "panel_sections": [],
      "beams": [],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "dry": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 2,
      "unit_system": "SI",
      "section_offset": 12.5,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        },
        {
          "id": "load_2d",
          "name": "LineLoad_1",
          "kind": "line",
          "x0": 1.0,
          "x1": 10.0,
          "y": 0.0,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": "load"
        }
      ],
      "beam_sections": [],
      "panel_sections": [],
      "beams": [],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": null,
      "boundary_conditions": [],
      "custom_parts": []
    },
    "section_pile_kn": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 2,
      "unit_system": "kN",
      "section_offset": 12.5,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1.7329255861365953,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1.8348623853211008,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.5,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1.529051987767584,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1.783893985728848,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1.9367991845056065,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2.4464831804281344,
            "DENSITY_WATER": 1.019367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000.0,
            "BULK_MODULUS_FLUID": 2200000.0,
            "DYNAMIC_VISCOSITY": 1e-06,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        },
        {
          "id": "load_2d",
          "name": "LineLoad_1",
          "kind": "line",
          "x0": 1.0,
          "x1": 10.0,
          "y": 0.0,
          "thickness": 0.25,
          "components": [
            0.0,
            -20.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": "load"
        }
      ],
      "beam_sections": [
        {
          "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7.85,
            "CROSS_AREA": 0.0198,
            "I33": 0.000552
          },
          "tables": {},
          "id": "beamsection_1",
          "name": "Sheet pile section",
          "spacing": 1.0
        }
      ],
      "panel_sections": [],
      "beams": [
        {
          "id": "beam_1",
          "name": "Sheet pile 1",
          "kind": "beam",
          "section": "beamsection_1",
          "points": [
            [
              12.5,
              0.0
            ],
            [
              12.5,
              -12.5
            ]
          ],
          "active": true,
          "derived_from": null
        }
      ],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "section_tall_pile": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 2,
      "unit_system": "SI",
      "section_offset": 12.5,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        },
        {
          "id": "load_2d",
          "name": "LineLoad_1",
          "kind": "line",
          "x0": 1.0,
          "x1": 10.0,
          "y": 0.0,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": "load"
        }
      ],
      "beam_sections": [
        {
          "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7850.0,
            "CROSS_AREA": 0.0198,
            "I33": 0.000552
          },
          "tables": {},
          "id": "beamsection_1",
          "name": "Sheet pile section",
          "spacing": 1.0
        }
      ],
      "panel_sections": [],
      "beams": [
        {
          "id": "beam_1",
          "name": "Sheet pile 1",
          "kind": "beam",
          "section": "beamsection_1",
          "points": [
            [
              12.0,
              5.0
            ],
            [
              12.0,
              -6.0
            ]
          ],
          "active": true,
          "derived_from": null
        }
      ],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "pile": {
      "name": "Staged excavation",
      "dimension": 2,
      "unit_system": "SI",
      "section_offset": 5.0,
      "domain": {
        "x0": 0.0,
        "x1": 60.0,
        "z0": 0.0,
        "z1": 10.0,
        "y_top": 0.0,
        "y_bottom": -40.0
      },
      "materials": [
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1e-08,
            "PERMEABILITY_YY": 1e-08,
            "PERMEABILITY_XY": 0.0,
            "GEO_COHESION": 2000.0,
            "GEO_FRICTION_ANGLE": 25.0,
            "K0_NC": 0.58
          },
          "tables": {},
          "id": "m_upper",
          "name": "Soft clay",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 30000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1e-05,
            "PERMEABILITY_YY": 1e-05,
            "PERMEABILITY_XY": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 32.0,
            "K0_NC": 0.47
          },
          "tables": {},
          "id": "m_lower",
          "name": "Dense sand",
          "color": "#b08a6a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        }
      ],
      "loads": [
        {
          "id": "surcharge",
          "name": "Load",
          "kind": "line",
          "x0": 6.0,
          "x1": 60.0,
          "y": 0.0,
          "thickness": 0.15,
          "components": [
            0.0,
            -10000.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        }
      ],
      "beam_sections": [
        {
          "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.0,
            "DENSITY": 7850.0,
            "CROSS_AREA": 0.015,
            "I33": 0.0003,
            "AREA_EFFECTIVE_Y": 0.0075
          },
          "tables": {},
          "id": "sheetpile",
          "name": "Sheet pile",
          "spacing": 1.0
        }
      ],
      "panel_sections": [],
      "beams": [
        {
          "id": "sheetpile",
          "name": "SheetPileWall",
          "kind": "beam",
          "section": "sheetpile",
          "points": [
            [
              6.0,
              0.0
            ],
            [
              6.0,
              -12.0
            ]
          ],
          "active": true,
          "derived_from": null
        }
      ],
      "anchor_sections": [
        {
          "constitutive_law": "TrussConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "CROSS_AREA": 0.002,
            "DENSITY": 0.0
          },
          "tables": {},
          "id": "strand",
          "name": "Strut",
          "spacing": 2.0,
          "tension_limit": null,
          "compression_limit": null
        }
      ],
      "anchors": [
        {
          "id": "strut",
          "name": "Strut",
          "kind": "anchor",
          "section": "strand",
          "head": [
            6.0,
            -1.0
          ],
          "tail": [
            5.0,
            -1.0
          ],
          "prestress": 0.0,
          "active": true
        }
      ],
      "interface_sections": [
        {
          "constitutive_law": "GeoIncrementalLinearElasticInterfaceLaw",
          "variables": {},
          "tables": {},
          "id": "contact",
          "name": "Wall contact",
          "material": null,
          "r_inter": 0.67,
          "virtual_thickness": 0.5,
          "permeability": "Neutral"
        }
      ],
      "interfaces": [
        {
          "id": "wall_contact",
          "name": "Interface",
          "kind": "interface",
          "section": "contact",
          "structure": "sheetpile",
          "points": null,
          "side": "both",
          "stretch": null,
          "active": true
        }
      ],
      "normal_loads": [
        {
          "id": "water_1",
          "name": "WaterLoad_Stage1",
          "kind": "normal",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ],
            [
              6.0,
              -1.0
            ]
          ],
          "fluid_pressure_type": "Hydrostatic",
          "pressure": 0.0,
          "reference_coordinate": -1.0,
          "active": true
        },
        {
          "id": "water_2",
          "name": "WaterLoad_Stage2",
          "kind": "normal",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ],
            [
              6.0,
              -1.0
            ]
          ],
          "fluid_pressure_type": "Hydrostatic",
          "pressure": 0.0,
          "reference_coordinate": -1.0,
          "active": true
        },
        {
          "id": "water_3",
          "name": "WaterLoad_Stage3",
          "kind": "normal",
          "points": [
            [
              0.0,
              -7.0
            ],
            [
              6.0,
              -7.0
            ],
            [
              6.0,
              -1.0
            ]
          ],
          "fluid_pressure_type": "Hydrostatic",
          "pressure": 0.0,
          "reference_coordinate": -1.0,
          "active": true
        }
      ],
      "water": {
        "y": -1.0,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.0,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "solid": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 3,
      "unit_system": "SI",
      "section_offset": null,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        }
      ],
      "beam_sections": [],
      "panel_sections": [],
      "beams": [],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "solid_wall": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 3,
      "unit_system": "SI",
      "section_offset": null,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        }
      ],
      "beam_sections": [],
      "panel_sections": [
        {
          "constitutive_law": "LinearElasticPlaneStress2DLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7850.0,
            "THICKNESS": 0.4
          },
          "tables": {},
          "id": "panelsection_1",
          "name": "Wall section"
        }
      ],
      "beams": [
        {
          "id": "panel_1",
          "name": "Wall 1",
          "kind": "panel",
          "section": "panelsection_1",
          "footprint": [
            [
              12.5,
              6.25
            ],
            [
              12.5,
              18.75
            ]
          ],
          "y_top": 0.0,
          "y_toe": -12.5,
          "active": true,
          "derived_from": null
        }
      ],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    },
    "solid_member": {
      "name": "Deep excavation — Rotterdam Zuid",
      "dimension": 3,
      "unit_system": "SI",
      "section_offset": null,
      "domain": {
        "x0": 0.0,
        "x1": 25.0,
        "z0": 0.0,
        "z1": 25.0,
        "y_top": 0.0,
        "y_bottom": -25.0
      },
      "materials": [
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 15000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074073e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 30.0
          },
          "tables": {},
          "id": "m1",
          "name": "Fill",
          "color": "#d8c48a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 25000000.0,
            "POISSON_RATIO": 0.28,
            "DENSITY_SOLID": 1834.8623853211009,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.736111111111111e-05,
            "PERMEABILITY_YY": 1.736111111111111e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.736111111111111e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 500.0,
            "GEO_FRICTION_ANGLE": 32.0
          },
          "tables": {},
          "id": "m2",
          "name": "Sand, loose",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 4000000.0,
            "POISSON_RATIO": 0.35,
            "DENSITY_SOLID": 1529.051987767584,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 1.1574074074074074e-09,
            "PERMEABILITY_YY": 1.1574074074074074e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 1.1574074074074074e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 5000.0,
            "GEO_FRICTION_ANGLE": 22.0
          },
          "tables": {},
          "id": "m3",
          "name": "Clay, soft",
          "color": "#8fa86b",
          "r_inter": 0.5,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
            "YOUNG_MODULUS": 12000000.0,
            "POISSON_RATIO": 0.33,
            "DENSITY_SOLID": 1783.893985728848,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-09,
            "PERMEABILITY_YY": 5.787037037037037e-09,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-09,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 15000.0,
            "GEO_FRICTION_ANGLE": 25.0
          },
          "tables": {},
          "id": "m4",
          "name": "Clay, stiff",
          "color": "#6f8fa8",
          "r_inter": 0.55,
          "interface_permeability": "Impermeable"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 45000000.0,
            "POISSON_RATIO": 0.25,
            "DENSITY_SOLID": 1936.7991845056065,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 5.787037037037037e-05,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 36.0
          },
          "tables": {},
          "id": "m5",
          "name": "Sand, dense",
          "color": "#b08a6a",
          "r_inter": 0.75,
          "interface_permeability": "Neutral"
        },
        {
          "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 2446.4831804281343,
            "DENSITY_WATER": 1019.367991845056,
            "POROSITY": 0.3,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_XX": 0.0,
            "PERMEABILITY_YY": 0.0,
            "PERMEABILITY_XY": 0.0,
            "PERMEABILITY_ZZ": 0.0,
            "PERMEABILITY_YZ": 0.0,
            "PERMEABILITY_ZX": 0.0
          },
          "tables": {},
          "id": "m6",
          "name": "Bedrock",
          "color": "#8d8d99",
          "r_inter": 1.0,
          "interface_permeability": "Impermeable"
        }
      ],
      "loads": [
        {
          "id": "load",
          "name": "SurfaceLoad_1",
          "kind": "surface",
          "x0": 1.0,
          "x1": 10.0,
          "z0": 14.0,
          "z1": 26.0,
          "y": null,
          "thickness": 0.25,
          "components": [
            0.0,
            -20000.0,
            0.0
          ],
          "distribution": "Uniform",
          "active": true,
          "derived_from": null
        }
      ],
      "beam_sections": [
        {
          "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7850.0,
            "CROSS_AREA": 0.0198,
            "I33": 0.000552
          },
          "tables": {},
          "id": "beamsection_1",
          "name": "Sheet pile section",
          "spacing": 1.0
        }
      ],
      "panel_sections": [],
      "beams": [
        {
          "id": "member_1",
          "name": "Member 1",
          "kind": "member",
          "section": "beamsection_1",
          "points": [
            [
              12.5,
              0.0,
              12.5
            ],
            [
              12.5,
              -12.5,
              12.5
            ]
          ],
          "active": true,
          "derived_from": null
        }
      ],
      "anchor_sections": [],
      "anchors": [],
      "interface_sections": [],
      "interfaces": [],
      "normal_loads": [],
      "water": {
        "y": -1.5,
        "margin": 3.0,
        "thickness": 0.06,
        "specific_weight": null
      },
      "boundary_conditions": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "pore_pressure",
          "name": "Pore pressure",
          "kind": "water_pressure",
          "on": "domain",
          "face": null,
          "part": null,
          "points": null,
          "fluid_pressure_type": "Hydrostatic",
          "is_fixed": true,
          "value": 0.0,
          "reference_coordinate": -1.5,
          "x_coordinates": null,
          "y_coordinates": null,
          "z_coordinates": null,
          "pressure_tension_cut_off": 0.0,
          "active": true
        }
      ],
      "custom_parts": []
    }
  },
  "calls": [
    {
      "title": "a sheet pile down the middle",
      "call": "Beams.draft",
      "project": "section",
      "args": [
        "beam"
      ],
      "result": {
        "id": "beam_1",
        "name": "Sheet pile 1",
        "kind": "beam",
        "section": "beamsection_1",
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a sheet pile along given points, on the first profile",
      "call": "Beams.draftFromPoints",
      "project": "pile",
      "args": [
        [
          [
            20,
            0
          ],
          [
            20,
            -6
          ]
        ]
      ],
      "result": {
        "id": "beam_1",
        "name": "Sheet pile 1",
        "kind": "beam",
        "section": "sheetpile",
        "points": [
          [
            20.0,
            0.0
          ],
          [
            20.0,
            -6.0
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a sheet pile below the model is refused",
      "call": "Beams.draftFromPoints",
      "project": "section",
      "args": [
        [
          [
            12,
            0
          ],
          [
            12,
            -40
          ]
        ]
      ],
      "error": "The sheet pile must stay inside the model domain."
    },
    {
      "title": "a sheet pile standing out above the ground",
      "call": "Beams.draftFromPoints",
      "project": "section",
      "args": [
        [
          [
            12,
            5
          ],
          [
            12,
            -6
          ]
        ]
      ],
      "result": {
        "id": "beam_1",
        "name": "Sheet pile 1",
        "kind": "beam",
        "section": "beamsection_1",
        "points": [
          [
            12.0,
            5.0
          ],
          [
            12.0,
            -6.0
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a sheet pile wholly above the ground is refused",
      "call": "Beams.draftFromPoints",
      "project": "section",
      "args": [
        [
          [
            12,
            5
          ],
          [
            12,
            1
          ]
        ]
      ],
      "error": "A sheet pile may stand out above the ground, but part of it has to be in the soil."
    },
    {
      "title": "a sheet pile in the solid model is refused",
      "call": "Beams.draft",
      "project": "solid",
      "args": [
        "beam"
      ],
      "error": "A sheet pile is a 2D section object; switch to 2D, or create a wall instead."
    },
    {
      "title": "the profile a first sheet pile brings",
      "call": "Beams.sectionsFor",
      "project": "section",
      "args": [
        {
          "id": "beam_1",
          "name": "Sheet pile 1",
          "kind": "beam",
          "section": "beamsection_1",
          "points": [
            [
              12.5,
              0.0
            ],
            [
              12.5,
              -12.5
            ]
          ],
          "active": true
        }
      ],
      "result": [
        {
          "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7850.0,
            "CROSS_AREA": 0.0198,
            "I33": 0.000552
          },
          "tables": {},
          "id": "beamsection_1",
          "name": "Sheet pile section",
          "spacing": 1.0
        }
      ]
    },
    {
      "title": "a wall across the middle of the site",
      "call": "Beams.draft",
      "project": "solid",
      "args": [
        "panel"
      ],
      "result": {
        "id": "panel_1",
        "name": "Wall 1",
        "kind": "panel",
        "section": "panelsection_1",
        "footprint": [
          [
            12.5,
            6.25
          ],
          [
            12.5,
            18.75
          ]
        ],
        "y_top": 0.0,
        "y_toe": -12.5,
        "active": true
      }
    },
    {
      "title": "a wall along a given footprint",
      "call": "Beams.draftPanel",
      "project": "solid",
      "args": [
        [
          [
            5,
            5
          ],
          [
            5,
            20
          ]
        ]
      ],
      "result": {
        "id": "panel_1",
        "name": "Wall 1",
        "kind": "panel",
        "section": "panelsection_1",
        "footprint": [
          [
            5.0,
            5.0
          ],
          [
            5.0,
            20.0
          ]
        ],
        "y_top": 0.0,
        "y_toe": -12.5,
        "active": true
      }
    },
    {
      "title": "the shell a first wall brings",
      "call": "Beams.sectionsFor",
      "project": "solid",
      "args": [
        {
          "id": "panel_1",
          "name": "Wall 1",
          "kind": "panel",
          "section": "panelsection_1",
          "footprint": [
            [
              12.5,
              6.25
            ],
            [
              12.5,
              18.75
            ]
          ],
          "y_top": 0.0,
          "y_toe": -12.5,
          "active": true
        }
      ],
      "result": [
        {
          "constitutive_law": "LinearElasticPlaneStress2DLaw",
          "variables": {
            "YOUNG_MODULUS": 210000000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY": 7850.0,
            "THICKNESS": 0.4
          },
          "tables": {},
          "id": "panelsection_1",
          "name": "Wall section"
        }
      ]
    },
    {
      "title": "a member standing in the middle",
      "call": "Beams.draft",
      "project": "solid",
      "args": [
        "member"
      ],
      "result": {
        "id": "member_1",
        "name": "Member 1",
        "kind": "member",
        "section": "beamsection_1",
        "points": [
          [
            12.5,
            0.0,
            12.5
          ],
          [
            12.5,
            -12.5,
            12.5
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a member along given points",
      "call": "Beams.draftMember",
      "project": "solid",
      "args": [
        [
          [
            3,
            0,
            3
          ],
          [
            3,
            -10,
            3
          ]
        ]
      ],
      "result": {
        "id": "member_1",
        "name": "Member 1",
        "kind": "member",
        "section": "beamsection_1",
        "points": [
          [
            3.0,
            0.0,
            3.0
          ],
          [
            3.0,
            -10.0,
            3.0
          ]
        ],
        "active": true
      }
    },
    {
      "title": "an anchor raking back from the pile",
      "call": "Anchors.draft",
      "project": "pile",
      "args": [],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor",
        "section": "strand",
        "head": [
          6.0,
          -3.0
        ],
        "tail": [
          14.19152,
          -8.735764
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "an anchor head snapped onto the pile",
      "call": "Anchors.draftFromPoints",
      "project": "pile",
      "args": [
        [
          [
            6.4,
            -2
          ],
          [
            20,
            -8
          ]
        ]
      ],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor",
        "section": "strand",
        "head": [
          6.0,
          -2.0
        ],
        "tail": [
          20.0,
          -8.0
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "an anchor head far from the pile is refused",
      "call": "Anchors.draftFromPoints",
      "project": "pile",
      "args": [
        [
          [
            10,
            -2
          ],
          [
            20,
            -8
          ]
        ]
      ],
      "error": "The anchor head must be placed on a sheet pile."
    },
    {
      "title": "a strut from the part of a pile above the ground",
      "call": "Anchors.draftFromPoints",
      "project": "section_tall_pile",
      "args": [
        [
          [
            12.3,
            4
          ],
          [
            16,
            4
          ]
        ]
      ],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor",
        "section": "tendon_1",
        "head": [
          12.0,
          4.0
        ],
        "tail": [
          16.0,
          4.0
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "an anchor tail below the model is refused",
      "call": "Anchors.draftFromPoints",
      "project": "section_tall_pile",
      "args": [
        [
          [
            12,
            4
          ],
          [
            16,
            -40
          ]
        ]
      ],
      "error": "The anchor must stay inside the model domain."
    },
    {
      "title": "an anchor raking back from a pile above the ground",
      "call": "Anchors.draft",
      "project": "section_tall_pile",
      "args": [],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor",
        "section": "tendon_1",
        "head": [
          12.0,
          2.25
        ],
        "tail": [
          20.19152,
          -3.485764
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "an anchor with nothing to hang from is refused",
      "call": "Anchors.draft",
      "project": "section",
      "args": [],
      "error": "An anchor hangs from a sheet pile; create one first."
    },
    {
      "title": "an anchor on a wall",
      "call": "Anchors.draft",
      "project": "solid_wall",
      "args": [],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor3d",
        "section": "tendon_1",
        "head": [
          12.5,
          -3.125,
          12.5
        ],
        "tail": [
          20.69152,
          -8.860764,
          12.5
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "an anchor on a member",
      "call": "Anchors.draft",
      "project": "solid_member",
      "args": [],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor3d",
        "section": "tendon_1",
        "head": [
          12.5,
          -3.125,
          12.5
        ],
        "tail": [
          20.69152,
          -8.860764,
          12.5
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "a first anchor in a kN model",
      "call": "Anchors.draft",
      "project": "section_pile_kn",
      "args": [],
      "result": {
        "id": "anchor_1",
        "name": "Anchor 1",
        "kind": "anchor",
        "section": "tendon_1",
        "head": [
          12.5,
          -3.125
        ],
        "tail": [
          20.69152,
          -8.860764
        ],
        "prestress": 0.0,
        "active": true
      }
    },
    {
      "title": "the tendon a first anchor brings, in kN",
      "call": "Anchors.sectionsFor",
      "project": "section_pile_kn",
      "args": [
        {
          "id": "anchor_1",
          "name": "Anchor 1",
          "kind": "anchor",
          "section": "tendon_1",
          "head": [
            12.5,
            -3.125
          ],
          "tail": [
            20.69152,
            -8.860764
          ],
          "prestress": 0.0,
          "active": true
        }
      ],
      "result": [
        {
          "constitutive_law": "TrussConstitutiveLaw",
          "variables": {
            "YOUNG_MODULUS": 195000000.0,
            "CROSS_AREA": 0.0006,
            "DENSITY": 7.85
          },
          "tables": {},
          "id": "tendon_1",
          "name": "Anchor tendon",
          "spacing": 2.5,
          "tension_limit": 900.0,
          "compression_limit": null
        }
      ]
    },
    {
      "title": "an interface on the first pile",
      "call": "Interfaces.draft",
      "project": "pile",
      "args": [],
      "result": {
        "id": "interface_1",
        "name": "Interface 1",
        "kind": "interface",
        "section": "contact",
        "structure": "sheetpile",
        "points": null,
        "side": "both",
        "stretch": null,
        "active": true
      }
    },
    {
      "title": "an interface with no pile is a free line",
      "call": "Interfaces.draft",
      "project": "section",
      "args": [],
      "result": {
        "id": "interface_1",
        "name": "Interface 1",
        "kind": "interface",
        "section": "interfacesection_1",
        "structure": null,
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "side": "left",
        "stretch": null,
        "active": true
      }
    },
    {
      "title": "an interface on a part of the pile, snapped onto it",
      "call": "Interfaces.draft",
      "project": "pile",
      "args": [
        null,
        [
          [
            6.3,
            -2
          ],
          [
            6,
            -5
          ]
        ]
      ],
      "result": {
        "id": "interface_1",
        "name": "Interface 1",
        "kind": "interface",
        "section": "contact",
        "structure": "sheetpile",
        "points": null,
        "side": "both",
        "stretch": [
          [
            6.0,
            -2.0
          ],
          [
            6.0,
            -5.0
          ]
        ],
        "active": true
      }
    },
    {
      "title": "an interface from one end of the pile to the other is the whole pile",
      "call": "Interfaces.draft",
      "project": "pile",
      "args": [
        null,
        [
          [
            6,
            -12
          ],
          [
            6,
            0
          ]
        ]
      ],
      "result": {
        "id": "interface_1",
        "name": "Interface 1",
        "kind": "interface",
        "section": "contact",
        "structure": "sheetpile",
        "points": null,
        "side": "both",
        "stretch": null,
        "active": true
      }
    },
    {
      "title": "a From far from the pile is refused",
      "call": "Interfaces.draft",
      "project": "pile",
      "args": [
        null,
        [
          [
            7.2,
            -2
          ],
          [
            6,
            -5
          ]
        ]
      ],
      "error": "From is 1.2 m from SheetPileWall; From and To are points on the pile."
    },
    {
      "title": "From and To at one point are refused",
      "call": "Interfaces.draft",
      "project": "pile",
      "args": [
        null,
        [
          [
            6.2,
            -3
          ],
          [
            6,
            -3
          ]
        ]
      ],
      "error": "From and To are the same point on SheetPileWall; the part of the pile needs length."
    },
    {
      "title": "the contact a first interface brings",
      "call": "Interfaces.sectionsFor",
      "project": "section",
      "args": [
        {
          "id": "interface_1",
          "name": "Interface 1",
          "kind": "interface",
          "section": "interfacesection_1",
          "structure": null,
          "points": [
            [
              12.5,
              0.0
            ],
            [
              12.5,
              -12.5
            ]
          ],
          "side": "left",
          "stretch": null,
          "active": true
        }
      ],
      "result": [
        {
          "constitutive_law": "GeoIncrementalLinearElasticInterfaceLaw",
          "variables": {},
          "tables": {},
          "id": "interfacesection_1",
          "name": "Interface",
          "material": "m1",
          "r_inter": 0.7,
          "virtual_thickness": 0.01,
          "permeability": "Neutral"
        }
      ]
    },
    {
      "title": "a normal load down the middle",
      "call": "NormalLoads.draft",
      "project": "section",
      "args": [],
      "result": {
        "id": "normalload_1",
        "name": "Normal load 1",
        "kind": "normal",
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "fluid_pressure_type": "Uniform",
        "pressure": 0.0,
        "active": true
      }
    },
    {
      "title": "a hydrostatic normal load takes the water level",
      "call": "NormalLoads.draft",
      "project": "section",
      "args": [
        {
          "hydrostatic": true
        }
      ],
      "result": {
        "id": "normalload_1",
        "name": "Normal load 1",
        "kind": "normal",
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "fluid_pressure_type": "Hydrostatic",
        "pressure": 0.0,
        "reference_coordinate": -1.5,
        "active": true
      }
    },
    {
      "title": "a hydrostatic normal load in a dry model has no level",
      "call": "NormalLoads.draft",
      "project": "dry",
      "args": [
        {
          "hydrostatic": true
        }
      ],
      "result": {
        "id": "normalload_1",
        "name": "Normal load 1",
        "kind": "normal",
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "fluid_pressure_type": "Hydrostatic",
        "pressure": 0.0,
        "active": true
      }
    },
    {
      "title": "a support on a face, fixed",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "face",
        {
          "face": "left"
        }
      ],
      "result": {
        "id": "displacement_1",
        "name": "Displacement 1",
        "kind": "displacement",
        "on": "face",
        "face": "left",
        "part": null,
        "points": null,
        "fixed": [
          true,
          true,
          true
        ],
        "active": true
      }
    },
    {
      "title": "a roller on the bottom",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "face",
        {
          "face": "bottom",
          "roller": true
        }
      ],
      "result": {
        "id": "displacement_1",
        "name": "Displacement 1",
        "kind": "displacement",
        "on": "face",
        "face": "bottom",
        "part": null,
        "points": null,
        "fixed": [
          false,
          true,
          false
        ],
        "active": true
      }
    },
    {
      "title": "a roller along a vertical line",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "line",
        {
          "points": [
            [
              5,
              0
            ],
            [
              5,
              -5
            ]
          ],
          "roller": true
        }
      ],
      "result": {
        "id": "displacement_1",
        "name": "Displacement 1",
        "kind": "displacement",
        "on": "line",
        "face": null,
        "part": null,
        "points": [
          [
            5.0,
            0.0
          ],
          [
            5.0,
            -5.0
          ]
        ],
        "fixed": [
          true,
          false,
          false
        ],
        "active": true
      }
    },
    {
      "title": "a roller along a sloping line is refused",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "line",
        {
          "points": [
            [
              0,
              0
            ],
            [
              5,
              -5
            ]
          ],
          "roller": true
        }
      ],
      "error": "A roller holds the component normal to its line, and a sloping line has no x or y normal; give the components it fixes."
    },
    {
      "title": "a support point at the centre, holding y",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "point",
        {
          "fixed": [
            false,
            true,
            false
          ]
        }
      ],
      "result": {
        "id": "displacement_1",
        "name": "Displacement 1",
        "kind": "displacement",
        "on": "point",
        "face": null,
        "part": null,
        "points": [
          [
            12.5,
            -12.5
          ]
        ],
        "fixed": [
          false,
          true,
          false
        ],
        "active": true
      }
    },
    {
      "title": "a support on the whole soil is refused",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "section",
      "args": [
        "domain",
        {}
      ],
      "error": "A displacement condition on the whole soil would hold the whole model still; put it on a face, a part, a line or a point."
    },
    {
      "title": "a support line in the solid model is refused",
      "call": "BoundaryConditions.draftDisplacement",
      "project": "solid",
      "args": [
        "line",
        {}
      ],
      "error": "A displacement line is drawn in the 2D section; switch to 2D to create one, or put the condition on a face or a part."
    },
    {
      "title": "a hydrostatic pressure takes the water level",
      "call": "BoundaryConditions.draftWaterPressure",
      "project": "section",
      "args": [
        "domain",
        {}
      ],
      "result": {
        "id": "waterpressure_1",
        "name": "Water pressure 1",
        "kind": "water_pressure",
        "on": "domain",
        "face": null,
        "part": null,
        "points": null,
        "fluid_pressure_type": "Hydrostatic",
        "is_fixed": true,
        "value": 0.0,
        "reference_coordinate": -1.5,
        "x_coordinates": null,
        "y_coordinates": null,
        "z_coordinates": null,
        "pressure_tension_cut_off": 0.0,
        "active": true
      }
    },
    {
      "title": "a hydrostatic pressure with no level anywhere is refused",
      "call": "BoundaryConditions.draftWaterPressure",
      "project": "dry",
      "args": [
        "domain",
        {}
      ],
      "error": "A hydrostatic water pressure needs the level where its pressure is zero: give its reference_coordinate. For a dry model, add no water pressure condition, or a Uniform one with value 0."
    },
    {
      "title": "a uniform pressure along a line, initial",
      "call": "BoundaryConditions.draftWaterPressure",
      "project": "dry",
      "args": [
        "line",
        {
          "fluid_pressure_type": "Uniform",
          "value": -5000,
          "is_fixed": false
        }
      ],
      "result": {
        "id": "waterpressure_1",
        "name": "Water pressure 1",
        "kind": "water_pressure",
        "on": "line",
        "face": null,
        "part": null,
        "points": [
          [
            12.5,
            0.0
          ],
          [
            12.5,
            -12.5
          ]
        ],
        "fluid_pressure_type": "Uniform",
        "is_fixed": false,
        "value": -5000.0,
        "reference_coordinate": null,
        "x_coordinates": null,
        "y_coordinates": null,
        "z_coordinates": null,
        "pressure_tension_cut_off": 0.0,
        "active": true
      }
    },
    {
      "title": "a phreatic line on a face",
      "call": "BoundaryConditions.draftWaterPressure",
      "project": "dry",
      "args": [
        "face",
        {
          "face": "right",
          "fluid_pressure_type": "Phreatic_Multi_Line",
          "x_coordinates": [
            0,
            25
          ],
          "y_coordinates": [
            -1,
            -2
          ],
          "pressure_tension_cut_off": 100000
        }
      ],
      "result": {
        "id": "waterpressure_1",
        "name": "Water pressure 1",
        "kind": "water_pressure",
        "on": "face",
        "face": "right",
        "part": null,
        "points": null,
        "fluid_pressure_type": "Phreatic_Multi_Line",
        "is_fixed": true,
        "value": 0.0,
        "reference_coordinate": null,
        "x_coordinates": [
          0.0,
          25.0
        ],
        "y_coordinates": [
          -1.0,
          -2.0
        ],
        "z_coordinates": null,
        "pressure_tension_cut_off": 100000.0,
        "active": true
      }
    },
    {
      "title": "a water pressure point in the solid model is refused",
      "call": "BoundaryConditions.draftWaterPressure",
      "project": "solid",
      "args": [
        "point",
        {}
      ],
      "error": "A water pressure point is drawn in the 2D section; switch to 2D to create one, or put the condition on the whole soil, a face or a part."
    },
    {
      "title": "a seepage face on the right face",
      "call": "BoundaryConditions.draftSeepage",
      "project": "section",
      "args": [
        "face",
        {
          "face": "right"
        }
      ],
      "result": {
        "id": "seepage_1",
        "name": "Seepage face 1",
        "kind": "seepage",
        "on": "face",
        "face": "right",
        "part": null,
        "points": null,
        "active": true
      }
    },
    {
      "title": "a seepage line down the right side",
      "call": "BoundaryConditions.draftSeepage",
      "project": "section",
      "args": [
        "line",
        {}
      ],
      "result": {
        "id": "seepage_1",
        "name": "Seepage face 1",
        "kind": "seepage",
        "on": "line",
        "face": null,
        "part": null,
        "points": [
          [
            25.0,
            0.0
          ],
          [
            25.0,
            -12.5
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a seepage line drawn",
      "call": "BoundaryConditions.draftSeepage",
      "project": "section",
      "args": [
        "line",
        {
          "points": [
            [
              25,
              -1
            ],
            [
              25,
              -6
            ]
          ],
          "name": "Exit"
        }
      ],
      "result": {
        "id": "seepage_1",
        "name": "Exit",
        "kind": "seepage",
        "on": "line",
        "face": null,
        "part": null,
        "points": [
          [
            25.0,
            -1.0
          ],
          [
            25.0,
            -6.0
          ]
        ],
        "active": true
      }
    },
    {
      "title": "a seepage face on the whole soil is refused",
      "call": "BoundaryConditions.draftSeepage",
      "project": "section",
      "args": [
        "domain",
        {}
      ],
      "error": "A seepage face is on a face of the model, or on a line along the soil's outer boundary."
    },
    {
      "title": "a seepage line in the solid model is refused",
      "call": "BoundaryConditions.draftSeepage",
      "project": "solid",
      "args": [
        "line",
        {}
      ],
      "error": "A seepage line is drawn in the 2D section; switch to 2D to create one, or put the seepage face on a face."
    },
    {
      "title": "the standard supports, with ids no condition has",
      "call": "BoundaryConditions.standardConditions",
      "project": "section",
      "args": [],
      "result": [
        {
          "id": "fixed_bottom_1",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left_1",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right_1",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front_1",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back_1",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        }
      ]
    },
    {
      "title": "the standard supports of a project with none",
      "call": "BoundaryConditions.standardConditions",
      "project": "dry",
      "args": [],
      "result": [
        {
          "id": "fixed_bottom",
          "name": "Fixed bottom",
          "kind": "displacement",
          "on": "face",
          "face": "bottom",
          "part": null,
          "points": null,
          "fixed": [
            true,
            true,
            true
          ],
          "active": true
        },
        {
          "id": "roller_left",
          "name": "Roller left",
          "kind": "displacement",
          "on": "face",
          "face": "left",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_right",
          "name": "Roller right",
          "kind": "displacement",
          "on": "face",
          "face": "right",
          "part": null,
          "points": null,
          "fixed": [
            true,
            false,
            false
          ],
          "active": true
        },
        {
          "id": "roller_front",
          "name": "Roller front",
          "kind": "displacement",
          "on": "face",
          "face": "front",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        },
        {
          "id": "roller_back",
          "name": "Roller back",
          "kind": "displacement",
          "on": "face",
          "face": "back",
          "part": null,
          "points": null,
          "fixed": [
            false,
            false,
            true
          ],
          "active": true
        }
      ]
    },
    {
      "title": "a point load",
      "call": "Loads.draftPoint",
      "project": "section",
      "args": [
        [
          5,
          0
        ]
      ],
      "result": {
        "id": "load_1",
        "name": "PointLoad_1",
        "kind": "point",
        "x": 5.0,
        "y": 0.0,
        "thickness": 0.25,
        "components": [
          0.0,
          -20000.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    },
    {
      "title": "a point load in kN",
      "call": "Loads.draftPoint",
      "project": "section_kn",
      "args": [
        [
          5,
          0
        ]
      ],
      "result": {
        "id": "load_1",
        "name": "PointLoad_1",
        "kind": "point",
        "x": 5.0,
        "y": 0.0,
        "thickness": 0.25,
        "components": [
          0.0,
          -20.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    },
    {
      "title": "a point load on the head of a pile above the ground",
      "call": "Loads.draftPoint",
      "project": "section_tall_pile",
      "args": [
        [
          12,
          5
        ]
      ],
      "result": {
        "id": "load_1",
        "name": "PointLoad_1",
        "kind": "point",
        "x": 12.0,
        "y": 5.0,
        "thickness": 0.25,
        "components": [
          0.0,
          -20000.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    },
    {
      "title": "a point load picked beside a pile above the ground snaps onto it",
      "call": "Loads.draftPoint",
      "project": "section_tall_pile",
      "args": [
        [
          12.4,
          4.8
        ]
      ],
      "result": {
        "id": "load_1",
        "name": "PointLoad_1",
        "kind": "point",
        "x": 12.0,
        "y": 4.8,
        "thickness": 0.25,
        "components": [
          0.0,
          -20000.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    },
    {
      "title": "a point load in the air, off any pile, is refused",
      "call": "Loads.draftPoint",
      "project": "section_tall_pile",
      "args": [
        [
          20,
          5
        ]
      ],
      "error": "The point-load coordinate must stay inside the model domain, or be on a sheet pile."
    },
    {
      "title": "a point load in the solid model is refused",
      "call": "Loads.draftPoint",
      "project": "solid",
      "args": [
        [
          5,
          0
        ]
      ],
      "error": "A 2D point load needs one finite x-y coordinate."
    },
    {
      "title": "a line load picked right to left",
      "call": "Loads.draftFromPoints",
      "project": "section",
      "args": [
        [
          [
            8,
            0
          ],
          [
            2,
            0
          ]
        ]
      ],
      "result": {
        "id": "load_1",
        "name": "LineLoad_1",
        "kind": "line",
        "x0": 2.0,
        "x1": 8.0,
        "y": 0.0,
        "thickness": 0.15,
        "components": [
          0.0,
          -20000.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    },
    {
      "title": "a surface load in the middle of the site",
      "call": "Loads.draftSurface",
      "project": "solid",
      "args": [],
      "result": {
        "id": "load_1",
        "name": "SurfaceLoad_1",
        "kind": "surface",
        "x0": 10.0,
        "x1": 15.0,
        "z0": 10.0,
        "z1": 15.0,
        "y": 0.0,
        "thickness": 0.15,
        "components": [
          0.0,
          -20000.0,
          0.0
        ],
        "distribution": "Uniform",
        "active": true
      }
    }
  ]
};
