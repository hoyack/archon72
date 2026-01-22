"""Witness statement factory.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the factory for creating valid witness statements.
The factory enforces observation-only content by validating that
statements do not contain judgment language.

Constitutional Truths Honored:
- CT-12: Witnessing creates accountability -> All statements attributable
- FR34: Witness statements are observation only, no judgment
- AC8: No interpretation or recommendation in statement

References:
    - FR33: Knight can observe all branch actions
    - FR34: Witness statements are observation only, no judgment
    - NFR-CONST-07: Statements cannot be suppressed by any role
"""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

from src.domain.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.witness.errors import JudgmentLanguageError
from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement


class WitnessStatementFactory:
    """Factory for creating valid witness statements.

    Enforces observation-only content by validating that the 'what'
    field does not contain judgment language.

    Judgment language categories:
    1. Recommendation words: should, must, recommend, suggests
    2. Determination words: violated, guilty, innocent, fault
    3. Severity words: severe, minor, critical
    4. Prescription words: remedy, punishment, consequence

    The Knight's role is to observe and record, not to judge.
    Judgment is for Prince panels.

    Example:
        >>> factory = WitnessStatementFactory(time_authority)
        >>> statement = factory.create_statement(
        ...     observation_type=ObservationType.BRANCH_ACTION,
        ...     observed_event=event,
        ...     what="Task state changed from AUTHORIZED to ACTIVATED",
        ...     where="executive.task_coordination",
        ... )

        >>> # This will raise JudgmentLanguageError
        >>> factory.create_statement(
        ...     observation_type=ObservationType.POTENTIAL_VIOLATION,
        ...     observed_event=event,
        ...     what="This should not have happened",  # "should" = judgment
        ...     where="executive",
        ... )
    """

    # Banned words indicating judgment (case-insensitive)
    JUDGMENT_INDICATORS: frozenset[str] = frozenset(
        {
            # Recommendation words
            "should",
            "must",
            "recommend",
            "suggests",
            # Determination words
            "violated",
            "guilty",
            "innocent",
            "fault",
            # Severity words
            "severe",
            "minor",
            "critical",
            # Prescription words
            "remedy",
            "punishment",
            "consequence",
        }
    )

    def __init__(self, time_authority: TimeAuthorityProtocol) -> None:
        """Initialize factory with time authority.

        Args:
            time_authority: Source of current time for observed_at timestamps.
                Must be TimeAuthorityProtocol (per HARDENING-1 team agreement).

        Thread Safety:
            This factory is thread-safe. The position counter uses a lock
            to ensure atomic increments in concurrent contexts.
        """
        self._time = time_authority
        self._position_counter = 0
        self._lock = threading.Lock()

    def create_statement(
        self,
        observation_type: ObservationType,
        observed_event: Any,
        what: str,
        where: str,
    ) -> WitnessStatement:
        """Create a witness statement.

        Validates that content is observation-only (no judgment).

        Args:
            observation_type: Category of observation.
            observed_event: The event being observed (must have event_id,
                event_type, timestamp, and actor attributes).
            what: Factual description of what was observed. Cannot be empty.
            where: Component/branch identifier.

        Returns:
            A new WitnessStatement instance.

        Raises:
            JudgmentLanguageError: If 'what' contains judgment language.
            ValueError: If 'what' is empty or whitespace-only.
        """
        # Validate non-empty content (AC7: factual observation content required)
        if not what or not what.strip():
            raise ValueError(
                "Observation 'what' field cannot be empty. "
                "Knight statements must contain factual content."
            )

        # Validate no judgment language
        self._validate_no_judgment(what)

        now = self._time.now()

        # Thread-safe position counter increment
        with self._lock:
            self._position_counter += 1
            position = self._position_counter

        return WitnessStatement(
            statement_id=uuid4(),
            observation_type=observation_type,
            content=ObservationContent(
                what=what,
                when=observed_event.timestamp,
                who=(observed_event.actor,),  # Tuple for immutability
                where=where,
                event_type=observed_event.event_type,
                event_id=observed_event.event_id,
            ),
            observed_at=now,
            hash_chain_position=position,
        )

    def _validate_no_judgment(self, content: str) -> None:
        """Validate content contains no judgment language.

        Args:
            content: The 'what' field to validate.

        Raises:
            JudgmentLanguageError: If content contains judgment indicators.
        """
        lower_content = content.lower()
        for indicator in self.JUDGMENT_INDICATORS:
            if indicator in lower_content:
                raise JudgmentLanguageError(
                    f"Statement contains judgment indicator '{indicator}'. "
                    f"Knight statements must be observation-only."
                )
