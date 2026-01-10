"""Writer Lock port - ensures single-writer constraint (Story 1.6, Task 4).

ADR-1 requires a single canonical writer. Only one Writer instance
may be active at any time. Failover requires a witnessed ceremony
(not automatic).

Production Implementation:
- Redis distributed lock with fencing token
- Lock TTL with heartbeat renewal
- Failover through witnessed ceremony

Constitutional Constraints:
- ADR-1: Single canonical writer (constitutionally required)
- CT-11: Silent failure destroys legitimacy
- Failover is ceremony-based: watchdog detection + human approval + witnessed promotion

Anti-Pattern Warning:
Automatic failover is FORBIDDEN. If the lock is lost, the system
must halt and wait for human intervention through a witnessed ceremony.
"""

from abc import ABC, abstractmethod


class WriterLockProtocol(ABC):
    """Abstract interface for writer lock operations.

    ADR-1 requires single canonical writer. This lock enforces
    that constraint at runtime.

    Production Implementation Notes:
    - Use Redis SETNX with TTL for distributed lock
    - Include fencing token to prevent zombie writes
    - Heartbeat renewal should happen at TTL/3 intervals
    - If heartbeat fails, Writer must halt immediately
    - Failover requires witnessed ceremony (Epic 5 dependency)

    For development/testing, use WriterLockStub which always succeeds.
    """

    @abstractmethod
    async def acquire(self) -> bool:
        """Acquire the writer lock.

        Must be called before accepting any writes.
        If lock cannot be acquired, another Writer is active.

        Returns:
            True if lock acquired successfully.
            False if lock is already held by another instance.

        Note:
            Do NOT retry acquisition automatically.
            If another instance holds the lock, that is the canonical writer.
        """
        ...

    @abstractmethod
    async def release(self) -> None:
        """Release the writer lock.

        Call this during graceful shutdown.
        If the process crashes, TTL will expire and release the lock.
        """
        ...

    @abstractmethod
    async def is_held(self) -> bool:
        """Check if this instance currently holds the lock.

        Call this before every write operation to ensure lock is still held.
        Lock could be lost due to:
        - TTL expiration (heartbeat failure)
        - Redis connectivity issues
        - Lock stolen (should not happen in correct implementation)

        Returns:
            True if this instance holds the lock.
            False if lock is not held.

        Raises:
            WriterLockNotHeldError should be raised by caller if False.
        """
        ...

    @abstractmethod
    async def renew(self) -> bool:
        """Renew the lock TTL (heartbeat).

        Should be called periodically (at TTL/3 intervals) to maintain lock.
        If renewal fails, Writer must halt immediately.

        Returns:
            True if renewal succeeded.
            False if renewal failed (lock lost).
        """
        ...
