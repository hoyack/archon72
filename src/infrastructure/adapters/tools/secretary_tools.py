"""Secretary-specific tool implementations for CrewAI.

These tools are specialized for the Secretary agent's transcript
analysis pipeline. Unlike Archon tools, these focus on extraction,
validation, clustering, and motion synthesis.

Tools:
- extraction_tool: Extract structured recommendations from speech text
- validation_tool: Validate extraction completeness against source
- clustering_tool: Group recommendations by semantic similarity
- motion_synthesis_tool: Generate formal motion text from clusters

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy -> log all tool invocations
- CT-12: Witnessing creates accountability -> outputs traceable to source
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from crewai.tools import BaseTool  # Use crewai's BaseTool, not crewai_tools
from structlog import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input Schemas
# ============================================================================


class ExtractionToolInput(BaseModel):
    """Input schema for ExtractionTool."""

    speech_content: str = Field(
        ..., description="The full text of the Archon speech to analyze"
    )
    archon_name: str = Field(..., description="Name of the Archon who gave the speech")
    context: str = Field(
        default="", description="Additional context (motion being debated, etc.)"
    )


class ValidationToolInput(BaseModel):
    """Input schema for ValidationTool."""

    extracted_json: str = Field(
        ..., description="JSON array of previously extracted recommendations"
    )
    original_content: str = Field(
        ..., description="Original speech content for comparison"
    )


class ClusteringToolInput(BaseModel):
    """Input schema for ClusteringTool."""

    recommendations_json: str = Field(
        ..., description="JSON array of recommendations to cluster"
    )
    similarity_threshold: float = Field(
        default=0.6, description="Minimum similarity score for clustering (0.0-1.0)"
    )


class MotionSynthesisToolInput(BaseModel):
    """Input schema for MotionSynthesisTool."""

    cluster_json: str = Field(
        ..., description="JSON object representing the recommendation cluster"
    )
    session_context: str = Field(
        ..., description="Context about the originating Conclave session"
    )


# ============================================================================
# Tool Implementations
# ============================================================================


class ExtractionTool(BaseTool):
    """Tool for extracting structured recommendations from Archon speech text.

    The Secretary uses this tool to identify all recommendations, proposals,
    suggestions, and action items from a single Archon's contribution.
    """

    name: str = "extraction_tool"
    description: str = (
        "Extract structured recommendations from Archon speech content. "
        "Identifies explicit proposals, implicit suggestions, action items, "
        "amendments, and concerns that imply needed action. Returns JSON array "
        "with category, type, text, keywords, and stance for each recommendation."
    )
    args_schema: type[BaseModel] = ExtractionToolInput

    def _run(
        self,
        speech_content: str,
        archon_name: str,
        context: str = "",
    ) -> str:
        """Execute extraction analysis.

        This is a stub implementation. The actual extraction logic
        is handled by the LLM through the CrewAI task prompt.
        The tool provides structured input/output for the agent.
        """
        logger.info(
            "extraction_tool_invoked",
            archon_name=archon_name,
            content_length=len(speech_content),
            has_context=bool(context),
        )

        # Return guidance for the LLM - actual extraction done by agent
        return (
            f"Analyze the speech from {archon_name}. "
            f"Content length: {len(speech_content)} characters. "
            f"Context: {context or 'General deliberation'}. "
            "Extract all recommendations and return as JSON array with fields: "
            "category, type, text, keywords, stance, source_archon."
        )


class ValidationTool(BaseTool):
    """Tool for validating extraction completeness.

    The Secretary uses this tool to double-check that all recommendations
    have been captured and none were missed during initial extraction.
    """

    name: str = "validation_tool"
    description: str = (
        "Validate extracted recommendations against original speech content. "
        "Checks for missed recommendations, misinterpretations, and incomplete "
        "extractions. Returns validated JSON with corrections and additions."
    )
    args_schema: type[BaseModel] = ValidationToolInput

    def _run(
        self,
        extracted_json: str,
        original_content: str,
    ) -> str:
        """Execute validation analysis."""
        logger.info(
            "validation_tool_invoked",
            extracted_length=len(extracted_json),
            original_length=len(original_content),
        )

        return (
            "Compare the extracted recommendations against the original content. "
            "Verify each extraction accurately represents the source. "
            "Identify any missed recommendations. "
            "Return validated JSON array with corrections, additions, and "
            "a confidence score (0.0-1.0) for completeness."
        )


class ClusteringTool(BaseTool):
    """Tool for semantic clustering of recommendations.

    The Secretary uses this tool to group similar recommendations
    by theme, enabling consensus identification across Archons.
    """

    name: str = "clustering_tool"
    description: str = (
        "Cluster recommendations by semantic similarity. Groups recommendations "
        "with similar themes, compatible stances, and actionable together. "
        "Returns JSON array of clusters with theme, canonical summary, "
        "member IDs, keywords, and archon names."
    )
    args_schema: type[BaseModel] = ClusteringToolInput

    def _run(
        self,
        recommendations_json: str,
        similarity_threshold: float = 0.6,
    ) -> str:
        """Execute clustering analysis."""
        logger.info(
            "clustering_tool_invoked",
            recommendations_length=len(recommendations_json),
            threshold=similarity_threshold,
        )

        return (
            f"Cluster the recommendations with similarity threshold {similarity_threshold}. "
            "Group by semantic theme, not just keyword overlap. "
            "Compatible stances can cluster together. "
            "Conflicting stances should NOT cluster. "
            "Return JSON array of clusters with: theme, canonical_summary, "
            "member_ids, combined_keywords, archon_names, archon_count."
        )


class MotionSynthesisTool(BaseTool):
    """Tool for generating formal motion text from clusters.

    The Secretary uses this tool to synthesize actionable motion
    text from high-consensus recommendation clusters.
    """

    name: str = "motion_synthesis_tool"
    description: str = (
        "Generate formal motion text for a recommendation cluster. "
        "Creates actionable, specific motion language suitable for "
        "the next Conclave agenda. Returns JSON with title, text, "
        "rationale, and implementation considerations."
    )
    args_schema: type[BaseModel] = MotionSynthesisToolInput

    def _run(
        self,
        cluster_json: str,
        session_context: str,
    ) -> str:
        """Execute motion synthesis."""
        logger.info(
            "motion_synthesis_tool_invoked",
            cluster_length=len(cluster_json),
            context_length=len(session_context),
        )

        return (
            "Generate a formal motion from this cluster. "
            "The motion must be: "
            "1. Actionable and specific "
            "2. Neutral in tone "
            "3. Include implementation considerations "
            "4. Reference the consensus basis "
            f"Session context: {session_context}. "
            "Return JSON with: title, motion_text, rationale, "
            "implementation_notes, source_archons."
        )


# ============================================================================
# Tool Registry
# ============================================================================

# Map tool names to tool classes (matches archon_tools.py pattern)
TOOL_NAME_TO_CLASS: dict[str, type[BaseTool]] = {
    "extraction_tool": ExtractionTool,
    "validation_tool": ValidationTool,
    "clustering_tool": ClusteringTool,
    "motion_synthesis_tool": MotionSynthesisTool,
}

# All secretary tool names
ALL_SECRETARY_TOOLS: list[str] = list(TOOL_NAME_TO_CLASS.keys())


def get_secretary_tool(name: str) -> BaseTool:
    """Get a Secretary tool instance by name.

    Args:
        name: Tool name (extraction_tool, validation_tool, etc.)

    Returns:
        Instantiated tool

    Raises:
        KeyError: If tool name not found
    """
    if name not in TOOL_NAME_TO_CLASS:
        raise KeyError(f"Unknown secretary tool: {name}")
    return TOOL_NAME_TO_CLASS[name]()


def get_all_secretary_tools() -> list[BaseTool]:
    """Get all Secretary tools as instantiated list."""
    return [tool_class() for tool_class in TOOL_NAME_TO_CLASS.values()]
