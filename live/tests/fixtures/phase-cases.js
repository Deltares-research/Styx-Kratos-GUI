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
        "id": "m1",
        "name": "Fill",
        "model": "Mohr-Coulomb",
        "type": "Drained",
        "color": "#d8c48a",
        "g_unsat": 17.0,
        "g_sat": 20.0,
        "E": 15000.0,
        "nu": 0.3,
        "c": 1.0,
        "phi": 30.0,
        "k": 1.0,
        "r_inter": 0.7,
        "interface_permeability": "Neutral",
        "porosity": null,
        "k0_nc": null
      },
      {
        "id": "m2",
        "name": "Sand, loose",
        "model": "Hardening Soil",
        "type": "Drained",
        "color": "#c4a86a",
        "g_unsat": 18.0,
        "g_sat": 20.5,
        "E": 25000.0,
        "nu": 0.28,
        "c": 0.5,
        "phi": 32.0,
        "k": 1.5,
        "r_inter": 0.7,
        "interface_permeability": "Neutral",
        "porosity": null,
        "k0_nc": null
      },
      {
        "id": "m3",
        "name": "Clay, soft",
        "model": "Soft Soil",
        "type": "Undrained (A)",
        "color": "#8fa86b",
        "g_unsat": 15.0,
        "g_sat": 16.0,
        "E": 4000.0,
        "nu": 0.35,
        "c": 5.0,
        "phi": 22.0,
        "k": 0.0001,
        "r_inter": 0.5,
        "interface_permeability": "Impermeable",
        "porosity": null,
        "k0_nc": null
      },
      {
        "id": "m4",
        "name": "Clay, stiff",
        "model": "Mohr-Coulomb",
        "type": "Undrained (A)",
        "color": "#6f8fa8",
        "g_unsat": 17.5,
        "g_sat": 18.5,
        "E": 12000.0,
        "nu": 0.33,
        "c": 15.0,
        "phi": 25.0,
        "k": 0.0005,
        "r_inter": 0.55,
        "interface_permeability": "Impermeable",
        "porosity": null,
        "k0_nc": null
      },
      {
        "id": "m5",
        "name": "Sand, dense",
        "model": "Hardening Soil",
        "type": "Drained",
        "color": "#b08a6a",
        "g_unsat": 19.0,
        "g_sat": 21.0,
        "E": 45000.0,
        "nu": 0.25,
        "c": 0.0,
        "phi": 36.0,
        "k": 5.0,
        "r_inter": 0.75,
        "interface_permeability": "Neutral",
        "porosity": null,
        "k0_nc": null
      },
      {
        "id": "m6",
        "name": "Bedrock",
        "model": "Linear Elastic",
        "type": "Non-porous",
        "color": "#8d8d99",
        "g_unsat": 24.0,
        "g_sat": 24.0,
        "E": 2000000.0,
        "nu": 0.2,
        "c": null,
        "phi": null,
        "k": 0.0,
        "r_inter": 1.0,
        "interface_permeability": "Impermeable",
        "porosity": null,
        "k0_nc": null
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
          -20.0,
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
      "specific_weight": 10.0
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
