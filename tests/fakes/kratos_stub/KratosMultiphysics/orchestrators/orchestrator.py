import os

# No flush=True anywhere here: Kratos writes from C++ and never flushes Python's stdout,
# so a flush here would hide a runner that forgot its own.


def _fail(project, stage_name, where):
    stage = project.GetSettings()["stages"][stage_name]
    if not stage.Has("stub_fail") or stage["stub_fail"].GetString() != where:
        return
    if where == "abort":
        # Like a crash in compiled code: no traceback, no buffer flush.
        os._exit(134)
    raise RuntimeError(f"stub failure in {where} of {stage_name}")


class _Stage:
    def __init__(self, project, name):
        self._project = project
        self._name = name

    def Run(self):
        print(f"stub: solve {self._name}")
        _fail(self._project, self._name, "solve")
        _fail(self._project, self._name, "abort")

    def GetFinalData(self):
        return {}


class Orchestrator:
    def __init__(self, project):
        self.__project = project

    def GetProject(self):
        return self.__project

    def CheckStageSettings(self, stage_name):
        if not self.__project.GetSettings()["stages"].Has(stage_name):
            raise KeyError(f"stage '{stage_name}' is not in 'stages'")

    def CreateStage(self, stage_name):
        return _Stage(self.__project, stage_name)

    def RunCurrentStagePreprocess(self, stage_name, data=None):
        print(f"stub: preprocess {stage_name}")
        _fail(self.__project, stage_name, "preprocess")

    def RunCurrentStagePostprocess(self, stage_name, data=None):
        print(f"stub: postprocess {stage_name}")
        _fail(self.__project, stage_name, "postprocess")
