# Styx GUI tutorials

Each tutorial builds one model in the Styx GUI, step by step, with a screenshot of each
step. Start with the first one if you are new to Styx.

| Tutorial | What you build |
|---|---|
| [CROW excavation wall](CROW_case.md) | A staged sheet-pile excavation in clay and sand, with a strut, an interface, water loads and Mohr-Coulomb soils, up to the bending moment in the wall |
| [Levee seepage](levee_seepage_case.md) | A steady-state groundwater flow under and through a clay levee, with drawn soil surfaces, water pressure conditions, a seepage face and Van Genuchten soils, up to the water pressures and the flow |

The screenshots are made from the GUI each time the code changes, so they show the GUI as
it is.

## Before you start

- Install Styx: see [Installation](../INSTALLATION.md).
- To run a model, Kratos must be set up on this machine: see
  [Setting up Kratos](../KRATOS_SETUP.md).
- Start the GUI: see [Run the app](../INSTALLATION.md#run-the-app).

## See also

- [Usage](../USAGE.md): every mode and tool of the GUI.
- [CLI tutorials](../cli_tutorials/README.md): the CROW excavation wall and the levee
  seepage case, built with `kratos-cli`. A model saved from the GUI opens in `kratos-cli`, and the other way round.
- [Examples](../../examples/README.md): the finished models, to open with
  **File > Open project…**.
