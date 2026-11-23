# Styx examples

Each example is a ready-made model in its own folder: the project file, as the GUI's
**Save** and `kratos-cli new` write it, and the same model as a Python script. Open one in
the GUI, run it with `kratos-cli`, or copy it as the start of your own model.

| Example | What is in it | Tutorials |
|---|---|---|
| [Simple dike](simple_dike) | A soil block with a sheet pile and a line load on its surface, in three stages | [CLI](../docs/cli_tutorials/simple_dike.md) |
| [CROW excavation wall](CROW_case/README.md) | A staged sheet-pile excavation in clay and sand, with a strut, an interface, water loads and Mohr-Coulomb soils | [GUI](../docs/gui_tutorials/CROW_case.md), [CLI](../docs/cli_tutorials/CROW_case.md) |
| [Levee seepage](levee_seepage/README.md) | A steady-state groundwater flow under and through a clay levee, with a seepage face and Van Genuchten soils | [GUI](../docs/gui_tutorials/levee_seepage_case.md), [CLI](../docs/cli_tutorials/levee_seepage_case.md) |
| [Muskat groundwater flow](Muskat_case/README.md) | Three steady-state groundwater flow models of one soil column: saturated, unsaturated, and with a seepage face | [CLI](../docs/cli_tutorials/Muskat_case.md) |

The tutorials build these models step by step. The example folders hold the end result.

## Before you start

- Install Styx: see [Installation](../docs/INSTALLATION.md).
- To run a model, Kratos must be set up on this machine: see
  [Setting up Kratos](../docs/KRATOS_SETUP.md).
- An edit with `kratos-cli` or a **Save** in the GUI writes into the example. To try
  changes without touching it, copy the folder first.

## See also

- [GUI tutorials](../docs/gui_tutorials/index.md) and
  [CLI tutorials](../docs/cli_tutorials/README.md): the models built step by step.
- [Command reference](../docs/CLI.md): every `kratos-cli` command and its options.
