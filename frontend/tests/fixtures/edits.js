/* Generated fixture -- each Delete the GUI offers, with the body it sends.
   tests/cli/test_edit_parity.py checks that the command line, and the route given this
   body, end on the same project; frontend/tests/test-edits.js checks that the GUI's
   function sends exactly this body.
   Not hand-edited. `python tests/cli/test_edit_parity.py --write` rebuilds it. */
window.EDITS_FIXTURE =
{
  "cases": [
    {
      "title": "an anchor",
      "call": "Anchors.remove",
      "target": "strut",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "anchors": [],
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
        ]
      }
    },
    {
      "title": "an interface",
      "call": "Interfaces.remove",
      "target": "wall_contact",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "interfaces": [],
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
        ]
      }
    },
    {
      "title": "a sheet pile nothing hangs from",
      "call": "Beams.remove",
      "target": "sheetpile",
      "route": "/api/project/structures",
      "project": {
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
        "anchors": [],
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
        "interfaces": [],
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "beams": [],
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
        ]
      }
    },
    {
      "title": "a line load",
      "call": "Loads.remove",
      "target": "surcharge",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
        "loads": []
      }
    },
    {
      "title": "a normal load",
      "call": "NormalLoads.remove",
      "target": "water_1",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "normal_loads": [
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
        ]
      }
    },
    {
      "title": "a boundary condition",
      "call": "BoundaryConditions.remove",
      "target": "roller_front",
      "route": "/api/project/conditions",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        ]
      }
    },
    {
      "title": "a soil layer",
      "call": "SoilLayersDialog.remove",
      "target": "L_mid",
      "route": "/api/project/layers",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ],
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
        ]
      }
    },
    {
      "title": "a sheet pile an anchor hangs from",
      "call": "Beams.remove",
      "target": "sheetpile",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "beams": [],
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
        ]
      }
    },
    {
      "title": "an anchor a stage switches on",
      "call": "Anchors.remove",
      "target": "strut",
      "route": "/api/project/structures",
      "project": {
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
        "layers": [
          {
            "id": "L_top",
            "name": "Soil_Top",
            "mat": "m_upper",
            "top": 0.0,
            "bottom": -7.0
          },
          {
            "id": "L_mid",
            "name": "Soil_Middle",
            "mat": "m_upper",
            "top": -7.0,
            "bottom": -10.0
          },
          {
            "id": "L_bot",
            "name": "Soil_Bottom",
            "mat": "m_lower",
            "top": -10.0,
            "bottom": -40.0
          }
        ]
      },
      "body": {
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
        "anchors": [],
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
        ]
      }
    }
  ]
};
