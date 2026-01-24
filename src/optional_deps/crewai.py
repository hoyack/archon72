"""Optional CrewAI dependency shim.

Provides stub classes when CrewAI isn't installed so modules can be imported
in test environments that don't include CrewAI.
"""

from __future__ import annotations

from typing import Any

CREWAI_AVAILABLE = True

try:
    from crewai import LLM, Agent, Crew, Process, Task
    from crewai.tools import BaseTool
except ModuleNotFoundError:  # pragma: no cover - exercised in CI without CrewAI
    CREWAI_AVAILABLE = False

    class _MissingCrewAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "CrewAI is not installed. Install 'crewai' to use this feature."
            )

    class LLM(_MissingCrewAI):
        pass

    class Agent(_MissingCrewAI):
        pass

    class Crew(_MissingCrewAI):
        pass

    class Task(_MissingCrewAI):
        pass

    class Process:
        sequential = "sequential"
        hierarchical = "hierarchical"

    class BaseTool:
        name: str = ""
        description: str = ""
        args_schema: type | None = None

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Allow tool stubs to be instantiated in tests without CrewAI.
            pass
