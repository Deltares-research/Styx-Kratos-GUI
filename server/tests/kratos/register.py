"""The "unverified construct" register (plan/full-test-and-validation-plan.md sec 8.3).

Every construct the exporter writes on inference -- a class or law name, a process shape,
a parameter -- that a structural test cannot prove, with what closes it. A construct is
closed only by a Kratos run whose results a check would have failed on had the construct
been wrong; `evidence` names that check. `tests/test_unverified_register.py` holds the
codebase to this list: every comment in `app/` that defers to "the first real run" must
be covered by a row here.

Status: "closed" (a run proves it), "fixed" (a run found it wrong; corrected and now
proven), "open" (nothing has run it yet), "blocked" (a run shows it cannot work as is).
"""

REGISTER = [
    {"id": "R1", "where": "kratos.py BEAMS (2, 8)", "what": "quadratic 2D beam class",
     "status": "closed", "evidence": "test_live_crow wall M/Q/N/ux vs Kratos' CROW curves"},
    {"id": "R2", "where": "kratos.py BEAMS (2, 1)", "what": "linear 2D beam class",
     "status": "fixed", "evidence": "registry check; test_live_constructs first-order pile "
     "within 15 % of second order (was LinearTimoshenkoCurvedBeamElement2D2N: not in Kratos)"},
    {"id": "R3", "where": "kratos.py BEAMS (3, *)", "what": "3D member classes",
     "status": "open", "evidence": "registry check only (3D 3-node fixed to the curved class); "
     "no 3D model with a member has run"},
    {"id": "R4", "where": "kratos.py SHELLS / kratos_materials.PANEL_LAW",
     "what": "3D wall shells and their law",
     "status": "closed", "evidence": "test_3d_crow_runs_every_stage_without_its_surcharge "
     "(the panel is active from stage 3); values not yet compared (M8 BM-2D3D-01)"},
    {"id": "R5", "where": "kratos.py INTERFACES (2, 3) / kratos_materials.INTERFACE_LAW",
     "what": "quadratic interface class, law and stiffness variables",
     "status": "closed", "evidence": "test_live_crow wall curves (contacts on both faces)"},
    {"id": "R6", "where": "kratos.py INTERFACES (2, 2)", "what": "linear interface class",
     "status": "blocked", "evidence": "not registered in Kratos; no linear U-Pw line "
     "interface exists (test_kratos_registry KNOWN_MISSING)"},
    {"id": "R7", "where": "kratos_materials.BEAM_LAW", "what": "beam law and variables",
     "status": "closed", "evidence": "test_live_crow wall curves"},
    {"id": "R8", "where": "kratos_materials.ANCHOR_LAW", "what": "truss law; prestress",
     "status": "closed", "evidence": "test_live_crow stages 5-7 with the strut; "
     "TRUSS_PRESTRESS_PK2 still open -- CROW's strut is not prestressed"},
    {"id": "R9", "where": "kratos_processes._master_slave_constraint",
     "what": "master/slave tie before installation",
     "status": "closed", "evidence": "test_live_crow stages 1-2 followed by wall agreement"},
    {"id": "R10", "where": "kratos_processes._normal_load Uniform",
     "what": "uniform normal-load process shape",
     "status": "closed", "evidence": "test_live_constructs: +50 kPa at depth, both orders, "
     "both drawing directions"},
    {"id": "R11", "where": "kratos.py NORMAL_LOAD_CONDITIONS (2, 2)",
     "what": "linear normal-load condition",
     "status": "fixed", "evidence": "was LineNormalLoadCondition2D2N (not in Kratos); "
     "UPwNormalFaceLoadCondition2D2N proven by the order-1 uniform load run"},
    {"id": "R12", "where": "kratos_materials.LINEAR_ELASTIC 3D", "what": "3D soil law",
     "status": "fixed", "evidence": "was GeoLinearElastic3DLaw (not in Kratos); "
     "test_the_3d_seed_with_its_surface_load_runs_and_settles"},
    {"id": "R13", "where": "kratos.py CONDITIONS (3, *)", "what": "3D surface-load faces",
     "status": "fixed", "evidence": "were reversed against their tetrahedra; deck rule 13 "
     "and the 3D seed run. With a strut or beam active in the same stage: blocked "
     "(Kratos neighbour search; test_3d_crow_with_its_surcharge_runs_every_stage xfail)"},
    {"id": "R14", "where": "app.crow MOHR_COULOMB / COULOMB_CONTACT",
     "what": "Mohr-Coulomb soil and Coulomb contact laws, typed with the reference's variables",
     "status": "closed", "evidence": "test_live_crow_mc: wall M, Q, N, u_x within Kratos' 2 % "
     "of its own MC CROW curves at every node of stages 3/4/6/7"},
    {"id": "R15", "where": "kratos_materials.material_parameters(k0=True)",
     "what": "the K0 stage runs elastic whatever the law",
     "status": "closed", "evidence": "test_live_crow_mc (the reference's stage 1 reads the "
     "elastic common/initial_materials.json)"},
    {"id": "R16", "where": "app.units / the whole deck",
     "what": "Kratos is unit-agnostic: a deck in kN, m, t, s",
     "status": "closed", "evidence": "test_live_units: CROW in SI and in kN agree x1000 at "
     "every node and Gauss point"},
    {"id": "K1", "where": "solver settings newmark_*", "what": "Kratos defaults used",
     "status": "closed", "evidence": "test_live_crow agrees with the reference without them"},
    {"id": "K2", "where": "gid_output output_interval", "what": "GiD writes every sub-step",
     "status": "closed", "evidence": "gid_results takes the last step (finding F6, "
     "test_results_round_trip)"},
]

COVERED_FILES = {"kratos.py", "kratos_materials.py", "kratos_processes.py"}
"""Files whose deferred-to-a-run comments the register is held against."""
