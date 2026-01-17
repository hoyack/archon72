"""Contact block port for dignified exit.

Story: consent-gov-7.4: Follow-Up Contact Prevention

Port interface for managing contact blocks. This port intentionally
has NO methods for removing blocks - blocks are permanent.

NFR-EXIT-02: No follow-up contact mechanism may exist.
FR46: System can prohibit follow-up contact after exit.

Structural Prohibition:
- No remove_block() method
- No unblock() method
- No allow_contact() method
- No enable_contact() method
- No reactivate() method

These methods do not exist because:
1. Exit is final
2. Contact prohibition is permanent
3. Structural absence prevents policy bypass
4. Architecture enforces constitution
"""

from typing import Protocol
from uuid import UUID

from src.domain.governance.exit.contact_block import ContactBlock


class ContactBlockPort(Protocol):
    """Port for contact block operations.

    This is an append-only port. Blocks can be added and queried,
    but NEVER removed. This is constitutional enforcement.

    Intentionally Missing Methods:
    - remove_block(): Blocks are permanent
    - unblock(): Cannot unblock
    - allow_contact(): Contact prohibited forever
    - delete_block(): No deletion

    Why Protocol?
    - Defines the interface adapters must implement
    - Type checking ensures compliance
    - No implementation details leaked

    Example:
        class InMemoryContactBlockAdapter(ContactBlockPort):
            def __init__(self):
                self._blocks: dict[UUID, ContactBlock] = {}

            async def add_block(self, block: ContactBlock) -> None:
                self._blocks[block.cluster_id] = block

            async def is_blocked(self, cluster_id: UUID) -> bool:
                return cluster_id in self._blocks

            async def get_block(self, cluster_id: UUID) -> ContactBlock | None:
                return self._blocks.get(cluster_id)

            async def get_all_blocked(self) -> list[UUID]:
                return list(self._blocks.keys())

            # Note: NO remove_block, unblock, etc.
    """

    async def add_block(self, block: ContactBlock) -> None:
        """Add a contact block (permanent).

        Once added, a block cannot be removed. This is structural.

        Args:
            block: The contact block to add.

        Raises:
            ValueError: If block already exists for this Cluster.
        """
        ...

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if a Cluster is blocked.

        Args:
            cluster_id: The Cluster to check.

        Returns:
            True if contact is blocked, False otherwise.
        """
        ...

    async def get_block(self, cluster_id: UUID) -> ContactBlock | None:
        """Get the block record for a Cluster.

        Args:
            cluster_id: The Cluster to look up.

        Returns:
            The ContactBlock if blocked, None otherwise.
        """
        ...

    async def get_all_blocked(self) -> list[UUID]:
        """Get all blocked Cluster IDs.

        Returns:
            List of all Cluster IDs that are blocked.
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENTIONALLY NOT DEFINED (NFR-EXIT-02 Structural Prohibition)
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # The following methods DO NOT EXIST and MUST NOT be added:
    #
    # async def remove_block(self, cluster_id: UUID) -> None: ...
    # async def unblock(self, cluster_id: UUID) -> None: ...
    # async def allow_contact(self, cluster_id: UUID) -> None: ...
    # async def delete_block(self, block_id: UUID) -> None: ...
    # async def enable_contact(self, cluster_id: UUID) -> None: ...
    # async def reactivate_contact(self, cluster_id: UUID) -> None: ...
    # async def lift_block(self, cluster_id: UUID) -> None: ...
    # async def temporary_allow(self, cluster_id: UUID, duration: timedelta) -> None: ...
    #
    # Why?
    # - Exit is final
    # - Contact prohibition is permanent
    # - Structural absence > policy that can be bypassed
    # - These methods not existing makes bypass impossible
    # ═══════════════════════════════════════════════════════════════════════════
