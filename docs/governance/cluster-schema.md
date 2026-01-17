# Aegis Cluster Schema

> **The Cluster is the smallest unit where work happens. Clusters are not commanded - they are activated.**

## Overview

This document defines the JSON schema for Aegis Clusters and the Critical Runtime Rules that govern their operation. The schema ensures human-in-the-loop execution without enabling coercion.

**Schema Version:** 1.0.0
**JSON Schema Draft:** 2020-12
**Schema File:** [schemas/cluster-schema.json](./schemas/cluster-schema.json)

---

## Schema Structure

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `cluster_id` | UUID | Stable identifier for the cluster |
| `version` | string | Schema version (currently "1.0.0") |
| `status` | enum | `active`, `paused`, or `retired` |
| `steward` | object | Human accountable operator |
| `capabilities` | object | What the cluster can do |
| `capacity` | object | How much work the cluster can accept |
| `consent_policy` | object | Explicit consent rules (prevents coercion) |
| `audit` | object | Auditability requirements |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable cluster name |
| `members` | object | Aggregate member count (privacy-preserving) |
| `interfaces` | object | Intake and delivery channels |

---

## Key Schema Sections

### Steward (Required)

The human point of accountability.

```json
{
  "steward": {
    "steward_id": "steward-17",
    "display_name": "Cluster Steward 17",
    "contact": {
      "channel": "slack",
      "address": "#aegis-cluster-17"
    },
    "auth_level": "standard"
  }
}
```

**Authorization Levels:**
- `standard` - Can accept standard-sensitivity tasks
- `sensitive` - Can accept sensitive tasks (requires gate)
- `restricted` - Can accept all task sensitivity levels

### Capabilities (Required)

What the cluster can do, declared and auditable.

```json
{
  "capabilities": {
    "tags": ["research", "analysis", "writing"],
    "tooling": ["google_docs", "github"],
    "domain_focus": ["security", "ai_governance"]
  }
}
```

**Capability Tags:**
`research`, `analysis`, `writing`, `review`, `design`, `dev_backend`, `dev_frontend`, `devops`, `security`, `data_engineering`, `qa_testing`, `product_ops`, `community_ops`, `incident_response`, `compliance_ops`, `other`

### Capacity (Required)

How much work the cluster can accept **without lying**.

```json
{
  "capacity": {
    "availability_status": "available",
    "max_concurrent_tasks": 3,
    "max_weekly_task_load": 10,
    "timezone": "America/Chicago",
    "hours_of_operation": {
      "start_local": "09:00",
      "end_local": "17:00"
    }
  }
}
```

**Availability Status:**
- `available` - Open for new tasks
- `limited` - Accepting only high-priority tasks
- `unavailable` - Not accepting new tasks

### Consent Policy (Required)

**This is what prevents coercion.**

```json
{
  "consent_policy": {
    "requires_explicit_acceptance": true,
    "refusal_is_penalty_free": true,
    "acceptance_method": "steward_accepts",
    "task_types_allowed": ["research_summary", "testing_validation"],
    "sensitive_task_gate": {
      "enabled": true,
      "requires_steward_auth_level": "sensitive"
    }
  }
}
```

**Critical Constants (Schema-Enforced):**
- `requires_explicit_acceptance`: **must be `true`**
- `refusal_is_penalty_free`: **must be `true`**

These are `const` values in the JSON schema - they cannot be overridden at the instance level. The ethics are baked into the contract.

**Acceptance Methods:**
- `steward_accepts` - Steward makes the decision
- `member_vote` - Democratic cluster decision
- `hybrid` - Steward proposes, members ratify

**Task Types Allowed:**
`research_summary`, `implementation_work`, `security_review`, `incident_support`, `content_creation`, `testing_validation`, `ops_runbook`, `governance_support`, `other`

### Audit (Required)

Auditability requirements for the cluster.

```json
{
  "audit": {
    "created_at": "2026-01-15T22:00:00Z",
    "updated_at": "2026-01-15T22:00:00Z",
    "audit_level": "standard",
    "event_log_enabled": true,
    "data_retention_days": 365
  }
}
```

**Note:** `event_log_enabled` is a schema constant - it must be `true`. All cluster decisions must be logged.

