"""Gives a groundwater flow stage the water pressure elements its time integration needs.

This file is not imported by this application. The exporter copies it, unchanged, into
every deck that needs it, as `kratos_gui_flow_elements.py`
(`core.kratos.deck_files.FLOW_ELEMENTS_NAME`). Kratos then runs it as a user-defined
process, with the Python that Kratos is installed for. So it imports Kratos and nothing
from this application, and the server never imports it.

Why a stage needs it
--------------------
Kratos' groundwater flow solver (`geomechanics_Pw_solver.py`) only checks the stage's
`solution_type` and picks a time scheme with it. Whether the flow is steady or
transient is decided by the elements alone:

*   `SteadyStatePwElement` assembles the permeability matrix only. Every step it solves
    is the steady state for that step's boundary conditions.
*   `TransientPwElement` adds the compressibility (storage) matrix, so the pressure
    moves towards the new steady state over time.

The element class is written in the .mdpa, and every stage reads that one file. The
exporter writes the steady class (`core.kratos.writer.FLOW_ELEMENTS`). A dynamic flow
stage therefore has to switch the soil to the transient class, and a static stage after
it has to switch back. Without the switch a dynamic stage jumps to the new steady state
in its first step and stays there.

What this process does
----------------------
`ExecuteInitialize` replaces every element of the parts in `model_part_name_list` with
`element_name`, using Kratos' own `ReplaceElementsAndConditionsProcess`. That keeps each
element's id, nodes, properties and flags (so an element a stage switched off stays
off), and updates every sub-model part that holds it, including the part the solver
assembles. Kratos runs `ExecuteInitialize` before it initialises the solver, so the
solver initialises the new elements.

With `zero_water_pressure_rate`, it also sets `DT_WATER_PRESSURE` to zero on the nodes of
those parts. The exporter asks for that when it switches to the transient class, which
it does only after a steady stage: a steady state has no rate of change, but the time
scheme computed one during the steady stage, and the transient stage's first step
would otherwise start from it.
"""

import KratosMultiphysics as Kratos
import KratosMultiphysics.GeoMechanicsApplication as Geo


def Factory(settings, model):
    if not isinstance(settings, Kratos.Parameters):
        raise TypeError("expected input shall be a Parameters object, encapsulating a json string")
    return SwitchFlowElements(model, settings["Parameters"])


class SwitchFlowElements(Kratos.Process):
    """Replaces the elements of `model_part_name_list` with `element_name` before the
    solver initialises. See the module docstring."""

    def __init__(self, model, parameters):
        super().__init__()
        parameters.ValidateAndAssignDefaults(Kratos.Parameters("""{
            "model_part_name_list": [],
            "element_name": "",
            "zero_water_pressure_rate": false
        }"""))
        self._model_parts = [model[name.GetString()]
                             for name in parameters["model_part_name_list"].values()]
        self._element_name = parameters["element_name"].GetString()
        if not self._element_name:
            raise ValueError("SwitchFlowElements needs an element_name")
        self._zero_rate = parameters["zero_water_pressure_rate"].GetBool()

    def ExecuteInitialize(self):
        for model_part in self._model_parts:
            Kratos.ReplaceElementsAndConditionsProcess(model_part, Kratos.Parameters(
                '{"element_name": "' + self._element_name + '"}')).Execute()
            if self._zero_rate:
                Kratos.VariableUtils().SetVariable(Geo.DT_WATER_PRESSURE, 0.0,
                                                   model_part.Nodes)
