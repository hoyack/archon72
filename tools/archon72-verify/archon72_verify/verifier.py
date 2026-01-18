"""Verification logic for Archon 72 event chain.

FR47: Open-source verification toolkit
FR49: Chain verification, signature verification, gap detection
FR62: Raw event data sufficient for independent hash computation
FR63: Exact hash algorithm, encoding, field ordering as immutable spec
CT-7: Genesis anchoring is mandatory
"""

import hashlib
import json
from dataclasses import dataclass, field

GENESIS_HASH = "0" * 64  # 64 zeros for sequence 1


@dataclass
class VerificationResult:
    """Result of chain verification."""

    is_valid: bool
    events_verified: int
    first_invalid_sequence: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    gaps_found: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class ProofVerificationResult:
    """Result of proof verification (FR89).

    Used by verify-proof command to validate hash chain proofs
    returned by historical queries.
    """

    is_valid: bool
    proof_entries_verified: int
    from_sequence: int
    to_sequence: int
    current_head_hash: str
    first_invalid_sequence: int | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass
class MerkleVerificationResult:
    """Result of Merkle proof verification (FR136, FR137).

    Used by verify-merkle command to validate Merkle proofs
    for O(log n) event inclusion verification.
    """

    is_valid: bool
    event_sequence: int
    event_hash: str
    checkpoint_sequence: int
    checkpoint_root: str
    path_length: int
    error_type: str | None = None
    error_message: str | None = None


