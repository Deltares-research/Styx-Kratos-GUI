from KratosMultiphysics.orchestrators.orchestrator import Orchestrator


class SequentialOrchestrator(Orchestrator):
    def Run(self):
        for stage_name in self._execution_list():
            self.CheckStageSettings(stage_name)
            current_stage = self.CreateStage(stage_name)
            self.RunCurrentStagePreprocess(stage_name)
            current_stage.Run()
            self.GetProject().GetOutputData()[stage_name] = current_stage.GetFinalData()
            self.RunCurrentStagePostprocess(stage_name)
            del current_stage

    def GetNumberOfStages(self):
        return len(self._execution_list())

    def _execution_list(self):
        settings = self.GetProject().GetSettings()
        if settings["orchestrator"]["settings"].Has("execution_list"):
            return settings["orchestrator"]["settings"]["execution_list"].GetStringArray()
        return settings["stages"].keys()
