# Simple dike, way 3: run the Python script

Part of [Simple dike with `kratos-cli`](README.md), which describes the model and the other
two ways to work with it.

In the commands below, `<repo>` is the folder you cloned this repository into, such as
`C:\Users\you\Styx-Kratos-GUI`. The ready-made model is in
[`examples/simple_dike/`](../../examples/simple_dike/).

---

## Before ways 2 and 3

Run [`kratos-init-powershell.bat`](../../cli/kratos-init-powershell.bat), in the `cli` folder: double-click it, or
from PowerShell:

```powershell
<repo>\cli\kratos-init-powershell.bat
```

It asks for the **project folder**: the folder that holds the model's `.py` file, such as
`<repo>\examples\simple_dike`.

It then opens a PowerShell that is ready for ways 2 and 3:

- it is in the project folder;
- `$repo`, `$model`, `$cli` and `$py` are set (it prints them);
- `KRATOS_GUI_RUNS` is the project folder, so runs are written there and read from there;
- the first time, it builds the Python environment (`.venv-windows`), which can take a few
  minutes.

If Kratos is not set up on this machine yet, it says so and stops: follow steps 1 and 2 of
[Setting up Kratos](../KRATOS_SETUP.md), then run it again. `exit` closes the
PowerShell it opened.

> [!IMPORTANT]
> Type every command that uses `$repo`, `$model`, `$cli` or `$py` in **that** PowerShell.
> In any other window they are empty, and PowerShell answers with an error such as
> *The term '\kratos-cli.bat' is not recognized*.

---

## Run the script

In the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3):

```powershell
& $py simple_dike.py                      # write the input files into this folder
& $py simple_dike.py --calculate          # write them, run Kratos, print a results summary
& $py simple_dike.py --out $HOME\deck     # write them somewhere else instead
```

`--calculate` prints the stages, the settlement (`uy`), the horizontal displacement (`ux`)
and the bending moment along the sheet pile. To look further, open the model in the shell
([way 2](2_open_in_the_shell.md)) and use its `results` lines.

What ends up in the folder is listed in [What gets written](README.md#what-gets-written).
