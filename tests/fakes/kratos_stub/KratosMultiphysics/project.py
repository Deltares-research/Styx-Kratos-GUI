class Project:
    def __init__(self, settings):
        self._settings = settings
        self._output = {}

    def GetSettings(self):
        return self._settings

    def GetOutputData(self):
        return self._output
