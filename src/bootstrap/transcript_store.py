"""Bootstrap wiring for transcript store dependencies."""

from __future__ import annotations

from src.application.ports.transcript_store import TranscriptStoreProtocol
from src.infrastructure.stubs.transcript_store_stub import TranscriptStoreStub

_transcript_store: TranscriptStoreProtocol | None = None


def get_transcript_store() -> TranscriptStoreProtocol:
    """Get transcript store instance."""
    global _transcript_store
    if _transcript_store is None:
        _transcript_store = TranscriptStoreStub()
    return _transcript_store


def set_transcript_store(store: TranscriptStoreProtocol) -> None:
    """Set custom transcript store (testing override)."""
    global _transcript_store
    _transcript_store = store


def reset_transcript_store() -> None:
    """Reset transcript store singleton."""
    global _transcript_store
    _transcript_store = None
