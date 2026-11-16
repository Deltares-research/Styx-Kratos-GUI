"""Deprecated: the construction sequence is `core.model.stages` now, in Kratos' word.

Kept so that model scripts and imports written before the rename keep working."""

from core.model.stages import *  # noqa: F401,F403
from core.model.stages import (  # noqa: F401
    FLOW, StageError,
)

GROUNDWATER_FLOW = FLOW
PhaseError = StageError
