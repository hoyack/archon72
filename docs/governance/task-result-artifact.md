# Task Result Artifact

> **Failure is allowed. Silence is not.**

## Overview

A Task Result Artifact is the contract from an **Aegis Cluster** back to the issuing **Earl**. It contains deliverables, status, issues encountered, and steward attestation.

**Schema Version:** 1.0.0
**JSON Schema Draft:** 2020-12
**Schema File:** [schemas/task-result-artifact.json](./schemas/task-result-artifact.json)

---

## Key Principles

### Mandatory Disclosure

Clusters must report:
- **Success** - Deliverables completed
- **Partial completion** - What was done, what wasn't
- **Failure** - Why it failed
- **Blockers** - What's preventing progress
- **Withdrawal** - Cluster is stepping back from the task

### No Silent Failure

The system does not allow tasks to disappear into a void. Every activated task must eventually have a result artifact, even if that result is "we couldn't do this."

This is enforced by:
1. Response policy timeouts in activation requests
2. Knight-Witness monitoring for stale tasks
3. Steward attestation requirements

---

## Schema Structure

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `result_id` | UUID | Unique identifier for this result |
| `request_id` | UUID | Reference to the activation request |
| `task_id` | UUID | Reference to parent task |
| `version` | string | Schema version ("1.0.0") |
| `submitted_at` | datetime | When the result was submitted |
| `cluster_id` | UUID | Cluster that executed the task |
| `steward_id` | string | Steward who approved submission |
| `status` | enum | Outcome status |
| `audit` | object | Audit trail with steward attestation |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `completion_summary` | string | Human-readable summary of outcome |
| `deliverables` | array | Artifacts produced |
| `acceptance_test_results` | array | Results of validation criteria |
| `issues` | array | Problems encountered |
| `blockers` | array | Unresolved blockers |
| `effort` | object | Time and contributor tracking |
| `notes` | string | Free-form notes |
| `feedback` | object | Feedback on the request itself |

---

## Status Values

| Status | Meaning | Required Fields |
|--------|---------|-----------------|
| `completed` | All deliverables provided, all acceptance tests pass | `deliverables` |
| `completed_with_issues` | Deliverables provided but with noted concerns | `deliverables`, `issues` |
| `partial` | Some deliverables provided, others not | `deliverables`, `issues` |
| `failed` | Could not complete the task | `issues` (explain why) |
| `blocked` | Cannot proceed without external resolution | `blockers` |
| `withdrawn` | Cluster is stepping back from the task | `completion_summary` (explain why) |

---

## Key Schema Sections

### Deliverables

Artifacts produced by the cluster.

```json
{
  "deliverables": [
    {
      "name": "threat-intel-summary.md",
      "format": "document",
      "location": "https://storage.example.com/deliverables/threat-intel-summary.md",
      "checksum": {
        "algorithm": "sha256",
        "value": "abc123..."
      },
      "size_bytes": 15234,
      "notes": "Covers 7 sources from the past 30 days"
    }
  ]
}
```

**Deliverable Formats:**
- `document` - Written content (markdown, PDF, etc.)
- `code` - Source code
- `data` - Structured data (CSV, JSON, etc.)
- `report` - Formal report
- `artifact` - Other build artifact
- `other` - Freeform

### Issues

Problems encountered during execution. **Mandatory disclosure.**

```json
{
  "issues": [
    {
      "issue_type": "scope_ambiguity",
      "description": "The term 'threat intelligence' was interpreted broadly; unclear if nation-state actors were in scope",
      "severity": "minor",
      "resolution": "Included nation-state threats but flagged for clarification",
      "escalated": false
    },
    {
      "issue_type": "resource_unavailable",
      "description": "One approved source (example-feed.com) was down during research period",
      "severity": "minor",
      "resolution": "Substituted with alternative approved source",
      "escalated": false
    }
  ]
}
```

**Issue Types:**
- `blocker` - Cannot proceed
- `constraint_conflict` - Constraints are mutually exclusive
- `resource_unavailable` - Required resource not available
- `scope_ambiguity` - Unclear what was being asked
- `quality_concern` - Concerns about output quality
- `timeline_risk` - Deadline at risk
- `external_dependency` - Waiting on external party
- `other` - Freeform

**Severity Levels:**
- `critical` - Task cannot succeed without resolution
- `major` - Significant impact on outcome
- `minor` - Noted but manageable
- `informational` - For awareness only

### Blockers

Unresolved blockers that prevented completion. **Required if status is `blocked`.**

```json
{
  "blockers": [
    {
      "blocker_type": "access_denied",
      "description": "Cannot access the approved source list - received 403 Forbidden",
      "suggested_resolution": "Request access credentials or provide alternative source list",
      "owner": "Earl"
    }
  ]
}
```

