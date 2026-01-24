"""Integration tests for petition submission API (Story 1.1, FR-1.1).

These tests verify the complete request/response flow through the API
with all components integrated (but using stub repositories).

Constitutional Compliance:
- FR-1.1: Accept petition submissions via REST API
- FR-1.2: Generate UUID petition_id
- FR-1.3: Validate petition schema
- FR-1.6: Set initial state to RECEIVED
- FR-10.1: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types
- NFR-1.1: p99 latency < 200ms (not tested here - requires load testing)
"""

import base64

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.petition_submission import (
    reset_petition_submission_dependencies,
)
from src.api.main import app


@pytest.fixture(autouse=True)
def reset_deps():
    """Reset DI singletons before and after each test."""
    reset_petition_submission_dependencies()
    yield
    reset_petition_submission_dependencies()


@pytest.fixture
def client() -> TestClient:
    """Create test client for the full app."""
    return TestClient(app, raise_server_exceptions=False)


class TestPetitionSubmissionIntegration:
    """Integration tests for petition submission flow."""

    def test_full_submit_and_retrieve_flow(self, client: TestClient) -> None:
        """Test complete submit -> retrieve flow (FR-1.1, FR-7.1)."""
        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GRIEVANCE",
                "text": "Integration test petition for the Three Fates system.",
            },
        )

        assert submit_response.status_code == 201
        submit_data = submit_response.json()

        # Verify submit response
        petition_id = submit_data["petition_id"]
        assert submit_data["state"] == "RECEIVED"
        assert submit_data["type"] == "GRIEVANCE"
        assert "content_hash" in submit_data
        assert "realm" in submit_data
        assert "created_at" in submit_data

        # Retrieve the petition
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        get_data = get_response.json()

        # Verify data consistency
        assert get_data["petition_id"] == petition_id
        assert get_data["state"] == "RECEIVED"
        assert get_data["type"] == "GRIEVANCE"
        assert get_data["content_hash"] == submit_data["content_hash"]
        assert get_data["realm"] == submit_data["realm"]

    def test_multiple_petitions_unique_ids(self, client: TestClient) -> None:
        """Multiple petitions get unique IDs (FR-1.2)."""
        petition_ids = []

        for i in range(5):
            response = client.post(
                "/v1/petition-submissions",
                json={
                    "type": "GENERAL",
                    "text": f"Petition number {i} for uniqueness test.",
                },
            )
            assert response.status_code == 201
            petition_ids.append(response.json()["petition_id"])

        # All IDs should be unique
        assert len(set(petition_ids)) == 5

    def test_all_petition_types_accepted(self, client: TestClient) -> None:
        """All petition types are accepted (FR-10.1)."""
        types = ["GENERAL", "CESSATION", "GRIEVANCE", "COLLABORATION"]

        for petition_type in types:
            response = client.post(
                "/v1/petition-submissions",
                json={
                    "type": petition_type,
                    "text": f"Test petition of type {petition_type}.",
                },
            )
            assert response.status_code == 201, f"Failed for type {petition_type}"
            assert response.json()["type"] == petition_type

    def test_content_hash_integrity(self, client: TestClient) -> None:
        """Content hash is computed correctly (HP-2)."""
        text = "Test content for hash verification."

        # Submit petition
        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": text},
        )
        assert response.status_code == 201

        # Get the hash
        content_hash = response.json()["content_hash"]

        # Verify it's valid base64
        hash_bytes = base64.b64decode(content_hash)
        assert len(hash_bytes) == 32  # Blake3 always produces 32 bytes

        # Submit same content again - hash should match
        response2 = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": text},
        )
        assert response2.status_code == 201
        assert response2.json()["content_hash"] == content_hash

    def test_validation_error_format(self, client: TestClient) -> None:
        """Validation errors follow expected format."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "INVALID",  # Invalid type
                "text": "Test petition.",
            },
        )

        assert response.status_code == 422
        # FastAPI validation error format
        assert "detail" in response.json()

    def test_not_found_error_format(self, client: TestClient) -> None:
        """Not found errors follow RFC 7807 format."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/v1/petition-submissions/{fake_id}")

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/petition-not-found"
        assert detail["status"] == 404
        assert fake_id in detail["detail"]

    def test_uuid_format_validation(self, client: TestClient) -> None:
        """UUID format is validated in path parameters."""
        response = client.get("/v1/petition-submissions/not-a-valid-uuid")
        assert response.status_code == 422

    def test_large_text_near_limit(self, client: TestClient) -> None:
        """Text near the 10,000 char limit is accepted."""
        large_text = "x" * 9999  # Just under limit

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": large_text},
        )

        assert response.status_code == 201
        assert response.json()["state"] == "RECEIVED"

    def test_unicode_text_handling(self, client: TestClient) -> None:
        """Unicode text is handled correctly."""
        unicode_text = "Petition with unicode: 日本語 中文 한국어 emoji 🎉"

        response = client.post(
            "/v1/petition-submissions",
            json={"type": "GENERAL", "text": unicode_text},
        )

        assert response.status_code == 201

        # Retrieve and verify
        petition_id = response.json()["petition_id"]
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200


