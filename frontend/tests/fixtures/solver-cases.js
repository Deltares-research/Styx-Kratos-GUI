/* Generated fixture -- what `core.model.solver.resolve` gives for a set of stages,
   which App.Stages.resolveSolver is held to (frontend/tests/test-stages.js).

   Not hand-edited. `python tests/test_solver_parity.py --write` rebuilds it.
*/
window.SOLVER_FIXTURE =
{
  "cases": [
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "line_search",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_line_search_iterations",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "first_alpha_value",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "second_alpha_value",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_alpha",
          "value": 0.2,
          "default": 0.1,
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_alpha",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "line_search_tolerance",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "broyden",
          "default": "lbfgs",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 3,
          "default": 5,
          "overridden": true,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "static",
      "model_strategy": null,
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "line_search",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_line_search_iterations",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "first_alpha_value",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "second_alpha_value",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_alpha",
          "value": 0.2,
          "default": 0.1,
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_alpha",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "line_search_tolerance",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "broyden",
          "default": "lbfgs",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "quasi_newton",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 3,
          "default": 5,
          "overridden": true,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "backward_euler",
          "default": "newmark",
          "overridden": true,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": null,
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "quasi_newton",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "lbfgs",
          "default": "lbfgs",
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.01,
          "default": 0.0,
          "overridden": true,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "linear",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "line_search",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_line_search_iterations",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "first_alpha_value",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "second_alpha_value",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_alpha",
          "value": 0.2,
          "default": 0.1,
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_alpha",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "line_search_tolerance",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "broyden",
          "default": "lbfgs",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "linear",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "linear",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "linear",
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "linear",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "line_search",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_line_search_iterations",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "first_alpha_value",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "second_alpha_value",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_alpha",
          "value": 0.2,
          "default": 0.1,
          "overridden": true,
          "locked": null
        },
        {
          "key": "max_alpha",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "line_search_tolerance",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "linear",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "quasi_newton",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_type",
          "value": "broyden",
          "default": "lbfgs",
          "overridden": true,
          "locked": null
        },
        {
          "key": "quasi_newton_max_rank",
          "value": 10,
          "default": 10,
          "overridden": false,
          "locked": null
        },
        {
          "key": "quasi_newton_restart_interval",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 3,
          "default": 5,
          "overridden": true,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "backward_euler",
          "default": "newmark",
          "overridden": true,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson",
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson",
          "default": "newton_raphson",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 5,
          "default": 5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 3,
          "default": 6,
          "overridden": true,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "gmres",
          "default": "gmres",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "flow",
      "time_integration": "static",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "LinearSolversApplication.sparse_lu",
          "default": "LinearSolversApplication.sparse_lu",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 1.0,
          "default": 1.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {},
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "line_search",
        "min_alpha": 0.2
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "linear",
        "min_iterations": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 3,
          "default": 6,
          "overridden": true,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "quasi_newton",
        "quasi_newton_type": "broyden",
        "linear_solver_type": "amgcl"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "gmres",
          "default": "gmres",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "bicgstab",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "lgmres",
        "linear_solver_tolerance": 1e-08
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "amgcl",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-08,
          "default": 1e-06,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_krylov_type",
          "value": "lgmres",
          "default": "gmres",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_gmres_krylov_space_dimension",
          "value": 100,
          "default": 100,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_smoother_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_coarsening_type",
          "value": "aggregation",
          "default": "aggregation",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "bicgstab",
        "linear_solver_scaling": true
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "bicgstab",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "ilu0",
          "default": "ilu0",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "strategy_type": "newton_raphson",
        "linear_solver_type": "cg",
        "minimum_step_fraction": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "cg",
          "default": "skyline_lu_factorization",
          "overridden": true,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_tolerance",
          "value": 1e-06,
          "default": 1e-06,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_max_iteration",
          "value": 200,
          "default": 200,
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_preconditioner_type",
          "value": "diagonal",
          "default": "diagonal",
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.01,
          "default": 0.0001,
          "overridden": true,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "scheme_type": "backward_euler",
        "newmark_theta": 1.0,
        "number_cycles": 3
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "backward_euler",
          "default": "newmark",
          "overridden": true,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        }
      ]
    },
    {
      "calculation": "mechanical",
      "time_integration": "dynamic",
      "model_strategy": "newton_raphson_with_seepage",
      "overrides": {
        "move_mesh_flag": true,
        "rayleigh_k": 0.01
      },
      "rows": [
        {
          "key": "strategy_type",
          "value": "newton_raphson_with_seepage",
          "default": "newton_raphson_with_seepage",
          "overridden": false,
          "locked": "A seepage face needs it: it opens and closes the face node by node as it iterates."
        },
        {
          "key": "linear_solver_type",
          "value": "skyline_lu_factorization",
          "default": "skyline_lu_factorization",
          "overridden": false,
          "locked": null
        },
        {
          "key": "linear_solver_scaling",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "min_iterations",
          "value": 6,
          "default": 6,
          "overridden": false,
          "locked": null
        },
        {
          "key": "number_cycles",
          "value": 1,
          "default": 1,
          "overridden": false,
          "locked": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
        },
        {
          "key": "reduction_factor",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "minimum_step_fraction",
          "value": 0.0001,
          "default": 0.0001,
          "overridden": false,
          "locked": null
        },
        {
          "key": "increase_factor",
          "value": 2.0,
          "default": 2.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "max_delta_time_factor",
          "value": 1000.0,
          "default": 1000.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "scheme_type",
          "value": "newmark",
          "default": "newmark",
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_beta",
          "value": 0.25,
          "default": 0.25,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_gamma",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "newmark_theta",
          "value": 0.5,
          "default": 0.5,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_m",
          "value": 0.0,
          "default": 0.0,
          "overridden": false,
          "locked": null
        },
        {
          "key": "rayleigh_k",
          "value": 0.01,
          "default": 0.0,
          "overridden": true,
          "locked": null
        },
        {
          "key": "block_builder",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "reform_dofs_at_each_step",
          "value": false,
          "default": false,
          "overridden": false,
          "locked": null
        },
        {
          "key": "compute_reactions",
          "value": true,
          "default": true,
          "overridden": false,
          "locked": null
        },
        {
          "key": "move_mesh_flag",
          "value": true,
          "default": false,
          "overridden": true,
          "locked": null
        }
      ]
    }
  ]
};
