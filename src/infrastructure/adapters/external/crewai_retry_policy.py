"""Documented retry policies for CrewAI adapters.

CrewAI calls are not retried explicitly in these adapters unless noted below.
"""

RETRY_POLICY_BY_ADAPTER: dict[str, str] = {
    "crewai_adapter": "No explicit retry; relies on CrewAI defaults and caller retries.",
    "crewai_deliberation_adapter": "No explicit retry; phase execution relies on CrewAI defaults.",
    "reviewer_crewai_adapter": "No explicit retry; JSON parse failures return abstain.",
    "planner_crewai_adapter": "No explicit retry; JSON parse failures raise errors.",
    "secretary_crewai_adapter": "No explicit retry; aggressive JSON cleaning + checkpoints.",
}
