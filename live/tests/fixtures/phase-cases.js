/* Generated fixture -- the one document both implementations of `active_parts` are
   held to. Milestone D asks for the phase tree to be resolved in the browser as well
   as on the server (plan sec D), and two implementations of one rule drift unless
   something says they agree. This is that something.

   A .js file assigning a global rather than a .json file, because the browser suite
   runs from `file://` and a fetch there is blocked; Python reads the same file and
   strips this one assignment off the front. One document, two readers -- see
   `server/tests/test_phase_parity.py`, which regenerates and compares it.

   Not hand-edited. `python server/tests/test_phase_parity.py --write` rebuilds it.
*/
window.PHASE_FIXTURE =
{
  "project": {
    "name": "Deep excavation \u2014 Rotterdam Zuid",
    "layered_soil": false,
    "dimension": 3,
    "unit_system": "SI",
    "section_offset": null,
    "domain": {
      "x0": 0.0,
      "x1": 50.0,
      "z0": 0.0,
      "z1": 40.0,
      "y_top": 0.0,
      "y_bottom": -60.0
    },
    "boreholes": [
      {
        "id": "bh1",
        "name": "BH-1",
        "x": 0.0,
        "y": 0.0,
        "head": 0.0,
        "water": -1.5
      }
    ],
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
    "layers": [
      {
        "id": "L1",
        "name": "Soil_1",
        "mat": "m1",
        "tops": {
          "bh1": 0.0
        },
        "bots": {
          "bh1": -8.0
        }
      },
      {
        "id": "L2",
        "name": "Soil_2",
        "mat": "m1",
        "tops": {
          "bh1": -8.0
        },
        "bots": {
          "bh1": -12.0
        }
      },
      {
        "id": "L3",
        "name": "Soil_3",
        "mat": "m2",
        "tops": {
          "bh1": -12.0
        },
        "bots": {
          "bh1": -60.0
        }
      }
    ],
    "excavation": {
      "x0": 0.0,
      "x1": 5.0,
      "z0": 10.0,
      "z1": 30.0,
      "floor_y": -8.0,
      "levels": [
        -2.0,
        -5.0,
        -8.0
      ]
    },
    "wall": {
      "thickness": 0.8,
      "top_y": 0.0,
      "toe_y": -13.0
    },
    "struts": {
      "xs": [
        14.0,
        20.0,
        26.0,
        32.0
      ],
      "y": -3.0,
      "radius": 0.28,
      "overhang": 0.8,
      "waler_width": 0.5,
      "waler_height": 0.6,
      "waler_offset": 0.5
    },
    "anchor_rows": {
      "xs": [
        15.0,
        21.0,
        27.0,
        33.0
      ],
      "head_y": -4.5,
      "length": 11.0,
      "inclination_deg": 35.0,
      "radius": 0.11,
      "head_offset": 0.4
    },
    "piles": {
      "xs": [
        16.0,
        22.0,
        28.0,
        34.0
      ],
      "zs": [
        14.0,
        20.0,
        26.0
      ],
      "radius": 0.3,
      "length": 9.0,
      "top_y": -7.0
    },
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
    "wells": {
      "positions": [
        [
          18.0,
          15.0
        ],
        [
          32.0,
          25.0
        ]
      ],
      "radius": 0.35,
      "top_y": 0.0,
      "length": 15.0
    },
    "water": {
      "y": -1.5,
      "margin": 3.0,
      "thickness": 0.06,
      "specific_weight": null
    },
    "mesh": {
      "element_size": 2.5,
      "order": 2,
      "algorithm_3d": "delaunay",
      "algorithm_2d": "frontal",
      "optimization": "gmsh",
      "smoothing": 10,
      "curvature_points": 16,
      "size_min_factor": 0.05,
      "second_order_linear": true,
      "body_sizes": {},
      "refinements": []
    },
    "custom_parts": [],
    "phases": [
      {
        "id": "initial",
        "name": "Initial stage",
        "parent": null,
        "calculation": "K0 procedure",
        "loading": "Staged construction",
        "activate": [],
        "deactivate": [
          "wall",
          "anchors",
          "load",
          "soil_L1__lift1",
          "soil_L1__lift2",
          "soil_L1__lift3"
        ],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "null_step",
        "name": "Null step",
        "parent": "initial",
        "calculation": "Null step",
        "loading": "Staged construction",
        "activate": [],
        "deactivate": [],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "build_wall",
        "name": "Wall installation",
        "parent": "null_step",
        "calculation": "Plastic",
        "loading": "Staged construction",
        "activate": [
          "wall",
          "load"
        ],
        "deactivate": [],
        "reset_displacements": true,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "dig_1",
        "name": "Dig to -2.0 m",
        "parent": "build_wall",
        "calculation": "Plastic",
        "loading": "Staged construction",
        "activate": [
          "soil_L1__lift1"
        ],
        "deactivate": [
          "soil_L1"
        ],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "prop",
        "name": "Strut installation",
        "parent": "dig_1",
        "calculation": "Plastic",
        "loading": "Staged construction",
        "activate": [
          "anchors"
        ],
        "deactivate": [],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "dig_2",
        "name": "Dig to -5.0 m",
        "parent": "prop",
        "calculation": "Plastic",
        "loading": "Staged construction",
        "activate": [
          "soil_L1__lift2",
          "soil_L1"
        ],
        "deactivate": [
          "soil_L1__lift1"
        ],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      },
      {
        "id": "settle",
        "name": "Consolidate",
        "parent": "dig_2",
        "calculation": "Plastic",
        "loading": "Staged construction",
        "activate": [],
        "deactivate": [
          "soil_L1__lift1"
        ],
        "reset_displacements": false,
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "time_interval": 0.0
      }
    ],
    "deck": null,
    "soil_body_keys": [
      "soil_L1",
      "soil_L2",
      "soil_L3",
      "soil_L1__lift1",
      "soil_L1__lift2",
      "soil_L1__lift3",
      "soil_L2__pit",
      "soil_L3__pit"
    ],
    "soil_body_labels": {
      "soil_L1": "Soil_1",
      "soil_L2": "Soil_2",
      "soil_L3": "Soil_3",
      "soil_L1__lift1": "Soil_1 \u00b7 lift 1",
      "soil_L1__lift2": "Soil_1 \u00b7 lift 2",
      "soil_L1__lift3": "Soil_1 \u00b7 lift 3",
      "soil_L2__pit": "Soil_2 \u00b7 below the pit",
      "soil_L3__pit": "Soil_3 \u00b7 below the pit"
    },
    "stageable_parts": [
      "soil_L1",
      "soil_L2",
      "soil_L3",
      "soil_L1__lift1",
      "soil_L1__lift2",
      "soil_L1__lift3",
      "soil_L2__pit",
      "soil_L3__pit",
      "excavation",
      "wall",
      "struts",
      "anchors",
      "piles",
      "load",
      "water",
      "wells"
    ]
  },
  "stageable_keys": [
    "soil_L1",
    "soil_L2",
    "soil_L3",
    "soil_L1__lift1",
    "soil_L1__lift2",
    "soil_L1__lift3",
    "soil_L2__pit",
    "soil_L3__pit",
    "excavation",
    "wall",
    "struts",
    "anchors",
    "piles",
    "load",
    "water",
    "wells"
  ],
  "active_parts": {
    "initial": [
      "excavation",
      "piles",
      "soil_L1",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "water",
      "wells"
    ],
    "null_step": [
      "excavation",
      "piles",
      "soil_L1",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "water",
      "wells"
    ],
    "build_wall": [
      "excavation",
      "load",
      "piles",
      "soil_L1",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "wall",
      "water",
      "wells"
    ],
    "dig_1": [
      "excavation",
      "load",
      "piles",
      "soil_L1__lift1",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "wall",
      "water",
      "wells"
    ],
    "prop": [
      "anchors",
      "excavation",
      "load",
      "piles",
      "soil_L1__lift1",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "wall",
      "water",
      "wells"
    ],
    "dig_2": [
      "anchors",
      "excavation",
      "load",
      "piles",
      "soil_L1",
      "soil_L1__lift2",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "wall",
      "water",
      "wells"
    ],
    "settle": [
      "anchors",
      "excavation",
      "load",
      "piles",
      "soil_L1",
      "soil_L1__lift2",
      "soil_L2",
      "soil_L2__pit",
      "soil_L3",
      "soil_L3__pit",
      "struts",
      "wall",
      "water",
      "wells"
    ]
  },
  "order": [
    "initial",
    "null_step",
    "build_wall",
    "dig_1",
    "prop",
    "dig_2",
    "settle"
  ]
};