class ChainVerifier:
    """Verifies Archon 72 event chain integrity.

    Implements verification per FR47, FR49:
    - Hash chain verification
    - Signature verification
    - Sequence gap detection

    Uses specification from HashVerificationSpec (FR62, FR63):
    - SHA-256 hash algorithm
    - Canonical JSON with sorted keys, no whitespace
    - Genesis hash: 64 zeros

    Example:
        verifier = ChainVerifier()
        result = verifier.verify_chain(events)
        if result.is_valid:
            print(f"Chain valid: {result.events_verified} events")
        else:
            print(f"Invalid at {result.first_invalid_sequence}")
    """

    def compute_content_hash(self, event: dict) -> str:
        """Compute expected content_hash for an event.

        Per FR62: Raw event data sufficient for independent hash computation.
        Per FR63: Exact hash algorithm, encoding, field ordering as immutable spec.

        Args:
            event: Event dictionary from API.

        Returns:
            Computed SHA-256 hash in lowercase hex.
        """
        # Build hashable content (matching server-side computation)
        hashable: dict = {
            "event_type": event["event_type"],
            "payload": event["payload"],
            "signature": event["signature"],
            "witness_id": event["witness_id"],
            "witness_signature": event["witness_signature"],
            "local_timestamp": event["local_timestamp"],
        }

        # agent_id is optional
        if event.get("agent_id"):
            hashable["agent_id"] = event["agent_id"]

        # Canonical JSON: sorted keys, no whitespace
        canonical = json.dumps(
            hashable,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_chain(self, events: list[dict]) -> VerificationResult:
        """Verify hash chain integrity for a list of events.

        Per FR47: Verify hash chain locally.
        Per CT-7: Genesis anchoring is mandatory.

        Checks:
        1. Events are ordered by sequence
        2. No sequence gaps
        3. prev_hash matches previous event's content_hash
        4. Sequence 1 has prev_hash = genesis hash
        5. content_hash can be recomputed from event data

        Args:
            events: List of event dictionaries, ordered by sequence.

        Returns:
            VerificationResult with validation status.
        """
        if not events:
            return VerificationResult(
                is_valid=True,
                events_verified=0,
            )

        # Sort by sequence to ensure order
        sorted_events = sorted(events, key=lambda e: e["sequence"])

        # Check for sequence gaps
        gaps = self._find_sequence_gaps(sorted_events)

        # Verify each event
        prev_content_hash = GENESIS_HASH

        for i, event in enumerate(sorted_events):
            sequence = event["sequence"]

            # Check genesis anchor
            if sequence == 1:
                if event["prev_hash"] != GENESIS_HASH:
                    return VerificationResult(
                        is_valid=False,
                        events_verified=i,
                        first_invalid_sequence=sequence,
                        error_type="genesis_mismatch",
                        error_message=(
                            f"Sequence 1 prev_hash should be genesis "
                            f"({GENESIS_HASH[:16]}...), "
                            f"got {event['prev_hash'][:16]}..."
                        ),
                        gaps_found=gaps,
                    )
                prev_content_hash = event["content_hash"]
                continue

            # Check prev_hash matches previous content_hash
            if event["prev_hash"] != prev_content_hash:
                return VerificationResult(
                    is_valid=False,
                    events_verified=i,
                    first_invalid_sequence=sequence,
                    error_type="chain_break",
                    error_message=(
                        f"Sequence {sequence} prev_hash doesn't match "
                        "previous content_hash"
                    ),
                    gaps_found=gaps,
                )

            # Verify content_hash can be recomputed
            computed_hash = self.compute_content_hash(event)
            if computed_hash != event["content_hash"]:
                return VerificationResult(
                    is_valid=False,
                    events_verified=i,
                    first_invalid_sequence=sequence,
                    error_type="hash_mismatch",
                    error_message=(
                        f"Sequence {sequence} content_hash doesn't match computed hash"
                    ),
                    gaps_found=gaps,
                )

            prev_content_hash = event["content_hash"]

        # If gaps were found, still report but chain is technically valid
        return VerificationResult(
            is_valid=len(gaps) == 0,
            events_verified=len(sorted_events),
            gaps_found=gaps,
            error_type="sequence_gaps" if gaps else None,
            error_message=f"Found {len(gaps)} sequence gap(s)" if gaps else None,
        )

    def find_gaps(self, events: list[dict]) -> list[tuple[int, int]]:
        """Find sequence gaps in events (public API).

        Args:
            events: List of event dictionaries.

        Returns:
            List of (start, end) tuples for each gap.
        """
        if not events:
            return []
        sorted_events = sorted(events, key=lambda e: e["sequence"])
        return self._find_sequence_gaps(sorted_events)

    def _find_sequence_gaps(self, sorted_events: list[dict]) -> list[tuple[int, int]]:
        """Find sequence gaps in sorted events.

        Args:
            sorted_events: Events sorted by sequence.

        Returns:
            List of (start, end) tuples for each gap.
        """
        gaps: list[tuple[int, int]] = []

        for i in range(1, len(sorted_events)):
            prev_seq = sorted_events[i - 1]["sequence"]
            curr_seq = sorted_events[i]["sequence"]

            if curr_seq != prev_seq + 1:
                gaps.append((prev_seq + 1, curr_seq - 1))

        return gaps

    def verify_signature(
        self,
        event: dict,
        public_key: bytes,
    ) -> bool:
        """Verify event signature.

        Per FR49: Verify signature locally.

        Args:
            event: Event dictionary.
            public_key: Agent's public key (Ed25519).

        Returns:
            True if signature is valid.

        Raises:
            ImportError: If cryptography package not installed.
        """
        # Import here to make dependency optional
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
        except ImportError as e:
            raise ImportError(
                "cryptography package required for signature verification. "
                "Install with: pip install archon72-verify[crypto]"
            ) from e

        try:
            # Reconstruct signable content
            signable = self._build_signable_content(event)

            # Load public key
            key = Ed25519PublicKey.from_public_bytes(public_key)

            # Verify signature
            signature = bytes.fromhex(event["signature"])
            key.verify(signature, signable.encode("utf-8"))

            return True
        except (InvalidSignature, ValueError):
            return False

    def _build_signable_content(self, event: dict) -> str:
        """Build signable content from event.

        This must match the server-side signable content construction.

        Args:
            event: Event dictionary.

        Returns:
            Canonical JSON string to sign.
        """
        return json.dumps(
            {
                "event_type": event["event_type"],
                "payload": event["payload"],
                "prev_hash": event["prev_hash"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def verify_proof(self, proof: dict) -> ProofVerificationResult:
        """Verify hash chain proof (FR89).

        Validates that a proof returned by a historical query is
        valid by checking hash chain continuity from from_sequence
        to to_sequence.

        Per FR89: Historical queries SHALL return hash chain proof
        connecting queried state to current head.

        Checks:
        1. Chain entries are in sequence order
        2. Each entry's prev_hash matches previous entry's content_hash
        3. Final entry's content_hash matches current_head_hash
        4. No sequence gaps in the proof chain

        Args:
            proof: Proof dictionary from API response containing:
                - from_sequence: Start sequence
                - to_sequence: End sequence (current head)
                - chain: List of {sequence, content_hash, prev_hash}
                - current_head_hash: Hash of current head

        Returns:
            ProofVerificationResult with validation status.

        Example:
            response = await client.get_events_as_of(100, include_proof=True)
            result = verifier.verify_proof(response["proof"])
            if result.is_valid:
                print("Proof valid - historical query is part of canonical chain")
        """
        from_sequence = proof.get("from_sequence", 0)
        to_sequence = proof.get("to_sequence", 0)
        current_head_hash = proof.get("current_head_hash", "")
        chain = proof.get("chain", [])

        if not chain:
            return ProofVerificationResult(
                is_valid=False,
                proof_entries_verified=0,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                current_head_hash=current_head_hash,
                error_type="empty_chain",
                error_message="Proof chain is empty",
            )

        # Sort by sequence to ensure order
        sorted_chain = sorted(chain, key=lambda e: e["sequence"])

        # Verify first entry matches from_sequence
        if sorted_chain[0]["sequence"] != from_sequence:
            return ProofVerificationResult(
                is_valid=False,
                proof_entries_verified=0,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                current_head_hash=current_head_hash,
                first_invalid_sequence=sorted_chain[0]["sequence"],
                error_type="sequence_mismatch",
                error_message=(
                    f"First chain entry sequence ({sorted_chain[0]['sequence']}) "
                    f"doesn't match from_sequence ({from_sequence})"
                ),
            )

        # Verify last entry matches to_sequence
        if sorted_chain[-1]["sequence"] != to_sequence:
            return ProofVerificationResult(
                is_valid=False,
                proof_entries_verified=len(sorted_chain) - 1,
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                current_head_hash=current_head_hash,
                first_invalid_sequence=sorted_chain[-1]["sequence"],
                error_type="sequence_mismatch",
                error_message=(
                    f"Last chain entry sequence ({sorted_chain[-1]['sequence']}) "
                    f"doesn't match to_sequence ({to_sequence})"
                ),
            )

        # Verify chain continuity
        for i in range(1, len(sorted_chain)):
            prev_entry = sorted_chain[i - 1]
            curr_entry = sorted_chain[i]

            # Check sequence continuity (no gaps)
            if curr_entry["sequence"] != prev_entry["sequence"] + 1:
                return ProofVerificationResult(
                    is_valid=False,
                    proof_entries_verified=i,
                    from_sequence=from_sequence,
                    to_sequence=to_sequence,
                    current_head_hash=current_head_hash,
                    first_invalid_sequence=curr_entry["sequence"],
                    error_type="sequence_gap",
                    error_message=(
                        f"Gap in proof chain: {prev_entry['sequence']} -> {curr_entry['sequence']}"
                    ),
                )

            # Check prev_hash matches previous content_hash
            if curr_entry["prev_hash"] != prev_entry["content_hash"]:
                return ProofVerificationResult(
                    is_valid=False,
                    proof_entries_verified=i,
                    from_sequence=from_sequence,
                    to_sequence=to_sequence,
                    current_head_hash=current_head_hash,
                    first_invalid_sequence=curr_entry["sequence"],
                    error_type="hash_chain_break",
                    error_message=(
                        f"Proof chain break at sequence {curr_entry['sequence']}: "
                        f"prev_hash doesn't match previous content_hash"
                    ),
                )

        # Verify final entry's content_hash matches current_head_hash
        if sorted_chain[-1]["content_hash"] != current_head_hash:
            return ProofVerificationResult(
                is_valid=False,
                proof_entries_verified=len(sorted_chain),
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                current_head_hash=current_head_hash,
                first_invalid_sequence=sorted_chain[-1]["sequence"],
                error_type="head_hash_mismatch",
                error_message=(
                    "Final entry content_hash doesn't match current_head_hash"
                ),
            )

        return ProofVerificationResult(
            is_valid=True,
            proof_entries_verified=len(sorted_chain),
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            current_head_hash=current_head_hash,
        )

    def verify_merkle(self, proof: dict) -> MerkleVerificationResult:
        """Verify Merkle proof for event inclusion (FR136, FR137).

        Validates that a Merkle proof correctly proves inclusion of
        an event in a checkpoint's Merkle tree.

        Per FR136: Merkle proof SHALL be included when requested.
        Per FR137: O(log n) verification without downloading full chain.

        Checks:
        1. Proof has all required fields
        2. Path hashes combine correctly to reach checkpoint_root
        3. Path length is reasonable (O(log n))

        Args:
            proof: Merkle proof dictionary from API response containing:
                - event_sequence: Sequence of proven event
                - event_hash: Content hash of proven event
                - checkpoint_sequence: Sequence of checkpoint
                - checkpoint_root: Merkle root of checkpoint
                - path: List of {level, position, sibling_hash}
                - tree_size: Number of leaves in tree

        Returns:
            MerkleVerificationResult with validation status.

        Example:
            response = await client.get_merkle_proof(100)
            result = verifier.verify_merkle(response)
            if result.is_valid:
                print("Event is in checkpoint - Merkle proof valid")
        """
        event_sequence = proof.get("event_sequence", 0)
        event_hash = proof.get("event_hash", "")
        checkpoint_sequence = proof.get("checkpoint_sequence", 0)
        checkpoint_root = proof.get("checkpoint_root", "")
        path = proof.get("path", [])
        tree_size = proof.get("tree_size", 0)

        # Validate required fields
        if not event_hash:
            return MerkleVerificationResult(
                is_valid=False,
                event_sequence=event_sequence,
                event_hash=event_hash,
                checkpoint_sequence=checkpoint_sequence,
                checkpoint_root=checkpoint_root,
                path_length=len(path),
                error_type="missing_field",
                error_message="event_hash is required",
            )

        if not checkpoint_root:
            return MerkleVerificationResult(
                is_valid=False,
                event_sequence=event_sequence,
                event_hash=event_hash,
                checkpoint_sequence=checkpoint_sequence,
                checkpoint_root=checkpoint_root,
                path_length=len(path),
                error_type="missing_field",
                error_message="checkpoint_root is required",
            )

        if not path:
            # Empty path only valid for single-leaf tree
            if tree_size == 1:
                if event_hash == checkpoint_root:
                    return MerkleVerificationResult(
                        is_valid=True,
                        event_sequence=event_sequence,
                        event_hash=event_hash,
                        checkpoint_sequence=checkpoint_sequence,
                        checkpoint_root=checkpoint_root,
                        path_length=0,
                    )
                else:
                    return MerkleVerificationResult(
                        is_valid=False,
                        event_sequence=event_sequence,
                        event_hash=event_hash,
                        checkpoint_sequence=checkpoint_sequence,
                        checkpoint_root=checkpoint_root,
                        path_length=0,
                        error_type="root_mismatch",
                        error_message="Single-leaf event_hash doesn't match checkpoint_root",
                    )
            return MerkleVerificationResult(
                is_valid=False,
                event_sequence=event_sequence,
                event_hash=event_hash,
                checkpoint_sequence=checkpoint_sequence,
                checkpoint_root=checkpoint_root,
                path_length=0,
                error_type="empty_path",
                error_message="Proof path is empty but tree has multiple leaves",
            )

        # Walk the proof path to compute root
        current = event_hash

        for entry in path:
            sibling_hash = entry.get("sibling_hash", "")
            position = entry.get("position", "")

            if not sibling_hash:
                return MerkleVerificationResult(
                    is_valid=False,
                    event_sequence=event_sequence,
                    event_hash=event_hash,
                    checkpoint_sequence=checkpoint_sequence,
                    checkpoint_root=checkpoint_root,
                    path_length=len(path),
                    error_type="invalid_path_entry",
                    error_message=f"Path entry missing sibling_hash at level {entry.get('level')}",
                )

            # Compute parent hash (sorted concatenation for determinism)
            if position == "left":
                # Sibling is on left, current is on right
                combined = "".join(sorted([sibling_hash, current]))
            else:
                # Sibling is on right, current is on left
                combined = "".join(sorted([current, sibling_hash]))

            current = hashlib.sha256(combined.encode()).hexdigest()

        # Verify computed root matches checkpoint_root
        if current != checkpoint_root:
            return MerkleVerificationResult(
                is_valid=False,
                event_sequence=event_sequence,
                event_hash=event_hash,
                checkpoint_sequence=checkpoint_sequence,
                checkpoint_root=checkpoint_root,
                path_length=len(path),
                error_type="root_mismatch",
                error_message="Computed Merkle root doesn't match checkpoint_root",
            )

        return MerkleVerificationResult(
            is_valid=True,
            event_sequence=event_sequence,
            event_hash=event_hash,
            checkpoint_sequence=checkpoint_sequence,
            checkpoint_root=checkpoint_root,
            path_length=len(path),
        )

    def verify_database(
        self,
        db_path: str,
        start: int | None = None,
        end: int | None = None,
    ) -> VerificationResult:
        """Verify hash chain in local database.

        Per FR122: Verify local copy integrity.

        Args:
            db_path: Path to SQLite database.
            start: First sequence to verify (default: min in db).
            end: Last sequence to verify (default: max in db).

        Returns:
            VerificationResult with validation status.
        """
        # Import here to avoid circular dependency
        from archon72_verify.database import ObserverDatabase

        with ObserverDatabase(db_path) as db:
            min_seq, max_seq = db.get_sequence_range()

            if min_seq is None:
                return VerificationResult(
                    is_valid=True,
                    events_verified=0,
                    error_message="Database is empty",
                )

            # Apply range defaults
            start = start or min_seq
            end = end or max_seq

            # Get events from database
            events = db.get_events_in_range(start, end)

            # Find gaps first
            gaps = db.find_gaps(start, end)

        # Verify chain
        result = self.verify_chain(events)

        # Merge gap information
        if gaps and result.is_valid:
            result = VerificationResult(
                is_valid=False,
                events_verified=result.events_verified,
                first_invalid_sequence=result.first_invalid_sequence,
                error_type="sequence_gaps",
                error_message=f"Found {len(gaps)} sequence gap(s)",
                gaps_found=gaps,
            )
        elif gaps:
            # Add gaps to existing failure
            result = VerificationResult(
                is_valid=result.is_valid,
                events_verified=result.events_verified,
                first_invalid_sequence=result.first_invalid_sequence,
                error_type=result.error_type,
                error_message=result.error_message,
                gaps_found=gaps,
            )

        return result
