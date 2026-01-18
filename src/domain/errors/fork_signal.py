"""Fork signal errors for Story 3.8 (FR84-FR85).

Domain errors for fork signal signing and rate limiting violations.

Constitutional Constraints:
- FR84: Fork detection signals MUST be signed
- FR85: Fork signal rate limiting prevents DoS
- CT-11: Silent failure destroys legitimacy - invalid signatures MUST be logged
- CT-13: Integrity outranks availability - reject unsigned/invalid signals
"""


class UnsignedForkSignalError(Exception):
    """Error for fork signals that lack a signature.

    Raised when a fork detection signal is received without
    a cryptographic signature (FR84 violation).

    Constitutional Constraints:
    - FR84: Fork signals MUST be signed
    - CT-11: Silent failure destroys legitimacy
    - CT-13: Integrity outranks availability
    """

    def __init__(self, message: str | None = None) -> None:
        """Initialize the error.

        Args:
            message: Optional custom error message
        """
        if message is None:
            message = "Fork signal received without signature (FR84 violation)"
        super().__init__(message)


class InvalidForkSignatureError(Exception):
    """Error for fork signals with invalid signatures.

    Raised when a fork detection signal's signature fails
    verification (FR84 violation - potential attack).

    Constitutional Constraints:
    - FR84: Fork signals MUST be signed AND verifiable
    - CT-11: Silent failure destroys legitimacy
    - CT-13: Integrity outranks availability

    Security Note:
        Invalid signatures may indicate:
        - Tampered signal (attack)
        - Key rotation issue
        - Corrupted transmission
        All cases MUST be logged as potential security events.
    """

    def __init__(
        self, message: str | None = None, *, key_id: str | None = None
    ) -> None:
        """Initialize the error.

        Args:
            message: Optional custom error message
            key_id: Optional key ID that was used for the invalid signature
        """
        if message is None:
            if key_id:
                message = (
                    f"Fork signal signature verification failed for key {key_id} "
                    "(FR84 violation - potential attack)"
                )
            else:
                message = (
                    "Fork signal signature verification failed "
                    "(FR84 violation - potential attack)"
                )
        elif key_id and key_id not in message:
            message = f"{message} (key_id: {key_id})"
        super().__init__(message)


class ForkSignalRateLimitExceededError(Exception):
    """Error for exceeding fork signal rate limit.

    Raised when a source exceeds the fork signal rate limit
    of 3 signals per hour (FR85).

    Constitutional Constraints:
    - FR85: More than 3 fork signals per hour triggers rate limiting
    - Prevents denial-of-service via fake fork spam

    Security Note:
        Rate limit violations may indicate:
        - DoS attack via fake fork spam
        - Misconfigured monitoring service
        - Actual cascade of constitutional crises
        All cases should be investigated.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        source_id: str | None = None,
        signal_count: int | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Optional custom error message
            source_id: Optional source ID that exceeded the limit
            signal_count: Optional count of signals from source
        """
        if message is None:
            parts = ["Fork signal rate limit exceeded (FR85)"]
            if source_id:
                parts.append(f"source: {source_id}")
            if signal_count is not None:
                parts.append(f"signal_count: {signal_count}")
            message = " - ".join(parts)
        else:
            # Append context to custom message if not already present
            if source_id and source_id not in message:
                message = f"{message} (source: {source_id})"
            if signal_count is not None and str(signal_count) not in message:
                message = f"{message} (count: {signal_count})"
        super().__init__(message)
