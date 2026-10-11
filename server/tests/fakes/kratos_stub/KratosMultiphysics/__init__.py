"""A stand-in for Kratos, for running `app.kratos_runner` where no Kratos is built.

Only what the runner touches: `Parameters`, `Registry`, `project.Project` and the two
orchestrators. `SequentialOrchestrator.Run` keeps the real loop's order (Kratos'
`orchestrators/sequential_orchestrator.py`): CheckStageSettings, CreateStage,
RunCurrentStagePreprocess, the stage's Run, RunCurrentStagePostprocess.

A stage may carry `"stub_fail": "preprocess" | "solve" | "postprocess" | "abort"`;
nothing in a real deck does.
"""

import json


class Parameters:
    def __init__(self, text="{}"):
        self._value = json.loads(text)

    @classmethod
    def _wrap(cls, value):
        wrapped = cls.__new__(cls)
        wrapped._value = value
        return wrapped

    def __getitem__(self, key):
        return Parameters._wrap(self._value[key])

    def Has(self, key):
        return key in self._value

    def IsNull(self):
        return self._value is None

    def GetString(self):
        return str(self._value)

    def GetStringArray(self):
        return list(self._value)

    def keys(self):
        return list(self._value.keys())


class _Registry(dict):
    def __getitem__(self, name):
        try:
            return super().__getitem__(name)
        except KeyError:
            raise KeyError(f"The item '{name}' is not registered") from None


Registry = _Registry({
    "Orchestrators.KratosMultiphysics.SequentialOrchestrator": {
        "ModuleName": "KratosMultiphysics.orchestrators.sequential_orchestrator",
        "ClassName": "SequentialOrchestrator",
    },
})
