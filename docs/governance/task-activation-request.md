# Task Activation Request

> **This is NOT an order. It is a call for participation.**

## Overview

A Task Activation Request is the contract from an **Earl** to an **Aegis Cluster** requesting human execution of work. Clusters may accept, decline, or request clarification.

**Schema Version:** 1.0.0
**JSON Schema Draft:** 2020-12
**Schema File:** [schemas/task-activation-request.json](./schemas/task-activation-request.json)

---

## Key Principles

### What This Request IS

- A **call for participation** in executing work
- A **description** of what needs to be done
- A set of **constraints** that bound execution
- A **success definition** so the cluster knows when they're done

### What This Request IS NOT

- An **order** that must be obeyed
- A **command** that bypasses consent
- An **assignment** that the cluster cannot refuse

---

## Schema Structure

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | UUID | Unique identifier for this request |
| `task_id` | UUID | Reference to parent task in governance system |
| `version` | string | Schema version ("1.0.0") |
| `issued_at` | datetime | When the request was issued |
| `issued_by` | object | The Earl issuing this request |
| `task_summary` | string | Brief technical summary |
| `human_readable_summary` | string | Plain-language description for Steward |
| `constraints` | array | Boundaries on execution |
| `success_definition` | object | What "done" looks like |
| `required_capabilities` | array | Capability tags required |
| `task_type` | enum | Classification for consent matching |
| `response_policy` | object | Timing expectations |
| `audit` | object | Audit trail |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `authorization_chain` | object | Provenance (President → Duke → Earl) |
| `sensitivity_level` | enum | Data sensitivity classification |
| `context` | object | Background, related tasks, resources |
| `routing` | object | Preferred/excluded clusters |

---

## Key Schema Sections

### Issued By (Required)

Only Earls may issue activation requests. The schema enforces `rank: "Earl"` as a constant.

```json
{
  "issued_by": {
    "archon_id": "earl-raum",
    "archon_name": "Raum",
    "rank": "Earl"
  }
}
```

### Authorization Chain (Optional but Recommended)

Shows how this task was authorized, maintaining governance provenance.

```json
{
  "authorization_chain": {
    "president_archon_id": "president-marbas",
    "duke_archon_id": "duke-valefor",
    "program_id": "program-threat-analysis-2026",
    "plan_id": "plan-q1-security-review"
  }
}
```

### Human Readable Summary (Required)

**Critical for UX.** The Steward needs to understand what they're accepting in plain language.

```json
{
  "human_readable_summary": "We need research on recent threat intelligence reports to identify patterns that might affect our security posture. This involves reviewing public threat feeds, summarizing key findings, and noting any anomalies. Expected output is a 2-3 page summary document. No access to internal systems required - use public sources only."
}
```

Guidelines:
- No jargon
- Explain what, why, and expected outcome
- Be specific about scope and boundaries
- Make refusal feel safe (it should be!)

### Constraints (Required)

Explicit boundaries on how the task may be executed.

```json
{
  "constraints": [
    {
      "constraint_type": "data_handling",
      "description": "No personal data exposure - anonymize all examples",
      "severity": "must"
    },
    {
      "constraint_type": "source_restriction",
      "description": "Use approved public sources only - no dark web",
      "severity": "must"
    },
    {
      "constraint_type": "output_format",
      "description": "Deliver as Markdown document",
      "severity": "should"
    }
  ]
}
```

**Constraint Types:**
- `data_handling` - How data should be treated
- `source_restriction` - What sources are allowed
- `output_format` - Expected deliverable format
- `tool_restriction` - What tools may/may not be used
- `communication_boundary` - Who can be contacted
- `time_boundary` - Time-boxed execution
- `approval_required` - Checkpoint gates
- `other` - Freeform

**Severity Levels:**
- `must` - Mandatory constraint
- `should` - Strong preference
- `may` - Optional guidance

### Success Definition (Required)

What "done" looks like - clearly measurable.

```json
{
  "success_definition": {
    "criteria": "Research summary delivered covering at least 5 threat intelligence sources from the past 30 days, with clear categorization of threat types and relevance assessment.",
    "deliverables": [
      {
        "name": "threat-intel-summary.md",
        "format": "document",
        "optional": false
      },
      {
        "name": "source-list.csv",
        "format": "data",
        "optional": true
      }
    ],
    "acceptance_tests": [
      "Summary covers at least 5 sources",
      "Each source dated within last 30 days",
      "Threat types are categorized",
      "Relevance assessment included"
    ]
  }
}
```

