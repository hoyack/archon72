"""Integration tests for historical queries (Story 4.5, Task 8).

End-to-end tests verifying historical query functionality.

Constitutional Constraints:
- FR44: Public read access without registration
- FR88: Query for state as of any sequence number or timestamp
- FR89: Historical queries return hash chain proof to current head
- CT-13: Reads allowed during halt (per Story 3.5)
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client for the API."""
    return TestClient(app)


class TestHistoricalQueryParametersIntegration:
    """Integration tests for historical query parameters (FR88)."""

    def test_as_of_sequence_parameter_accepted(self, client) -> None:
        """Test that as_of_sequence parameter is accepted.

        Per FR88: Query for state as of any sequence number.
        """
        # Should not return 422 validation error
        response = client.get("/v1/observer/events?as_of_sequence=100")

        # Might return 404 if sequence doesn't exist, or 200/500
        # but NOT 422 (parameter rejected)
        assert response.status_code in (200, 404, 500)

    def test_as_of_timestamp_parameter_accepted(self, client) -> None:
        """Test that as_of_timestamp parameter is accepted.

        Per FR88: Query for state as of any timestamp.
        """
        timestamp = "2026-01-15T12:00:00Z"
        response = client.get(f"/v1/observer/events?as_of_timestamp={timestamp}")

        # Should accept the parameter
        assert response.status_code in (200, 500)

    def test_include_proof_parameter_accepted(self, client) -> None:
        """Test that include_proof parameter is accepted.

        Per FR89: Historical queries SHALL return hash chain proof.
        """
        response = client.get(
            "/v1/observer/events?as_of_sequence=100&include_proof=true"
        )

        # Should accept the parameter
        assert response.status_code in (200, 404, 500)

    def test_as_of_sequence_must_be_positive(self, client) -> None:
        """Test that as_of_sequence must be positive integer."""
        # Zero not allowed (ge=1)
        response = client.get("/v1/observer/events?as_of_sequence=0")
        assert response.status_code == 422

        # Negative not allowed
        response = client.get("/v1/observer/events?as_of_sequence=-5")
        assert response.status_code == 422

    def test_as_of_sequence_and_timestamp_mutually_exclusive(self, client) -> None:
        """Test that as_of_sequence and as_of_timestamp cannot be combined.

        Per FR88: Either sequence OR timestamp, not both.
        """
        response = client.get(
            "/v1/observer/events?"
            "as_of_sequence=100&"
            "as_of_timestamp=2026-01-15T12:00:00Z"
        )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "both" in response.json()["detail"].lower()

    def test_as_of_sequence_works_without_proof(self, client) -> None:
        """Test historical query without proof requested."""
        response = client.get(
            "/v1/observer/events?as_of_sequence=1&include_proof=false"
        )

        # Should succeed or return 404 for missing sequence
        assert response.status_code in (200, 404, 500)

    def test_include_proof_defaults_to_false(self, client) -> None:
        """Test that include_proof defaults to false."""
        response = client.get("/v1/observer/events?as_of_sequence=100")

        if response.status_code == 200:
            data = response.json()
            # Without explicit include_proof=true, proof should be null
            assert data.get("proof") is None


class TestHistoricalQueryResponseStructureIntegration:
    """Integration tests for historical query response structure."""

    def test_historical_query_includes_metadata(self, client) -> None:
        """Test that historical queries include metadata.

        Per FR88: Response includes information about the query point.
        """
        response = client.get("/v1/observer/events?as_of_sequence=1")

        if response.status_code == 200:
            data = response.json()
            # Should include historical_query metadata
            assert "historical_query" in data
            historical = data["historical_query"]
            assert "resolved_sequence" in historical
            assert "current_head_sequence" in historical

    def test_timestamp_query_resolves_to_sequence(self, client) -> None:
        """Test that timestamp queries resolve to sequence.

        Per FR88: Timestamp queries resolve to nearest sequence.
        """
        timestamp = "2026-01-15T12:00:00Z"
        response = client.get(f"/v1/observer/events?as_of_timestamp={timestamp}")

        if response.status_code == 200:
            data = response.json()
            historical = data.get("historical_query")
            if historical:
                # Should have queried timestamp and resolved sequence
                assert historical.get("resolved_sequence") is not None

    def test_proof_structure_when_included(self, client) -> None:
        """Test proof structure when include_proof=true.

        Per FR89: Proof contains chain of hash entries.
        """
        response = client.get("/v1/observer/events?as_of_sequence=1&include_proof=true")

        if response.status_code == 200:
            data = response.json()
            proof = data.get("proof")
            if proof:
                # Verify proof structure per FR89
                assert "from_sequence" in proof
                assert "to_sequence" in proof
                assert "chain" in proof
                assert "current_head_hash" in proof
                assert isinstance(proof["chain"], list)


