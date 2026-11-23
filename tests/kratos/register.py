"""The "unverified construct" register (plan/active/full-test-and-validation-plan.md sec 8.3).

Every construct the exporter writes on inference -- a class or law name, a process shape,
a parameter -- that a structural test cannot prove, with what closes it. A construct is
closed only by a Kratos run whose results a check would have failed on had the construct
been wrong; `evidence` names that check. `tests/test_unverified_register.py` holds the
codebase to this list: every comment in `core/` that defers to "the first real run" must
be covered by a row here.

Status: "closed" (a run proves it), "fixed" (a run found it wrong; corrected and now
proven), "open" (nothing has run it yet), "blocked" (a run shows it cannot work as is).
"""

REGISTER = [
    {"id": "R1", "where": "kratos/writer.py BEAMS (2, 8)", "what": "quadratic 2D beam class",
     "status": "closed", "evidence": "test_results_regression (a Kratos run of the staged "
     "test model); wall M/Q/N/ux validated outside this repository against Kratos' own "
     "reference results"},
    {"id": "R2", "where": "kratos/writer.py BEAMS (2, 1)", "what": "linear 2D beam class",
     "status": "fixed", "evidence": "registry check; test_live_constructs first-order pile "
     "within 15 % of second order (was LinearTimoshenkoCurvedBeamElement2D2N: not in Kratos)"},
    {"id": "R3", "where": "kratos/writer.py BEAMS (3, *)", "what": "3D member classes",
     "status": "open", "evidence": "registry check only (3D 3-node fixed to the curved class); "
     "no 3D model with a member has run"},
    {"id": "R4", "where": "kratos/writer.py SHELLS / kratos/materials.PANEL_LAW",
     "what": "3D wall shells and their law",
     "status": "closed", "evidence": "test_3d_excavation_runs_every_stage_without_its_"
     "surcharge (the panel is active from stage 3); values not yet compared (M8 BM-2D3D-01)"},
    {"id": "R5", "where": "kratos/writer.py INTERFACES (2, 3) / kratos/materials.INTERFACE_LAW",
     "what": "quadratic interface class, law and stiffness variables",
     "status": "closed", "evidence": "test_results_regression (contacts on both faces); "
     "wall curves validated outside this repository against Kratos' own reference results"},
    {"id": "R6", "where": "kratos/writer.py INTERFACES (2, 2)", "what": "linear interface class",
     "status": "blocked", "evidence": "not registered in Kratos; no linear U-Pw line "
     "interface exists (test_kratos_registry KNOWN_MISSING)"},
    {"id": "R7", "where": "kratos/materials.BEAM_LAW", "what": "beam law and variables",
     "status": "closed", "evidence": "test_results_regression; wall curves "
     "validated outside this repository against Kratos' own reference results"},
    {"id": "R8", "where": "kratos/materials.ANCHOR_LAW", "what": "truss law; prestress",
     "status": "closed", "evidence": "test_results_regression stages 5-7 with the strut; "
     "TRUSS_PRESTRESS_PK2 still open -- no strut run so far is prestressed"},
    {"id": "R9", "where": "kratos/parameters._master_slave_constraint",
     "what": "master/slave tie before installation",
     "status": "closed", "evidence": "test_results_regression stages 1-2 and on; wall "
     "agreement validated outside this repository against Kratos' own reference results"},
    {"id": "R10", "where": "kratos/parameters._normal_load Uniform",
     "what": "uniform normal-load process shape",
     "status": "closed", "evidence": "test_live_constructs: +50 kPa at depth, both orders, "
     "both drawing directions"},
    {"id": "R11", "where": "kratos/writer.py NORMAL_LOAD_CONDITIONS (2, 2)",
     "what": "linear normal-load condition",
     "status": "fixed", "evidence": "was LineNormalLoadCondition2D2N (not in Kratos); "
     "UPwNormalFaceLoadCondition2D2N proven by the order-1 uniform load run"},
    {"id": "R12", "where": "kratos/materials.LINEAR_ELASTIC 3D", "what": "3D soil law",
     "status": "fixed", "evidence": "was GeoLinearElastic3DLaw (not in Kratos); "
     "test_the_3d_seed_with_its_surface_load_runs_and_settles"},
    {"id": "R13", "where": "kratos/writer.py CONDITIONS (3, *)", "what": "3D surface-load faces",
     "status": "fixed", "evidence": "were reversed against their tetrahedra; deck rule 13 "
     "and the 3D seed run. With a strut or beam active in the same stage: blocked "
     "(Kratos neighbour search; test_3d_excavation_with_its_surcharge_runs_every_stage xfail)"},
    {"id": "R14", "where": "tests/models/excavation.py MOHR_COULOMB / COULOMB_CONTACT",
     "what": "Mohr-Coulomb soil and Coulomb contact laws, typed with the reference's variables",
     "status": "closed", "evidence": "test_kratos_registry (the laws are registered); wall "
     "M, Q, N, u_x within Kratos' 2 % at every node, validated outside this repository "
     "against Kratos' own reference results"},
    {"id": "R15", "where": "kratos/materials.material_parameters(k0=True)",
     "what": "the K0 stage runs elastic whatever the law",
     "status": "closed", "evidence": "validated outside this repository against Kratos' own "
     "reference results, whose stage 1 reads the elastic common/initial_materials.json"},
    {"id": "R16", "where": "core.model.units / the whole deck",
     "what": "Kratos is unit-agnostic: a deck in kN, m, t, s",
     "status": "closed", "evidence": "test_live_units: the test model in SI and in kN "
     "agree x1000 at every node and Gauss point"},
    {"id": "R17", "where": "kratos/parameters._normal_flux / writer.FLUX_CONDITIONS",
     "what": "prescribed flux: the PwNormalFlux / UPwNormalFlux conditions, NORMAL_FLUID_FLUX "
     "set by the scalar process, and its sign (FLUX_INTO_SOIL)",
     "status": "open", "evidence": "the condition names and their nodal NORMAL_FLUID_FLUX "
     "read are Kratos master's source; test_live_flux (written, not yet run) holds the "
     "process and that a positive user flux puts water in"},
    {"id": "K1", "where": "solver settings newmark_*", "what": "Kratos defaults used",
     "status": "closed", "evidence": "wall curves validated outside this repository "
     "against Kratos' own reference results, without them"},
    {"id": "K2", "where": "gid_output output_interval", "what": "GiD writes every sub-step",
     "status": "closed", "evidence": "core.results.gid_reader takes the last step (finding F6, "
     "test_results_round_trip)"},
    {"id": "K3", "where": "kratos/prestress_workaround.py",
     "what": "TEMPORARY: a prestressed anchor's stress carried without its prestress",
     "status": "fixed", "evidence": "test_live_prestress: null stages after a prestressed "
     "strut moved 0.28 mm each without it and do not move with it. The canary "
     "test_kratos_still_counts_the_prestress_twice fails once Kratos is fixed, and the "
     "workaround then goes"},
]

COVERED_FILES = {"kratos/writer.py", "kratos/materials.py", "kratos/parameters.py"}
"""Files whose deferred-to-a-run comments the register is held against, relative to
`core/`."""