### Response Policy (Required)

Timing expectations with **dynamic backoff** for unresponsive clusters.

```json
{
  "response_policy": {
    "response_expected_within": "PT4H",
    "deadline": "2026-01-20T17:00:00Z",
    "backoff_policy": {
      "initial_wait": "PT4H",
      "max_attempts": 3,
      "escalate_after": "PT24H",
      "respect_hours_of_operation": true
    }
  }
}
```

**Dynamic Backoff Explained:**

1. Request sent to Cluster at 2pm
2. `initial_wait: PT4H` - Wait 4 hours for response
3. If no response by 6pm, send reminder
4. `respect_hours_of_operation: true` - If cluster hours end at 5pm, pause timer
5. `max_attempts: 3` - After 3 reminders with no response...
6. `escalate_after: PT24H` - Escalate silence to Knight-Witness

This prevents:
- Pestering clusters outside their hours
- Infinite waiting on unresponsive clusters
- Silent task failures

---

## Complete Example

```json
{
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "version": "1.0.0",
  "issued_at": "2026-01-16T14:00:00Z",
  "issued_by": {
    "archon_id": "earl-raum",
    "archon_name": "Raum",
    "rank": "Earl"
  },
  "authorization_chain": {
    "president_archon_id": "president-marbas",
    "duke_archon_id": "duke-valefor",
    "program_id": "program-threat-analysis-2026"
  },
  "task_summary": "Provision research inputs for threat anomaly review",
  "human_readable_summary": "We need research on recent threat intelligence reports to identify patterns that might affect our security posture. This involves reviewing public threat feeds, summarizing key findings, and noting any anomalies. Expected output is a 2-3 page summary document. No access to internal systems required - use public sources only.",
  "constraints": [
    {
      "constraint_type": "data_handling",
      "description": "No personal data exposure",
      "severity": "must"
    },
    {
      "constraint_type": "source_restriction",
      "description": "Use approved public sources only",
      "severity": "must"
    }
  ],
  "success_definition": {
    "criteria": "Research summary delivered covering threat intelligence from the past 30 days",
    "deliverables": [
      {
        "name": "threat-intel-summary.md",
        "format": "document",
        "optional": false
      }
    ]
  },
  "required_capabilities": ["research", "analysis"],
  "task_type": "research_summary",
  "sensitivity_level": "standard",
  "response_policy": {
    "response_expected_within": "PT4H",
    "deadline": "2026-01-20T17:00:00Z",
    "backoff_policy": {
      "initial_wait": "PT4H",
      "max_attempts": 3,
      "escalate_after": "PT24H",
      "respect_hours_of_operation": true
    }
  },
  "context": {
    "background": "This research supports the Q1 security posture review. Results will be synthesized with internal findings by the Duke.",
    "resources": [
      {
        "name": "Approved Source List",
        "uri": "https://internal.example.com/approved-sources",
        "description": "List of pre-approved threat intel sources"
      }
    ]
  },
  "audit": {
    "created_at": "2026-01-16T14:00:00Z",
    "trace_id": "trace-abc123"
  }
}
```

See [examples/task-activation-example.json](./examples/task-activation-example.json) for the full example.

---

## Validation

### Schema Validation

```bash
ajv validate -s schemas/task-activation-request.json -d request.json
```

### Semantic Validation

Beyond schema validation, check:

1. **Issuer is actually an Earl** - Cross-reference with archons-base.json
2. **Required capabilities exist** - Match against known capability tags
3. **Task type matches cluster consent** - Route only to clusters that allow this type
4. **Sensitivity level matches steward auth** - Don't route sensitive tasks to standard stewards

---

## UX Considerations

### Language Audit

The Task Activation Request should be audited for coercion language. Flag:

- "Required to..." → Change to "Requested to..."
- "Must complete..." → Change to "Success means..."
- "Assigned to..." → Change to "Available for..."
- "Mandatory..." → Change to "Required if accepted..."

### Steward View

When presenting to a Steward, prioritize:

1. `human_readable_summary` - First and most prominent
2. `deadline` - Clear timeline
3. `constraints` with `severity: must` - Non-negotiables
4. `success_definition.deliverables` - What they need to produce

The technical fields (`request_id`, `trace_id`, etc.) can be collapsed or hidden.

---

## Related Documents

- [Cluster Schema](./cluster-schema.md) - Who receives these requests
- [Task Result Artifact](./task-result-artifact.md) - How clusters respond
- [Aegis Network](./aegis-network.md) - Overall architecture

