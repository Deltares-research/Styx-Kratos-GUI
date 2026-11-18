/* Generated fixture -- each Delete the GUI offers, with the request it sends.
   tests/cli/test_edit_parity.py checks that the command line, and the route given this
   request, end on the same project; frontend/tests/test-edits.js checks that the GUI
   sends exactly this request.
   Not hand-edited. `python tests/cli/test_edit_parity.py --write` rebuilds it. */
window.EDITS_FIXTURE =
{
  "projects": {
    "pit": {
      "name": "Staged excavation",
      "layered_soil": true,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
      ],
      "lines": [
        {
          "id": "floor_1",
          "name": "Floor of lift 1",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ]
          ]
        },
        {
          "id": "floor_2",
          "name": "Floor of lift 2",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ]
          ]
        }
      ],
      "bodies": [
        {
          "id": "lift1",
          "name": "lift 1",
          "layer": "L_top",
          "point": [
            3.0,
            -1.0
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_top",
          "point": [
            33.0,
            -3.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift2",
          "name": "lift 2",
          "layer": "L_top",
          "point": [
            3.0,
            -3.25
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift3",
          "name": "lift 3",
          "layer": "L_top",
          "point": [
            3.0,
            -5.75
          ],
          "mat": "m_upper"
        },
        {
          "id": "pit",
          "name": "below the pit",
          "layer": "L_mid",
          "point": [
            3.0,
            -8.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_mid",
          "point": [
            33.0,
            -8.5
          ],
          "mat": "m_upper"
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
      "interface_sides": "screen",
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
      "fluid": {
        "bulk_modulus": null,
        "dynamic_viscosity": null
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
      "gravity_acceleration": 9.81,
      "mesh": {
        "element_size": 5.0,
        "order": 2,
        "algorithm_3d": "delaunay",
        "algorithm_2d": "frontal",
        "optimization": "gmsh",
        "smoothing": 10,
        "curvature_points": 16,
        "size_min_factor": 0.05,
        "second_order_linear": true,
        "body_sizes": {
          "sheetpile": 0.5,
          "strut": 0.5,
          "wall_contact": 0.5,
          "water_1": 0.5,
          "soil_L_mid__pit": 1.0,
          "soil_L_top__lift3": 1.0
        },
        "size_bands": {},
        "refinements": [
          {
            "kind": "box",
            "size": 0.8,
            "thickness": 30.0,
            "x_min": -1.0,
            "x_max": 9.0,
            "z_min": -1.0,
            "z_max": 11.0,
            "y_min": -15.0,
            "y_max": 1.0
          }
        ]
      },
      "custom_parts": [],
      "stages": [],
      "deck": null,
      "soil_body_keys": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot"
      ],
      "soil_body_labels": {
        "soil_L_top__lift1": "lift 1",
        "soil_L_top__retained": "retained",
        "soil_L_top__lift2": "lift 2",
        "soil_L_top__lift3": "lift 3",
        "soil_L_mid__pit": "below the pit",
        "soil_L_mid__retained": "retained",
        "soil_L_bot": "Soil_Bottom"
      },
      "soil_body_materials": {
        "soil_L_top__lift1": "m_upper",
        "soil_L_top__retained": "m_upper",
        "soil_L_top__lift2": "m_upper",
        "soil_L_top__lift3": "m_upper",
        "soil_L_mid__pit": "m_upper",
        "soil_L_mid__retained": "m_upper",
        "soil_L_bot": "m_lower"
      },
      "stageable_parts": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot",
        "sheetpile",
        "strut",
        "wall_contact",
        "water_1",
        "water_2",
        "water_3",
        "surcharge",
        "fixed_bottom",
        "roller_left",
        "roller_right",
        "roller_front",
        "roller_back",
        "pore_pressure"
      ],
      "model_strategies": {}
    },
    "pit with a drawn box": {
      "name": "Staged excavation",
      "layered_soil": true,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
      ],
      "lines": [
        {
          "id": "floor_1",
          "name": "Floor of lift 1",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ]
          ]
        },
        {
          "id": "floor_2",
          "name": "Floor of lift 2",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ]
          ]
        }
      ],
      "bodies": [
        {
          "id": "lift1",
          "name": "lift 1",
          "layer": "L_top",
          "point": [
            3.0,
            -1.0
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_top",
          "point": [
            33.0,
            -3.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift2",
          "name": "lift 2",
          "layer": "L_top",
          "point": [
            3.0,
            -3.25
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift3",
          "name": "lift 3",
          "layer": "L_top",
          "point": [
            3.0,
            -5.75
          ],
          "mat": "m_upper"
        },
        {
          "id": "pit",
          "name": "below the pit",
          "layer": "L_mid",
          "point": [
            3.0,
            -8.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_mid",
          "point": [
            33.0,
            -8.5
          ],
          "mat": "m_upper"
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
      "interface_sides": "screen",
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
      "fluid": {
        "bulk_modulus": null,
        "dynamic_viscosity": null
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
      "gravity_acceleration": 9.81,
      "mesh": {
        "element_size": 5.0,
        "order": 2,
        "algorithm_3d": "delaunay",
        "algorithm_2d": "frontal",
        "optimization": "gmsh",
        "smoothing": 10,
        "curvature_points": 16,
        "size_min_factor": 0.05,
        "second_order_linear": true,
        "body_sizes": {
          "sheetpile": 0.5,
          "strut": 0.5,
          "wall_contact": 0.5,
          "water_1": 0.5,
          "soil_L_mid__pit": 1.0,
          "soil_L_top__lift3": 1.0,
          "drawn_0": 0.5
        },
        "size_bands": {},
        "refinements": [
          {
            "kind": "box",
            "size": 0.8,
            "thickness": 30.0,
            "x_min": -1.0,
            "x_max": 9.0,
            "z_min": -1.0,
            "z_max": 11.0,
            "y_min": -15.0,
            "y_max": 1.0
          }
        ]
      },
      "custom_parts": [
        {
          "key": "drawn_0",
          "label": "drawn_0",
          "color": "#888888",
          "source": "gui",
          "source_file": "drawn.brep",
          "recipe": {
            "kind": "box",
            "origin": [
              0,
              -5,
              0
            ],
            "size": [
              2,
              2,
              2
            ]
          },
          "imported_from": null,
          "mat": null,
          "bbox": [
            0.0,
            -5.0,
            0.0,
            2.0,
            -3.0,
            2.0
          ]
        }
      ],
      "stages": [],
      "deck": null,
      "soil_body_keys": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot"
      ],
      "soil_body_labels": {
        "soil_L_top__lift1": "lift 1",
        "soil_L_top__retained": "retained",
        "soil_L_top__lift2": "lift 2",
        "soil_L_top__lift3": "lift 3",
        "soil_L_mid__pit": "below the pit",
        "soil_L_mid__retained": "retained",
        "soil_L_bot": "Soil_Bottom"
      },
      "soil_body_materials": {
        "soil_L_top__lift1": "m_upper",
        "soil_L_top__retained": "m_upper",
        "soil_L_top__lift2": "m_upper",
        "soil_L_top__lift3": "m_upper",
        "soil_L_mid__pit": "m_upper",
        "soil_L_mid__retained": "m_upper",
        "soil_L_bot": "m_lower"
      },
      "stageable_parts": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot",
        "sheetpile",
        "strut",
        "wall_contact",
        "water_1",
        "water_2",
        "water_3",
        "drawn_0",
        "surcharge",
        "fixed_bottom",
        "roller_left",
        "roller_right",
        "roller_front",
        "roller_back",
        "pore_pressure"
      ],
      "model_strategies": {}
    },
    "pit with a spare material": {
      "name": "Staged excavation",
      "layered_soil": true,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
        },
        {
          "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
          "variables": {
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 2000000.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 1732.9255861365953,
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "PERMEABILITY_XX": 1e-08,
            "PERMEABILITY_YY": 1e-08,
            "PERMEABILITY_XY": 0.0,
            "GEO_COHESION": 2000.0,
            "GEO_FRICTION_ANGLE": 25.0,
            "K0_NC": 0.58
          },
          "tables": {},
          "id": "m_spare",
          "name": "Spare",
          "color": "#c4a86a",
          "r_inter": 0.7,
          "interface_permeability": "Neutral"
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
      ],
      "lines": [
        {
          "id": "floor_1",
          "name": "Floor of lift 1",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ]
          ]
        },
        {
          "id": "floor_2",
          "name": "Floor of lift 2",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ]
          ]
        }
      ],
      "bodies": [
        {
          "id": "lift1",
          "name": "lift 1",
          "layer": "L_top",
          "point": [
            3.0,
            -1.0
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_top",
          "point": [
            33.0,
            -3.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift2",
          "name": "lift 2",
          "layer": "L_top",
          "point": [
            3.0,
            -3.25
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift3",
          "name": "lift 3",
          "layer": "L_top",
          "point": [
            3.0,
            -5.75
          ],
          "mat": "m_upper"
        },
        {
          "id": "pit",
          "name": "below the pit",
          "layer": "L_mid",
          "point": [
            3.0,
            -8.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_mid",
          "point": [
            33.0,
            -8.5
          ],
          "mat": "m_upper"
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
      "interface_sides": "screen",
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
      "fluid": {
        "bulk_modulus": null,
        "dynamic_viscosity": null
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
      "gravity_acceleration": 9.81,
      "mesh": {
        "element_size": 5.0,
        "order": 2,
        "algorithm_3d": "delaunay",
        "algorithm_2d": "frontal",
        "optimization": "gmsh",
        "smoothing": 10,
        "curvature_points": 16,
        "size_min_factor": 0.05,
        "second_order_linear": true,
        "body_sizes": {
          "sheetpile": 0.5,
          "strut": 0.5,
          "wall_contact": 0.5,
          "water_1": 0.5,
          "soil_L_mid__pit": 1.0,
          "soil_L_top__lift3": 1.0
        },
        "size_bands": {},
        "refinements": [
          {
            "kind": "box",
            "size": 0.8,
            "thickness": 30.0,
            "x_min": -1.0,
            "x_max": 9.0,
            "z_min": -1.0,
            "z_max": 11.0,
            "y_min": -15.0,
            "y_max": 1.0
          }
        ]
      },
      "custom_parts": [],
      "stages": [],
      "deck": null,
      "soil_body_keys": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot"
      ],
      "soil_body_labels": {
        "soil_L_top__lift1": "lift 1",
        "soil_L_top__retained": "retained",
        "soil_L_top__lift2": "lift 2",
        "soil_L_top__lift3": "lift 3",
        "soil_L_mid__pit": "below the pit",
        "soil_L_mid__retained": "retained",
        "soil_L_bot": "Soil_Bottom"
      },
      "soil_body_materials": {
        "soil_L_top__lift1": "m_upper",
        "soil_L_top__retained": "m_upper",
        "soil_L_top__lift2": "m_upper",
        "soil_L_top__lift3": "m_upper",
        "soil_L_mid__pit": "m_upper",
        "soil_L_mid__retained": "m_upper",
        "soil_L_bot": "m_lower"
      },
      "stageable_parts": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot",
        "sheetpile",
        "strut",
        "wall_contact",
        "water_1",
        "water_2",
        "water_3",
        "surcharge",
        "fixed_bottom",
        "roller_left",
        "roller_right",
        "roller_front",
        "roller_back",
        "pore_pressure"
      ],
      "model_strategies": {}
    },
    "pit without strut or contact": {
      "name": "Staged excavation",
      "layered_soil": true,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
      ],
      "lines": [
        {
          "id": "floor_1",
          "name": "Floor of lift 1",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ]
          ]
        },
        {
          "id": "floor_2",
          "name": "Floor of lift 2",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ]
          ]
        }
      ],
      "bodies": [
        {
          "id": "lift1",
          "name": "lift 1",
          "layer": "L_top",
          "point": [
            3.0,
            -1.0
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_top",
          "point": [
            33.0,
            -3.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift2",
          "name": "lift 2",
          "layer": "L_top",
          "point": [
            3.0,
            -3.25
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift3",
          "name": "lift 3",
          "layer": "L_top",
          "point": [
            3.0,
            -5.75
          ],
          "mat": "m_upper"
        },
        {
          "id": "pit",
          "name": "below the pit",
          "layer": "L_mid",
          "point": [
            3.0,
            -8.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_mid",
          "point": [
            33.0,
            -8.5
          ],
          "mat": "m_upper"
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
      "anchors": [],
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
      "interfaces": [],
      "interface_sides": "screen",
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
      "fluid": {
        "bulk_modulus": null,
        "dynamic_viscosity": null
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
      "gravity_acceleration": 9.81,
      "mesh": {
        "element_size": 5.0,
        "order": 2,
        "algorithm_3d": "delaunay",
        "algorithm_2d": "frontal",
        "optimization": "gmsh",
        "smoothing": 10,
        "curvature_points": 16,
        "size_min_factor": 0.05,
        "second_order_linear": true,
        "body_sizes": {
          "sheetpile": 0.5,
          "water_1": 0.5,
          "soil_L_mid__pit": 1.0,
          "soil_L_top__lift3": 1.0
        },
        "size_bands": {},
        "refinements": [
          {
            "kind": "box",
            "size": 0.8,
            "thickness": 30.0,
            "x_min": -1.0,
            "x_max": 9.0,
            "z_min": -1.0,
            "z_max": 11.0,
            "y_min": -15.0,
            "y_max": 1.0
          }
        ]
      },
      "custom_parts": [],
      "stages": [],
      "deck": null,
      "soil_body_keys": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot"
      ],
      "soil_body_labels": {
        "soil_L_top__lift1": "lift 1",
        "soil_L_top__retained": "retained",
        "soil_L_top__lift2": "lift 2",
        "soil_L_top__lift3": "lift 3",
        "soil_L_mid__pit": "below the pit",
        "soil_L_mid__retained": "retained",
        "soil_L_bot": "Soil_Bottom"
      },
      "soil_body_materials": {
        "soil_L_top__lift1": "m_upper",
        "soil_L_top__retained": "m_upper",
        "soil_L_top__lift2": "m_upper",
        "soil_L_top__lift3": "m_upper",
        "soil_L_mid__pit": "m_upper",
        "soil_L_mid__retained": "m_upper",
        "soil_L_bot": "m_lower"
      },
      "stageable_parts": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot",
        "sheetpile",
        "water_1",
        "water_2",
        "water_3",
        "surcharge",
        "fixed_bottom",
        "roller_left",
        "roller_right",
        "roller_front",
        "roller_back",
        "pore_pressure"
      ],
      "model_strategies": {}
    },
    "staged pit": {
      "name": "Staged excavation",
      "layered_soil": true,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
            "POROSITY": 0.0,
            "BULK_MODULUS_SOLID": 10000000000.0,
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
      ],
      "lines": [
        {
          "id": "floor_1",
          "name": "Floor of lift 1",
          "points": [
            [
              0.0,
              -2.0
            ],
            [
              6.0,
              -2.0
            ]
          ]
        },
        {
          "id": "floor_2",
          "name": "Floor of lift 2",
          "points": [
            [
              0.0,
              -4.5
            ],
            [
              6.0,
              -4.5
            ]
          ]
        }
      ],
      "bodies": [
        {
          "id": "lift1",
          "name": "lift 1",
          "layer": "L_top",
          "point": [
            3.0,
            -1.0
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_top",
          "point": [
            33.0,
            -3.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift2",
          "name": "lift 2",
          "layer": "L_top",
          "point": [
            3.0,
            -3.25
          ],
          "mat": "m_upper"
        },
        {
          "id": "lift3",
          "name": "lift 3",
          "layer": "L_top",
          "point": [
            3.0,
            -5.75
          ],
          "mat": "m_upper"
        },
        {
          "id": "pit",
          "name": "below the pit",
          "layer": "L_mid",
          "point": [
            3.0,
            -8.5
          ],
          "mat": "m_upper"
        },
        {
          "id": "retained",
          "name": "retained",
          "layer": "L_mid",
          "point": [
            33.0,
            -8.5
          ],
          "mat": "m_upper"
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
      "interface_sides": "screen",
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
      "fluid": {
        "bulk_modulus": null,
        "dynamic_viscosity": null
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
      "gravity_acceleration": 9.81,
      "mesh": {
        "element_size": 5.0,
        "order": 2,
        "algorithm_3d": "delaunay",
        "algorithm_2d": "frontal",
        "optimization": "gmsh",
        "smoothing": 10,
        "curvature_points": 16,
        "size_min_factor": 0.05,
        "second_order_linear": true,
        "body_sizes": {
          "sheetpile": 0.5,
          "strut": 0.5,
          "wall_contact": 0.5,
          "water_1": 0.5,
          "soil_L_mid__pit": 1.0,
          "soil_L_top__lift3": 1.0
        },
        "size_bands": {},
        "refinements": [
          {
            "kind": "box",
            "size": 0.8,
            "thickness": 30.0,
            "x_min": -1.0,
            "x_max": 9.0,
            "z_min": -1.0,
            "z_max": 11.0,
            "y_min": -15.0,
            "y_max": 1.0
          }
        ]
      },
      "custom_parts": [],
      "stages": [
        {
          "id": "initial",
          "name": "Initial stage",
          "parent": null,
          "calculation": "mechanical",
          "stress_initialisation": "K0",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "sheetpile",
            "strut",
            "wall_contact",
            "surcharge",
            "water_1",
            "water_2",
            "water_3"
          ],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "null_step",
          "name": "Null step",
          "parent": "initial",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "install_sheetpile",
          "name": "SheetPileWall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "sheetpile",
            "wall_contact",
            "surcharge"
          ],
          "deactivate": [],
          "reset_displacements": true,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "dig_1",
          "name": "First excavation",
          "parent": "install_sheetpile",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "water_1"
          ],
          "deactivate": [
            "soil_L_top__lift1"
          ],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "install_strut",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "strut"
          ],
          "deactivate": [],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "dig_2",
          "name": "Second excavation",
          "parent": "install_strut",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "water_2"
          ],
          "deactivate": [
            "soil_L_top__lift2",
            "water_1"
          ],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "dig_3",
          "name": "Third excavation",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "water_3"
          ],
          "deactivate": [
            "soil_L_top__lift3",
            "water_2"
          ],
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 150,
          "tolerated_error": 0.001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        }
      ],
      "deck": null,
      "soil_body_keys": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot"
      ],
      "soil_body_labels": {
        "soil_L_top__lift1": "lift 1",
        "soil_L_top__retained": "retained",
        "soil_L_top__lift2": "lift 2",
        "soil_L_top__lift3": "lift 3",
        "soil_L_mid__pit": "below the pit",
        "soil_L_mid__retained": "retained",
        "soil_L_bot": "Soil_Bottom"
      },
      "soil_body_materials": {
        "soil_L_top__lift1": "m_upper",
        "soil_L_top__retained": "m_upper",
        "soil_L_top__lift2": "m_upper",
        "soil_L_top__lift3": "m_upper",
        "soil_L_mid__pit": "m_upper",
        "soil_L_mid__retained": "m_upper",
        "soil_L_bot": "m_lower"
      },
      "stageable_parts": [
        "soil_L_top__lift1",
        "soil_L_top__retained",
        "soil_L_top__lift2",
        "soil_L_top__lift3",
        "soil_L_mid__pit",
        "soil_L_mid__retained",
        "soil_L_bot",
        "sheetpile",
        "strut",
        "wall_contact",
        "water_1",
        "water_2",
        "water_3",
        "surcharge",
        "fixed_bottom",
        "roller_left",
        "roller_right",
        "roller_front",
        "roller_back",
        "pore_pressure"
      ],
      "model_strategies": {}
    }
  },
  "cases": [
    {
      "title": "an anchor",
      "call": "Anchors.remove",
      "target": "strut",
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit",
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
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit",
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
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit without strut or contact",
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
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit",
      "body": {
        "loads": []
      }
    },
    {
      "title": "a line",
      "call": "Lines.remove",
      "target": "floor_2",
      "method": "PATCH",
      "route": "/api/project/lines",
      "project": "pit",
      "body": {
        "lines": [
          {
            "id": "floor_1",
            "name": "Floor of lift 1",
            "points": [
              [
                0.0,
                -2.0
              ],
              [
                6.0,
                -2.0
              ]
            ]
          }
        ]
      }
    },
    {
      "title": "a normal load",
      "call": "NormalLoads.remove",
      "target": "water_1",
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit",
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
      "method": "PATCH",
      "route": "/api/project/conditions",
      "project": "pit",
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
      "title": "a soil layer, in the soil layers window",
      "call": "Dialogs.soilLayers",
      "target": "L_mid",
      "method": "PATCH",
      "route": "/api/project/layers",
      "project": "pit",
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
              "POROSITY": 0.0,
              "BULK_MODULUS_SOLID": 10000000000.0,
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
              "POROSITY": 0.0,
              "BULK_MODULUS_SOLID": 10000000000.0,
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
      "title": "a soil layer, in the model tree",
      "call": "deleteLayerById",
      "target": "L_mid",
      "method": "PATCH",
      "route": "/api/project/layers",
      "project": "pit",
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
        "domain": {
          "x0": 0.0,
          "x1": 60.0,
          "z0": 0.0,
          "z1": 10.0,
          "y_top": 0.0,
          "y_bottom": -40.0
        },
        "water": {
          "y": -1.0,
          "margin": 3.0,
          "thickness": 0.06,
          "specific_weight": null
        },
        "custom_parts": []
      }
    },
    {
      "title": "a stage",
      "call": "Explorer.mountPhases",
      "target": "dig_2",
      "method": "PATCH",
      "route": "/api/project/stages",
      "project": "staged pit",
      "body": {
        "stages": [
          {
            "id": "initial",
            "name": "Initial stage",
            "parent": null,
            "calculation": "mechanical",
            "stress_initialisation": "K0",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [],
            "deactivate": [
              "sheetpile",
              "strut",
              "wall_contact",
              "surcharge",
              "water_1",
              "water_2",
              "water_3"
            ],
            "reset_displacements": false,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 15,
            "tolerated_error": 0.0001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          },
          {
            "id": "null_step",
            "name": "Null step",
            "parent": "initial",
            "calculation": "mechanical",
            "stress_initialisation": "none",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [],
            "deactivate": [],
            "reset_displacements": false,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 150,
            "tolerated_error": 0.0001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          },
          {
            "id": "install_sheetpile",
            "name": "SheetPileWall installation",
            "parent": "null_step",
            "calculation": "mechanical",
            "stress_initialisation": "none",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [
              "sheetpile",
              "wall_contact",
              "surcharge"
            ],
            "deactivate": [],
            "reset_displacements": true,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 150,
            "tolerated_error": 0.001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          },
          {
            "id": "dig_1",
            "name": "First excavation",
            "parent": "install_sheetpile",
            "calculation": "mechanical",
            "stress_initialisation": "none",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [
              "water_1"
            ],
            "deactivate": [
              "soil_L_top__lift1"
            ],
            "reset_displacements": false,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 150,
            "tolerated_error": 0.001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          },
          {
            "id": "install_strut",
            "name": "Strut installation",
            "parent": "dig_1",
            "calculation": "mechanical",
            "stress_initialisation": "none",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [
              "strut"
            ],
            "deactivate": [],
            "reset_displacements": false,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 150,
            "tolerated_error": 0.001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          },
          {
            "id": "dig_3",
            "name": "Third excavation",
            "parent": "install_strut",
            "calculation": "mechanical",
            "stress_initialisation": "none",
            "time_integration": "static",
            "loading": "Staged construction",
            "activate": [
              "water_3"
            ],
            "deactivate": [
              "soil_L_top__lift3",
              "water_2"
            ],
            "reset_displacements": false,
            "convergence_criterion": "residual_criterion",
            "max_iterations": 150,
            "tolerated_error": 0.001,
            "absolute_tolerance": 1e-09,
            "start_time": 0.0,
            "duration": 1.0,
            "time_step": 1.0,
            "solver_settings": {}
          }
        ]
      }
    },
    {
      "title": "a material set",
      "call": "Dialogs.materials",
      "target": "m_spare",
      "method": "PATCH",
      "route": "/api/project/materials",
      "project": "pit with a spare material",
      "body": {
        "materials": [
          {
            "constitutive_law": "GeoLinearElasticPlaneStrain2DLaw",
            "variables": {
              "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
              "YOUNG_MODULUS": 2000000.0,
              "POISSON_RATIO": 0.3,
              "DENSITY_SOLID": 1732.9255861365953,
              "POROSITY": 0.0,
              "BULK_MODULUS_SOLID": 10000000000.0,
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
              "POROSITY": 0.0,
              "BULK_MODULUS_SOLID": 10000000000.0,
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
        "fluid": {
          "bulk_modulus": null,
          "dynamic_viscosity": null
        }
      }
    },
    {
      "title": "a custom volume",
      "call": "LivePatches.deleteCustomPart",
      "target": "drawn_0",
      "method": "DELETE",
      "route": "/api/geometry/parts/drawn_0",
      "project": "pit with a drawn box",
      "body": null
    },
    {
      "title": "every custom volume",
      "call": "Command.run",
      "target": "clear",
      "method": "DELETE",
      "route": "/api/project/custom_parts",
      "project": "pit with a drawn box",
      "body": null
    },
    {
      "title": "one part of a cut soil layer",
      "call": "LivePatches.deleteBody",
      "target": "soil_L_mid__pit",
      "method": "DELETE",
      "route": "/api/project/bodies/soil_L_mid__pit",
      "project": "pit",
      "body": null
    },
    {
      "title": "one part of a cut soil layer a stage switches",
      "call": "LivePatches.deleteBody",
      "target": "soil_L_top__lift3",
      "method": "DELETE",
      "route": "/api/project/bodies/soil_L_top__lift3",
      "project": "staged pit",
      "body": null
    },
    {
      "title": "a sheet pile an anchor hangs from",
      "call": "Beams.remove",
      "target": "sheetpile",
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "pit",
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
      "method": "PATCH",
      "route": "/api/project/structures",
      "project": "staged pit",
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
