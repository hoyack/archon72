"""ResultCertificationService application service (Story 2.8, FR99-FR101, FR141-FR142).

This service orchestrates result certification and procedural record
generation for deliberation outcomes.

Constitutional Constraints:
- FR99: Deliberation results SHALL have certified result events
- FR100: Certification SHALL include result_hash, participant_count, certification_timestamp
- FR101: Certification signature SHALL be verifiable
- FR141: Procedural records SHALL be generated for each deliberation
- FR142: Records SHALL include agenda, participants, votes, timeline, decisions

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> All operations traced
- CT-13: Integrity outranks availability -> Verify before accepting

Architecture Pattern:
    ResultCertificationService orchestrates FR99-FR101/FR141-FR142 compliance:

    certify_deliberation_result(input):
      ├─ halt_checker.is_halted()        # HALT FIRST rule
      ├─ certifier.compute_result_hash() # FR99 - hash content
      ├─ certifier.certify_result()      # FR99-FR101 - sign & store
      └─ Return certification with hash

    generate_procedural_record(deliberation_id):
      ├─ halt_checker.is_halted()        # HALT FIRST rule
      └─ record_generator.generate_record()  # FR141-FR142 - generate record
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.procedural_record_generator import (
    ProceduralRecordData,
    ProceduralRecordGeneratorPort,
)
from src.application.ports.result_certifier import (
    CertificationResult,
    ResultCertifierPort,
)
from src.domain.errors.writer import SystemHaltedError

logger = structlog.get_logger()


@dataclass
class CertifyResultInput:
    """Input for certifying a deliberation result.

    Attributes:
        deliberation_id: UUID of the deliberation.
        result_content: The result content to certify (will be hashed).
        participant_count: Number of participants in deliberation.
        result_type: Type of result (e.g., "vote", "resolution", "decision").
    """

    deliberation_id: UUID
    result_content: dict[str, Any]
    participant_count: int
    result_type: str


@dataclass
class CertifyResultOutput:
    """Output from certifying a deliberation result.

    Attributes:
        certification: The certification result with signature.
        result_hash: The SHA-256 hash of the result content.
    """

    certification: CertificationResult
    result_hash: str


class ResultCertificationService:
    """Application service for result certification (FR99-FR101, FR141-FR142).

    This service provides the primary interface for:
    - Certifying deliberation results (FR99-FR101)
    - Generating procedural records (FR141-FR142)
    - Verifying certifications and records

    HALT FIRST Rule:
        Every operation checks halt state before proceeding.
        Never retry after SystemHaltedError.

    Attributes:
        _halt_checker: Interface for checking halt state.
        _certifier: Interface for result certification.
        _record_generator: Interface for procedural record generation.
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        certifier: ResultCertifierPort,
        record_generator: ProceduralRecordGeneratorPort,
    ) -> None:
        """Initialize the service with required dependencies.

        Args:
            halt_checker: Interface for checking halt state.
            certifier: Interface for result certification.
            record_generator: Interface for procedural record generation.

        Raises:
            TypeError: If any required dependency is None.
        """
        if halt_checker is None:
            raise TypeError("halt_checker is required")
        if certifier is None:
            raise TypeError("certifier is required")
        if record_generator is None:
            raise TypeError("record_generator is required")

        self._halt_checker = halt_checker
        self._certifier = certifier
        self._record_generator = record_generator

    async def certify_deliberation_result(
        self,
        input_data: CertifyResultInput,
    ) -> CertifyResultOutput:
        """Certify a deliberation result with cryptographic signature (FR99-FR101).

        Flow:
            1. HALT CHECK (fail fast if halted)
            2. Compute result_hash from content
            3. Create certification with signature
            4. Return certification with hash

        Args:
            input_data: The certification input data.

        Returns:
            CertifyResultOutput with certification and hash.

        Raises:
            SystemHaltedError: If system is halted (HALT FIRST rule).
        """
        # HALT FIRST - Check before any operation
        if await self._halt_checker.is_halted():
            logger.warning(
                "certification_blocked_halted",
                deliberation_id=str(input_data.deliberation_id),
            )
            raise SystemHaltedError("System halted - cannot certify result")

        # Compute result hash (FR99)
        result_hash = await self._certifier.compute_result_hash(
            result_content=input_data.result_content,
        )

        # Create certification (FR99-FR101)
        certification = await self._certifier.certify_result(
            deliberation_id=input_data.deliberation_id,
            result_content=input_data.result_content,
        )

        logger.info(
            "deliberation_result_certified",
            result_id=str(certification.result_id),
            deliberation_id=str(input_data.deliberation_id),
            participant_count=input_data.participant_count,
            result_type=input_data.result_type,
            result_hash_prefix=result_hash[:8],
            certification_key_id=certification.certification_key_id,
        )

        return CertifyResultOutput(
            certification=certification,
            result_hash=result_hash,
        )

    async def verify_result_certification(
        self,
        result_id: UUID,
        signature: str,
    ) -> bool:
        """Verify a certification signature (FR101).

        Args:
            result_id: The UUID of the result to verify.
            signature: The signature to verify.

        Returns:
            True if signature is valid, False otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            logger.warning(
                "verification_blocked_halted",
                result_id=str(result_id),
            )
            raise SystemHaltedError("System halted - cannot verify certification")

        is_valid = await self._certifier.verify_certification(
            result_id=result_id,
            signature=signature,
        )

        if is_valid:
            logger.debug(
                "certification_verification_passed",
                result_id=str(result_id),
            )
        else:
            logger.warning(
                "certification_verification_failed",
                result_id=str(result_id),
            )

        return is_valid

    async def generate_procedural_record(
        self,
        deliberation_id: UUID,
    ) -> ProceduralRecordData:
        """Generate a procedural record for a deliberation (FR141-FR142).

        Args:
            deliberation_id: The UUID of the deliberation.

        Returns:
            ProceduralRecordData with complete record.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            logger.warning(
                "record_generation_blocked_halted",
                deliberation_id=str(deliberation_id),
            )
            raise SystemHaltedError("System halted - cannot generate procedural record")

        record = await self._record_generator.generate_record(
            deliberation_id=deliberation_id,
        )

        logger.info(
            "procedural_record_generated",
            record_id=str(record.record_id),
            deliberation_id=str(deliberation_id),
            record_hash_prefix=record.record_hash[:8],
            agenda_item_count=len(record.agenda_items),
            participant_count=len(record.participant_ids),
            decision_count=len(record.decisions),
        )

        return record

    async def verify_procedural_record(
        self,
        record_id: UUID,
    ) -> bool:
        """Verify a procedural record's integrity.

        Args:
            record_id: The UUID of the record to verify.

        Returns:
            True if record is valid, False otherwise.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT FIRST
        if await self._halt_checker.is_halted():
            logger.warning(
                "record_verification_blocked_halted",
                record_id=str(record_id),
            )
            raise SystemHaltedError("System halted - cannot verify procedural record")

        is_valid = await self._record_generator.verify_record(
            record_id=record_id,
        )

        if is_valid:
            logger.debug(
                "procedural_record_verification_passed",
                record_id=str(record_id),
            )
        else:
            logger.warning(
                "procedural_record_verification_failed",
                record_id=str(record_id),
            )

        return is_valid

    async def get_certification(
        self,
        result_id: UUID,
    ) -> CertificationResult | None:
        """Get a stored certification result.

        Args:
            result_id: The UUID of the result.

        Returns:
            The CertificationResult if found, None otherwise.
        """
        return await self._certifier.get_certification(result_id)

    async def get_procedural_record(
        self,
        record_id: UUID,
    ) -> ProceduralRecordData | None:
        """Get a stored procedural record.

        Args:
            record_id: The UUID of the record.

        Returns:
            The ProceduralRecordData if found, None otherwise.
        """
        return await self._record_generator.get_record(record_id)
