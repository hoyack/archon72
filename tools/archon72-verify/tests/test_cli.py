"""Tests for CLI (Task 4).

Tests for CLI commands: check-chain, verify-signature, check-gaps.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from archon72_verify.cli import app
from archon72_verify.verifier import GENESIS_HASH, VerificationResult


runner = CliRunner()


class TestCLIVersion:
    """Tests for version command."""

    def test_cli_version_command(self):
        """Verify --version flag shows version."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "archon72-verify version" in result.stdout
        assert "0.1.0" in result.stdout

    def test_cli_version_short_flag(self):
        """Verify -v flag shows version."""
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0
        assert "archon72-verify version" in result.stdout


class TestCLICheckChain:
    """Tests for check-chain command."""

    def test_cli_check_chain_command_exists(self):
        """Verify check-chain command exists."""
        result = runner.invoke(app, ["check-chain", "--help"])

        assert result.exit_code == 0
        assert "check-chain" in result.stdout
        assert "--from" in result.stdout
        assert "--to" in result.stdout

    def test_cli_check_chain_offline_mode(self):
        """Verify offline mode with file input."""
        # Create temp file with valid chain
        events = []
        prev_hash = GENESIS_HASH
        for i in range(1, 4):
            import hashlib

            hashable = {
                "event_type": "test",
                "payload": {"n": i},
                "signature": "sig",
                "witness_id": "w",
                "witness_signature": "ws",
                "local_timestamp": "2026-01-01T00:00:00Z",
            }
            canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
            content_hash = hashlib.sha256(canonical.encode()).hexdigest()

            events.append(
                {
                    "sequence": i,
                    "event_type": "test",
                    "payload": {"n": i},
                    "signature": "sig",
                    "witness_id": "w",
                    "witness_signature": "ws",
                    "local_timestamp": "2026-01-01T00:00:00Z",
                    "prev_hash": prev_hash,
                    "content_hash": content_hash,
                }
            )
            prev_hash = content_hash

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                ["check-chain", "--from", "1", "--to", "3", "--file", temp_path],
            )

            assert result.exit_code == 0
            assert "VALID" in result.stdout
            assert "3 events" in result.stdout
        finally:
            Path(temp_path).unlink()

    def test_cli_check_chain_json_output(self):
        """Verify JSON output format."""
        # Create temp file with events
        events = []
        prev_hash = GENESIS_HASH
        import hashlib

        hashable = {
            "event_type": "test",
            "payload": {},
            "signature": "sig",
            "witness_id": "w",
            "witness_signature": "ws",
            "local_timestamp": "2026-01-01T00:00:00Z",
        }
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()

        events.append(
            {
                "sequence": 1,
                "event_type": "test",
                "payload": {},
                "signature": "sig",
                "witness_id": "w",
                "witness_signature": "ws",
                "local_timestamp": "2026-01-01T00:00:00Z",
                "prev_hash": prev_hash,
                "content_hash": content_hash,
            }
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                [
                    "check-chain",
                    "--from",
                    "1",
                    "--to",
                    "1",
                    "--file",
                    temp_path,
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["is_valid"] is True
            assert output["events_verified"] == 1
        finally:
            Path(temp_path).unlink()

    def test_cli_check_chain_invalid_exit_code(self):
        """Verify exit code 1 for invalid chain."""
        # Create temp file with invalid chain
        events = [
            {
                "sequence": 1,
                "event_type": "test",
                "payload": {},
                "signature": "sig",
                "witness_id": "w",
                "witness_signature": "ws",
                "local_timestamp": "2026-01-01T00:00:00Z",
                "prev_hash": "wrong" * 16,  # Invalid genesis
                "content_hash": "abc" * 21 + "a",
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                ["check-chain", "--from", "1", "--to", "1", "--file", temp_path],
            )

            assert result.exit_code == 1
            assert "INVALID" in result.stdout
        finally:
            Path(temp_path).unlink()


class TestCLIVerifySignature:
    """Tests for verify-signature command."""

    def test_cli_verify_signature_command_exists(self):
        """Verify verify-signature command exists."""
        result = runner.invoke(app, ["verify-signature", "--help"])

        assert result.exit_code == 0
        assert "verify-signature" in result.stdout

    @patch("archon72_verify.cli.ObserverClient")
    def test_cli_verify_signature_calls_api(self, mock_client_class):
        """Verify command calls API for event."""
        mock_client = AsyncMock()
        mock_client.get_event_by_id.return_value = {
            "event_id": "test-id",
            "sequence": 1,
        }
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            app,
            ["verify-signature", "test-id", "--api-url", "http://test"],
        )

        # Should succeed (placeholder implementation)
        assert result.exit_code == 0
        mock_client.get_event_by_id.assert_called_once_with("test-id")


class TestCLICheckGaps:
    """Tests for check-gaps command."""

    def test_cli_check_gaps_command_exists(self):
        """Verify check-gaps command exists."""
        result = runner.invoke(app, ["check-gaps", "--help"])

        assert result.exit_code == 0
        assert "check-gaps" in result.stdout
        assert "--from" in result.stdout
        assert "--to" in result.stdout

    def test_cli_check_gaps_no_gaps(self):
        """Verify no gaps returns success."""
        events = [
            {"sequence": 1},
            {"sequence": 2},
            {"sequence": 3},
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(events, f)
            temp_path = f.name

        try:
            result = runner.invoke(
                app,
                ["check-gaps", "--from", "1", "--to", "3", "--file", temp_path],
            )

            assert result.exit_code == 0
            assert "No gaps found" in result.stdout
        finally:
            Path(temp_path).unlink()

    def test_cli_check_gaps_with_gaps(self):
        """Verify gaps are reported."""
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
                app,
                ["check-gaps", "--from", "1", "--to", "5", "--file", temp_path],
            )

            assert result.exit_code == 1
            assert "gap" in result.stdout.lower()
            assert "3" in result.stdout and "4" in result.stdout
        finally:
            Path(temp_path).unlink()

    def test_cli_check_gaps_json_output(self):
        """Verify JSON output format."""
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
                app,
                [
                    "check-gaps",
                    "--from",
                    "1",
                    "--to",
                    "3",
                    "--file",
                    temp_path,
                    "--format",
                    "json",
                ],
            )

            # JSON output regardless of exit code
            output = json.loads(result.stdout)
            assert "gaps" in output
            assert output["gaps"] == [[2, 2]]
        finally:
            Path(temp_path).unlink()


# =============================================================================
# Export Command Tests (Story 4.7 - FR139, FR140)
# =============================================================================


class TestCLIExport:
    """Tests for export command (FR139)."""

    def test_cli_export_command_exists(self):
        """Verify export command exists."""
        result = runner.invoke(app, ["export", "--help"])

        assert result.exit_code == 0
        assert "export" in result.stdout
        assert "--output" in result.stdout
        assert "--format" in result.stdout

    def test_cli_export_has_sequence_options(self):
        """Verify export has sequence filter options."""
        result = runner.invoke(app, ["export", "--help"])

        assert "--from-seq" in result.stdout
        assert "--to-seq" in result.stdout

    def test_cli_export_has_date_options(self):
        """Verify export has date filter options."""
        result = runner.invoke(app, ["export", "--help"])

        assert "--from-date" in result.stdout
        assert "--to-date" in result.stdout

    def test_cli_export_has_event_type_option(self):
        """Verify export has event type filter option."""
        result = runner.invoke(app, ["export", "--help"])

        assert "--event-type" in result.stdout

    def test_cli_export_format_options(self):
        """Verify export supports jsonl and csv formats."""
        result = runner.invoke(app, ["export", "--help"])

        assert "jsonl" in result.stdout
        assert "csv" in result.stdout


class TestCLIAttestation:
    """Tests for attestation command (FR140)."""

    def test_cli_attestation_command_exists(self):
        """Verify attestation command exists."""
        result = runner.invoke(app, ["attestation", "--help"])

        assert result.exit_code == 0
        assert "attestation" in result.stdout

    def test_cli_attestation_requires_sequence_range(self):
        """Verify attestation requires sequence range parameters."""
        result = runner.invoke(app, ["attestation", "--help"])

        assert "--from-seq" in result.stdout
        assert "--to-seq" in result.stdout

    def test_cli_attestation_has_output_option(self):
        """Verify attestation has output file option."""
        result = runner.invoke(app, ["attestation", "--help"])

        assert "--output" in result.stdout

    def test_cli_attestation_has_format_option(self):
        """Verify attestation has format option."""
        result = runner.invoke(app, ["attestation", "--help"])

        assert "--format" in result.stdout


# =============================================================================
# Local Database Commands Tests (Story 4.10 - FR122, FR123)
# =============================================================================


class TestCLIInitDb:
    """Tests for init-db command (AC4)."""

    def test_cli_init_db_command_exists(self):
        """Verify init-db command exists."""
        result = runner.invoke(app, ["init-db", "--help"])

        assert result.exit_code == 0
        assert "init-db" in result.stdout
        assert "Initialize local observer database" in result.stdout

    def test_cli_init_db_creates_database(self):
        """AC4: init-db creates the required schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            result = runner.invoke(app, ["init-db", str(db_path)])

            assert result.exit_code == 0
            assert "initialized" in result.stdout.lower()
            assert db_path.exists()

    def test_cli_init_db_warns_on_existing(self):
        """Verify warning when database already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create file first
            db_path.touch()

            # Should warn but not error
            result = runner.invoke(app, ["init-db", str(db_path)], input="y\n")

            assert result.exit_code == 0
            assert "Warning" in result.stdout or "already exists" in result.stdout


class TestCLICheckGapsLocalDb:
    """Tests for check-gaps with --local-db (FR122, FR123)."""

    def test_cli_check_gaps_local_db_option_exists(self):
        """Verify --local-db option exists."""
        result = runner.invoke(app, ["check-gaps", "--help"])

        assert "--local-db" in result.stdout

    def test_cli_check_gaps_with_local_db(self):
        """AC1: check-gaps --local-db detects gaps in local copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archon72_verify.database import ObserverDatabase

            db_path = Path(tmpdir) / "test.db"

            # Create database with gaps
            with ObserverDatabase(db_path) as db:
                db.init_schema()
                for seq in [100, 101, 104, 105]:
                    db.insert_event({
                        "event_id": f"evt-{seq}",
                        "sequence": seq,
                        "event_type": "test",
                        "payload": {},
                        "content_hash": f"hash_{seq}",
                        "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                        "signature": "sig",
                        "agent_id": "agent",
                        "witness_id": "witness",
                        "witness_signature": "wsig",
                        "local_timestamp": "2026-01-01T00:00:00Z",
                        "authority_timestamp": None,
                        "hash_algorithm_version": "1.0",
                        "sig_alg_version": "ed25519-v1",
                    })

            result = runner.invoke(
                app,
                ["check-gaps", "--local-db", str(db_path)],
            )

            # Should find gap at 102-103
            assert result.exit_code == 1
            assert "102" in result.stdout
            assert "103" in result.stdout

    def test_cli_check_gaps_local_db_no_gaps(self):
        """Verify no gaps returns success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archon72_verify.database import ObserverDatabase

            db_path = Path(tmpdir) / "test.db"

            # Create database without gaps
            with ObserverDatabase(db_path) as db:
                db.init_schema()
                for seq in [1, 2, 3, 4, 5]:
                    db.insert_event({
                        "event_id": f"evt-{seq}",
                        "sequence": seq,
                        "event_type": "test",
                        "payload": {},
                        "content_hash": f"hash_{seq}",
                        "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                        "signature": "sig",
                        "agent_id": "agent",
                        "witness_id": "witness",
                        "witness_signature": "wsig",
                        "local_timestamp": "2026-01-01T00:00:00Z",
                        "authority_timestamp": None,
                        "hash_algorithm_version": "1.0",
                        "sig_alg_version": "ed25519-v1",
                    })

            result = runner.invoke(
                app,
                ["check-gaps", "--local-db", str(db_path)],
            )

            assert result.exit_code == 0
            assert "No gaps" in result.stdout

    def test_cli_check_gaps_local_db_reports_count(self):
        """AC2: Gap detection reports total count of missing events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archon72_verify.database import ObserverDatabase

            db_path = Path(tmpdir) / "test.db"

            # Create database with gap of 3 events (7-9)
            with ObserverDatabase(db_path) as db:
                db.init_schema()
                for seq in [1, 2, 3, 4, 5, 6, 10]:
                    db.insert_event({
                        "event_id": f"evt-{seq}",
                        "sequence": seq,
                        "event_type": "test",
                        "payload": {},
                        "content_hash": f"hash_{seq}",
                        "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                        "signature": "sig",
                        "agent_id": "agent",
                        "witness_id": "witness",
                        "witness_signature": "wsig",
                        "local_timestamp": "2026-01-01T00:00:00Z",
                        "authority_timestamp": None,
                        "hash_algorithm_version": "1.0",
                        "sig_alg_version": "ed25519-v1",
                    })

            result = runner.invoke(
                app,
                ["check-gaps", "--local-db", str(db_path)],
            )

            # Should report 3 missing events (7, 8, 9)
            assert "3 missing" in result.stdout.lower() or "3" in result.stdout

    def test_cli_check_gaps_local_db_json_output(self):
        """Verify JSON output format for local-db gap detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archon72_verify.database import ObserverDatabase

            db_path = Path(tmpdir) / "test.db"

            with ObserverDatabase(db_path) as db:
                db.init_schema()
                for seq in [1, 3]:  # Gap at 2
                    db.insert_event({
                        "event_id": f"evt-{seq}",
                        "sequence": seq,
                        "event_type": "test",
                        "payload": {},
                        "content_hash": f"hash_{seq}",
                        "prev_hash": f"hash_{seq-1}" if seq > 1 else "0" * 64,
                        "signature": "sig",
                        "agent_id": "agent",
                        "witness_id": "witness",
                        "witness_signature": "wsig",
                        "local_timestamp": "2026-01-01T00:00:00Z",
                        "authority_timestamp": None,
                        "hash_algorithm_version": "1.0",
                        "sig_alg_version": "ed25519-v1",
                    })

            result = runner.invoke(
                app,
                ["check-gaps", "--local-db", str(db_path), "--format", "json"],
            )

            output = json.loads(result.stdout)
            assert "gaps" in output
            assert "total_gaps" in output
            assert "total_missing_events" in output
            assert output["total_gaps"] == 1
            assert output["total_missing_events"] == 1


class TestCLIFillGaps:
    """Tests for fill-gaps command (AC3)."""

    def test_cli_fill_gaps_command_exists(self):
        """Verify fill-gaps command exists."""
        result = runner.invoke(app, ["fill-gaps", "--help"])

        assert result.exit_code == 0
        assert "fill-gaps" in result.stdout
        assert "--local-db" in result.stdout

    def test_cli_fill_gaps_requires_local_db(self):
        """Verify fill-gaps requires --local-db option."""
        result = runner.invoke(app, ["fill-gaps", "--help"])

        assert "--local-db" in result.stdout
        # Should be required
        assert "-d" in result.stdout


class TestCLISync:
    """Tests for sync command."""

    def test_cli_sync_command_exists(self):
        """Verify sync command exists."""
        result = runner.invoke(app, ["sync", "--help"])

        assert result.exit_code == 0
        assert "sync" in result.stdout
        assert "--local-db" in result.stdout

    def test_cli_sync_has_batch_size_option(self):
        """Verify sync has batch-size option."""
        result = runner.invoke(app, ["sync", "--help"])

        assert "--batch-size" in result.stdout
