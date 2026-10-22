# Graph Report - Styx-Kratos-GUI  (2026-10-22)

## Corpus Check
- Large corpus: 369 files · ~550,764 words. Semantic extraction will be expensive (many LLM tokens). Consider running on a subfolder.

## Summary
- 7257 nodes · 17543 edges · 303 communities (232 shown, 71 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 981 edges (avg confidence: 0.91)
- Token cost: 304,371 input · 0 output

## Community Hubs (Navigation)
- API Contract Tests
- CLI Structure Drafts
- Project Edit Updates
- Kratos Deck Export Tests
- Mesh and Deck Jobs
- CLI Edit Commands
- Loads and Computed Fields
- Project Schema Tests
- Result Field Catalogue
- Kratos Deck Writer
- Real Run and CI Tests
- Backend Shared Routing
- Kratos Units Tests
- Meshing and Calculation Routes
- Session Edit Contract
- Project Schema Models
- Interface Detection
- Run Catalogue
- Run Listing Tests
- MDPA Import
- GiD Result Reader
- Kratos Interface Tests
- 2D Geometry Build
- CLI Analysis Commands
- Legacy Project Migration
- MDPA Reader
- Gmsh Meshing
- Frontend Results Panel
- CLI Results Commands
- CLI Shell
- Solid Model Builder
- Import Layering Rules
- CLI Tutorials
- Frontend Dialogs
- Run Archive Download
- Structures Commands
- Material Definitions
- Result Mesh Rendering
- 3D Geometry Build Tests
- 2D Meshing Tests
- Browser E2E Harness
- Deck Property Tests
- Stage Process Tests
- Display Tessellation
- External Deck Opening
- External Deck Model
- 3D Kratos Export
- Deck Invariant Checks
- CLI Pipeline Commands
- Frontend Undo History
- MDPA Deck Model
- Project File IO
- Old Record Detection
- Frontend Beams
- Frontend Results Windows
- Kratos Run Integration
- Model Script Loading
- Ground Commands
- Gmsh Session and 3D Build
- Results Plot Window
- viewport.js
- patches.js
- test_result_members.py
- test_result_parts.py
- anchors.js
- model.js
- test_results_regression.py
- _beam()
- test_importer.py
- model/__init__.py
- open()
- test_tessellate.py
- Panel
- phases.js
- test_section_structures_3d.py
- test_results_round_trip.py
- test_water_level.py
- volumes.py
- test_gui_commands.py
- test_export_golden.py
- geometry/__init__.py
- test_app_wiring.py
- routes/results.py
- test_calculate.py
- test_script_writer.py
- test_kratos_runner.py
- CLI Reference Doc
- calculation.py
- backend/main.py
- run()
- test_load_translation.py
- test_wall_translation.py
- test_kratos_stages.py
- terminal/shell.py
- Architecture Doc
- Shell
- sys
- interfaces.js
- repository_files()
- test_stage_commands.py
- test_kratos_solver.py
- CommandError
- announcing()
- test_ci_workflow.py
- test_github_config.py
- test_tier_runner.py
- test_route_contract.py
- test_launcher.py
- commands/project.py
- Features Doc
- Testing Doc and CI
- mesh-labels.js
- test_js_coverage_summary.py
- test_mesh_parts.py
- commands/phases.py
- process_creation()
- _project()
- loads.js
- soil-volume-dialog.js
- Contributing Guide
- cli/conftest.py
- script_writer.py
- test_feature_matrix.py
- test_schema_bounds.py
- subprocess
- scripting.py
- results-view.js
- cad_import.py
- model/phases.py
- material-sets.js
- fake_kratos.py
- test_script_command.py
- README Overview
- ui.js
- part-colors.js
- mountLivePhases()
- buildGroups()
- bindPointer()
- Orchestrator
- _anchor()
- launcher.py
- paint()
- interpreter()
- parameters.py
- translate()
- test_results_cache.py
- explorer.js
- refresh()
- syncSectionGrid()
- test-model.js
- test_parity.py
- project_parameters()
- load_translation.py
- default_phases()
- test_draft_parity.py
- test-frozen-ui.js
- rebuildDerived()
- node-parts.js
- ruler.js
- units.js
- project_with()
- test_style.py
- core/kratos/__init__.py
- Kratos Setup Doc
- results-render.js
- init()
- test-import-dialogs.js
- test_custom_part_routes.py
- test_conftest_tiers.py
- write_deck()
- linearise()
- Parameters
- canvas-renderer.js
- draw-input.js
- test_main.py
- test_phases.py
- _with_interfaces()
- enabled()
- make_results_field_fixture.py
- WaterUpdate
- deck.js
- Security Policy
- test-patches-results.js
- test-results.js
- padded()
- test_event_loop.py
- _auxiliary()
- staged_excavation_phases()
- GUI Usage Doc
- syntax_check.py
- mdpa-import-dialog.js
- apply()
- copy()
- test_mdpa_property.py
- geometryRows()
- renameObject()
- syncDimensionAvailability()
- syncModelMode()
- animate()
- test-patches.js
- test_no_examples.py
- Pipeline Diagram
- export.js
- syncTrees()
- test-dock.js
- test-download.js
- test-interfaces.js
- test-normal-loads.js
- test-results-plot.js
- test-viewport-live.js
- test_unverified_register.py
- parse_args()
- make_viewport_fixture.py
- base/js/orbit.js
- toolbars.js
- calculate.js
- download.js
- material-library.js
- frontend/js/orbit.js
- harness.js
- test-draw-pointer.js
- test-patches-phases.js
- test-water.js
- tests/conftest.py
- FakeOrchestrator
- .prompt()
- command.js
- build()
- anchorProps()
- availableNow()
- test-api.js
- test-canvas-renderer.js
- test-material-sets.js
- test-phases.js
- test_post_geometry_create_line_and_surface_stay_drawable()
- domains()
- set_excavation()
- api.js
- open()
- zip.js
- test-orbit.js
- test-results-view.js
- unresolved()
- stage_name()
- test-calculate.js
- test-draw-input.js
- test-mesh-labels.js
- test-patches-modes.js
- test_two_deck_presses_at_the_same_moment_start_one_run()
- test_the_test_model_runs_as_a_script()
- Results Mode Concepts
- water-command.js
- click()
- withExportStubs()
- test-material-library.js
- test-part-colors.js
- test-shortcuts.js
- PlatformEnvironmentTests
- test_the_server_s_own_packages_stay_imported_when_a_script_sits_above_them()
- kratos-shell.sh
- kratos-cli.sh
- run.sh script
- test_a_round_trip_keeps_the_original_footprint()
- test_a_relative_path_is_read_from_the_repository_root()

## God Nodes (most connected - your core abstractions)
1. `Project` - 425 edges
2. `seed_project()` - 334 edges
3. `MeshRequest` - 159 edges
4. `fixture()` - 153 edges
5. `load()` - 152 edges
6. `session()` - 141 edges
7. `excavation_project()` - 122 edges
8. `export_project()` - 117 edges
9. `Answer` - 90 edges
10. `deck_of()` - 80 edges

## Surprising Connections (you probably didn't know these)
- `test_a_deck_project_points_at_its_deck()` --uses--> `Project`  [INFERRED]
  tests/test_deck.py → core/model/schemas.py
- `by_id()` --uses--> `Project`  [INFERRED]
  tests/test_load_translation.py → core/model/schemas.py
- `test_mesh_labels_route_returns_the_export_numbering()` --uses--> `Project`  [INFERRED]
  tests/test_mesh_labels.py → core/model/schemas.py
- `Host header check against DNS rebinding` --semantically_similar_to--> `Use Styx from another computer (--host, KRATOS_GUI_ALLOWED_HOSTS)`  [INFERRED] [semantically similar]
  SECURITY.md → docs/INSTALLATION.md
- `simple_dike.py --gui option (open GUI on the runs of the folder)` --semantically_similar_to--> `GUI and CLI share project file and runs (File > Open project, results open)`  [INFERRED] [semantically similar]
  examples/simple_dike/README.md → docs/cli_tutorials/CROW_case.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **GUI / kratos-cli parity contract** — contributing_core_session, contributing_gui_cli_parity, docs_cli_gui_command_box_table, tests_cli_test_gui_commands, readme_shared_project_file, docs_usage_command_box [INFERRED 0.85]
- **Local server security controls** — security_localhost_binding, security_host_header_check, security_origin_check, docs_installation_remote_access [EXTRACTED 1.00]
- **Kratos connection configuration** — docs_kratos_setup_kratos_local_json, docs_kratos_setup_env_vars, docs_kratos_setup_separate_process, docs_kratos_setup_run_folder, docs_cli_run_calculate, docs_usage_calculate [EXTRACTED 1.00]
- **kratos-cli workflow: build, mesh, phase, export/run, read results** — docs_cli_tutorials_1_build_from_scratch_kratos_cli_shell, docs_cli_tutorials_1_build_from_scratch_mesh_command, docs_cli_tutorials_1_build_from_scratch_phases, docs_cli_tutorials_1_build_from_scratch_check_export_run, docs_cli_tutorials_1_build_from_scratch_results_commands [EXTRACTED 1.00]
- **Staged excavation sequence: lifts, strut, interface, water loads switched by phases** — docs_cli_tutorials_crow_case_phases_staged_excavation, docs_cli_tutorials_crow_case_excavation_lifts, docs_cli_tutorials_crow_case_part_keys, docs_cli_tutorials_crow_case_strut_anchor, docs_cli_tutorials_crow_case_wall_interface, docs_cli_tutorials_crow_case_hydrostatic_normal_load [EXTRACTED 1.00]
- **Equivalent model representations: project file, model script, Kratos deck** — examples_simple_dike_readme_simple_dike_json, examples_simple_dike_simple_dike, examples_crow_case_readme_crow_json, examples_crow_case_crow, docs_cli_tutorials_1_build_from_scratch_script_command, docs_cli_tutorials_readme_kratos_input_deck [INFERRED 0.85]
- **Styx model-to-Kratos-results pipeline** — docs_developer_pipeline_solids, docs_developer_pipeline_fe_mesh, docs_developer_pipeline_split_stage, docs_developer_pipeline_write_deck, docs_developer_pipeline_solve, docs_developer_pipeline_read_back [EXTRACTED 1.00]
- **Styx architecture design decisions** — docs_developer_architecture_gmsh_worker_decision, docs_developer_architecture_kratos_subprocess_decision, docs_developer_architecture_frozen_base_live_layer, docs_developer_architecture_part_keys, docs_developer_architecture_logic_without_dom, docs_developer_architecture_runs_are_folders [EXTRACTED 1.00]
- **Styx test infrastructure** — docs_developer_testing_test_tiers, frontend_tests_index, requirements_dev_playwright, requirements_dev_pytest_cov, docs_developer_testing_quickjs, docs_developer_testing_ci [INFERRED 0.85]

## Communities (303 total, 71 thin omitted)

### Community 0 - "API Contract Tests"
Cohesion: 0.02
Nodes (93): seed_project(), client(), interface_section(), restore_3d(), _staged_project(), test_a_2d_model_survives_a_round_trip_through_the_solid_model(), test_a_3d_structural_model_goes_from_patch_to_deck_through_the_api(), test_a_custom_part_may_carry_a_soil_material() (+85 more)

### Community 1 - "CLI Structure Drafts"
Cohesion: 0.04
Nodes (78): _drafted(), anchor(), anchor_head(), borehole(), _default_head(), DraftError, _finite(), _first_section() (+70 more)

### Community 2 - "Project Edit Updates"
Cohesion: 0.03
Nodes (88): MaterialsUpdate, PhasesUpdate, add_borehole(), add_layer(), add_phase(), assign_part_material(), _joined(), _locate() (+80 more)

### Community 3 - "Kratos Deck Export Tests"
Cohesion: 0.03
Nodes (80): anchored_project(), deck_of(), _gravity_processes(), _load_process(), midside_failures(), piled_project(), _pressure_processes(), _stage_settings() (+72 more)

### Community 4 - "Mesh and Deck Jobs"
Cohesion: 0.04
Nodes (71): mesh_labels_job(), node_parts_job(), export_project(), MeshRequest, test_the_kn_deck_is_the_si_deck_in_kilonewtons(), runs(), export(), golden() (+63 more)

### Community 5 - "CLI Edit Commands"
Cohesion: 0.03
Nodes (58): section_prism(), load(), test_a_field_with_a_command_of_its_own_points_at_it(), test_add_takes_a_record_from_a_file_and_remove_takes_it_away(), test_get_without_a_path_prints_the_whole_project(), test_set_takes_text_that_is_not_json_as_text(), test_set_writes_a_number(), empty() (+50 more)

### Community 6 - "Loads and Computed Fields"
Cohesion: 0.03
Nodes (28): _load_sections(), loaded_elements(), point_on_panel(), point_on_polyline(), Project, _reject_duplicates(), SpaceAnchor, _hangs_from() (+20 more)

### Community 7 - "Project Schema Tests"
Cohesion: 0.03
Nodes (60): _contact(), _layered_pit(), _normal_load(), _phase(), _phased(), _sand(), _simple_with_a_load(), test_a_lift_crossing_a_layer_boundary_yields_one_body_per_layer() (+52 more)

### Community 8 - "Result Field Catalogue"
Cohesion: 0.04
Nodes (51): at_node(), catalogue(), _component(), Definition, _deviatoric_stress(), displacement(), _displacements(), _locations() (+43 more)

### Community 9 - "Kratos Deck Writer"
Cohesion: 0.04
Nodes (46): _adjacent_material(), _align_conditions(), _anchor_of(), _anchor_ties(), _beam_bodies(), _beam_of(), _bodies(), _boundary_constraints() (+38 more)

### Community 10 - "Real Run and CI Tests"
Cohesion: 0.04
Nodes (50): test_results_of_a_real_run_are_read_by_path(), all_workflows(), check_names(), commands(), kratos(), lint(), load(), pull_request_checks() (+42 more)

### Community 11 - "Backend Shared Routing"
Cohesion: 0.05
Nodes (36): not_for_a_deck(), read_upload(), refusals(), clear_custom_parts(), create_geometry(), delete_geometry_part(), get_geometry(), import_geometry() (+28 more)

### Community 12 - "Kratos Units Tests"
Cohesion: 0.04
Nodes (53): browser_type_launch_args(), test_an_unsupported_element_type_fails_loudly_before_anything_is_written(), _bare(), _round_numbers(), test_a_lift_keeps_the_stiffness_of_the_layer_it_was_dug_from(), test_a_lifts_contact_takes_the_layer_it_was_dug_from(), test_a_line_load_is_written_in_newtons_per_metre(), test_a_material_that_says_nothing_about_porosity_still_gets_a_number() (+45 more)

### Community 13 - "Meshing and Calculation Routes"
Cohesion: 0.04
Nodes (41): run_mesh_job(), _calculate_deck(), calculate_project(), export_mdpa(), import_mdpa(), refusals(), MeshingError, _discard() (+33 more)

### Community 14 - "Session Edit Contract"
Cohesion: 0.04
Nodes (49): LayersUpdate, StructuresUpdate, add_material(), add_section(), add_structure(), check_recipe(), _collection(), DeckReadOnly (+41 more)

### Community 15 - "Project Schema Models"
Cohesion: 0.07
Nodes (35): main(), _load_variable(), section_kind(), Anchor, AnchorRows, Base, Beam, BeamSection (+27 more)

### Community 16 - "Interface Detection"
Cohesion: 0.06
Nodes (41): _adjacent(), _barriers(), _centroid(), _components(), _duplicate(), _edges_of(), _emit(), _facing() (+33 more)

### Community 17 - "Run Catalogue"
Cohesion: 0.06
Nodes (41): _base_for(), directory_of(), failed_at(), file_path(), _files(), _gid_output_name(), _member_files(), _member_output() (+33 more)

### Community 18 - "Run Listing Tests"
Cohesion: 0.05
Nodes (50): describe(), runs(), test_nothing_between_the_project_and_the_deck_converts_a_unit(), client(), failed_log(), finished_log(), make_run(), outside_run() (+42 more)

### Community 19 - "MDPA Import"
Cohesion: 0.05
Nodes (42): import_mdpa(), to_sections(), reimported(), session(), test_a_2d_deck_draws_its_triangles_directly_with_no_boundary_extraction(), test_a_2d_deck_needs_no_standing_up(), test_a_2d_quadrilateral_class_is_soil_rather_than_unknown(), test_a_3d_deck_is_already_in_the_world_frame_and_is_left_alone() (+34 more)

### Community 20 - "GiD Result Reader"
Cohesion: 0.05
Nodes (40): Block, GaussSet, _number(), read_mesh(), read_results(), dedent(), reference_stage(), test_a_block_carries_its_element_type_and_node_count() (+32 more)

### Community 21 - "Kratos Interface Tests"
Cohesion: 0.05
Nodes (39): beam_nodes(), entries_of(), interface_block(), interface_material(), interface_parts(), session(), soil_nodes(), test_a_boundary_group_picks_up_the_copies_that_land_on_it() (+31 more)

### Community 22 - "2D Geometry Build"
Cohesion: 0.05
Nodes (38): build_geometry(), _anchored_section(), full(), _loaded_section(), _piled_section(), section_project(), simple(), staged() (+30 more)

### Community 23 - "CLI Analysis Commands"
Cohesion: 0.06
Nodes (27): calculate_model(), _ran(), register(), run_deck(), _run_options(), register(), run_shell(), export_deck() (+19 more)

### Community 24 - "Legacy Project Migration"
Cohesion: 0.05
Nodes (37): _anchor(), _anchor_section(), _beam_section(), _interface_section(), is_legacy(), _load(), material(), migrate() (+29 more)

### Community 25 - "MDPA Reader"
Cohesion: 0.05
Nodes (24): bbox_of(), _element_labels(), _entities(), Entity, ImportError_, MdpaModel, _nodes(), Part (+16 more)

### Community 26 - "Gmsh Meshing"
Cohesion: 0.06
Nodes (31): _add_tie_segments(), _apply_refinements(), _boundary_section(), _boundary_surfaces(), _configure(), _finite_element_volumes(), _interface_sections(), _left_of() (+23 more)

### Community 27 - "Frontend Results Panel"
Cohesion: 0.10
Nodes (52): archiveUrl(), atNode(), base(), changed(), chooseStage(), defaultField(), describeCurrent(), download() (+44 more)

### Community 28 - "CLI Results Commands"
Cohesion: 0.08
Nodes (33): _first_location(), get_archive(), get_file(), _label(), list_fields(), list_files(), list_members(), list_runs() (+25 more)

### Community 29 - "CLI Shell"
Cohesion: 0.05
Nodes (45): words(), cli(), run(), Ran, piped(), run(), test_a_blank_line_parts_one_echoed_command_from_the_next(), test_a_byte_order_mark_from_a_powershell_pipe_is_not_part_of_the_line() (+37 more)

### Community 30 - "Solid Model Builder"
Cohesion: 0.05
Nodes (28): _assign_by_priority(), _attach_anchors(), _build_display_only(), _build_layered_soil(), _build_solids(), box(), own(), _clip_to_model() (+20 more)

### Community 31 - "Import Layering Rules"
Cohesion: 0.06
Nodes (32): core_imports(), imports(), layer(), module_aliases(), parsed(), prose_spans(), _repo_root(), served_file() (+24 more)

### Community 32 - "CLI Tutorials"
Cohesion: 0.06
Nodes (52): Build the model step by step (tutorial), Beam section (sheet pile; steel properties on the section, no separate material), show / check / export / run workflow, GeoLinearElasticPlaneStrain2DLaw, Global water level (water <level>); borehole --water is not used by Kratos, K0 procedure (initial stresses), kratos-cli shell (one command per line, open project implied), KRATOS_GUI_RUNS environment variable (runs folder shared with GUI) (+44 more)

### Community 33 - "Frontend Dialogs"
Cohesion: 0.08
Nodes (40): commitMaterials(), commitOnEnter(), drag(), up(), fieldBuilders(), colorRow(), numRow(), row() (+32 more)

### Community 34 - "Run Archive Download"
Cohesion: 0.04
Nodes (19): archive(), client(), copied(), _route(), test_a_field_as_csv_is_the_gui_s_csv(), test_a_field_is_the_route_s_field(), test_a_profile_as_csv_is_the_gui_s_plot_csv(), test_a_profile_is_the_plot_route_s_curves() (+11 more)

### Community 35 - "Structures Commands"
Cohesion: 0.10
Nodes (38): _active(), add_section(), add_structure(), _anchor_fields(), _beam_fields(), _components(), _fields(), _interface_fields() (+30 more)

### Community 36 - "Material Definitions"
Cohesion: 0.06
Nodes (24): _anchor_variables(), _beam_variables(), _check(), dimension_law(), _fill(), _interface_variables(), jaky(), material_parameters() (+16 more)

### Community 37 - "Result Mesh Rendering"
Cohesion: 0.07
Nodes (34): outline_of(), stage_sections(), triangles_of(), dedent(), section_of(), segments_of(), test_a_3d_part_is_drawn_as_its_skin_without_the_shared_face(), test_a_3d_skin_offers_no_per_element_colouring() (+26 more)

### Community 38 - "3D Geometry Build Tests"
Cohesion: 0.05
Nodes (28): bounding_box(), CustomPart, test_every_staged_body_occupies_the_band_and_side_it_is_named_for(), assert_bounds(), _expected_soil_volume(), project(), test_a_footprint_overhanging_the_domain_leaves_no_free_floating_surface(), test_a_load_footprint_splits_the_top_face_at_its_own_edges() (+20 more)

### Community 39 - "2D Meshing Tests"
Cohesion: 0.07
Nodes (29): a_box(), anchored_section(), beam_mesh(), edge_lengths_by_band(), excavation_deck(), excavation_like(), mesh_nodes_at(), piled_section() (+21 more)

### Community 40 - "Browser E2E Harness"
Cohesion: 0.08
Nodes (28): app_page(), browser_type_launch_args(), command(), _free_port(), live_server(), log_text(), calculate(), deck_case() (+20 more)

### Community 41 - "Deck Property Tests"
Cohesion: 0.05
Nodes (32): _phased(), test_a_3d_phase_list_still_activates_and_deactivates_its_parts(), test_property_ids_stay_unique_across_soil_wall_member_and_tendon(), test_the_member_takes_the_sheet_piles_profile_library(), test_the_panel_section_becomes_a_material_entry_mapped_to_its_part(), test_the_pile_shell_thickness_is_the_profiles_area_per_metre_run(), test_the_tendon_becomes_a_material_entry_with_its_prestress(), test_a_sheet_pile_is_installed_in_its_own_stage() (+24 more)

### Community 42 - "Stage Process Tests"
Cohesion: 0.07
Nodes (30): carrying(), doc(), modules(), named(), processes(), stages_with(), test_a_dug_out_lifts_interface_stops_carrying_stress(), test_a_part_installed_this_stage_has_no_previous_stress_to_carry() (+22 more)

### Community 43 - "Display Tessellation"
Cohesion: 0.06
Nodes (28): _add_edges(), _colors_by_volume(), DisplayModel, _first_facet(), _group_by_color(), _node_coordinates(), _outer_surfaces(), _overlay_section() (+20 more)

### Community 44 - "External Deck Opening"
Cohesion: 0.05
Nodes (27): client(), deck_script(), gid_output(), stage(), staged_stage(), stand_in(), test_a_deck_file_gone_since_opening_is_reported_not_crashed_on(), test_a_deck_is_not_remeshed() (+19 more)

### Community 45 - "External Deck Model"
Cohesion: 0.09
Nodes (27): _calculation(), deck_name(), deck_project(), DeckError, _flattened(), input_files(), _mdpa_file(), _mesh() (+19 more)

### Community 46 - "3D Kratos Export"
Cohesion: 0.09
Nodes (33): beams_of(), deck_of(), loaded(), session(), shells_of(), _stage_settings(), structured(), test_a_2d_point_load_is_written_as_a_3d_point_condition() (+25 more)

### Community 47 - "Deck Invariant Checks"
Cohesion: 0.12
Nodes (38): every_exported_deck_is_sound(), checked(), check_deck(), _condition_order(), _connectivity(), deck_dimension(), _dimension(), _k0() (+30 more)

### Community 48 - "CLI Pipeline Commands"
Cohesion: 0.05
Nodes (20): save(), test_a_deck_is_not_exported(), test_a_deck_is_not_meshed(), test_a_model_with_nothing_to_mesh_is_not_exported(), test_a_model_with_nothing_to_mesh_is_not_meshed(), test_calculate_runs_a_deck_project_as_the_files_it_is(), test_export_names_the_mesh_as_asked(), test_export_writes_the_kratos_deck() (+12 more)

### Community 49 - "Frontend Undo History"
Cohesion: 0.10
Nodes (31): changed(), clone(), current(), defaultEnv(), install(), record(), redo(), reset() (+23 more)

### Community 50 - "MDPA Deck Model"
Cohesion: 0.08
Nodes (24): preview(), Block, _connectivity(), Deck, _nodes(), parse(), Part, _part_data() (+16 more)

### Community 51 - "Project File IO"
Cohesion: 0.07
Nodes (18): ProjectFileError, _replace(), _write(), write_script(), client(), _temp_files(), test_a_cross_site_request_is_refused(), test_a_foreign_host_is_refused_before_any_route_runs() (+10 more)

### Community 53 - "Frontend Beams"
Cohesion: 0.14
Nodes (38): available(), collection(), copy(), defaultPanelSection(), defaultSection(), draft(), draftFromPoints(), draftMember() (+30 more)

### Community 54 - "Frontend Results Windows"
Cohesion: 0.10
Nodes (39): confirmDialog(), install(), askForNode(), bind(), bindResultsProbe(), closePlotWindow(), closeResultsWindow(), esc() (+31 more)

### Community 55 - "Kratos Run Integration"
Cohesion: 0.08
Nodes (21): forget_cache(), client(), test_a_model_is_calculated_by_kratos(), run(), runs_root(), client(), deck_text(), fake_run() (+13 more)

### Community 56 - "Model Script Loading"
Cohesion: 0.11
Nodes (28): load_project(), client(), test_a_broken_builder_reports_its_own_failure(), test_a_builder_may_be_named_after_what_it_builds(), test_a_builder_that_returns_something_else_says_what_it_returned(), test_a_helper_module_beside_the_script_can_be_imported(), test_a_helper_that_takes_arguments_is_not_mistaken_for_the_entry_point(), test_a_missing_file_says_where_it_looked() (+20 more)

### Community 57 - "Ground Commands"
Cohesion: 0.17
Nodes (27): add_borehole(), add_layer(), add_material(), _borehole_fields(), _domain_line(), list_boreholes(), list_layers(), list_materials() (+19 more)

### Community 58 - "Gmsh Session and 3D Build"
Cohesion: 0.11
Nodes (27): session(), test_post_geometry_import_adds_custom_part_and_invalidates(), test_every_entity_is_a_surface(), conformity(), groups(), structured(), test_a_member_becomes_named_one_dimensional_curves(), test_a_panel_becomes_named_two_dimensional_faces() (+19 more)

### Community 59 - "Results Plot Window"
Cohesion: 0.11
Nodes (33): axisLabel(), cell(), changed(), command(), csv(), decimalsOf(), esc(), extreme() (+25 more)

### Community 60 - "viewport.js"
Cohesion: 0.08
Nodes (23): buildPartColors(), clearImportedMesh(), clearNodeMark(), computeGroupKeys(), computeModeGroups(), disposeGroup(), dolly(), fillTriad() (+15 more)

### Community 61 - "patches.js"
Cohesion: 0.09
Nodes (32): Results explorer panel, addPartColorSlot(), addPartColorToggle(), addPartColorToggles(), adoptProject(), collapsibleResultsPanel(), deleteCustomPart(), deleteObject() (+24 more)

### Community 62 - "test_result_members.py"
Cohesion: 0.07
Nodes (19): available(), member_name(), profile(), Quantity, UnknownQuantity, _value(), client(), output() (+11 more)

### Community 63 - "test_result_parts.py"
Cohesion: 0.09
Nodes (19): element_owner(), stage_parts(), StagePart, dedent(), dedent(), model(), stage_mesh(), test_a_node_only_part_is_carried_but_never_called_dead() (+11 more)

### Community 64 - "anchors.js"
Cohesion: 0.15
Nodes (32): available(), collection(), copy(), defaultSection(), draft(), draftFromPoints(), edit(), extent() (+24 more)

### Community 65 - "model.js"
Cohesion: 0.11
Nodes (30): beamLength(), beamNumberEditor(), beamProps(), contactMaterialEditor(), contactNumberEditor(), contactPermeabilityEditor(), fixed(), groupedInteger() (+22 more)

### Community 66 - "test_results_regression.py"
Cohesion: 0.06
Nodes (18): member_output(), project(), run(), test_a_plot_has_one_panel_per_stage_with_the_wall_in_it(), test_effective_stress_is_compression_negative_and_q_is_not(), test_every_stage_agrees_with_the_phase_model_about_what_exists(), test_interfaces_are_reported_as_unwritten_rather_than_as_demolished(), test_stage_one_has_the_ground_and_nothing_that_is_built_later() (+10 more)

### Community 67 - "_beam()"
Cohesion: 0.10
Nodes (32): _beam(), _member(), _panel(), _panel_section(), _section(), _space_anchor(), test_3d_structures_become_part_keys_so_the_frontend_can_pick_them(), test_a_2d_anchor_may_hang_from_a_2d_pile_while_a_3d_one_hangs_from_a_panel() (+24 more)

### Community 68 - "test_importer.py"
Cohesion: 0.13
Nodes (29): process_import(), import_job(), assert_one_box(), binary_stl(), client(), data_dir(), gmsh_session(), _normal() (+21 more)

### Community 69 - "model/__init__.py"
Cohesion: 0.10
Nodes (17): read_output(), deep_vertical_stress(), nodes_block(), peak_moment(), run(), soil_block(), solid_excavation(), test_3d_excavation_runs_every_stage_without_its_surcharge() (+9 more)

### Community 70 - "open()"
Cohesion: 0.11
Nodes (26): algorithmRow(), bodyControls(), fromProject(), merge(), meshBodies(), meshTargets(), open(), close() (+18 more)

### Community 71 - "test_tessellate.py"
Cohesion: 0.08
Nodes (20): display(), project(), project_with_line_and_surface(), sections_of(), signed_volume(), test_a_drawn_line_renders_as_an_edges_only_section(), test_a_drawn_surface_renders_as_a_visible_flat_section(), test_box_shaped_parts_tessellate_exactly() (+12 more)

### Community 72 - "Panel"
Cohesion: 0.09
Nodes (11): Member, _ordered_like(), Panel, _beam_from(), _is_vertical(), _number_of(), _panel_from(), _partner_of() (+3 more)

### Community 73 - "phases.js"
Cohesion: 0.17
Nodes (29): activeParts(), added(), blank(), branchProblem(), chainTo(), copied(), copy(), days() (+21 more)

### Community 74 - "test_section_structures_3d.py"
Cohesion: 0.08
Nodes (17): small_model(), test_without_settings_the_project_meshes_with_its_own(), drawable(), drawn(), project_with_2d_structures(), section(), sections_of(), solid() (+9 more)

### Community 75 - "test_results_round_trip.py"
Cohesion: 0.11
Nodes (19): active_elements(), gid_type(), _mesh_text(), output_base(), _results_text(), write_run(), nodes_in(), pw() (+11 more)

### Community 76 - "test_water_level.py"
Cohesion: 0.09
Nodes (22): client(), current(), every_field(), put(), test_a_law_this_application_cannot_pair_is_kept_and_named(), test_a_project_starts_in_si(), test_a_round_trip_returns_the_same_numbers(), test_a_variable_whose_dimension_is_unknown_is_kept_and_named() (+14 more)

### Community 77 - "volumes.py"
Cohesion: 0.14
Nodes (19): add_value(), _edited(), get_value(), register(), remove_value(), set_value(), _short(), add_volume() (+11 more)

### Community 78 - "test_gui_commands.py"
Cohesion: 0.13
Nodes (18): block(), documented(), gui_commands(), module_defining(), not_mine_words(), plot_verbs(), read(), results_verbs() (+10 more)

### Community 79 - "test_export_golden.py"
Cohesion: 0.06
Nodes (17): deck(), every_named_part(), materials(), session(), staged_deck(), staged_doc(), test_every_body_a_stage_solves_carries_elements(), test_every_part_any_stage_names_is_in_the_mdpa() (+9 more)

### Community 80 - "geometry/__init__.py"
Cohesion: 0.09
Nodes (15): node_parts(), _close(), differences(), summary(), test_a_count_within_two_percent_is_not_a_change(), test_the_deck_structure_matches_its_snapshot(), _saved(), _solid_excavation() (+7 more)

### Community 81 - "test_app_wiring.py"
Cohesion: 0.09
Nodes (17): check_mesh_keys(), unknown_mesh_keys(), owner(), _route_functions(), _session_calls(), test_check_mesh_keys_lets_the_model_own_keys_through(), test_check_mesh_keys_names_every_unknown_key_sorted(), test_each_edit_route_makes_its_edit_through_core_session() (+9 more)

### Community 82 - "routes/results.py"
Cohesion: 0.09
Nodes (13): results_archive(), _results_error(), results_file(), results_member_plot(), results_members(), results_run(), results_runs(), results_stage_at() (+5 more)

### Community 83 - "test_calculate.py"
Cohesion: 0.10
Nodes (17): failed_stage(), marker(), runs(), test_a_failure_in_the_very_first_stage_is_named(), test_a_run_where_every_stage_ended_blames_none_of_them(), test_a_stage_name_may_contain_spaces(), test_a_timeout_with_its_output_in_bytes_is_still_reported(), timed_out() (+9 more)

### Community 84 - "test_script_writer.py"
Cohesion: 0.10
Nodes (19): with_imported_part(), test_a_cad_file_is_imported_and_given_a_material(), deck_dir(), obj_text(), drawn(), round_trip(), run_as(), solids_here() (+11 more)

### Community 85 - "test_kratos_runner.py"
Cohesion: 0.13
Nodes (17): deck(), markers(), run_runner(), stub_on_path(), test_a_real_export_runs_through_the_stand_in(), test_a_stage_that_raises_begins_and_never_ends(), test_an_orchestrator_the_registry_does_not_know_fails_before_any_stage(), test_every_stage_is_announced_in_execution_order() (+9 more)

### Community 86 - "CLI Reference Doc"
Cohesion: 0.10
Nodes (26): Release workflow (tag -> release.yml archives and GitHub release), CLI.md (kratos-cli reference), Axes convention (x across, y up, z out of section), --out and --dry-run write options, Output and exit codes (0 ok, 1 refused, 2 bad command line, --json), GUI command box to kratos-cli mapping table, kratos-cli (terminal tool of Styx), Model scripts (project() function, script/build, python pit.py --calculate) (+18 more)

### Community 87 - "calculation.py"
Cohesion: 0.12
Nodes (18): Busy, CalculationError, _contents(), _execute(), _explain(), new_run_directory(), _one_at_a_time(), run_deck() (+10 more)

### Community 88 - "backend/main.py"
Cohesion: 0.09
Nodes (9): health(), index(), lifespan(), worker_crashed(), allowed_hosts(), do_not_cache_sources(), _host_name(), only_this_browser_tab() (+1 more)

### Community 89 - "run()"
Cohesion: 0.10
Nodes (18): run(), stand_in(), test_a_deck_that_cannot_be_written_frees_the_button(), test_a_failed_run_comes_back_with_what_kratos_said(), test_a_kratos_the_interpreter_cannot_load_is_explained_too(), test_a_missing_kratos_is_explained_rather_than_left_as_a_traceback(), test_a_run_past_the_timeout_is_given_up_on_and_says_where(), test_a_run_that_works_reports_no_failed_stage() (+10 more)

### Community 90 - "test_load_translation.py"
Cohesion: 0.11
Nodes (18): by_id(), kinds(), raised(), test_a_line_load_at_the_borehole_top_still_translates_when_nothing_is_drawn(), test_a_line_load_below_the_ground_surface_gets_no_counterpart(), test_a_line_load_buried_in_the_embankment_still_gets_no_counterpart(), test_a_line_load_gains_a_surface_counterpart_in_3d(), test_a_line_load_on_a_drawn_embankment_translates() (+10 more)

### Community 91 - "test_wall_translation.py"
Cohesion: 0.16
Nodes (17): applied(), panel_of(), project_with(), test_a_footprint_narrowed_in_3d_survives_a_trip_through_the_section(), test_a_panel_narrowed_clear_of_the_section_plane_is_not_built_in_the_section(), test_a_plane_anchors_head_is_a_node_of_the_translated_wall(), test_a_raking_pile_gets_no_panel_and_says_so(), test_a_sheet_pile_gains_a_wall_panel_in_3d() (+9 more)

### Community 92 - "test_kratos_stages.py"
Cohesion: 0.11
Nodes (15): operation(), preprocess(), solver(), stage_names(), test_a_phased_project_exports_one_stage_per_phase(), test_a_project_with_no_phases_exports_the_two_stage_deck_it_always_did(), test_a_stage_that_changes_nothing_writes_no_operations(), test_an_unphased_deck_still_starts_at_zero() (+7 more)

### Community 93 - "terminal/shell.py"
Cohesion: 0.11
Nodes (13): _command_groups(), completions(), Leave, _named(), _parser(), _readline(), complete(), _save_history() (+5 more)

### Community 94 - "Architecture Doc"
Cohesion: 0.11
Nodes (19): Architecture reference, Part keys, Code size of Styx, Code counting method (ast for Python, function keywords for ES5 JS), Developer guide, Code map (graphify GRAPH_TREE.html, GRAPH_REPORT.md), Kratos GeoMechanics deck files (.mdpa, MaterialParameters.json, ProjectParameters.json, initial_materials.json, kratos_gui_units.json), Three Gmsh jobs: build solids, draw (tessellate), mesh (+11 more)

### Community 95 - "Shell"
Cohesion: 0.16
Nodes (3): error(), _has_words(), Shell

### Community 96 - "sys"
Cohesion: 0.10
Nodes (12): checkout(), checkout(), stored(), test_every_phase_has_an_answer_and_the_order_is_the_chain(), test_the_active_set_is_always_a_subset_of_what_can_be_staged(), test_the_fixture_exercises_the_cases_a_chain_walk_gets_wrong(), test_the_fixture_is_a_parseable_javascript_assignment(), test_the_fixture_on_disk_is_what_the_server_computes() (+4 more)

### Community 97 - "interfaces.js"
Cohesion: 0.19
Nodes (24): available(), collection(), copy(), defaultSection(), draft(), edit(), isInterfaceKey(), length() (+16 more)

### Community 98 - "repository_files()"
Cohesion: 0.10
Nodes (16): lines_matching(), module_names(), old_core_pattern(), renamed_names_in_prose(), renamed_pattern(), repository_files(), shown(), stale_pattern() (+8 more)

### Community 99 - "test_stage_commands.py"
Cohesion: 0.10
Nodes (11): deck(), _phase(), pit(), test_activate_and_deactivate_switch_parts_from_a_phase_on(), test_add_before_inserts_a_phase_into_the_chain(), test_add_puts_a_phase_at_the_end_with_its_settings_and_parts(), test_copy_repeats_a_phase_s_solver_settings(), test_remove_heals_the_chain() (+3 more)

### Community 100 - "test_kratos_solver.py"
Cohesion: 0.11
Nodes (16): session(), stages(), test_a_deck_with_a_beam_switches_rotation_dofs_on(), test_a_staged_deck_reads_the_mesh_before_its_first_operation(), test_each_stage_is_one_step_and_the_settling_stages_sit_before_zero(), test_each_stage_writes_its_own_gid_output(), test_every_stage_carries_a_runnable_solver_block(), test_the_default_tolerances_and_step_controls() (+8 more)

### Community 101 - "CommandError"
Cohesion: 0.16
Nodes (14): _deck_location(), _deck_mdpa(), _is_parameters(), _mdpa_of(), _node_parts(), _parts(), _position(), register() (+6 more)

### Community 102 - "announcing()"
Cohesion: 0.10
Nodes (12): announcing(), _announce(), __init__(), RunCurrentStagePostprocess(), RunCurrentStagePreprocess(), main(), run(), Project (+4 more)

### Community 103 - "test_ci_workflow.py"
Cohesion: 0.08
Nodes (9): commands(), job(), test_a_quickjs_that_does_not_build_does_not_fail_the_install(), test_coverage_is_taken_over_the_core_the_backend_and_the_command_line(), test_the_reports_are_kept_from_where_pytest_writes_them(), tiers(), workflow(), test_the_link_check_settings_are_ones_lychee_accepts() (+1 more)

### Community 104 - "test_github_config.py"
Cohesion: 0.13
Nodes (18): codeql(), commands(), launcher(), lint(), load(), pinned_ruff(), test_codeql_covers_both_languages_of_the_app(), test_codeql_leaves_the_vendored_library_alone() (+10 more)

### Community 105 - "test_tier_runner.py"
Cohesion: 0.11
Nodes (14): names(), pytest_args(), run_with(), execute(), runner(), test_a_failing_step_fails_the_tier_but_the_rest_still_run(), test_an_unavailable_step_is_reported_and_not_run(), test_browser_is_quick_with_the_browser_suite_in() (+6 more)

### Community 106 - "test_route_contract.py"
Cohesion: 0.12
Nodes (13): api_routes(), Contract, deck_client(), _fresh(), _id(), _project(), _readable(), _structures() (+5 more)

### Community 107 - "test_launcher.py"
Cohesion: 0.11
Nodes (13): main(), port_in_use(), listening(), stood_in(), test_a_failed_setup_is_one_line_and_exit_code_one(), test_a_free_port_is_not_in_use(), test_a_named_host_is_allowed_through_to_the_server(), test_a_port_with_a_server_on_it_is_in_use() (+5 more)

### Community 108 - "commands/project.py"
Cohesion: 0.20
Nodes (15): build_project(), check_project(), described(), _file(), headline(), new_project(), register(), set_water() (+7 more)

### Community 109 - "Features Doc"
Cohesion: 0.13
Nodes (20): deck show and node inspection commands, Site and soil commands (domain, water, borehole, material, layer, excavation, volume), Fixed solver settings (static U-Pw, Newton-Raphson, skyline_lu_factorization), FEATURES.md (Styx features and their status), Interface elements and stiffness/strength defaults, Jaky's K0 = 1 - sin(phi) from GEO_FRICTION_ANGLE, K0 procedure and initial_materials.json, core/kratos/parameters.py (SOLVER, ORCHESTRATOR) (+12 more)

### Community 110 - "Testing Doc and CI"
Cohesion: 0.11
Nodes (17): How to run the tests, CI: e2e tier on Windows/Ubuntu, 95% line coverage gate, Self-hosted Kratos runner (nightly kratos tier, Saturday benchmarks), quickjs headless JavaScript tests (KRATOS_GUI_QUICKJS_PYTHON), Test tiers (quick, browser, e2e, kratos, bench, perf, all), Styx browser app page, Command panel (cmd-entry), Browser unit test page (+9 more)

### Community 111 - "mesh-labels.js"
Cohesion: 0.13
Nodes (17): anyActive(), dedupe(), elementsFromSections(), fanOffsets(), groupCoincident(), hide(), install(), isActive() (+9 more)

### Community 112 - "test_js_coverage_summary.py"
Cohesion: 0.17
Nodes (15): below(), _module(), summarise(), table(), script(), test_a_function_is_covered_when_it_ran_at_least_once(), test_a_module_with_no_functions_is_fully_covered(), test_a_script_reported_twice_is_merged_not_double_counted() (+7 more)

### Community 113 - "test_mesh_parts.py"
Cohesion: 0.16
Nodes (15): by_key(), points(), segments(), test_a_one_sided_interface_has_only_that_side(), test_a_soil_body_is_triangles_covering_exactly_its_own_area(), test_a_solid_model_draws_each_body_by_its_own_skin(), test_a_structure_is_line_segments_with_no_faces(), test_a_surface_load_is_the_ground_edges_under_its_footprint() (+7 more)

### Community 114 - "commands/phases.py"
Cohesion: 0.24
Nodes (19): add_phase(), _added(), _calculation(), copy_phase(), default_phases(), _edited(), list_phases(), _listed() (+11 more)

### Community 115 - "process_creation()"
Cohesion: 0.14
Nodes (15): _area(), _check(), _closed_loop(), process_creation(), _vector(), create_job(), test_creator_creates_box(), test_creator_creates_cylinder() (+7 more)

### Community 116 - "_project()"
Cohesion: 0.15
Nodes (15): active_parts(), transitions(), _phase(), _project(), test_a_chain_runs_in_tree_order_not_list_order(), test_a_part_switched_both_ways_in_one_phase_is_refused(), test_a_phase_that_names_nothing_inherits_its_parent_exactly(), test_a_transition_reports_only_what_actually_changes() (+7 more)

### Community 117 - "loads.js"
Cohesion: 0.20
Nodes (20): available(), collection(), copy(), draftFromPoints(), draftPoint(), draftSurface(), edit(), extent() (+12 more)

### Community 118 - "soil-volume-dialog.js"
Cohesion: 0.19
Nodes (21): areaOf(), domainSpan(), formFor(), measure(), num(), open(), check(), close() (+13 more)

### Community 119 - "Contributing Guide"
Cohesion: 0.13
Nodes (14): CONTRIBUTING.md (How to contribute to Styx), CodeQL and dependency review (CODE_SECURITY variable), 95 % line coverage gate, Documents-to-update table, Self-hosted Kratos runner (kratos.yml, nightly), Main branch ruleset (.github/rulesets/main.json), Pull request conventions (conventional title, label, template, one topic), Required CI checks (tests, lint, launcher, pip-audit, gitleaks) (+6 more)

### Community 120 - "cli/conftest.py"
Cohesion: 0.12
Nodes (12): DimensionUpdate, set_dimension(), set_domain(), no_colour_from_this_machine(), site(), stand_in_kratos(), this_machine_has_no_kratos(), test_a_section_of_the_seed_comes_back_as_the_section() (+4 more)

### Community 121 - "script_writer.py"
Cohesion: 0.17
Nodes (12): _code(), _deck_script(), _docstring(), _fields(), _flat(), _grouped(), _heading(), _imports() (+4 more)

### Community 122 - "test_feature_matrix.py"
Cohesion: 0.16
Nodes (15): classes(), export_of(), project_with(), test_a_hydrostatic_normal_load_needs_and_uses_the_water_level(), test_a_line_load_lands_on_the_ground_surface(), test_a_pile_writes_beam_elements_on_its_own_part(), test_any_one_feature_left_out_still_exports(), test_bare_soil_is_soil_and_nothing_else() (+7 more)

### Community 123 - "test_schema_bounds.py"
Cohesion: 0.13
Nodes (10): _adapter(), _cases(), _flatten(), _is_int(), _models(), _numeric_cases(), test_a_bound_accepts_its_edge_and_refuses_past_it(), test_every_refusal_says_which_bound() (+2 more)

### Community 124 - "subprocess"
Cohesion: 0.14
Nodes (9): platform_venv_name(), decoys(), test_the_command_file_puts_the_repository_on_the_path_not_the_user_s_folder(), test_the_posix_wrapper_runs_the_command_in_the_platform_environment(), test_the_posix_wrapper_uses_the_windows_environment_in_git_bash(), test_the_posix_wrapper_works_from_the_user_s_folder(), test_the_windows_wrapper_runs_the_command_in_the_windows_environment(), test_the_windows_wrapper_works_from_the_user_s_folder() (+1 more)

### Community 125 - "scripting.py"
Cohesion: 0.17
Nodes (8): _beside(), _exited(), _find_project(), _line_in(), _resolve(), _run(), ScriptError, with_solids()

### Community 126 - "results-view.js"
Cohesion: 0.20
Nodes (18): clear(), css(), deformFactor(), describeAt(), displacementOf(), draw(), ensureLegend(), escape() (+10 more)

### Community 127 - "cad_import.py"
Cohesion: 0.17
Nodes (9): _bodies(), _checked(), _merge_cad(), _Points, _read_obj(), _read_stl(), _solid_from_triangles(), line() (+1 more)

### Community 128 - "model/phases.py"
Cohesion: 0.19
Nodes (10): added(), _chain_to(), copied(), _copies(), _fresh_id(), inserted(), _last(), removed() (+2 more)

### Community 129 - "material-sets.js"
Cohesion: 0.25
Nodes (18): addMaterial(), copy(), dimension(), duplicateMaterial(), editor(), attempt(), draw(), field() (+10 more)

### Community 130 - "fake_kratos.py"
Cohesion: 0.15
Nodes (10): stage_members(), _du(), fake_run(), _member_outputs(), _pw(), _stress(), _u(), test_a_fake_run_reads_as_a_complete_run_with_member_curves() (+2 more)

### Community 131 - "test_script_command.py"
Cohesion: 0.12
Nodes (9): python(), test_a_model_built_in_the_terminal_comes_back_whole(), test_script_reads_a_script_too(), test_script_writes_the_model_as_a_file_that_builds_it_again(), test_the_file_asks_what_to_do_when_told_nothing(), test_the_file_writes_the_deck_kratos_cli_export_writes(), test_the_gui_does_not_replace_a_file_unless_told_to(), test_the_gui_opens_the_file() (+1 more)

### Community 132 - "README Overview"
Cohesion: 0.18
Nodes (15): REST API (/api/project, /api/mesh, /api/calculate, /api/results), Installation troubleshooting, README.md (Styx overview), CITATION.cff, Construction phases (staged calculation), CROW excavation case tutorial, Deltares, FastAPI server (+7 more)

### Community 133 - "ui.js"
Cohesion: 0.16
Nodes (11): attachTip(), collapsibleDock(), dockSections(), el(), hideTip(), menuLayer(), popup(), splitter() (+3 more)

### Community 134 - "part-colors.js"
Cohesion: 0.25
Nodes (15): baseOf(), candidates(), command(), create(), isOn(), stateOf(), drawn(), keysUnder() (+7 more)

### Community 135 - "mountLivePhases()"
Cohesion: 0.23
Nodes (18): addPhaseCheck(), addPhaseChecks(), emptyPhaseState(), mountLivePhases(), paintPhaseChecks(), phaseById(), phaseLog(), phasePropRow() (+10 more)

### Community 136 - "buildGroups()"
Cohesion: 0.14
Nodes (15): addLoadGlyphs(), addWaterLine(), buildGroups(), edgeMaterial(), loadElevation(), loadGlyphGroup(), loadGlyphSpec(), materialFor() (+7 more)

### Community 137 - "bindPointer()"
Cohesion: 0.15
Nodes (18): applyImportedVisibility(), applyPhaseVisibility(), bindPointer(), boundsOf(), hoverImportedNode(), keysFor(), phaseHidden(), pickables() (+10 more)

### Community 138 - "Orchestrator"
Cohesion: 0.20
Nodes (4): _fail(), Orchestrator, _Stage, SequentialOrchestrator

### Community 139 - "_anchor()"
Cohesion: 0.15
Nodes (15): _anchor(), _anchor_section(), test_a_tendon_may_be_massless(), test_an_anchor_head_must_sit_on_a_sheet_pile(), test_an_anchor_head_must_sit_on_an_active_pile(), test_an_anchor_head_on_a_pile_segment_is_accepted(), test_an_anchor_is_a_dimension_native_head_and_tail(), test_an_anchor_rejects_a_degenerate_line() (+7 more)

### Community 140 - "launcher.py"
Cohesion: 0.20
Nodes (8): check_environment(), ensure_environment(), _ensure_supported_python(), requirements_changed(), _requirements_digest(), venv_python(), RequirementStampTests, test_the_venv_interpreter_is_preferred_when_it_exists()

### Community 141 - "paint()"
Cohesion: 0.21
Nodes (12): _flagged(), answer(), _lead(), _line(), _marked(), mark(), paint(), test_a_line_with_lines_under_it_is_a_heading() (+4 more)

### Community 142 - "interpreter()"
Cohesion: 0.12
Nodes (9): interpreter(), _settings(), repository_root(), test_a_configured_interpreter_that_is_not_there_is_reported_not_guessed(), test_a_settings_file_that_is_missing_or_broken_is_not_fatal(), test_the_environment_still_wins_over_the_file(), test_the_kratos_build_is_put_on_both_paths(), test_the_machine_can_be_configured_in_a_file_instead_of_the_environment() (+1 more)

### Community 143 - "parameters.py"
Cohesion: 0.17
Nodes (8): _activate(), _deactivate(), _gid_output(), _import_mdpa(), _json_output(), _preprocess(), _solver_settings(), Stage

### Community 144 - "translate()"
Cohesion: 0.12
Nodes (11): translate(), test_a_renamed_counterpart_keeps_its_own_name_on_a_later_switch(), test_a_translated_pair_is_built_once_in_each_dimension(), test_a_translated_pair_is_drawn_once_in_the_solid_model(), test_an_edit_made_in_the_section_reaches_the_solid_model(), test_the_default_name_is_renumbered_to_match_its_source(), test_the_line_counterpart_is_named_for_its_own_kind(), test_the_line_counterpart_keeps_the_footprints_x_extent_and_pressure() (+3 more)

### Community 145 - "test_results_cache.py"
Cohesion: 0.12
Nodes (10): counting(), wrapper(), runs_root(), seven_stages(), test_health_answers_while_a_stage_is_being_parsed(), slow(), test_the_cache_is_bounded_by_size_not_unbounded(), real() (+2 more)

### Community 146 - "explorer.js"
Cohesion: 0.24
Nodes (16): clearRowHighlight(), commit(), deleteLayerNode(), editorControl(), expandAll(), layerIdOf(), mountPhases(), mountSelection() (+8 more)

### Community 147 - "refresh()"
Cohesion: 0.21
Nodes (17): fail(), fetchLabels(), forgetNodeParts(), generateMesh(), isVisible(), labelledPoints(), meshRefinements(), meshSettings() (+9 more)

### Community 148 - "syncSectionGrid()"
Cohesion: 0.18
Nodes (17): frameBBox(), gridCell(), gridReference(), makeReferenceGrid(), modelGridSpan(), orientReferenceGrid(), rebuildFrame(), resetReferenceGrid() (+9 more)

### Community 149 - "test-model.js"
Cohesion: 0.18
Nodes (10): anchoredProject(), contactedProject(), labels(), pairedWall(), partRows(), piledProject(), project(), surfaceRows() (+2 more)

### Community 150 - "test_parity.py"
Cohesion: 0.18
Nodes (9): boreholes(), _fields(), layers(), materials(), _object_literals(), test_boreholes_match_frozen_data_js(), test_layers_match_frozen_data_js(), test_materials_match_frozen_data_js() (+1 more)

### Community 151 - "project_parameters()"
Cohesion: 0.13
Nodes (8): _constraint(), _gravity(), _load(), _master_slave_constraint(), _normal_load(), _pore_pressure(), _process_parts(), project_parameters()

### Community 152 - "load_translation.py"
Cohesion: 0.18
Nodes (7): _is_default(), _line_from(), _number_of(), _partner_of(), _surface_from(), _translatable(), _translated_name()

### Community 153 - "default_phases()"
Cohesion: 0.16
Nodes (11): default_phases(), _model(), _staged(), test_a_new_model_gets_no_excavation_phase(), test_an_unexcavated_project_still_gets_a_sequence(), test_staged_excavation_phases_leave_the_ground_under_the_pit_alone(), test_staged_excavation_phases_make_a_project_that_validates(), test_staged_excavation_phases_reproduce_the_reference_sequence() (+3 more)

### Community 154 - "test_draft_parity.py"
Cohesion: 0.21
Nodes (11): UnitsUpdate, set_units(), document(), on_disk(), projects(), rendered(), test_every_structure_tool_is_called(), test_the_fixture_is_what_the_python_says() (+3 more)

### Community 155 - "test-frozen-ui.js"
Cohesion: 0.17
Nodes (10): boot(), setView(), commandRig(), commandRigWith(), enter(), frozenCommand(), host(), key() (+2 more)

### Community 156 - "rebuildDerived()"
Cohesion: 0.14
Nodes (16): customPartChild(), dropFrozenInterfaceRow(), dropWaterLevelNode(), ensureAnchorNode(), ensureInterfaceNode(), ensureNormalLoadNode(), ensureSheetPileNode(), ensureWaterLevelNode() (+8 more)

### Community 157 - "node-parts.js"
Cohesion: 0.24
Nodes (12): build(), hint(), neighbourOf(), partList(), partsOf(), pickOnScreen(), positionKey(), report() (+4 more)

### Community 158 - "ruler.js"
Cohesion: 0.21
Nodes (12): axesOf(), format(), hideAll(), install(), minorDivisions(), niceStep(), paint(), plan() (+4 more)

### Community 159 - "units.js"
Cohesion: 0.32
Nodes (15): command(), convert(), convertVariables(), current(), fromSI(), gravity(), label(), quantityOf() (+7 more)

### Community 160 - "project_with()"
Cohesion: 0.17
Nodes (11): project_with(), switched(), test_a_footprint_narrowed_off_the_cut_in_3d_leaves_the_section(), test_a_footprint_touching_the_cut_is_in_the_section(), test_a_name_the_user_chose_is_carried_across_untouched(), test_a_new_surface_counterpart_spans_the_full_out_of_plane_width(), test_a_pair_made_in_3d_stays_one_pair_too(), test_a_pair_stays_one_pair_over_many_switches() (+3 more)

### Community 161 - "test_style.py"
Cohesion: 0.20
Nodes (10): plain(), test_a_command_line_argparse_cannot_read_is_said_in_colour_too(), test_a_pipe_or_a_file_gets_no_colour(), test_an_answer_is_in_colour_at_a_terminal(), test_an_error_is_red_at_a_terminal_and_plain_in_a_pipe(), test_colour_changes_no_character_of_an_answer(), test_force_color_gives_colour_to_a_pipe(), test_the_prompt_names_the_project_in_colour() (+2 more)

### Community 162 - "core/kratos/__init__.py"
Cohesion: 0.19
Nodes (6): checkout(), exporter_names(), registered(), test_the_name_is_registered_in_kratos(), test_the_scan_found_the_registry(), test_each_deck_file_has_one_name_shared_by_its_writers_and_readers()

### Community 163 - "Kratos Setup Doc"
Cohesion: 0.23
Nodes (14): export command (Kratos input files), run and calculate commands, KRATOS_SETUP.md (Set up Kratos), Environment variables KRATOS_GUI_PYTHON, KRATOS_GUI_KRATOS, KRATOS_GUI_RUNS, KRATOS_GUI_TIMEOUT, kratos.local.json (python, kratos keys), Install Kratos from PyPI (KratosGeoMechanicsApplication), Run folder (~/KratosGUI/runs, never overwritten), Build Kratos from source (macOS or unreleased versions) (+6 more)

### Community 164 - "results-render.js"
Cohesion: 0.23
Nodes (11): clamp01(), colors(), deform(), format(), legend(), lookup(), position(), ramp() (+3 more)

### Community 165 - "init()"
Cohesion: 0.17
Nodes (14): applyRadiusLimits(), buildTriad(), cameraAngles(), clampAngles(), effectiveNavMode(), forcePanIfNeeded(), init(), makeRenderer() (+6 more)

### Community 166 - "test-import-dialogs.js"
Cohesion: 0.17
Nodes (8): with_(), choose(), drop(), files(), ok(), rig(), ctx, wrap()

### Community 167 - "test_custom_part_routes.py"
Cohesion: 0.25
Nodes (11): _box(), client(), _layers_patch_still_works(), _phase_naming(), test_a_part_freed_from_its_phases_can_then_be_deleted(), test_a_recipe_that_cannot_be_built_is_refused_with_its_reason(), test_clearing_custom_parts_a_phase_names_is_refused_naming_the_phase(), test_clearing_custom_parts_drops_their_mesh_sizes_only() (+3 more)

### Community 168 - "test_conftest_tiers.py"
Cohesion: 0.22
Nodes (11): run(), session(), test_a_browser_test_runs_by_default_when_playwright_is_there(), test_a_test_in_the_e2e_folder_is_e2e_without_saying_so(), test_a_tier_is_skipped_without_its_flag(), test_a_tier_runs_with_its_flag(), test_an_unmarked_test_always_runs(), test_running_the_benchmarks_also_runs_the_kratos_tests() (+3 more)

### Community 169 - "write_deck()"
Cohesion: 0.14
Nodes (8): write_deck(), write_text(), test_a_written_deck_can_be_read_back_by_this_project(), test_the_deck_lands_on_disk_as_the_bytes_it_was_rendered_as(), test_the_mdpa_is_named_exactly_what_the_parameters_ask_kratos_for(), test_the_three_input_files_are_written_under_the_deck_name(), test_write_text_keeps_crlf_line_endings(), test_the_deck_writes_its_system_beside_itself()

### Community 170 - "linearise()"
Cohesion: 0.14
Nodes (8): linearise(), PhaseError, build(), _project(), test_a_branch_cannot_be_linearised(), test_a_chain_runs_root_first(), test_a_fifty_phase_chain_runs_in_tree_order_however_it_is_listed(), test_an_unphased_project_runs_no_stages()

### Community 172 - "canvas-renderer.js"
Cohesion: 0.27
Nodes (7): CanvasRenderer(), colorOf(), positionsOf(), segmentJob(), shade(), toScreen(), triangleJob()

### Community 173 - "draw-input.js"
Cohesion: 0.36
Nodes (13): cancel(), commit(), finish(), getIntersection(), handleCommand(), init(), onClick(), onContextMenu() (+5 more)

### Community 174 - "test_main.py"
Cohesion: 0.14
Nodes (3): test_every_id_a_command_takes_says_what_it_is(), bare(), test_it_runs_as_a_module_from_any_folder()

### Community 175 - "test_phases.py"
Cohesion: 0.24
Nodes (9): _ids(), test_a_phase_tree_that_is_not_a_tree_is_refused_by_name(), test_add_puts_a_blank_phase_at_the_end_of_the_sequence(), test_an_edit_of_a_phase_that_is_not_there_changes_nothing(), test_copy_repeats_the_solver_settings_but_not_the_parts(), test_insert_puts_a_phase_between_a_phase_and_its_parent(), _test_model(), test_remove_heals_the_chain() (+1 more)

### Community 176 - "_with_interfaces()"
Cohesion: 0.22
Nodes (11): _interface(), test_a_free_interface_must_detach_one_side(), test_a_free_interface_needs_a_usable_polyline(), test_an_interface_becomes_a_part_key_so_the_frontend_can_pick_it(), test_an_interface_follows_a_structure_or_its_own_points_but_never_both(), test_an_interface_must_follow_a_sheet_pile_the_project_has(), test_an_interface_must_name_a_section_the_project_has(), test_duplicate_interface_ids_are_rejected() (+3 more)

### Community 177 - "enabled()"
Cohesion: 0.20
Nodes (6): Parser, enabled(), _reads_escape_codes(), Terminal, test_a_dumb_terminal_gets_no_colour(), test_no_color_takes_it_away_even_at_a_terminal()

### Community 178 - "make_results_field_fixture.py"
Cohesion: 0.26
Nodes (8): compact_json(), main(), record(), field(), render(), round_all(), stress(), u()

### Community 179 - "WaterUpdate"
Cohesion: 0.27
Nodes (7): WaterUpdate, set_water(), set_water_level(), test_a_water_level_keeps_the_rest_of_an_existing_one(), test_a_water_level_outside_the_model_is_refused(), test_an_edit_never_changes_the_project_it_was_given(), test_water_is_set_and_removed()

### Community 180 - "deck.js"
Cohesion: 0.22
Nodes (6): Existing Kratos deck (external_deck), Ways into the model (GUI, command box, run script, existing deck, import mesh, export, kratos-cli), integer(), label(), parts(), summary()

### Community 181 - "Security Policy"
Cohesion: 0.31
Nodes (9): Use Styx from another computer (--host, KRATOS_GUI_ALLOWED_HOSTS), SECURITY.md (Security policy), Host header check against DNS rebinding, In-scope vulnerabilities (imported files, Host/Origin bypass, vulnerable packages), Default bind to 127.0.0.1, Origin check (refuse requests from pages not served by Styx), Out-of-scope issues (own scripts, --host exposure, Kratos/Gmsh bugs), Private vulnerability reporting (+1 more)

### Community 182 - "test-patches-results.js"
Cohesion: 0.25
Nodes (6): answer(), done(), field(), plot(), rig(), ctx

### Community 183 - "test-results.js"
Cohesion: 0.25
Nodes (6): FIELD(), lines(), said(), setup(), showing(), viewing()

### Community 184 - "padded()"
Cohesion: 0.18
Nodes (7): padded(), test_a_load_buried_in_the_embankment_still_gets_no_counterpart(), test_a_load_on_the_visible_top_of_a_drawn_layer_translates(), test_a_surface_load_with_no_elevation_still_means_the_top_of_the_model(), test_the_elevation_survives_the_round_trip(), test_the_pad_is_placed_on_the_face_not_on_the_padded_ground(), test_the_surface_load_carries_the_elevation_it_was_translated_from()

### Community 185 - "test_event_loop.py"
Cohesion: 0.36
Nodes (5): _offloads(), _routes(), test_every_async_route_is_cheap_or_hands_its_work_off(), test_the_cheap_list_names_only_routes_that_exist(), test_the_route_table_was_found()

### Community 186 - "_auxiliary()"
Cohesion: 0.20
Nodes (5): _apply_final_stresses(), _auxiliary(), _extrapolate_to_nodes(), _find_neighbours_of_interfaces(), _k0_procedure()

### Community 187 - "staged_excavation_phases()"
Cohesion: 0.20
Nodes (7): _ordinal(), staged_excavation_phases(), add(), test_an_anchor_is_installed_after_the_lift_that_exposes_it(), test_more_than_ten_lifts_are_still_named(), test_staged_excavation_phases_reset_displacements_when_the_wall_goes_in(), test_the_first_staged_phase_is_the_only_k0_one()

### Community 188 - "GUI Usage Doc"
Cohesion: 0.33
Nodes (10): results commands (runs, show, fields, field, at, members, profile, get, archive), Output requested from Kratos (GiD .post.res/.post.msh, wall forces, interface tractions), USAGE.md (Use the GUI), Flow conditions mode (global water level), Mesh mode (Mesh properties window), GUI modes (Soil, Structures, Mesh, Flow conditions, Staged construction, Results), Results mode (contours, wall plots, node values, CSV/SVG/ZIP), Staged construction mode (Phases explorer) (+2 more)

### Community 189 - "syntax_check.py"
Cohesion: 0.27
Nodes (4): brackets(), main(), parsed(), scan()

### Community 190 - "mdpa-import-dialog.js"
Cohesion: 0.38
Nodes (9): checklistRow(), closeChecklist(), footer(), open(), close(), escape(), handleFile(), summarize() (+1 more)

### Community 191 - "apply()"
Cohesion: 0.22
Nodes (10): apply(), extentOf(), high(), low(), fromProject(), loadsFor(), projectTitle(), structuresFor() (+2 more)

### Community 192 - "copy()"
Cohesion: 0.24
Nodes (10): addSoilBodySection(), persistStack(), refreshBodies(), save(), copy(), discard(), restoreLayers(), restoreSoil() (+2 more)

### Community 193 - "test_mdpa_property.py"
Cohesion: 0.31
Nodes (4): decks(), test_a_random_deck_reads_back_as_written(), test_crlf_and_lf_decks_read_the_same(), write()

### Community 194 - "geometryRows()"
Cohesion: 0.22
Nodes (9): customPartProps(), domainEditor(), finiteOnly(), geometryRows(), layerProps(), outOfPlaneAxis(), partMaterialEditor(), recipeExtent() (+1 more)

### Community 195 - "renameObject()"
Cohesion: 0.39
Nodes (9): anchorByKey(), beamByKey(), interfaceByKey(), loadByKey(), normalLoadByKey(), objectName(), partByKey(), renameObject() (+1 more)

### Community 196 - "syncDimensionAvailability()"
Cohesion: 0.31
Nodes (9): applyRulers(), gateRail(), menuItemsFor(), nameStructureActions(), rulersOn(), setToolbarDisabled(), syncDimensionAvailability(), syncHistoryButtons() (+1 more)

### Community 197 - "syncModelMode()"
Cohesion: 0.28
Nodes (9): modeDef(), nameSoilBodyActions(), openOnDefaultMode(), gate(), patchFor(), sectionLabel(), setModelMode(), syncModelMode() (+1 more)

### Community 198 - "animate()"
Cohesion: 0.31
Nodes (9): animate(), fanOffsets(), labelsOn(), nodeUnderPointer(), paintNodeFans(), pickableNodes(), projectNode(), projectToScreen() (+1 more)

### Community 200 - "test_no_examples.py"
Cohesion: 0.36
Nodes (5): allowed(), offending_lines(), test_no_tracked_file_mentions_an_example_case(), test_no_tracked_path_names_an_example_case(), tracked_files()

### Community 201 - "Pipeline Diagram"
Cohesion: 0.43
Nodes (8): Model-to-results pipeline (10 steps), Pipeline swimlane diagram (Styx model to Kratos results), FE mesh (tri / tet), Read back (GiD + JSON), Solids (OCC booleans), Solve stage by stage (Kratos), Split + stage (interfaces, phases), Write deck (.mdpa + 2 JSON)

### Community 202 - "export.js"
Cohesion: 0.46
Nodes (7): baseName(), files(), integer(), log(), meshRequest(), run(), save()

### Community 203 - "syncTrees()"
Cohesion: 0.25
Nodes (7): containsNode(), orderTree(), setImportedParts(), soilNodes(), syncTrees(), topLevelUnion(), customGeometryNode()

### Community 204 - "test-dock.js"
Cohesion: 0.32
Nodes (3): dockFixture(), withDock(), withResultsDock()

### Community 205 - "test-download.js"
Cohesion: 0.29
Nodes (5): fakeFileHandle(), handle, withPickers(), withSaveStubs(), restore()

### Community 206 - "test-interfaces.js"
Cohesion: 0.39
Nodes (6): pile(), project(), rig(), ctx, section(), solid()

### Community 207 - "test-normal-loads.js"
Cohesion: 0.39
Nodes (6): project(), rig(), ctx, section(), solid(), specFor()

### Community 208 - "test-results-plot.js"
Cohesion: 0.32
Nodes (3): plotOf(), setup(), stage()

### Community 209 - "test-viewport-live.js"
Cohesion: 0.36
Nodes (4): boot(), sceneGroups(), standIns(), until()

### Community 211 - "parse_args()"
Cohesion: 0.33
Nodes (4): parse_args(), server_environment(), test_the_launcher_allows_the_host_it_was_told_to_listen_on(), test_the_launcher_listens_on_loopback_by_default()

### Community 212 - "make_viewport_fixture.py"
Cohesion: 0.38
Nodes (4): of_model(), main(), record(), render()

### Community 213 - "base/js/orbit.js"
Cohesion: 0.52
Nodes (5): down(), fire(), move(), up(), wheel()

### Community 215 - "calculate.js"
Cohesion: 0.57
Nodes (6): integer(), log(), report(), request(), results(), run()

### Community 216 - "download.js"
Cohesion: 0.48
Nodes (6): anchor(), extensionOf(), pickFile(), settle(), write(), writeHandle()

### Community 217 - "material-library.js"
Cohesion: 0.52
Nodes (6): addSoil(), applyInterface(), asMaterial(), copy(), dimension(), find()

### Community 218 - "frontend/js/orbit.js"
Cohesion: 0.52
Nodes (5): down(), fire(), move(), up(), wheel()

### Community 219 - "harness.js"
Cohesion: 0.38
Nodes (4): codeOf(), isolate(), restoreLeaks(), same()

### Community 220 - "test-draw-pointer.js"
Cohesion: 0.38
Nodes (3): rig(), ctx, onError()

### Community 221 - "test-patches-phases.js"
Cohesion: 0.38
Nodes (3): done(), rig(), ctx

### Community 223 - "test-water.js"
Cohesion: 0.38
Nodes (4): dryProject(), project(), row(), rows()

### Community 224 - "tests/conftest.py"
Cohesion: 0.38
Nodes (3): _enabled(), _in_e2e_folder(), pytest_collection_modifyitems()

### Community 227 - "command.js"
Cohesion: 0.73
Nodes (5): mount(), note(), ok(), run(), write()

### Community 228 - "build()"
Cohesion: 0.53
Nodes (5): build(), demoSubmenu(), mountBar(), open(), openAt()

### Community 229 - "anchorProps()"
Cohesion: 0.53
Nodes (6): anchorEndEditor(), anchorNumberEditor(), anchorProps(), spaceAnchorProps(), tendonNumberEditor(), tendonRows()

### Community 230 - "availableNow()"
Cohesion: 0.33
Nodes (6): availableIn2D(), availableIn3D(), availableNow(), in2D(), in3D(), setNavigation()

### Community 237 - "test_post_geometry_create_line_and_surface_stay_drawable()"
Cohesion: 0.33
Nodes (3): test_app_sources_are_never_cached(), test_frozen_assets_are_served(), test_post_geometry_create_line_and_surface_stay_drawable()

### Community 238 - "domains()"
Cohesion: 0.33
Nodes (4): domains(), test_the_domain_list_shrinks_as_the_pit_is_dug(), test_the_initial_stage_holds_only_soil(), test_the_wall_joins_the_domain_list_when_it_is_installed()

### Community 239 - "set_excavation()"
Cohesion: 0.40
Nodes (3): set_excavation(), test_one_level_says_that_a_layered_model_digs_nothing(), test_the_excavation_is_dug_in_the_levels_given()

### Community 240 - "api.js"
Cohesion: 0.50
Nodes (3): create(), request(), messageFrom()

### Community 241 - "open()"
Cohesion: 0.60
Nodes (4): open(), close(), escape(), handleFile()

### Community 242 - "zip.js"
Cohesion: 0.70
Nodes (4): block(), crc32(), create(), stamp()

### Community 245 - "test-results-view.js"
Cohesion: 0.50
Nodes (3): payload(), section(), stage()

### Community 246 - "unresolved()"
Cohesion: 0.40
Nodes (3): resolves(), test_unresolved_finds_what_is_gone_and_leaves_what_is_there_alone(), unresolved()

### Community 252 - "test-mesh-labels.js"
Cohesion: 0.83
Nodes (3): flatProjector(), planOf(), points()

## Ambiguous Edges - Review These
- `Styx browser app page` → `FastAPI 0.143.0`  [AMBIGUOUS]
  frontend/index.html · relation: conceptually_related_to

## Knowledge Gaps
- **22 isolated node(s):** `CITATION.cff`, `CodeQL and dependency review (CODE_SECURITY variable)`, `Supported versions (main and next release only)`, `Output and exit codes (0 ok, 1 refused, 2 bad command line, --json)`, `core/model/migration.py (old kN projects converted on open)` (+17 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2258 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **71 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Project` connect `Loads and Computed Fields` to `model/phases.py`, `CLI Structure Drafts`, `API Contract Tests`, `Project Edit Updates`, `Mesh and Deck Jobs`, `CLI Edit Commands`, `Kratos Deck Export Tests`, `test_the_test_model_runs_as_a_script()`, `Kratos Deck Writer`, `Backend Shared Routing`, `Kratos Units Tests`, `Meshing and Calculation Routes`, `Session Edit Contract`, `Project Schema Models`, `translate()`, `MDPA Import`, `Kratos Interface Tests`, `2D Geometry Build`, `CLI Analysis Commands`, `load_translation.py`, `default_phases()`, `Gmsh Meshing`, `Legacy Project Migration`, `test_draft_parity.py`, `Solid Model Builder`, `project_with()`, `Structures Commands`, `Material Definitions`, `3D Geometry Build Tests`, `test_custom_part_routes.py`, `2D Meshing Tests`, `Deck Property Tests`, `linearise()`, `Display Tessellation`, `External Deck Opening`, `External Deck Model`, `3D Kratos Export`, `CLI Pipeline Commands`, `MDPA Deck Model`, `WaterUpdate`, `Old Record Detection`, `Project File IO`, `Model Script Loading`, `Ground Commands`, `Gmsh Session and 3D Build`, `staged_excavation_phases()`, `padded()`, `model/__init__.py`, `test_tessellate.py`, `Panel`, `test_section_structures_3d.py`, `test_water_level.py`, `volumes.py`, `test_export_golden.py`, `geometry/__init__.py`, `test_app_wiring.py`, `test_script_writer.py`, `test_load_translation.py`, `test_wall_translation.py`, `test_kratos_solver.py`, `CommandError`, `announcing()`, `commands/project.py`, `set_excavation()`, `commands/phases.py`, `_project()`, `cli/conftest.py`, `script_writer.py`, `test_feature_matrix.py`, `scripting.py`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Are the 316 inferred relationships involving `Project` (e.g. with `check_mesh_keys()` and `not_for_a_deck()`) actually correct?**
  _`Project` has 316 INFERRED edges - model-reasoned connections that need verification._
- **What connects `CITATION.cff`, `CodeQL and dependency review (CODE_SECURITY variable)`, `Supported versions (main and next release only)` to the rest of the system?**
  _22 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `API Contract Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.016198413765291034 - nodes in this community are weakly interconnected._
- **Why does `App script load order` connect `Testing Doc and CI` to `frontend/js/orbit.js`, `results-render.js`, `patches.js`, `viewport.js`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `MeshRequest` (e.g. with `check_mesh_keys()` and `generate_mesh()`) actually correct?**
  _`MeshRequest` has 36 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Styx browser app page` and `FastAPI 0.143.0`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._