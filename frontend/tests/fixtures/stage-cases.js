/* Generated fixture -- the one document both implementations of `active_parts` are
   held to. Milestone D asks for the stage tree to be resolved in the browser as well
   as on the server (plan sec D), and two implementations of one rule drift unless
   something says they agree. This is that something.

   A .js file assigning a global rather than a .json file, because the browser suite
   runs from `file://` and a fetch there is blocked; Python reads the same file and
   strips this one assignment off the front. One document, two readers -- see
   `tests/test_stage_parity.py`, which regenerates and compares it.

   Not hand-edited. `python tests/test_stage_parity.py --write` rebuilds it.
*/
window.STAGE_FIXTURE =
{
  "edits": [
    {
      "call": "added",
      "args": [],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        },
        {
          "id": "stage_8",
          "name": "Stage 8",
          "parent": "settle",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        }
      ]
    },
    {
      "call": "inserted",
      "args": [
        "dig_1"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "stage_8",
          "name": "New stage",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "stage_8",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "inserted",
      "args": [
        "initial"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "removed",
      "args": [
        "prop"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "removed",
      "args": [
        "initial"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "copied",
      "args": [
        "build_wall"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "stage_8",
          "name": "Wall installation (copy)",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "stage_8",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "copied",
      "args": [
        "settle"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        },
        {
          "id": "stage_8",
          "name": "Consolidate (copy)",
          "parent": "settle",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "dig_1",
        [
          "wall"
        ],
        false
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside",
            "wall"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie",
            "wall"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "prop",
        [
          "soil_L1",
          "anchors"
        ],
        false
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [
            "soil_L1",
            "anchors"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside",
            "soil_L1",
            "anchors"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "settle",
        [
          "soil_L1__lift1"
        ],
        true
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "build_wall",
        [
          "wall"
        ],
        false
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [
            "wall"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1",
            "wall"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "null_step",
        [
          "soil_L1__lift1"
        ],
        true
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setActive",
      "args": [
        "prop",
        [
          "soil_L1"
        ],
        true
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "initial",
        "calculation",
        "flow"
      ],
      "result": [
        {
          "id": "initial",
          "name": "Initial stage",
          "parent": null,
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "null_step",
          "name": "Null step",
          "parent": "initial",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-08,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "flow",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "water_pressure_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "dig_1",
        "calculation",
        "flow"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "initial",
        "stress_initialisation",
        "gravity"
      ],
      "result": [
        {
          "id": "initial",
          "name": "Initial stage",
          "parent": null,
          "calculation": "mechanical",
          "stress_initialisation": "gravity",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "dig_1",
        "stress_initialisation",
        "K0"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "dig_1",
        "time_integration",
        "dynamic"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "dynamic",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "dig_1",
        "convergence_criterion",
        "displacement_criterion"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-12,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {}
        },
        {
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "settle",
        "convergence_criterion",
        "residual_criterion"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "edited",
      "args": [
        "prop",
        "name",
        "Props"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Props",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "editedSolver",
      "args": [
        "dig_1",
        "strategy_type",
        "line_search"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "residual_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-09,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "line_search"
          }
        },
        {
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "editedSolver",
      "args": [
        "settle",
        "linear_solver_type",
        "bicgstab"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "bicgstab"
          }
        }
      ]
    },
    {
      "call": "editedSolver",
      "args": [
        "settle",
        "strategy_type",
        null
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setPhreaticLine",
      "args": [
        "null_step",
        "low"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": "high",
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setPhreaticLine",
      "args": [
        "dig_1",
        null
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": "low",
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setSoilWater",
      "args": [
        "build_wall",
        "soil_L1",
        "dry"
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L1": "dry"
          },
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {
            "soil_L1": ""
          },
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setSoilWater",
      "args": [
        "prop",
        "soil_L2",
        null
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setValues",
      "args": [
        "build_wall",
        "clay",
        {
          "value": -15.0
        }
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {
            "clay": {
              "value": -15.0
            }
          },
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {
            "clay": {
              "value": -10.0
            }
          },
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    },
    {
      "call": "setValues",
      "args": [
        "dig_2",
        "clay",
        null
      ],
      "result": [
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
            "pile",
            "tie",
            "load",
            "soil_L1__lift1",
            "soil_L1__lift2",
            "soil_L1__lift3"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
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
          "id": "build_wall",
          "name": "Wall installation",
          "parent": "null_step",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "pile",
            "load"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {},
          "reset_displacements": true,
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
          "id": "dig_1",
          "name": "Dig to -2.0 m",
          "parent": "build_wall",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift1"
          ],
          "deactivate": [
            "soil_L1__outside"
          ],
          "phreatic_line": "low",
          "soil_water": {},
          "condition_values": {},
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
          "id": "prop",
          "name": "Strut installation",
          "parent": "dig_1",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "tie"
          ],
          "deactivate": [],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": "dry"
          },
          "condition_values": {},
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
          "id": "dig_2",
          "name": "Dig to -5.0 m",
          "parent": "prop",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [
            "soil_L1__lift2",
            "soil_L1__outside"
          ],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {
            "soil_L2": ""
          },
          "condition_values": {},
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
          "id": "settle",
          "name": "Consolidate",
          "parent": "dig_2",
          "calculation": "mechanical",
          "stress_initialisation": "none",
          "time_integration": "static",
          "loading": "Staged construction",
          "activate": [],
          "deactivate": [
            "soil_L1__lift1"
          ],
          "phreatic_line": null,
          "soil_water": {},
          "condition_values": {
            "clay": {
              "value": -25.0
            }
          },
          "reset_displacements": false,
          "convergence_criterion": "displacement_criterion",
          "max_iterations": 15,
          "tolerated_error": 0.0001,
          "absolute_tolerance": 1e-06,
          "start_time": 0.0,
          "duration": 1.0,
          "time_step": 1.0,
          "solver_settings": {
            "strategy_type": "newton_raphson",
            "linear_solver_type": "amgcl"
          }
        }
      ]
    }
  ],
  "project": {
    "name": "Deep excavation \u2014 Rotterdam Zuid",
    "layered_soil": true,
    "dimension": 3,
    "unit_system": "SI",
    "section_offset": null,
    "domain": {
      "x0": 0.0,
      "x1": 25.0,
      "z0": 0.0,
      "z1": 25.0,
      "y_top": 0.0,
      "y_bottom": -60.0
    },
    "materials": [
      {
        "constitutive_law": "GeoIncrementalLinearElastic3DLaw",
        "variables": {
          "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
          "YOUNG_MODULUS": 15000000.0,
          "POISSON_RATIO": 0.3,
          "DENSITY_SOLID": 1732.9255861365953,
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
          "POROSITY": 0.3,
          "BULK_MODULUS_SOLID": 10000000000.0,
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
        "top": 0.0,
        "bottom": -8.0
      },
      {
        "id": "L2",
        "name": "Soil_2",
        "mat": "m1",
        "top": -8.0,
        "bottom": -12.0
      },
      {
        "id": "L3",
        "name": "Soil_3",
        "mat": "m2",
        "top": -12.0,
        "bottom": -60.0
      }
    ],
    "lines": [
      {
        "id": "pit_side",
        "name": "Pit side",
        "points": [
          [
            5.0,
            0.0
          ],
          [
            5.0,
            -60.0
          ]
        ]
      },
      {
        "id": "pit_level_1",
        "name": "Pit level 1",
        "points": [
          [
            0.0,
            -2.0
          ],
          [
            5.0,
            -2.0
          ]
        ]
      },
      {
        "id": "pit_level_2",
        "name": "Pit level 2",
        "points": [
          [
            0.0,
            -5.0
          ],
          [
            5.0,
            -5.0
          ]
        ]
      }
    ],
    "bodies": [
      {
        "id": "lift1",
        "name": "lift 1",
        "layer": "L1",
        "point": [
          2.5,
          -1.0
        ],
        "mat": "m1"
      },
      {
        "id": "outside",
        "name": "outside the pit",
        "layer": "L1",
        "point": [
          15.0,
          -4.0
        ],
        "mat": "m1"
      },
      {
        "id": "lift2",
        "name": "lift 2",
        "layer": "L1",
        "point": [
          2.5,
          -3.5
        ],
        "mat": "m1"
      },
      {
        "id": "lift3",
        "name": "lift 3",
        "layer": "L1",
        "point": [
          2.5,
          -6.5
        ],
        "mat": "m1"
      },
      {
        "id": "pit",
        "name": "below the pit",
        "layer": "L2",
        "point": [
          2.5,
          -10.0
        ],
        "mat": "m1"
      },
      {
        "id": "outside",
        "name": "outside the pit",
        "layer": "L2",
        "point": [
          15.0,
          -10.0
        ],
        "mat": "m1"
      },
      {
        "id": "pit",
        "name": "below the pit",
        "layer": "L3",
        "point": [
          2.5,
          -36.0
        ],
        "mat": "m2"
      },
      {
        "id": "outside",
        "name": "outside the pit",
        "layer": "L3",
        "point": [
          15.0,
          -36.0
        ],
        "mat": "m2"
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
        "variables": {},
        "tables": {},
        "id": "s",
        "name": "S",
        "spacing": 1.0
      }
    ],
    "panel_sections": [],
    "beams": [
      {
        "id": "pile",
        "name": "Pile",
        "kind": "beam",
        "section": "s",
        "points": [
          [
            5.0,
            0.0
          ],
          [
            5.0,
            -13.0
          ]
        ],
        "active": true,
        "derived_from": null
      }
    ],
    "anchor_sections": [
      {
        "constitutive_law": "TrussConstitutiveLaw",
        "variables": {},
        "tables": {},
        "id": "t",
        "name": "T",
        "spacing": 2.5,
        "tension_limit": null,
        "compression_limit": null
      }
    ],
    "anchors": [
      {
        "id": "tie",
        "name": "Tie",
        "kind": "anchor",
        "section": "t",
        "head": [
          5.0,
          -1.0
        ],
        "tail": [
          3.0,
          -1.0
        ],
        "prestress": 0.0,
        "head_end": "free",
        "tail_end": "fixed",
        "active": true
      }
    ],
    "interface_sections": [],
    "interfaces": [],
    "interface_sides": "screen",
    "drawn_phreatic_lines": "whole_soil",
    "normal_loads": [],
    "water": {
      "y": -1.5,
      "margin": 3.0,
      "thickness": 0.06
    },
    "fluid": {
      "specific_weight": null,
      "bulk_modulus": null,
      "dynamic_viscosity": null
    },
    "soil_water": {
      "soil_L3": "low"
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
      },
      {
        "id": "high",
        "name": "High",
        "kind": "water_pressure",
        "on": "domain",
        "face": null,
        "part": null,
        "points": null,
        "fluid_pressure_type": "Phreatic_Multi_Line",
        "is_fixed": true,
        "value": 0.0,
        "reference_coordinate": null,
        "x_coordinates": [
          -100.0,
          100.0
        ],
        "y_coordinates": [
          -1.0,
          -1.0
        ],
        "z_coordinates": null,
        "pressure_tension_cut_off": 0.0,
        "active": true
      },
      {
        "id": "low",
        "name": "Low",
        "kind": "water_pressure",
        "on": "domain",
        "face": null,
        "part": null,
        "points": null,
        "fluid_pressure_type": "Head_Line",
        "is_fixed": true,
        "value": 0.0,
        "reference_coordinate": null,
        "x_coordinates": [
          -100.0,
          100.0
        ],
        "y_coordinates": [
          -6.0,
          -6.0
        ],
        "z_coordinates": null,
        "pressure_tension_cut_off": 0.0,
        "active": true
      },
      {
        "id": "clay",
        "name": "Clay",
        "kind": "water_pressure",
        "on": "part",
        "face": null,
        "part": "soil_L2",
        "points": null,
        "fluid_pressure_type": "Uniform",
        "is_fixed": true,
        "value": -10.0,
        "reference_coordinate": null,
        "x_coordinates": null,
        "y_coordinates": null,
        "z_coordinates": null,
        "pressure_tension_cut_off": 0.0,
        "active": true
      }
    ],
    "gravity_acceleration": 9.81,
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
      "size_bands": {},
      "refinements": []
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
          "pile",
          "tie",
          "load",
          "soil_L1__lift1",
          "soil_L1__lift2",
          "soil_L1__lift3"
        ],
        "phreatic_line": null,
        "soil_water": {},
        "condition_values": {},
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
        "phreatic_line": null,
        "soil_water": {},
        "condition_values": {},
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
        "id": "build_wall",
        "name": "Wall installation",
        "parent": "null_step",
        "calculation": "mechanical",
        "stress_initialisation": "none",
        "time_integration": "static",
        "loading": "Staged construction",
        "activate": [
          "pile",
          "load"
        ],
        "deactivate": [],
        "phreatic_line": null,
        "soil_water": {},
        "condition_values": {},
        "reset_displacements": true,
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
        "id": "dig_1",
        "name": "Dig to -2.0 m",
        "parent": "build_wall",
        "calculation": "mechanical",
        "stress_initialisation": "none",
        "time_integration": "static",
        "loading": "Staged construction",
        "activate": [
          "soil_L1__lift1"
        ],
        "deactivate": [
          "soil_L1__outside"
        ],
        "phreatic_line": "low",
        "soil_water": {},
        "condition_values": {},
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
        "id": "prop",
        "name": "Strut installation",
        "parent": "dig_1",
        "calculation": "mechanical",
        "stress_initialisation": "none",
        "time_integration": "static",
        "loading": "Staged construction",
        "activate": [
          "tie"
        ],
        "deactivate": [],
        "phreatic_line": null,
        "soil_water": {
          "soil_L2": "dry"
        },
        "condition_values": {},
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
        "id": "dig_2",
        "name": "Dig to -5.0 m",
        "parent": "prop",
        "calculation": "mechanical",
        "stress_initialisation": "none",
        "time_integration": "static",
        "loading": "Staged construction",
        "activate": [
          "soil_L1__lift2",
          "soil_L1__outside"
        ],
        "deactivate": [
          "soil_L1__lift1"
        ],
        "phreatic_line": null,
        "soil_water": {
          "soil_L2": ""
        },
        "condition_values": {
          "clay": {
            "value": -25.0
          }
        },
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
        "id": "settle",
        "name": "Consolidate",
        "parent": "dig_2",
        "calculation": "mechanical",
        "stress_initialisation": "none",
        "time_integration": "static",
        "loading": "Staged construction",
        "activate": [],
        "deactivate": [
          "soil_L1__lift1"
        ],
        "phreatic_line": null,
        "soil_water": {},
        "condition_values": {},
        "reset_displacements": false,
        "convergence_criterion": "displacement_criterion",
        "max_iterations": 15,
        "tolerated_error": 0.0001,
        "absolute_tolerance": 1e-06,
        "start_time": 0.0,
        "duration": 1.0,
        "time_step": 1.0,
        "solver_settings": {
          "strategy_type": "newton_raphson",
          "linear_solver_type": "amgcl"
        }
      }
    ],
    "deck": null,
    "soil_body_keys": [
      "soil_L1__lift1",
      "soil_L1__outside",
      "soil_L1__lift2",
      "soil_L1__lift3",
      "soil_L2__pit",
      "soil_L2__outside",
      "soil_L3__pit",
      "soil_L3__outside"
    ],
    "soil_body_labels": {
      "soil_L1__lift1": "lift 1",
      "soil_L1__outside": "outside the pit",
      "soil_L1__lift2": "lift 2",
      "soil_L1__lift3": "lift 3",
      "soil_L2__pit": "below the pit",
      "soil_L2__outside": "outside the pit",
      "soil_L3__pit": "below the pit",
      "soil_L3__outside": "outside the pit"
    },
    "soil_body_materials": {
      "soil_L1__lift1": "m1",
      "soil_L1__outside": "m1",
      "soil_L1__lift2": "m1",
      "soil_L1__lift3": "m1",
      "soil_L2__pit": "m1",
      "soil_L2__outside": "m1",
      "soil_L3__pit": "m2",
      "soil_L3__outside": "m2"
    },
    "stageable_parts": [
      "soil_L1__lift1",
      "soil_L1__outside",
      "soil_L1__lift2",
      "soil_L1__lift3",
      "soil_L2__pit",
      "soil_L2__outside",
      "soil_L3__pit",
      "soil_L3__outside",
      "pile",
      "tie",
      "load",
      "fixed_bottom",
      "roller_left",
      "roller_right",
      "roller_front",
      "roller_back",
      "pore_pressure",
      "high",
      "low",
      "clay"
    ],
    "model_strategies": {}
  },
  "stageable_keys": [
    "soil_L1__lift1",
    "soil_L1__outside",
    "soil_L1__lift2",
    "soil_L1__lift3",
    "soil_L2__pit",
    "soil_L2__outside",
    "soil_L3__pit",
    "soil_L3__outside",
    "pile",
    "tie",
    "load",
    "fixed_bottom",
    "roller_left",
    "roller_right",
    "roller_front",
    "roller_back",
    "pore_pressure",
    "high",
    "low",
    "clay"
  ],
  "active_parts": {
    "initial": [
      "clay",
      "fixed_bottom",
      "high",
      "low",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__outside",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit"
    ],
    "null_step": [
      "clay",
      "fixed_bottom",
      "high",
      "low",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__outside",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit"
    ],
    "build_wall": [
      "clay",
      "fixed_bottom",
      "high",
      "load",
      "low",
      "pile",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__outside",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit"
    ],
    "dig_1": [
      "clay",
      "fixed_bottom",
      "high",
      "load",
      "low",
      "pile",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__lift1",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit"
    ],
    "prop": [
      "clay",
      "fixed_bottom",
      "high",
      "load",
      "low",
      "pile",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__lift1",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit",
      "tie"
    ],
    "dig_2": [
      "clay",
      "fixed_bottom",
      "high",
      "load",
      "low",
      "pile",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__lift2",
      "soil_L1__outside",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit",
      "tie"
    ],
    "settle": [
      "clay",
      "fixed_bottom",
      "high",
      "load",
      "low",
      "pile",
      "pore_pressure",
      "roller_back",
      "roller_front",
      "roller_left",
      "roller_right",
      "soil_L1__lift2",
      "soil_L1__outside",
      "soil_L2__outside",
      "soil_L2__pit",
      "soil_L3__outside",
      "soil_L3__pit",
      "tie"
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
  ],
  "water_in": {
    "as_built": {
      "phreatic": "high",
      "soil_water": {
        "soil_L3": "low"
      },
      "values": {}
    },
    "initial": {
      "phreatic": "high",
      "soil_water": {
        "soil_L3": "low"
      },
      "values": {}
    },
    "null_step": {
      "phreatic": "high",
      "soil_water": {
        "soil_L3": "low"
      },
      "values": {}
    },
    "build_wall": {
      "phreatic": "high",
      "soil_water": {
        "soil_L3": "low"
      },
      "values": {}
    },
    "dig_1": {
      "phreatic": "low",
      "soil_water": {},
      "values": {}
    },
    "prop": {
      "phreatic": "low",
      "soil_water": {
        "soil_L2": "dry"
      },
      "values": {}
    },
    "dig_2": {
      "phreatic": "low",
      "soil_water": {},
      "values": {
        "clay": {
          "value": -25.0
        }
      }
    },
    "settle": {
      "phreatic": "low",
      "soil_water": {},
      "values": {
        "clay": {
          "value": -25.0
        }
      }
    }
  }
};
