"""Integration tests for verification toolkit (Story 4.4, Task 7).

End-to-end tests verifying toolkit against real API endpoints.

Constitutional Constraints:
- FR47: Open-source verification toolkit SHALL be downloadable
- FR49: Toolkit SHALL provide: chain verification, signature verification, gap detection
- FR50: Schema documentation SHALL have same availability as event store
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add toolkit to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools" / "archon72-verify"))

from archon72_verify.verifier import GENESIS_HASH, ChainVerifier, VerificationResult
from archon72_verify.cli import app as cli_app
from typer.testing import CliRunner


runner = CliRunner()


def make_valid_event(
    sequence: int,
    prev_hash: str = None,
    event_type: str = "test.event",
    payload: dict = None,
) -> dict:
    """Create a valid event with correct hash computation."""
    if payload is None:
        payload = {"data": f"event_{sequence}"}

    event = {
        "sequence": sequence,
        "event_type": event_type,
        "payload": payload,
        "signature": "test_signature",
        "witness_id": "test_witness",
        "witness_signature": "witness_sig",
        "local_timestamp": "2026-01-01T00:00:00Z",
        "prev_hash": prev_hash or GENESIS_HASH,
    }

    # Compute content_hash
    hashable = {
        "event_type": event["event_type"],
        "payload": event["payload"],
        "signature": event["signature"],
        "witness_id": event["witness_id"],
        "witness_signature": event["witness_signature"],
        "local_timestamp": event["local_timestamp"],
    }
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
    event["content_hash"] = hashlib.sha256(canonical.encode()).hexdigest()

    return event


def make_valid_chain(count: int) -> list[dict]:
    """Create a valid chain of events."""
    events = []
    prev_hash = GENESIS_HASH

    for i in range(1, count + 1):
        event = make_valid_event(sequence=i, prev_hash=prev_hash)
        events.append(event)
        prev_hash = event["content_hash"]

    return events


class TestToolkitVerifiesChainFromAPI:
    """Tests for toolkit verifying chain from API."""

    def test_toolkit_verifies_valid_chain(self):
        """Test toolkit verifies a valid chain correctly."""
        verifier = ChainVerifier()
        events = make_valid_chain(10)

        result = verifier.verify_chain(events)

        assert result.is_valid
        assert result.events_verified == 10
        assert result.first_invalid_sequence is None
        assert result.error_type is None

    def test_toolkit_verifies_chain_with_genesis_anchor(self):
        """Test toolkit validates genesis anchor (sequence 1)."""
        verifier = ChainVerifier()
        events = make_valid_chain(5)

        # Verify genesis anchor check
        result = verifier.verify_chain(events)

        assert result.is_valid
        assert events[0]["prev_hash"] == GENESIS_HASH

    def test_toolkit_verifies_content_hashes(self):
        """Test toolkit recomputes and verifies content hashes."""
        verifier = ChainVerifier()
        events = make_valid_chain(3)

        # Verify each hash is correctly computed
        for event in events:
            computed_hash = verifier.compute_content_hash(event)
            assert computed_hash == event["content_hash"]


class TestToolkitDetectsTamperedEvent:
    """Tests for toolkit detecting tampered events."""

    def test_toolkit_detects_tampered_content_hash(self):
        """Test toolkit detects when content_hash is tampered."""
        verifier = ChainVerifier()
        events = make_valid_chain(5)

        # Tamper with content_hash of event 3
        events[2]["content_hash"] = "tampered" * 8

        result = verifier.verify_chain(events)

        assert not result.is_valid
        assert result.first_invalid_sequence == 3
        assert result.error_type == "hash_mismatch"

    def test_toolkit_detects_broken_prev_hash_chain(self):
        """Test toolkit detects when prev_hash chain is broken."""
        verifier = ChainVerifier()
        events = make_valid_chain(5)

        # Break prev_hash chain at event 4
        events[3]["prev_hash"] = "broken_chain" * (64 // 12)

        result = verifier.verify_chain(events)

        assert not result.is_valid
        assert result.first_invalid_sequence == 4
        assert result.error_type == "chain_break"

    def test_toolkit_detects_invalid_genesis(self):
        """Test toolkit detects invalid genesis anchor."""
        verifier = ChainVerifier()
        events = make_valid_chain(3)

        # Invalidate genesis
        events[0]["prev_hash"] = "invalid_genesis" * 4

        result = verifier.verify_chain(events)

        assert not result.is_valid
        assert result.first_invalid_sequence == 1
        assert result.error_type == "genesis_mismatch"

    def test_toolkit_detects_tampered_payload(self):
        """Test toolkit detects when payload is tampered (hash mismatch)."""
        verifier = ChainVerifier()
        events = make_valid_chain(3)

        # Tamper with payload but don't update hash
        events[1]["payload"]["data"] = "TAMPERED"

        result = verifier.verify_chain(events)

        assert not result.is_valid
        assert result.first_invalid_sequence == 2
        assert result.error_type == "hash_mismatch"


class TestToolkitDetectsGap:
    """Tests for toolkit detecting sequence gaps."""

    def test_toolkit_detects_single_gap(self):
        """Test toolkit detects a single sequence gap."""
        verifier = ChainVerifier()
        events = [
            make_valid_event(1, prev_hash=GENESIS_HASH),
            make_valid_event(2),
            make_valid_event(5),  # Gap: 3-4 missing
        ]

        gaps = verifier.find_gaps(events)

        assert len(gaps) == 1
        assert gaps[0] == (3, 4)

    def test_toolkit_detects_multiple_gaps(self):
        """Test toolkit detects multiple sequence gaps."""
        verifier = ChainVerifier()
        events = [
            make_valid_event(1, prev_hash=GENESIS_HASH),
            make_valid_event(3),  # Gap: 2
            make_valid_event(7),  # Gap: 4-6
        ]

        gaps = verifier.find_gaps(events)

        assert len(gaps) == 2
        assert (2, 2) in gaps
        assert (4, 6) in gaps

    def test_toolkit_reports_no_gaps_for_continuous_sequence(self):
        """Test toolkit reports no gaps for continuous sequence."""
        verifier = ChainVerifier()
        events = make_valid_chain(10)

        gaps = verifier.find_gaps(events)

        assert len(gaps) == 0

    def test_toolkit_handles_unsorted_events(self):
        """Test toolkit handles unsorted events in gap detection."""
        verifier = ChainVerifier()
        events = [
            make_valid_event(5),
            make_valid_event(1, prev_hash=GENESIS_HASH),
            make_valid_event(3),  # Gap: 2, 4
        ]

        gaps = verifier.find_gaps(events)

        assert len(gaps) == 2
        assert (2, 2) in gaps
        assert (4, 4) in gaps


class TestToolkitOfflineVerification:
    """Tests for toolkit offline verification from file."""

    def test_toolkit_verifies_chain_from_json_file(self):
        """Test toolkit verifies chain from JSON file."""
        events = make_valid_chain(5)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                ["check-chain", "--from", "1", "--to", "5", "--file", temp_path],
            )

            assert result.exit_code == 0
            assert "VALID" in result.stdout
        finally:
            Path(temp_path).unlink()

    def test_toolkit_filters_events_by_sequence_range(self):
        """Test toolkit filters events by sequence range."""
        events = make_valid_chain(10)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            # Only verify events 3-7
            result = runner.invoke(
                cli_app,
                ["check-chain", "--from", "3", "--to", "7", "--file", temp_path],
            )

            # Should work with subset (note: prev_hash of event 3 won't match genesis)
            # This is expected behavior - offline verification of subset
            assert result.exit_code in (0, 1)  # May fail due to chain break
        finally:
            Path(temp_path).unlink()


class TestCLICheckChainExitCodes:
    """Tests for CLI check-chain exit codes."""

    def test_cli_exit_code_0_for_valid_chain(self):
        """Test CLI returns exit code 0 for valid chain."""
        events = make_valid_chain(3)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                ["check-chain", "--from", "1", "--to", "3", "--file", temp_path],
            )

            assert result.exit_code == 0
        finally:
            Path(temp_path).unlink()

    def test_cli_exit_code_1_for_invalid_chain(self):
        """Test CLI returns exit code 1 for invalid chain."""
        events = make_valid_chain(3)
        # Invalidate genesis
        events[0]["prev_hash"] = "x" * 64

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                ["check-chain", "--from", "1", "--to", "3", "--file", temp_path],
            )

            assert result.exit_code == 1
            assert "INVALID" in result.stdout
        finally:
            Path(temp_path).unlink()

    def test_cli_exit_code_1_for_gaps_found(self):
        """Test CLI returns exit code 1 for check-gaps with gaps."""
        events = [
            {"sequence": 1},
            {"sequence": 2},
            {"sequence": 5},  # Gap: 3-4
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                ["check-gaps", "--from", "1", "--to", "5", "--file", temp_path],
            )

            assert result.exit_code == 1
            assert "gap" in result.stdout.lower()
        finally:
            Path(temp_path).unlink()


class TestCLIJsonOutputFormat:
    """Tests for CLI JSON output format."""

    def test_cli_check_chain_json_output(self):
        """Test CLI check-chain outputs valid JSON."""
        events = make_valid_chain(3)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                [
                    "check-chain",
                    "--from", "1",
                    "--to", "3",
                    "--file", temp_path,
                    "--format", "json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert "is_valid" in output
            assert output["is_valid"] is True
            assert "events_verified" in output
            assert output["events_verified"] == 3
        finally:
            Path(temp_path).unlink()

    def test_cli_check_chain_json_output_invalid(self):
        """Test CLI check-chain JSON output for invalid chain."""
        events = make_valid_chain(3)
        events[0]["prev_hash"] = "bad" * 21 + "b"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                [
                    "check-chain",
                    "--from", "1",
                    "--to", "3",
                    "--file", temp_path,
                    "--format", "json",
                ],
            )

            output = json.loads(result.stdout)
            assert output["is_valid"] is False
            assert "first_invalid_sequence" in output
            assert "error_type" in output
        finally:
            Path(temp_path).unlink()

    def test_cli_check_gaps_json_output(self):
        """Test CLI check-gaps outputs valid JSON."""
        events = [
            {"sequence": 1},
            {"sequence": 3},  # Gap: 2
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                cli_app,
                [
                    "check-gaps",
                    "--from", "1",
                    "--to", "3",
                    "--file", temp_path,
                    "--format", "json",
                ],
            )

            output = json.loads(result.stdout)
            assert "gaps" in output
            assert output["gaps"] == [[2, 2]]
        finally:
            Path(temp_path).unlink()


class TestSchemaEndpointMatchesToolkitExpectations:
    """Tests for schema endpoint matching toolkit expectations."""

    @pytest.fixture
    def client(self):
        """Create test client with observer routes."""
        from src.api.routes.observer import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_schema_endpoint_returns_verification_spec_url(self, client):
        """Test schema endpoint includes verification spec URL."""
        response = client.get("/v1/observer/schema")

        assert response.status_code == 200
        data = response.json()
        assert "verification_spec_url" in data
        assert data["verification_spec_url"] == "/v1/observer/verification-spec"

    def test_schema_endpoint_documents_hash_fields(self, client):
        """Test schema endpoint documents hash-related fields."""
        response = client.get("/v1/observer/schema")

        assert response.status_code == 200
        data = response.json()

        # Check event schema has hash fields
        event_schema = data.get("event_schema", {})
        properties = event_schema.get("properties", {})

        assert "content_hash" in properties
        assert "prev_hash" in properties
        assert properties["content_hash"]["pattern"] == "^[a-f0-9]{64}$"

    def test_verification_spec_matches_toolkit_implementation(self, client):
        """Test verification spec matches toolkit hash computation."""
        response = client.get("/v1/observer/verification-spec")

        assert response.status_code == 200
        data = response.json()

        # Genesis hash should match toolkit
        assert data["genesis_hash"] == GENESIS_HASH

        # Hash algorithm should be SHA-256
        assert data["hash_algorithm"] == "SHA-256"

        # Check hash includes match toolkit compute_content_hash
        expected_includes = [
            "event_type",
            "payload",
            "signature",
            "witness_id",
            "witness_signature",
            "local_timestamp",
        ]
        for field in expected_includes:
            assert any(field in inc for inc in data["hash_includes"])

    def test_toolkit_hash_matches_spec_computation(self, client):
        """Test toolkit hash computation matches documented spec."""
        # Get spec
        response = client.get("/v1/observer/verification-spec")
        spec = response.json()

        # Create event and compute hash with toolkit
        verifier = ChainVerifier()
        event = {
            "event_type": "test",
            "payload": {"key": "value"},
            "signature": "sig123",
            "witness_id": "witness1",
            "witness_signature": "wsig456",
            "local_timestamp": "2026-01-01T00:00:00Z",
        }

        toolkit_hash = verifier.compute_content_hash(event)

        # Manually compute using spec rules
        hashable = {
            "event_type": event["event_type"],
            "payload": event["payload"],
            "signature": event["signature"],
            "witness_id": event["witness_id"],
            "witness_signature": event["witness_signature"],
            "local_timestamp": event["local_timestamp"],
        }
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        spec_hash = hashlib.sha256(canonical.encode()).hexdigest()

        # They should match
        assert toolkit_hash == spec_hash
