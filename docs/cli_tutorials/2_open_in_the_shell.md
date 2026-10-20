# Simple dike, way 2: open the ready-made model in the shell

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

## Open the model in the shell

In the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3), open the shell on
`simple_dike.py`:

```powershell
& $cli shell simple_dike.py
```

Then type these lines. `.` is the model's folder, and `1` is the newest run.

```text
# The model
show
parts
phases list

# Write the input files, then run them
export --out .
run .

# The runs and their stages
results runs
results show 1
results fields 1

# Fields: last stage by default, or pick one with --stage (a number or a name)
results field 1 uy
results field 1 uy --stage 2
results field 1 syy
results at 1 6

# The sheet pile: M, Q, N, ux or uy along it
results members 1
results profile 1 wall M

# Every value, to a CSV file
results field 1 uy --csv uy.csv

exit
```

---

## One command at a time, without the shell

Every shell line also works on its own: put `& $cli` in front, and the model file after the
command name. In the model's folder:

```powershell
& $cli show   simple_dike.py                 # what the model holds
& $cli parts  simple_dike.py                 # its parts
& $cli phases simple_dike.py list            # its stages
& $cli export simple_dike.py --out .         # write the input files
& $cli run    . --runs-dir .                 # run Kratos
& $cli results field 1 uy --runs-dir .       # read a result
```

What ends up in the folder is listed in [What gets written](README.md#what-gets-written).
