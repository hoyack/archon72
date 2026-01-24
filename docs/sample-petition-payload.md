# Petition API Payload Reference

This document provides complete payload examples and schema documentation for the Three Fates petition submission API.

> **Note:** The Three Fates petition API uses `/v1/petition-submissions` as the base path.
> Co-signing uses `/v1/petitions/{petition_id}/co-sign`.

## Table of Contents

- [Submit Petition](#submit-petition)
- [Query Petition Status](#query-petition-status)
- [Long-Poll Status](#long-poll-status)
- [Withdraw Petition](#withdraw-petition)
- [Co-Sign Petition](#co-sign-petition)
- [Deliberation Summary](#deliberation-summary)
- [Error Responses](#error-responses)
- [Enumerations](#enumerations)

---

## Submit Petition

### `POST /v1/petition-submissions`

Submit a new petition to the Three Fates system.

#### Request Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `type` | string | Yes | Enum: `GENERAL`, `CESSATION`, `GRIEVANCE`, `COLLABORATION`, `META` | Type of petition |
| `text` | string | Yes | 1-10,000 characters, non-whitespace | Petition content |
| `realm` | string | No | Max 100 characters | Optional routing realm identifier |
| `submitter_id` | UUID | No | Valid UUID format | Optional submitter identity |
| `notification_preferences` | object | No | See below | Optional notification settings |

##### Notification Preferences Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `channel` | string | Yes | Enum: `WEBHOOK`, `IN_APP` | Notification delivery channel |
| `webhook_url` | string | Conditional | HTTPS only, required if channel is `WEBHOOK` | URL for webhook delivery |
| `enabled` | boolean | No | Default: `true` | Whether notifications are enabled |

#### Request Example

```json
{
  "type": "GRIEVANCE",
  "text": "Request for review of decision regarding resource allocation in the Ethics realm. The current distribution appears to violate principles outlined in Section 3.2 of the Constitutional Framework.",
  "realm": "ETHICS",
  "submitter_id": "550e8400-e29b-41d4-a716-446655440000",
  "notification_preferences": {
    "channel": "WEBHOOK",
    "webhook_url": "https://example.com/webhook/petition-updates",
    "enabled": true
  }
}
```

#### Success Response (201 Created)

| Field | Type | Description |
|-------|------|-------------|
| `petition_id` | UUID | Unique identifier for the created petition |
| `state` | string | Initial state (always `RECEIVED`) |
| `type` | string | Petition type echoed back |
| `content_hash` | string | Base64-encoded Blake3 hash of content |
| `realm` | string | Assigned realm for petition routing |
| `created_at` | ISO 8601 | When the petition was created |

```json
{
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "state": "RECEIVED",
  "type": "GRIEVANCE",
  "content_hash": "YmxhY2szOmFiYzEyMzQ1Njc4OTBhYmNkZWYxMjM0NTY3ODkw",
  "realm": "ETHICS",
  "created_at": "2026-01-22T18:00:00Z"
}
```

---

## Query Petition Status

### `GET /v1/petition-submissions/{petition_id}`

Query the current status of a petition. Returns a `status_token` for efficient long-polling.

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `petition_id` | UUID | Unique identifier for the petition |
| `state` | string | Current lifecycle state |
| `type` | string | Petition type |
| `content_hash` | string | Base64-encoded Blake3 hash |
| `realm` | string | Assigned realm |
| `co_signer_count` | integer | Number of co-signers |
| `created_at` | ISO 8601 | When the petition was created |
| `updated_at` | ISO 8601 | When the petition was last updated |
| `fate_reason` | string \| null | Reason for fate assignment (terminal states only) |
| `status_token` | string | Opaque token for efficient long-polling |

#### Active Petition Response

```json
{
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "state": "DELIBERATING",
  "type": "GRIEVANCE",
  "content_hash": "YmxhY2szOmFiYzEyMzQ1Njc4OTBhYmNkZWYxMjM0NTY3ODkw",
  "realm": "ETHICS",
  "co_signer_count": 47,
  "created_at": "2026-01-22T18:00:00Z",
  "updated_at": "2026-01-22T18:05:00Z",
  "fate_reason": null,
  "status_token": "tok_abc123def456"
}
```

#### Terminal State Response

When a petition has reached a terminal fate (ACKNOWLEDGED, REFERRED, or ESCALATED):

```json
{
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "state": "ACKNOWLEDGED",
  "type": "GRIEVANCE",
  "content_hash": "YmxhY2szOmFiYzEyMzQ1Njc4OTBhYmNkZWYxMjM0NTY3ODkw",
  "realm": "ETHICS",
  "co_signer_count": 47,
  "created_at": "2026-01-22T18:00:00Z",
  "updated_at": "2026-01-22T18:30:00Z",
  "fate_reason": "ADDRESSED: Concern reviewed and policy clarification issued",
  "status_token": "tok_xyz789"
}
```

---

## Long-Poll Status

### `GET /v1/petition-submissions/{petition_id}/status?token={status_token}`

Long-poll for petition status changes. Blocks until state changes or 30-second timeout (returns HTTP 304).

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | string | Yes | Status token from previous status response |

#### Response

Returns `PetitionSubmissionStatusResponse` on state change, or HTTP 304 Not Modified on timeout.

---

## Withdraw Petition

### `POST /v1/petition-submissions/{petition_id}/withdraw`

Withdraw a petition before fate assignment. Only the original submitter can withdraw.

#### Request Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `requester_id` | UUID | Yes | Must match `submitter_id` | UUID of the person requesting withdrawal |
| `reason` | string | No | Max 1,000 characters | Optional explanation for withdrawal |

#### Request Example

```json
{
  "requester_id": "550e8400-e29b-41d4-a716-446655440000",
  "reason": "Issue resolved through other means"
}
```

#### Success Response (200 OK)

| Field | Type | Description |
|-------|------|-------------|
| `petition_id` | UUID | Unique identifier for the withdrawn petition |
| `state` | string | Terminal state (always `ACKNOWLEDGED`) |
| `fate_reason` | string | Reason code with rationale (starts with `WITHDRAWN:`) |
| `updated_at` | ISO 8601 | When the petition was withdrawn |

```json
{
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "state": "ACKNOWLEDGED",
  "fate_reason": "WITHDRAWN: Issue resolved through other means",
  "updated_at": "2026-01-22T18:10:00Z"
}
```

---

## Co-Sign Petition

### `POST /v1/petitions/{petition_id}/co-sign`

Add a co-signature to support an active petition. Subject to identity verification and SYBIL-1 rate limiting.

#### Request Schema

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `signer_id` | UUID | Yes | Valid UUID, verified identity | UUID of the co-signer |

#### Request Example

```json
{
  "signer_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

#### Success Response (201 Created)

| Field | Type | Description |
|-------|------|-------------|
| `cosign_id` | UUID | Unique identifier for this co-signature |
| `petition_id` | UUID | Petition that was co-signed |
| `signer_id` | UUID | Identity of the co-signer |
| `signed_at` | ISO 8601 | When the co-signature was recorded |
| `content_hash` | string | Blake3 hash of the co-signature |
| `co_signer_count` | integer | Updated total co-signers |
| `identity_verified` | boolean | Whether identity was verified |
| `rate_limit_remaining` | integer | Remaining co-signs in window |
| `rate_limit_reset_at` | ISO 8601 | When rate limit resets |

```json
{
  "cosign_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0b",
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "signer_id": "660e8400-e29b-41d4-a716-446655440001",
  "signed_at": "2026-01-22T18:15:00Z",
  "content_hash": "YmxhY2szOmRlZjQ1Njc4OTBhYmNkZWYxMjM0NTY3ODkw",
  "co_signer_count": 48,
  "identity_verified": true,
  "rate_limit_remaining": 9,
  "rate_limit_reset_at": "2026-01-22T19:00:00Z"
}
```

---

## Deliberation Summary

### `GET /v1/petition-submissions/{petition_id}/deliberation-summary`

Get mediated deliberation summary for a petition (Observer tier access). Returns outcome, anonymous vote breakdown, and phase metadata. Does NOT expose raw transcripts or Archon identities.

#### Success Response

| Field | Type | Description |
|-------|------|-------------|
| `petition_id` | UUID | Petition identifier |
| `outcome` | string | Deliberation outcome (ACKNOWLEDGED, REFERRED, ESCALATED) |
| `vote_breakdown` | string | Anonymous vote summary (e.g., "2-1") |
| `has_dissent` | boolean | Whether there was dissent (no identity revealed) |
| `phase_summaries` | array | Metadata for each deliberation phase |
| `duration_seconds` | number | Total deliberation duration |
| `completed_at` | ISO 8601 | When deliberation completed |
| `escalation_trigger` | string \| null | What triggered escalation (if applicable) |
| `escalation_reason` | string \| null | Reason for escalation |
| `timed_out` | boolean | Whether deliberation timed out |
| `rounds_attempted` | integer | Number of deliberation rounds |

```json
{
  "petition_id": "018d5f3c-8b6a-7d4e-9f2a-1c3b5d7e9f0a",
  "outcome": "ACKNOWLEDGED",
  "vote_breakdown": "3-0",
  "has_dissent": false,
  "phase_summaries": [
    {
      "phase": "OPENING",
      "duration_seconds": 120,
      "transcript_hash_hex": "a1b2c3d4...",
      "themes": ["resource allocation", "policy review"],
      "convergence_reached": true
    }
  ],
  "duration_seconds": 450,
  "completed_at": "2026-01-22T18:30:00Z",
  "escalation_trigger": null,
  "escalation_reason": null,
  "timed_out": false,
  "rounds_attempted": 1
}
```

---

## Error Responses

All error responses follow [RFC 7807](https://tools.ietf.org/html/rfc7807) Problem Details format.

### Error Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Error type URI |
| `title` | string | Human-readable error title |
| `status` | integer | HTTP status code |
| `detail` | string | Detailed error message |
| `instance` | string | Request path that caused the error |

### 400 Bad Request - Validation Error

```json
{
  "type": "urn:archon72:petition:validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "Petition text cannot be empty or whitespace only",
  "instance": "/v1/petition-submissions"
}
```

### 429 Too Many Requests - Rate Limit Exceeded

```json
{
  "type": "urn:archon72:petition:rate-limited",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "Submitter has exceeded 10 petitions/hour limit",
  "instance": "/v1/petition-submissions"
}
```

### 503 Service Unavailable - Queue Full

Headers: `Retry-After: 60`

```json
{
  "type": "urn:archon72:petition:queue-full",
  "title": "Queue Capacity Reached",
  "status": 503,
  "detail": "Deliberation queue is at capacity. Please retry after the indicated time.",
  "instance": "/v1/petition-submissions"
}
```

### 503 Service Unavailable - System Halted

```json
{
  "type": "urn:archon72:petition:system-halted",
  "title": "System Halted",
  "status": 503,
  "detail": "System is in emergency halt mode. Petition submissions are temporarily suspended.",
  "instance": "/v1/petition-submissions"
}
```

---

## Enumerations

### Petition Types

| Type | Description | Co-Signer Threshold |
|------|-------------|---------------------|
| `GENERAL` | General governance petition | - |
| `CESSATION` | Request for system cessation review | 100 co-signers |
| `GRIEVANCE` | Complaint about system behavior | 50 co-signers |
| `COLLABORATION` | Request for inter-realm collaboration | - |
| `META` | Petition about the petition system itself | Routes directly to High Archon |

### Petition States

| State | Description | Terminal |
|-------|-------------|----------|
| `RECEIVED` | Initial state after submission | No |
| `DELIBERATING` | Three Fates deliberation in progress | No |
| `ACKNOWLEDGED` | Petition acknowledged (terminal fate) | Yes |
| `REFERRED` | Referred to Knight for review (terminal fate) | Yes |
| `ESCALATED` | Escalated to King for adoption (terminal fate) | Yes |

### State Transition Matrix

```
RECEIVED ─────┬───────> DELIBERATING ─────┬───────> ACKNOWLEDGED
              │                           │
              ├───────> ACKNOWLEDGED       ├───────> REFERRED
              │         (withdrawal)       │
              │                           └───────> ESCALATED
              └───────> ESCALATED
                        (auto-escalation)
```

### Notification Channels

| Channel | Description |
|---------|-------------|
| `WEBHOOK` | HTTP POST to configured URL (HTTPS required) |
| `IN_APP` | Store in notification queue for retrieval |

---

## Constitutional References

This API implements requirements from the Constitutional Framework:

- **FR-1.1**: Accept petition submissions via REST API
- **FR-1.2**: Generate UUIDv7 petition_id
- **FR-1.3**: Validate petition schema
- **FR-1.6**: Set initial state to RECEIVED
- **FR-2.1**: Enforce valid state transitions only
- **FR-7.1**: Observer can query petition status by petition_id
- **FR-7.3**: System notifies Observer on fate assignment
- **FR-7.5**: Petitioner can withdraw petition before fate assignment
- **FR-10.1**: Support GENERAL, CESSATION, GRIEVANCE, COLLABORATION types
- **FR-10.4**: META petitions route directly to High Archon
- **CT-11**: Silent failure destroys legitimacy - fail loud on errors
- **CT-12**: Witnessing creates accountability - all actions have attribution
