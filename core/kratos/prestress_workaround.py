"""TEMPORARY WORKAROUND for a Kratos limitation. Remove it once Kratos stops counting
an anchor's prestress twice when it carries the anchor's stress into the next stage.

This file is not imported by this application. The exporter copies it, unchanged, into
every deck that needs it, as `kratos_gui_prestress_workaround.py`
(`core.kratos.deck_files.PRESTRESS_WORKAROUND_NAME`). Kratos then runs it as a
user-defined process, with the Python that Kratos is installed for. So it imports Kratos
and nothing from this application, and the server never imports it.

The problem
-----------
At the start of every stage, GeoMechanics resets DISPLACEMENT to zero. A structural
element computes its strain from DISPLACEMENT, so it only keeps its stress in the next
stage through `ApplyFinalStressesOfPreviousStageToInitialState`. That process reads each
element's `PK2_STRESS_VECTOR` at the end of a stage. It then gives that stress to the
element's constitutive law as the initial stress of the next stage.

An anchor is a `LinearTrussElement`. Its `PK2_STRESS_VECTOR` includes the prestress
(`TRUSS_PRESTRESS_PK2`), because the element adds the property to the stress that its law
computes. The element also adds the property to its internal force. When the stress is
carried as it is, the prestress becomes part of the law's initial stress, and the element
then adds it again. So each stage after the anchor's installation adds the full
prestress to the anchor once more.

This was found by running the staged excavation of `tests/models/excavation.py`, with a
prestressed strut, through Kratos 10.4.4. Each stage started the strut at its previous
end stress plus the full prestress. A stage that changed nothing still moved the wall.

What this process does
----------------------
It makes Kratos' process store the stress of the anchor's law without the prestress. The
element adds the prestress by itself, so the prestress is then counted once.

Kratos' process stores the stresses in `ExecuteInitialize`. This process comes directly
before it in the same process list:

*   `ExecuteInitialize` sets `TRUSS_PRESTRESS_PK2` to zero on the anchors' properties, so
    the stress that Kratos stores does not include the prestress.
*   `ExecuteBeforeSolutionLoop` sets the value back, after the stresses are stored and
    before anything is solved.

Between the two calls, the solver only initialises its elements, and that does not read
the prestress.

The order matters. The exporter writes this process directly before
`ApplyFinalStressesOfPreviousStageToInitialState` in the same list
(`core.kratos.parameters._auxiliary`). Kratos runs the `ExecuteInitialize` of every
process in list order, then initialises the solver, then runs the
`ExecuteBeforeSolutionLoop` of every process in list order.

Why not a copy of Kratos' process that subtracts the prestress? Kratos' Python interface
has no `InitialState`, so only C++ code can set the initial stress.

Removing it
-----------
When Kratos counts the prestress once, `test_kratos_still_counts_the_prestress_twice` in
`tests/kratos/test_live_prestress.py` fails. Then delete these:

*   this file;
*   `PRESTRESS_WORKAROUND_*` in `core/kratos/deck_files.py`;
*   `_exclude_prestress` and `Stage.prestressed` in `core/kratos/parameters.py`;
*   `_Deck.prestressed` in `core/kratos/writer.py`;
*   the tests that check these.

Anchors then use Kratos' process alone, like every other structure.
"""

import KratosMultiphysics as Kratos
import KratosMultiphysics.StructuralMechanicsApplication as Structural


def Factory(settings, model):
    if not isinstance(settings, Kratos.Parameters):
        raise TypeError("expected input shall be a Parameters object, encapsulating a json string")
    return ExcludePrestressFromCarriedStress(model, settings["Parameters"])


class ExcludePrestressFromCarriedStress(Kratos.Process):
    """Hides `TRUSS_PRESTRESS_PK2` from the anchors of `model_part_name_list` while
    `ApplyFinalStressesOfPreviousStageToInitialState` stores their stresses. This class is
    temporary: see the module docstring."""

    def __init__(self, model, parameters):
        super().__init__()
        parameters.ValidateAndAssignDefaults(Kratos.Parameters("""{
            "model_part_name_list": []
        }"""))
        self._model_parts = [model[name.GetString()]
                             for name in parameters["model_part_name_list"].values()]
        self._hidden = []

    def ExecuteInitialize(self):
        """Set the prestress of each anchor's properties to zero. Kratos' process comes
        next in the list and stores the stresses without the prestress."""
        seen = set()
        for model_part in self._model_parts:
            for element in model_part.Elements:
                properties = element.Properties
                if properties.Id in seen:
                    continue
                seen.add(properties.Id)
                if not properties.Has(Structural.TRUSS_PRESTRESS_PK2):
                    continue
                prestress = properties.GetValue(Structural.TRUSS_PRESTRESS_PK2)
                if prestress != 0.0:
                    self._hidden.append((properties, prestress))
                    properties.SetValue(Structural.TRUSS_PRESTRESS_PK2, 0.0)

    def ExecuteBeforeSolutionLoop(self):
        """Set each prestress back to its value. The stresses are stored by now, and
        nothing is solved yet."""
        for properties, prestress in self._hidden:
            properties.SetValue(Structural.TRUSS_PRESTRESS_PK2, prestress)
        self._hidden = []