class TestPetitionSubmissionRealmRouting:
    """Integration tests for realm routing (HP-3)."""

    def test_default_realm_assigned(self, client: TestClient) -> None:
        """Petitions without realm get default realm assigned."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition without explicit realm.",
            },
        )

        assert response.status_code == 201
        assert response.json()["realm"]  # Should have a realm

    def test_explicit_realm_used(self, client: TestClient) -> None:
        """Petitions with valid realm use that realm."""
        # Use a realm from the canonical set (9 realms from archons-base.json)
        # The stub is pre-populated with canonical realms
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for specific realm.",
                "realm": "realm_privacy_discretion_services",  # Canonical realm
            },
        )

        assert response.status_code == 201
        assert response.json()["realm"] == "realm_privacy_discretion_services"

    def test_invalid_realm_rejected_with_error(self, client: TestClient) -> None:
        """Invalid realm produces proper error response."""
        response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition for invalid realm.",
                "realm": "realm_that_does_not_exist",
            },
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/invalid-realm"
        assert "realm_that_does_not_exist" in detail["detail"]


class TestPetitionStatusQueryIntegration:
    """Integration tests for petition status query endpoint (Story 1.8, FR-7.1, FR-7.4)."""

    def test_full_flow_submit_query_verify_response(self, client: TestClient) -> None:
        """Test full flow: submit petition -> query status -> verify response (AC9)."""
        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "CESSATION",
                "text": "Integration test for status query verification.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        data = get_response.json()

        # Verify all required fields (AC2)
        assert data["petition_id"] == petition_id
        assert data["type"] == "CESSATION"
        assert data["state"] == "RECEIVED"
        assert data["co_signer_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data
        assert "realm" in data
        assert "content_hash" in data
        # fate_reason should be None for non-terminal state
        assert data.get("fate_reason") is None

    def test_query_returns_correct_state_after_submission(
        self, client: TestClient
    ) -> None:
        """Query returns correct initial state immediately after submission (AC9)."""
        # Submit petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "State verification test petition.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]
        submit_state = submit_response.json()["state"]

        # Query status immediately
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        assert get_response.json()["state"] == submit_state
        assert get_response.json()["state"] == "RECEIVED"

    def test_query_nonexistent_petition_returns_404(self, client: TestClient) -> None:
        """Query for non-existent petition_id returns 404 with RFC 7807 (AC9)."""
        nonexistent_id = "12345678-1234-1234-1234-123456789012"

        response = client.get(f"/v1/petition-submissions/{nonexistent_id}")

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["type"] == "https://archon72.io/errors/petition-not-found"
        assert detail["title"] == "Petition Not Found"
        assert detail["status"] == 404
        assert nonexistent_id in detail["detail"]

    def test_co_signer_count_default_zero(self, client: TestClient) -> None:
        """co_signer_count defaults to 0 for new petitions (FR-7.4)."""
        # Submit petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Test petition for co_signer_count default.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Query status
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")

        assert get_response.status_code == 200
        assert get_response.json()["co_signer_count"] == 0

    def test_response_timing_basic_check(self, client: TestClient) -> None:
        """Basic latency check for status query response (AC9).

        Note: Comprehensive p99 < 100ms testing (NFR-1.2, AC10) requires
        load testing infrastructure. This is a basic sanity check.
        """
        import time

        # Submit petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Latency test petition.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Time the status query
        start = time.monotonic()
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        elapsed_ms = (time.monotonic() - start) * 1000

        assert get_response.status_code == 200
        # Basic sanity check - should complete well under 1 second
        # Real p99 < 100ms testing needs load testing framework
        assert elapsed_ms < 1000, f"Response took {elapsed_ms}ms (expected < 1000ms)"


class TestPetitionWithdrawalIntegration:
    """Integration tests for petition withdrawal flow (Story 7.3, FR-7.5)."""

    def test_full_submit_and_withdraw_flow(self, client: TestClient) -> None:
        """Test complete submit -> withdraw flow (AC1)."""
        from uuid import uuid4

        submitter_id = str(uuid4())

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to be withdrawn in integration test.",
                "submitter_id": submitter_id,
            },
        )

        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]
        assert submit_response.json()["state"] == "RECEIVED"

        # Withdraw the petition
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": submitter_id,
                "reason": "Changed my mind about this petition",
            },
        )

        assert withdraw_response.status_code == 200
        withdraw_data = withdraw_response.json()
        assert withdraw_data["petition_id"] == petition_id
        assert withdraw_data["state"] == "ACKNOWLEDGED"
        assert "WITHDRAWN" in withdraw_data["fate_reason"]
        assert "Changed my mind" in withdraw_data["fate_reason"]

        # Verify the petition state persisted
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["state"] == "ACKNOWLEDGED"
        assert "WITHDRAWN" in get_data["fate_reason"]

    def test_withdraw_prevents_further_state_changes(self, client: TestClient) -> None:
        """Withdrawn petition cannot be modified further (AC2)."""
        from uuid import uuid4

        submitter_id = str(uuid4())

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Petition to verify withdrawal finality.",
                "submitter_id": submitter_id,
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Withdraw the petition
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": submitter_id,
            },
        )
        assert withdraw_response.status_code == 200

        # Try to withdraw again - should fail
        second_withdraw = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": submitter_id,
            },
        )

        assert second_withdraw.status_code == 400
        detail = second_withdraw.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:already-fated"
        assert "ACKNOWLEDGED" in detail["detail"]

    def test_withdraw_without_reason_uses_default(self, client: TestClient) -> None:
        """Withdrawal without reason uses default reason (AC1)."""
        from uuid import uuid4

        submitter_id = str(uuid4())

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "CESSATION",
                "text": "Petition to test default withdrawal reason.",
                "submitter_id": submitter_id,
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Withdraw without reason
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": submitter_id,
            },
        )

        assert withdraw_response.status_code == 200
        data = withdraw_response.json()
        assert "WITHDRAWN" in data["fate_reason"]
        assert "withdrew" in data["fate_reason"].lower()

    def test_withdraw_unauthorized_different_submitter(
        self, client: TestClient
    ) -> None:
        """Different user cannot withdraw another's petition (AC3)."""
        from uuid import uuid4

        original_submitter = str(uuid4())
        attacker_id = str(uuid4())

        # Submit a petition
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GRIEVANCE",
                "text": "Petition that should not be withdrawable by others.",
                "submitter_id": original_submitter,
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Attacker tries to withdraw
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": attacker_id,
            },
        )

        assert withdraw_response.status_code == 403
        detail = withdraw_response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:unauthorized-withdrawal"

        # Verify petition unchanged
        get_response = client.get(f"/v1/petition-submissions/{petition_id}")
        assert get_response.status_code == 200
        assert get_response.json()["state"] == "RECEIVED"  # Still original state

    def test_withdraw_anonymous_petition_rejected(self, client: TestClient) -> None:
        """Anonymous petitions cannot be withdrawn (AC3)."""
        from uuid import uuid4

        # Submit an anonymous petition (no submitter_id)
        submit_response = client.post(
            "/v1/petition-submissions",
            json={
                "type": "GENERAL",
                "text": "Anonymous petition that cannot be withdrawn.",
            },
        )
        assert submit_response.status_code == 201
        petition_id = submit_response.json()["petition_id"]

        # Anyone trying to withdraw
        any_user_id = str(uuid4())
        withdraw_response = client.post(
            f"/v1/petition-submissions/{petition_id}/withdraw",
            json={
                "requester_id": any_user_id,
            },
        )

        assert withdraw_response.status_code == 403
        detail = withdraw_response.json()["detail"]
        assert detail["type"] == "urn:archon72:petition:unauthorized-withdrawal"

    def test_withdraw_rfc7807_error_format(self, client: TestClient) -> None:
        """Withdrawal errors follow RFC 7807 format with governance extensions."""
        from uuid import uuid4

        nonexistent_id = str(uuid4())

        response = client.post(
            f"/v1/petition-submissions/{nonexistent_id}/withdraw",
            json={
                "requester_id": str(uuid4()),
            },
        )

        assert response.status_code == 404
        detail = response.json()["detail"]

        # RFC 7807 required fields
        assert "type" in detail
        assert "title" in detail
        assert "status" in detail
        assert "detail" in detail
        assert "instance" in detail

        # Governance extension (D7)
        assert "petition_id" in detail
        assert detail["petition_id"] == nonexistent_id
