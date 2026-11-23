# Styx CLI tutorials

Each tutorial builds one model with `kratos-cli` in PowerShell, command by command, and
shows what each command prints. Start with the simple dike if you are new to the command
line.

| Tutorial | What you build |
|---|---|
| [Simple dike](simple_dike.md) | A soil block with a sheet pile and a line load on its surface, in three stages |
| [CROW excavation wall](CROW_case.md) | A staged sheet-pile excavation in clay and sand, with a strut, water loads and Mohr-Coulomb soils, up to the bending moment in the wall |
| [Levee seepage](levee_seepage_case.md) | A steady-state groundwater flow under and through a clay levee, with a seepage face and Van Genuchten soils |
| [Muskat groundwater flow](Muskat_case.md) | Three steady-state groundwater flow models of one soil column: saturated, unsaturated, and with a seepage face |

The simple dike and the CROW excavation wall each give three ways to work: build the model
from scratch, open the ready-made model in the shell, or run its Python script in one
command.

Tests follow these pages each time the code changes: each command must work and print what
the page shows. So the pages match the current version of `kratos-cli`.

## Before you start

- Install Styx: see [Installation](../INSTALLATION.md).
- To run a model, Kratos must be set up on this machine: see
  [Setting up Kratos](../KRATOS_SETUP.md).
- In the commands, `<repo>` is the folder you cloned this repository into, such as
  `C:\Users\you\Styx-Kratos-GUI`.

## See also

- [Command reference](../CLI.md): every `kratos-cli` command and its options.
- [GUI tutorials](../gui_tutorials/index.md): the CROW excavation wall and the levee seepage
  case, built in the GUI.
  A model saved from `kratos-cli` opens in the GUI, and the other way round.
- [Examples](../../examples/README.md): the finished models of these tutorials.