**Blocker Types:**
- `missing_information` - Need more details to proceed
- `access_denied` - Cannot access required resource
- `dependency_failed` - Another task/system failed
- `resource_unavailable` - Resource doesn't exist
- `constraint_impossible` - Constraints cannot all be satisfied
- `external_system_down` - External dependency unavailable
- `other` - Freeform

### Steward Attestation (Required)

The steward must attest that the result is accurate and complete.

```json
{
  "audit": {
    "created_at": "2026-01-18T16:30:00Z",
    "trace_id": "trace-abc123",
    "steward_attestation": {
      "attested": true,
      "attested_at": "2026-01-18T16:30:00Z",
      "attestation_method": "manual_review"
    }
  }
}
```

**Critical:** `attested` is a schema constant that must be `true`. A result cannot be submitted without steward attestation.

**Attestation Methods:**
- `manual_review` - Steward personally reviewed
- `automated_check` - Automated validation passed, steward approved
- `delegated` - Steward delegated review to cluster member

### Feedback (Optional)

Clusters can provide feedback on the request itself, improving future activations.

```json
{
  "feedback": {
    "request_clarity": "mostly_clear",
    "constraints_reasonable": true,
    "deadline_achievable": true,
    "suggestions": "Including example output format would help future similar requests"
  }
}
```

---

## Complete Example

```json
{
  "result_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "version": "1.0.0",
  "submitted_at": "2026-01-18T16:30:00Z",
  "cluster_id": "9c5f8a55-06f2-4f2b-bd95-0d2b9d14b0c4",
  "steward_id": "steward-17",
  "status": "completed",
  "completion_summary": "Research completed covering 7 threat intelligence sources from the past 30 days. Identified 3 significant threat patterns relevant to the security posture review. No anomalies detected beyond baseline expectations.",
  "deliverables": [
    {
      "name": "threat-intel-summary.md",
      "format": "document",
      "location": "https://storage.example.com/deliverables/threat-intel-summary.md",
      "checksum": {
        "algorithm": "sha256",
        "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      },
      "size_bytes": 15234
    },
    {
      "name": "source-list.csv",
      "format": "data",
      "location": "https://storage.example.com/deliverables/source-list.csv",
      "size_bytes": 2048,
      "notes": "Optional deliverable - included for reference"
    }
  ],
  "acceptance_test_results": [
    {
      "test": "Summary covers at least 5 sources",
      "passed": true,
      "notes": "Covered 7 sources"
    },
    {
      "test": "Each source dated within last 30 days",
      "passed": true
    },
    {
      "test": "Threat types are categorized",
      "passed": true
    },
    {
      "test": "Relevance assessment included",
      "passed": true
    }
  ],
  "issues": [],
  "effort": {
    "started_at": "2026-01-17T09:00:00Z",
    "completed_at": "2026-01-18T15:00:00Z",
    "estimated_hours": 8,
    "actual_hours": 10,
    "contributors_count": 2
  },
  "notes": "Excellent approved source list - made the research straightforward. Consider adding a few more sources for future requests.",
  "feedback": {
    "request_clarity": "clear",
    "constraints_reasonable": true,
    "deadline_achievable": true
  },
  "audit": {
    "created_at": "2026-01-18T16:30:00Z",
    "trace_id": "trace-abc123",
    "steward_attestation": {
      "attested": true,
      "attested_at": "2026-01-18T16:30:00Z",
      "attestation_method": "manual_review"
    }
  }
}
```

See [examples/task-result-example.json](./examples/task-result-example.json) for the full example.

---

## Validation

### Schema Validation

```bash
ajv validate -s schemas/task-result-artifact.json -d result.json
```

### Semantic Validation

Beyond schema validation, verify:

1. **request_id exists** - References a real activation request
2. **cluster_id matches** - Cluster that accepted the request
3. **steward_id matches** - Steward associated with that cluster
4. **Deliverables exist** - Locations are accessible
5. **Checksums match** - Integrity verification passes

### Business Rule Validation

| Status | Required Validation |
|--------|---------------------|
| `blocked` | `blockers` array must be non-empty |
| `failed` | `issues` array must explain failure |
| `partial` | `deliverables` present but `issues` explain gaps |
| `completed` | All required deliverables present |

---

## Earl Processing

When an Earl receives a result artifact:

1. **Validate schema** - Reject malformed results
2. **Verify attestation** - Steward must have attested
3. **Check deliverables** - Verify locations and checksums
4. **Aggregate status** - Update task state
5. **Handle blockers** - If blocked, determine resolution path
6. **Forward to Duke** - Results integrated into program

The Earl **does not judge quality**. They **report reality**.

---

## Related Documents

- [Task Activation Request](./task-activation-request.md) - What the cluster is responding to
- [Cluster Schema](./cluster-schema.md) - Who submits these results
- [Task Lifecycle](./task-lifecycle.md) - State transitions
- [Enforcement Flow](./enforcement-flow.md) - Handling violations

