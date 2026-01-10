"""Integration tests for regulatory export (Story 4.7).

Tests end-to-end export functionality (FR139, FR140).

Constitutional Constraints:
- FR44: No authentication required
- FR48: Rate limits identical for all users
- FR139: Export SHALL support structured audit format (JSON Lines, CSV)
- FR140: Third-party attestation interface with attestation metadata
"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.observer import router
from src.domain.events import Event
from src.infrastructure.stubs.event_store_stub import EventStoreStub


def create_test_event(
    sequence: int,
    event_type: str = "test.event",
    payload: dict[str, Any] | None = None,
    authority_timestamp: datetime | None = None,
) -> Event:
    """Create a test event with given parameters."""
    ts = authority_timestamp or datetime.now(timezone.utc)
    return Event(
        event_id=uuid4(),
        sequence=sequence,
        event_type=event_type,
        payload=payload or {"test": "data"},
        prev_hash="0" * 64 if sequence == 1 else "a" * 64,
        content_hash="b" * 64,
        signature="sig123",
        witness_id="witness-001",
        witness_signature="wsig123",
        local_timestamp=ts,
        authority_timestamp=ts,
    )


class TestExportEndpointIntegration:
    """Integration tests for export endpoint (FR139)."""

    @pytest.fixture
    def app_with_test_events(self):
        """Create FastAPI app with test events in store."""
        from src.api.dependencies.observer import (
            get_event_store,
            get_export_service,
            get_observer_service,
        )
        from src.application.services.export_service import ExportService
        from src.application.services.observer_service import ObserverService

        # Create a store with test events
        store = EventStoreStub()
        for i in range(1, 6):
            event = create_test_event(
                sequence=i,
                event_type=f"type_{i % 3}",
                authority_timestamp=datetime(2026, 1, i, 12, 0, 0, tzinfo=timezone.utc),
            )
            store.add_event(event)

        # Override dependencies
        app = FastAPI()
        app.include_router(router)

        def _get_event_store():
            return store

        def _get_observer_service():
            return ObserverService(
                event_store=store,
                halt_checker=None,
                checkpoint_repo=None,
                merkle_service=None,
            )

        def _get_export_service():
            return ExportService(event_store=store)

        app.dependency_overrides[get_event_store] = _get_event_store
        app.dependency_overrides[get_observer_service] = _get_observer_service
        app.dependency_overrides[get_export_service] = _get_export_service

        return app

    @pytest.fixture
    def client(self, app_with_test_events):
        """Create test client."""
        return TestClient(app_with_test_events)

    def test_export_endpoint_returns_jsonl_by_default(self, client) -> None:
        """Verify export returns JSON Lines format by default (FR139)."""
        response = client.get("/v1/observer/export")

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/x-ndjson"

    def test_export_endpoint_returns_csv_when_requested(self, client) -> None:
        """Verify export returns CSV format when requested (FR139)."""
        response = client.get("/v1/observer/export?format=csv")

        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/csv; charset=utf-8"

    def test_export_jsonl_content_is_valid_json(self, client) -> None:
        """Verify JSONL content is valid JSON per line."""
        response = client.get("/v1/observer/export?format=jsonl")

        content = response.text
        lines = [line for line in content.strip().split("\n") if line]

        assert len(lines) == 5
        for line in lines:
            # Each line should be valid JSON
            parsed = json.loads(line)
            assert "event_id" in parsed
            assert "sequence" in parsed
            assert "content_hash" in parsed

    def test_export_csv_content_has_header(self, client) -> None:
        """Verify CSV content starts with header row."""
        response = client.get("/v1/observer/export?format=csv")

        content = response.text
        reader = csv.reader(io.StringIO(content))
        header = next(reader)

        assert "event_id" in header
        assert "sequence" in header
        assert "content_hash" in header
        assert "prev_hash" in header
        assert "witness_id" in header

    def test_export_no_authentication_required(self, client) -> None:
        """Verify export requires no authentication (FR44)."""
        # No auth headers
        response = client.get("/v1/observer/export")

        # Should succeed without auth
        assert response.status_code == 200

    def test_export_includes_verification_fields(self, client) -> None:
        """Verify export includes all hash chain verification fields (CT-11)."""
        response = client.get("/v1/observer/export?format=jsonl")

        line = response.text.strip().split("\n")[0]
        event = json.loads(line)

        # Required verification fields
        assert "content_hash" in event
        assert "prev_hash" in event
        assert "signature" in event
        assert "witness_id" in event
        assert "witness_signature" in event

    def test_export_includes_witness_attribution(self, client) -> None:
        """Verify export includes witness attribution (CT-12)."""
        response = client.get("/v1/observer/export?format=jsonl")

        line = response.text.strip().split("\n")[0]
        event = json.loads(line)

        assert "witness_id" in event
        assert "witness_signature" in event
        assert event["witness_id"] is not None

    def test_export_with_sequence_filter(self, client) -> None:
        """Verify export respects sequence range filter."""
        response = client.get(
            "/v1/observer/export?start_sequence=2&end_sequence=4"
        )

        content = response.text
        lines = [line for line in content.strip().split("\n") if line]

        assert len(lines) == 3
        for line in lines:
            event = json.loads(line)
            assert 2 <= event["sequence"] <= 4

    def test_export_with_date_filter(self, client) -> None:
        """Verify export respects date range filter."""
        response = client.get(
            "/v1/observer/export"
            "?start_date=2026-01-02T00:00:00Z"
            "&end_date=2026-01-04T23:59:59Z"
        )

        content = response.text
        lines = [line for line in content.strip().split("\n") if line]

        assert len(lines) == 3  # Events 2, 3, 4


class TestAttestationEndpointIntegration:
    """Integration tests for attestation endpoint (FR140)."""

    @pytest.fixture
    def app_with_test_events(self):
        """Create FastAPI app with test events in store."""
        from src.api.dependencies.observer import (
            get_event_store,
            get_export_service,
            get_observer_service,
        )
        from src.application.services.export_service import ExportService
        from src.application.services.observer_service import ObserverService

        store = EventStoreStub()
        for i in range(1, 6):
            event = create_test_event(sequence=i)
            store.add_event(event)

        app = FastAPI()
        app.include_router(router)

        def _get_event_store():
            return store

        def _get_observer_service():
            return ObserverService(
                event_store=store,
                halt_checker=None,
                checkpoint_repo=None,
                merkle_service=None,
            )

        def _get_export_service():
            return ExportService(event_store=store)

        app.dependency_overrides[get_event_store] = _get_event_store
        app.dependency_overrides[get_observer_service] = _get_observer_service
        app.dependency_overrides[get_export_service] = _get_export_service

        return app

    @pytest.fixture
    def client(self, app_with_test_events):
        """Create test client."""
        return TestClient(app_with_test_events)

    def test_attestation_endpoint_returns_metadata(self, client) -> None:
        """Verify attestation returns metadata (FR140)."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=1&end_sequence=5"
        )

        assert response.status_code == 200
        metadata = response.json()

        assert "export_id" in metadata
        assert "exported_at" in metadata
        assert "sequence_start" in metadata
        assert "sequence_end" in metadata
        assert "event_count" in metadata
        assert "chain_hash_at_export" in metadata
        assert "exporter_id" in metadata

    def test_attestation_requires_sequence_range(self, client) -> None:
        """Verify attestation requires start/end sequence."""
        # Missing parameters
        response = client.get("/v1/observer/export/attestation")

        assert response.status_code == 422  # Validation error

    def test_attestation_validates_sequence_order(self, client) -> None:
        """Verify attestation validates start <= end sequence."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=5&end_sequence=1"
        )

        assert response.status_code == 400
        assert "end_sequence must be >= start_sequence" in response.json()["detail"]

    def test_attestation_includes_correct_sequence_range(self, client) -> None:
        """Verify attestation includes requested sequence range."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=2&end_sequence=4"
        )

        metadata = response.json()
        assert metadata["sequence_start"] == 2
        assert metadata["sequence_end"] == 4

    def test_attestation_includes_event_count(self, client) -> None:
        """Verify attestation includes correct event count."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=1&end_sequence=5"
        )

        metadata = response.json()
        assert metadata["event_count"] == 5

    def test_attestation_includes_chain_hash(self, client) -> None:
        """Verify attestation includes chain hash at export time."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=1&end_sequence=5"
        )

        metadata = response.json()
        assert "chain_hash_at_export" in metadata
        assert len(metadata["chain_hash_at_export"]) == 64  # SHA-256 hex

    def test_attestation_includes_exporter_id(self, client) -> None:
        """Verify attestation includes exporter identification."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=1&end_sequence=5"
        )

        metadata = response.json()
        assert metadata["exporter_id"] == "archon72-observer-api"

    def test_attestation_no_authentication_required(self, client) -> None:
        """Verify attestation requires no authentication (FR44)."""
        response = client.get(
            "/v1/observer/export/attestation?start_sequence=1&end_sequence=5"
        )

        # Should succeed without auth
        assert response.status_code == 200


class TestExportContentValidity:
    """Tests for export content validity (CT-11, FR139)."""

    @pytest.fixture
    def app_with_test_events(self):
        """Create FastAPI app with test events in store."""
        from src.api.dependencies.observer import (
            get_event_store,
            get_export_service,
            get_observer_service,
        )
        from src.application.services.export_service import ExportService
        from src.application.services.observer_service import ObserverService

        store = EventStoreStub()
        for i in range(1, 4):
            event = create_test_event(
                sequence=i,
                payload={"value": f"test_{i}"},
            )
            store.add_event(event)

        app = FastAPI()
        app.include_router(router)

        def _get_event_store():
            return store

        def _get_observer_service():
            return ObserverService(
                event_store=store,
                halt_checker=None,
                checkpoint_repo=None,
                merkle_service=None,
            )

        def _get_export_service():
            return ExportService(event_store=store)

        app.dependency_overrides[get_event_store] = _get_event_store
        app.dependency_overrides[get_observer_service] = _get_observer_service
        app.dependency_overrides[get_export_service] = _get_export_service

        return app

    @pytest.fixture
    def client(self, app_with_test_events):
        """Create test client."""
        return TestClient(app_with_test_events)

    def test_export_payload_is_preserved(self, client) -> None:
        """Verify payload data is preserved in export."""
        response = client.get("/v1/observer/export?format=jsonl")

        lines = response.text.strip().split("\n")
        for i, line in enumerate(lines, 1):
            event = json.loads(line)
            assert event["payload"]["value"] == f"test_{i}"

    def test_export_timestamps_are_iso8601(self, client) -> None:
        """Verify timestamps are in ISO 8601 format."""
        response = client.get("/v1/observer/export?format=jsonl")

        line = response.text.strip().split("\n")[0]
        event = json.loads(line)

        # Should be parseable as ISO 8601
        local_ts = event["local_timestamp"]
        assert "T" in local_ts  # ISO 8601 format

    def test_export_sequence_is_ordered(self, client) -> None:
        """Verify events are exported in sequence order."""
        response = client.get("/v1/observer/export?format=jsonl")

        lines = response.text.strip().split("\n")
        sequences = [json.loads(line)["sequence"] for line in lines]

        assert sequences == sorted(sequences)

    def test_csv_can_be_parsed(self, client) -> None:
        """Verify CSV export can be fully parsed."""
        response = client.get("/v1/observer/export?format=csv")

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        assert len(rows) == 3
        for row in rows:
            assert "event_id" in row
            assert "sequence" in row
            assert row["sequence"].isdigit()
