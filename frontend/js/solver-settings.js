/* Generated from core/model/solver.py -- the expert solver settings of a stage: what
   each one is, its default, and when it applies. The browser resolves them with
   App.Stages.solverRows, written the way `core.model.solver.resolve` is, and
   tests/test_solver_parity.py holds the two to the same answers. App.STAGE_SETTINGS
   is the convergence criteria of each calculation type, their absolute tolerances and
   the stage's other defaults (`solver.CRITERIA`, `ABSOLUTE_TOLERANCES`,
   `STAGE_DEFAULTS`).

   Not hand-edited. `python tests/test_solver_parity.py --write` rebuilds it.
*/
var App = window.App || {};
App.SOLVER_SETTINGS = [
  {
    "key": "strategy_type",
    "label": "Strategy",
    "group": "Strategy",
    "kind": "select",
    "default": [
      {
        "when": {
          "calculation": [
            "flow"
          ]
        },
        "from": "model_strategy"
      },
      {
        "value": "newton_raphson"
      }
    ],
    "options": [
      [
        "quasi_newton",
        "Quasi-Newton"
      ],
      [
        "newton_raphson",
        "Newton-Raphson"
      ],
      [
        "line_search",
        "Newton-Raphson with line search"
      ],
      [
        "linear",
        "Linear (one solve)"
      ]
    ],
    "locked": [
      {
        "when": {
          "model_strategy": [
            "newton_raphson_with_seepage"
          ]
        },
        "value": "newton_raphson_with_seepage",
        "label": "Newton-Raphson with seepage",
        "reason": "A seepage face needs it: it opens and closes the face node by node as it iterates."
      }
    ],
    "deck": "strategy_type",
    "help": "How each step's equations are solved. Quasi-Newton factorises the stiffness matrix once and updates its inverse from the residuals; Newton-Raphson rebuilds and factorises it every iteration."
  },
  {
    "key": "quasi_newton_type",
    "label": "Update",
    "group": "Strategy",
    "kind": "select",
    "default": [
      {
        "value": "lbfgs"
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton"
      ]
    },
    "options": [
      [
        "lbfgs",
        "L-BFGS"
      ],
      [
        "broyden",
        "Broyden"
      ]
    ],
    "deck": "quasi_newton_type",
    "help": "How the inverse of the stiffness matrix is updated between iterations."
  },
  {
    "key": "quasi_newton_max_rank",
    "label": "Stored updates",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 10
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton"
      ]
    },
    "deck": "quasi_newton_max_rank",
    "help": "How many updates are kept; the oldest is dropped beyond it.",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "quasi_newton_restart_interval",
    "label": "Restart interval",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 100
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton"
      ]
    },
    "deck": "quasi_newton_restart_interval",
    "help": "Rebuild and refactorise the stiffness matrix every this many iterations.",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "max_line_search_iterations",
    "label": "Line search iterations",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 5
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "max_line_search_iterations",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "first_alpha_value",
    "label": "First step length",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 0.5
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "first_alpha_value",
    "above": 0
  },
  {
    "key": "second_alpha_value",
    "label": "Second step length",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 1.0
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "second_alpha_value",
    "above": 0
  },
  {
    "key": "min_alpha",
    "label": "Smallest step length",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 0.1
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "min_alpha",
    "above": 0
  },
  {
    "key": "max_alpha",
    "label": "Largest step length",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 2.0
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "max_alpha",
    "above": 0
  },
  {
    "key": "line_search_tolerance",
    "label": "Line search tolerance",
    "group": "Strategy",
    "kind": "number",
    "default": [
      {
        "value": 0.5
      }
    ],
    "when": {
      "strategy_type": [
        "line_search"
      ]
    },
    "deck": "line_search_tolerance",
    "above": 0
  },
  {
    "key": "linear_solver_type",
    "label": "Linear solver",
    "group": "Linear solver",
    "kind": "select",
    "default": [
      {
        "value": "LinearSolversApplication.sparse_lu"
      }
    ],
    "options": [
      [
        "LinearSolversApplication.sparse_lu",
        "Sparse LU (direct)"
      ],
      [
        "skyline_lu_factorization",
        "Skyline LU (direct)"
      ],
      [
        "amgcl",
        "AMGCL (iterative)"
      ],
      [
        "bicgstab",
        "BiCGStab (iterative)"
      ],
      [
        "cg",
        "CG (iterative)"
      ]
    ],
    "locked": [
      {
        "when": {
          "strategy_type": [
            "quasi_newton"
          ]
        },
        "value": "LinearSolversApplication.sparse_lu",
        "reason": "The quasi-Newton strategy factorises the stiffness matrix once with Sparse LU and reuses it; it uses no other linear solver."
      }
    ],
    "deck": "linear_solver_settings.solver_type"
  },
  {
    "key": "linear_solver_scaling",
    "label": "Scaling",
    "group": "Linear solver",
    "kind": "check",
    "default": [
      {
        "when": {
          "linear_solver_type": [
            "amgcl",
            "bicgstab",
            "cg"
          ]
        },
        "value": false
      },
      {
        "value": true
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ]
    },
    "deck": "linear_solver_settings.scaling",
    "help": "Scale the system to a unit diagonal before solving it."
  },
  {
    "key": "linear_solver_tolerance",
    "label": "Tolerance",
    "group": "Linear solver",
    "kind": "number",
    "default": [
      {
        "value": 1e-06
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl",
        "bicgstab",
        "cg"
      ]
    },
    "deck": "linear_solver_settings.tolerance",
    "above": 0
  },
  {
    "key": "linear_solver_max_iteration",
    "label": "Max linear iterations",
    "group": "Linear solver",
    "kind": "number",
    "default": [
      {
        "when": {
          "linear_solver_type": [
            "amgcl"
          ]
        },
        "value": 100
      },
      {
        "value": 200
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl",
        "bicgstab",
        "cg"
      ]
    },
    "deck": "linear_solver_settings.max_iteration",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "linear_solver_preconditioner_type",
    "label": "Preconditioner",
    "group": "Linear solver",
    "kind": "select",
    "default": [
      {
        "when": {
          "linear_solver_type": [
            "cg"
          ]
        },
        "value": "diagonal"
      },
      {
        "value": "ilu0"
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "bicgstab",
        "cg"
      ]
    },
    "options": [
      [
        "ilu0",
        "ILU(0)"
      ],
      [
        "ilu",
        "ILU"
      ],
      [
        "diagonal",
        "Diagonal"
      ],
      [
        "none",
        "None"
      ]
    ],
    "deck": "linear_solver_settings.preconditioner_type",
    "help": "Kratos' default is none. ILU(0) is what makes BiCGStab converge on a stiffness matrix; CG takes the diagonal one, which keeps a symmetric system symmetric."
  },
  {
    "key": "linear_solver_krylov_type",
    "label": "Krylov method",
    "group": "Linear solver",
    "kind": "select",
    "default": [
      {
        "value": "gmres"
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl"
      ]
    },
    "options": [
      [
        "gmres",
        "GMRES"
      ],
      [
        "lgmres",
        "LGMRES"
      ],
      [
        "fgmres",
        "FGMRES"
      ],
      [
        "bicgstab",
        "BiCGStab"
      ],
      [
        "bicgstabl",
        "BiCGStab(L)"
      ],
      [
        "cg",
        "CG"
      ],
      [
        "idrs",
        "IDR(s)"
      ]
    ],
    "deck": "linear_solver_settings.krylov_type"
  },
  {
    "key": "linear_solver_gmres_krylov_space_dimension",
    "label": "Krylov space dimension",
    "group": "Linear solver",
    "kind": "number",
    "default": [
      {
        "value": 100
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl"
      ],
      "linear_solver_krylov_type": [
        "gmres",
        "lgmres",
        "fgmres"
      ]
    },
    "deck": "linear_solver_settings.gmres_krylov_space_dimension",
    "help": "Iterations between restarts of the GMRES method.",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "linear_solver_smoother_type",
    "label": "Smoother",
    "group": "Linear solver",
    "kind": "select",
    "default": [
      {
        "value": "ilu0"
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl"
      ]
    },
    "options": [
      [
        "ilu0",
        "ILU(0)"
      ],
      [
        "ilut",
        "ILUT"
      ],
      [
        "iluk",
        "ILU(k)"
      ],
      [
        "spai0",
        "SPAI-0"
      ],
      [
        "spai1",
        "SPAI-1"
      ],
      [
        "damped_jacobi",
        "Damped Jacobi"
      ],
      [
        "gauss_seidel",
        "Gauss-Seidel"
      ],
      [
        "chebyshev",
        "Chebyshev"
      ]
    ],
    "deck": "linear_solver_settings.smoother_type"
  },
  {
    "key": "linear_solver_coarsening_type",
    "label": "Coarsening",
    "group": "Linear solver",
    "kind": "select",
    "default": [
      {
        "value": "aggregation"
      }
    ],
    "when": {
      "strategy_type": [
        "newton_raphson",
        "line_search",
        "linear",
        "newton_raphson_with_seepage"
      ],
      "linear_solver_type": [
        "amgcl"
      ]
    },
    "options": [
      [
        "aggregation",
        "Aggregation"
      ],
      [
        "smoothed_aggregation",
        "Smoothed aggregation"
      ],
      [
        "smoothed_aggr_emin",
        "Smoothed aggregation (energy minimising)"
      ],
      [
        "ruge_stuben",
        "Ruge-Stuben"
      ]
    ],
    "deck": "linear_solver_settings.coarsening_type"
  },
  {
    "key": "min_iterations",
    "label": "Min iterations",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "value": 6
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton",
        "newton_raphson",
        "line_search",
        "newton_raphson_with_seepage"
      ]
    },
    "deck": "min_iterations",
    "help": "A step that converges in fewer iterations than this is followed by a larger one.",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "number_cycles",
    "label": "Attempts per step",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "value": 1
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton",
        "newton_raphson",
        "line_search",
        "newton_raphson_with_seepage"
      ]
    },
    "locked": [
      {
        "when": {
          "strategy_type": [
            "newton_raphson_with_seepage"
          ]
        },
        "value": 1,
        "reason": "Kratos' seepage strategy refuses more than one: it cannot undo the faces it opened before trying a step again."
      }
    ],
    "deck": "number_cycles",
    "help": "How often a step that does not converge is tried again with a smaller step before the stage stops.",
    "integer": true,
    "minimum": 1
  },
  {
    "key": "reduction_factor",
    "label": "Step reduction factor",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "when": {
          "calculation": [
            "flow"
          ]
        },
        "value": 1.0
      },
      {
        "value": 0.5
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton",
        "newton_raphson",
        "line_search",
        "newton_raphson_with_seepage"
      ]
    },
    "deck": "reduction_factor",
    "above": 0,
    "maximum": 1
  },
  {
    "key": "minimum_step_fraction",
    "label": "Smallest step (x duration)",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "value": 0.0001
      }
    ],
    "when": {
      "strategy_type": [
        "quasi_newton",
        "newton_raphson",
        "line_search",
        "newton_raphson_with_seepage"
      ]
    },
    "deck": "time_stepping.minimum_allowable_value",
    "help": "A step cut below this fraction of the stage's duration stops the stage (Kratos: 'The time step is too small'). Never more than the stage's own time step. Kratos' own default.",
    "above": 0,
    "maximum": 1
  },
  {
    "key": "increase_factor",
    "label": "Step increase factor",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "when": {
          "calculation": [
            "mechanical"
          ],
          "time_integration": [
            "dynamic"
          ]
        },
        "value": 1.0
      },
      {
        "when": {
          "calculation": [
            "flow"
          ],
          "strategy_type": [
            "quasi_newton",
            "newton_raphson",
            "line_search",
            "newton_raphson_with_seepage"
          ]
        },
        "value": 1.0
      },
      {
        "value": 2.0
      }
    ],
    "deck": "increase_factor",
    "minimum": 1
  },
  {
    "key": "max_delta_time_factor",
    "label": "Largest step (x time step)",
    "group": "Time step control",
    "kind": "number",
    "default": [
      {
        "value": 1000.0
      }
    ],
    "deck": "time_stepping.max_delta_time_factor",
    "help": "The largest a step grows to after steps that converged in few iterations, as a multiple of the stage's time step.",
    "minimum": 1
  },
  {
    "key": "scheme_type",
    "label": "Time scheme",
    "group": "Time integration",
    "kind": "select",
    "default": [
      {
        "value": "newmark"
      }
    ],
    "when": {
      "time_integration": [
        "dynamic"
      ]
    },
    "options": [
      [
        "newmark",
        "Newmark"
      ],
      [
        "backward_euler",
        "Backward Euler"
      ]
    ],
    "deck": "scheme_type",
    "help": "In a mechanical stage, Backward Euler integrates the water pressure in time without inertia: Kratos' quasi-static U-Pw, the only one it builds Backward Euler for (geomechanics_U_Pw_solver.py)."
  },
  {
    "key": "newmark_beta",
    "label": "Newmark beta",
    "group": "Time integration",
    "kind": "number",
    "default": [
      {
        "value": 0.25
      }
    ],
    "when": {
      "calculation": [
        "mechanical"
      ],
      "time_integration": [
        "dynamic"
      ],
      "scheme_type": [
        "newmark"
      ]
    },
    "deck": "newmark_beta",
    "above": 0
  },
  {
    "key": "newmark_gamma",
    "label": "Newmark gamma",
    "group": "Time integration",
    "kind": "number",
    "default": [
      {
        "value": 0.5
      }
    ],
    "when": {
      "calculation": [
        "mechanical"
      ],
      "time_integration": [
        "dynamic"
      ],
      "scheme_type": [
        "newmark"
      ]
    },
    "deck": "newmark_gamma",
    "above": 0
  },
  {
    "key": "newmark_theta",
    "label": "Newmark theta",
    "group": "Time integration",
    "kind": "number",
    "default": [
      {
        "value": 0.5
      }
    ],
    "when": {
      "time_integration": [
        "dynamic"
      ],
      "scheme_type": [
        "newmark"
      ]
    },
    "deck": "newmark_theta",
    "help": "For the water pressure.",
    "above": 0,
    "maximum": 1
  },
  {
    "key": "rayleigh_m",
    "label": "Rayleigh mass damping",
    "group": "Damping",
    "kind": "number",
    "default": [
      {
        "value": 0.0
      }
    ],
    "when": {
      "calculation": [
        "mechanical"
      ],
      "time_integration": [
        "dynamic"
      ],
      "scheme_type": [
        "newmark"
      ]
    },
    "deck": "rayleigh_m",
    "help": "Rayleigh's alpha: the damping proportional to the mass.",
    "panel": "stage",
    "minimum": 0
  },
  {
    "key": "rayleigh_k",
    "label": "Rayleigh stiffness damping",
    "group": "Damping",
    "kind": "number",
    "default": [
      {
        "value": 0.0
      }
    ],
    "when": {
      "calculation": [
        "mechanical"
      ],
      "time_integration": [
        "dynamic"
      ],
      "scheme_type": [
        "newmark"
      ]
    },
    "deck": "rayleigh_k",
    "help": "Rayleigh's beta: the damping proportional to the stiffness.",
    "panel": "stage",
    "minimum": 0
  },
  {
    "key": "block_builder",
    "label": "Block builder",
    "group": "Assembly",
    "kind": "check",
    "default": [
      {
        "value": true
      }
    ],
    "deck": "block_builder",
    "help": "Assemble the whole system and fix its constraints in place, rather than eliminating them."
  },
  {
    "key": "reform_dofs_at_each_step",
    "label": "Reform DOFs each step",
    "group": "Assembly",
    "kind": "check",
    "default": [
      {
        "when": {
          "calculation": [
            "flow"
          ]
        },
        "value": true
      },
      {
        "value": false
      }
    ],
    "deck": "reform_dofs_at_each_step"
  },
  {
    "key": "compute_reactions",
    "label": "Compute reactions",
    "group": "Assembly",
    "kind": "check",
    "default": [
      {
        "value": true
      }
    ],
    "deck": "compute_reactions"
  },
  {
    "key": "move_mesh_flag",
    "label": "Updated mesh",
    "group": "Assembly",
    "kind": "check",
    "default": [
      {
        "value": false
      }
    ],
    "when": {
      "calculation": [
        "mechanical"
      ]
    },
    "deck": "move_mesh_flag",
    "help": "Move the mesh with the displacements, so each step is solved on the deformed geometry."
  }
];
App.STAGE_SETTINGS = {
  "criteria": {
    "mechanical": [
      [
        "residual_criterion",
        "Residual"
      ],
      [
        "displacement_criterion",
        "Displacement"
      ]
    ],
    "flow": [
      [
        "water_pressure_criterion",
        "Water pressure"
      ],
      [
        "residual_criterion",
        "Residual"
      ]
    ]
  },
  "absolute_tolerances": {
    "residual_criterion": 1e-09,
    "displacement_criterion": 1e-12,
    "water_pressure_criterion": 1e-08
  },
  "defaults": {
    "max_iterations": 15,
    "tolerated_error": 0.0001,
    "duration": 1.0,
    "time_step": 1.0
  }
};