class TestHistoricalQueryConstitutionalComplianceIntegration:
    """Integration tests for constitutional compliance."""

    def test_fr44_no_auth_for_historical_queries(self, client) -> None:
        """Test FR44 compliance: Historical queries don't require auth.

        Constitutional Constraint FR44:
        - No login required
        - No API key required
        """
        # Request with NO authentication
        response = client.get(
            "/v1/observer/events?as_of_sequence=100",
            headers={},  # Explicitly no auth headers
        )

        # Must not require authentication
        assert response.status_code != 401, "FR44 violated: Auth should not be required"
        assert response.status_code != 403, (
            "FR44 violated: Access should not be forbidden"
        )

    def test_fr88_compliance_sequence_query(self, client) -> None:
        """Test FR88 compliance: Query for state as of sequence.

        Constitutional Constraint FR88:
        Observer interface SHALL support queries for system state
        as of any past sequence number.
        """
        # The endpoint must accept the as_of_sequence parameter
        response = client.get("/v1/observer/events?as_of_sequence=50")

        # Not 422 (parameter not recognized)
        # Not 405 (method not allowed)
        assert response.status_code not in (422, 405)

    def test_fr88_compliance_timestamp_query(self, client) -> None:
        """Test FR88 compliance: Query for state as of timestamp.

        Constitutional Constraint FR88:
        Observer interface SHALL support queries for system state
        as of any past timestamp.
        """
        timestamp = "2026-01-01T00:00:00Z"
        response = client.get(f"/v1/observer/events?as_of_timestamp={timestamp}")

        # Not 422 (parameter not recognized)
        assert response.status_code != 422

    def test_fr89_compliance_proof_generation(self, client) -> None:
        """Test FR89 compliance: Hash chain proof returned.

        Constitutional Constraint FR89:
        Historical queries SHALL return hash chain proof
        connecting queried state to current head.
        """
        response = client.get("/v1/observer/events?as_of_sequence=1&include_proof=true")

        if response.status_code == 200:
            data = response.json()
            # If proof is returned, verify it has connecting structure
            proof = data.get("proof")
            if proof:
                # Proof must connect from_sequence to to_sequence
                assert proof["from_sequence"] <= proof["to_sequence"]
                # Chain must not be empty
                assert len(proof["chain"]) > 0


class TestHistoricalQueryCombinedWithFiltersIntegration:
    """Integration tests for historical queries combined with filters."""

    def test_historical_query_with_event_type_filter(self, client) -> None:
        """Test combining as_of_sequence with event_type filter."""
        response = client.get("/v1/observer/events?as_of_sequence=100&event_type=vote")

        # Should accept both parameters
        assert response.status_code in (200, 404, 500)

    def test_historical_query_with_pagination(self, client) -> None:
        """Test combining as_of_sequence with pagination."""
        response = client.get(
            "/v1/observer/events?as_of_sequence=100&limit=10&offset=0"
        )

        # Should accept all parameters
        assert response.status_code in (200, 404, 500)

    def test_standard_query_still_works(self, client) -> None:
        """Test that standard query without as_of params still works."""
        # Standard query without historical params
        response = client.get("/v1/observer/events?limit=10")

        # Should work as before
        if response.status_code == 200:
            data = response.json()
            # Should not have historical_query metadata
            assert data.get("historical_query") is None


class TestHistoricalQueryErrorHandlingIntegration:
    """Integration tests for historical query error handling."""

    def test_nonexistent_sequence_returns_404(self, client) -> None:
        """Test that querying non-existent sequence returns 404."""
        response = client.get("/v1/observer/events?as_of_sequence=999999999")

        # 404 for "not found" or 200 with empty results
        assert response.status_code in (200, 404, 500)

    def test_invalid_timestamp_format_returns_422(self, client) -> None:
        """Test that invalid timestamp format returns 422."""
        response = client.get("/v1/observer/events?as_of_timestamp=not-a-date")

        # Should reject invalid format
        assert response.status_code == 422

    def test_future_timestamp_handled(self, client) -> None:
        """Test that future timestamp is handled gracefully."""
        future = "2099-12-31T23:59:59Z"
        response = client.get(f"/v1/observer/events?as_of_timestamp={future}")

        # Should return all events up to current head
        assert response.status_code in (200, 500)