---

## Critical Runtime Rules

These rules **cannot be enforced by schema alone** - they require runtime validation and monitoring.

### CR-1: No Silent Assignment

A task is **never** considered "in progress" until:
- Cluster Steward explicitly accepts, **OR**
- Cluster acceptance method completes (member_vote, etc.)

**Violation indicator:** Task state changes to `in_progress` without corresponding acceptance event.

### CR-2: Refusal is Penalty-Free

Declining a task **cannot reduce**:
- Cluster standing
- Access
- Future invitations

If you later want "reliability scoring," it must be opt-in and disclosed.

**Violation indicator:** Cluster metrics degraded after decline, or fewer activations routed after refusal.

### CR-3: Steward is Accountable

All task accept/decline decisions must be recorded as an **append-only event** with:
- Timestamp
- Steward ID
- Task ID
- Decision
- Reason (optional)

**Violation indicator:** Decision exists without corresponding audit event.

### CR-4: Earl Cannot Bypass the Steward

Earl may **only**:
- Request activation
- Receive accept/decline
- Receive deliverables

Earl **cannot**:
- Force acceptance
- Route around refusal
- Inject results without cluster submission

**Violation indicator:** Task completes without cluster acceptance, or results appear without steward attestation.

---

## Validation

### Schema Validation

Validate cluster definitions against the JSON schema:

```bash
# Using ajv-cli
ajv validate -s schemas/cluster-schema.json -d cluster-definition.json

# Using Python jsonschema
python -c "
import json
from jsonschema import validate
schema = json.load(open('schemas/cluster-schema.json'))
data = json.load(open('cluster-definition.json'))
validate(data, schema)
print('Valid')
"
```

### Runtime Validation

Critical Runtime Rules require monitoring:

| Rule | Detection Method |
|------|------------------|
| CR-1 | Compare task state transitions to acceptance events |
| CR-2 | Monitor cluster metrics after decline events |
| CR-3 | Audit log completeness checks |
| CR-4 | Provenance verification on all results |

The **Knight-Witness** is responsible for monitoring these rules.

---

## Example: Minimal Valid Cluster

```json
{
  "cluster_id": "9c5f8a55-06f2-4f2b-bd95-0d2b9d14b0c4",
  "version": "1.0.0",
  "name": "Aegis Cluster 17 — Research & Analysis",
  "status": "active",
  "steward": {
    "steward_id": "steward-17",
    "display_name": "Cluster Steward 17",
    "contact": {
      "channel": "slack",
      "address": "#aegis-cluster-17"
    },
    "auth_level": "standard"
  },
  "members": {
    "member_count": 18
  },
  "capabilities": {
    "tags": ["research", "analysis", "writing"],
    "tooling": ["google_docs", "github"],
    "domain_focus": ["security", "ai_governance"]
  },
  "capacity": {
    "availability_status": "available",
    "max_concurrent_tasks": 3,
    "max_weekly_task_load": 10,
    "timezone": "America/Chicago",
    "hours_of_operation": {
      "start_local": "09:00",
      "end_local": "17:00"
    }
  },
  "consent_policy": {
    "requires_explicit_acceptance": true,
    "refusal_is_penalty_free": true,
    "acceptance_method": "steward_accepts",
    "task_types_allowed": ["research_summary", "testing_validation"],
    "sensitive_task_gate": {
      "enabled": true,
      "requires_steward_auth_level": "sensitive"
    }
  },
  "interfaces": {
    "intake_channels": ["web_portal", "slack"],
    "delivery_channels": ["web_portal", "slack"]
  },
  "audit": {
    "created_at": "2026-01-15T22:00:00Z",
    "updated_at": "2026-01-15T22:00:00Z",
    "audit_level": "standard",
    "event_log_enabled": true,
    "data_retention_days": 365
  }
}
```

See [examples/cluster-17-example.json](./examples/cluster-17-example.json) for the full example.

---

## Related Documents

- [Aegis Network](./aegis-network.md) - Network overview and architecture
- [Task Activation Request](./task-activation-request.md) - How Earls request work
- [Task Result Artifact](./task-result-artifact.md) - How Clusters report results
- [Enforcement Flow](./enforcement-flow.md) - Violation handling

