# Executive RFP Layer: From Mandate to Request for Proposal

## Problem Statement

The current Executive Pipeline produces thin outputs (1 Epic, 1 Work Package) from a passed motion. The "How" is not sufficiently debated—we jump straight to implementation artifacts without establishing detailed requirements and constraints.

**Current flow**:
```
Motion PASS → Executive → 1 Epic + 1 Work Package → Administrative
```

**Problem**: The Administrative layer receives vague scope. How can they propose solutions without detailed requirements?

## Proposed Solution: RFP Generation Layer

Transform Executive into an RFP (Request for Proposal) generation layer where all 11 Presidents deliberate the "How" in detail, producing a government-contract-style RFP document.

**Proposed flow**:
```
Motion PASS → Executive Mini-Conclave → RFP Document → Administrative Proposals → Proposal Review
```

## What the RFP Should Contain

Like a government contract RFP, the output should define WHAT is needed without prescribing HOW to build it:

### 1. Background and Context
- Motion text and rationale
- Business justification
- Strategic alignment

### 2. Scope of Work (SOW)
- High-level objectives
- Boundaries (what's in/out of scope)
- Success criteria

### 3. Requirements

**Functional Requirements**:
- What the solution must DO
- User-facing capabilities
- System behaviors

**Non-Functional Requirements**:
- Performance expectations
- Scalability needs
- Reliability/availability targets
- Security requirements
- Compliance requirements

### 4. Constraints

**Technical Constraints**:
- Must integrate with X
- Must not break Y
- Technology boundaries

**Resource Constraints**:
- Budget envelope (if known)
- Timeline expectations
- Available capacity

**Organizational Constraints**:
- Approval requirements
- Change management needs
- Training/documentation requirements

### 5. Evaluation Criteria
- How proposals will be judged
- Weighted priorities (cost vs. speed vs. quality)
- Minimum viable thresholds

### 6. Deliverables
- What the solution must produce
- Acceptance criteria
- Verification methods

### 7. Terms and Conditions
- Governance requirements
- Reporting expectations
- Escalation paths

## What the RFP Should NOT Contain

- Specific implementation tasks
- Specific technologies/brands (unless truly constrained)
- Specific methods/approaches
- Story points or time estimates
- Detailed technical designs

## President Contribution Model

Each President contributes from their portfolio perspective:

| President | Portfolio | Contribution Focus |
|-----------|-----------|-------------------|
| Marbas | Technical Solutions | Technical requirements, integration constraints, solution architecture |
| Glasya-Labolas | Conflict Operations | Risk identification, conflict resolution, adversarial considerations |
| Gaap | Knowledge Transfer | Documentation requirements, training needs, knowledge management |
| Valac | Resource Discovery | Resource constraints, capacity assessment, discovery requirements |
| Malphas | Infrastructure Development | Infrastructure requirements, deployment constraints, platform needs |
| Haagenti | Alchemical Transformation | Transformation requirements, change management, evolution paths |
| Caim | Behavioral Intelligence | User behavior requirements, intelligence gathering, analytics needs |
| Buer | Wellness & Recovery | Reliability requirements, recovery procedures, health monitoring |
| Amy | Astrology & Divination | Forecasting requirements, prediction capabilities, planning horizons |
| Ose | Identity & Perception | Identity requirements, perception management, brand considerations |
| Foras | Herbalism & Ethics | Ethical requirements, compliance constraints, governance needs |

## Mini-Conclave Process

### Phase 1: Requirements Elicitation
Each President analyzes the motion from their portfolio lens and identifies:
- Requirements relevant to their domain
- Constraints they can identify
- Risks they foresee
- Dependencies on other portfolios

### Phase 2: Cross-Portfolio Discussion
Presidents debate and refine:
- Conflicting requirements
- Overlapping constraints
- Dependency chains
- Priority weighting

### Phase 3: RFP Synthesis
Consolidate contributions into a unified RFP document:
- Merge compatible requirements
- Resolve conflicts (or flag for escalation)
- Establish evaluation criteria
- Define acceptance thresholds

## RFP Document Schema

```json
{
  "schema_version": "1.0",
  "rfp_id": "rfp-<uuid>",
  "mandate_id": "mandate-<uuid>",
  "created_at": "ISO8601",
  "status": "draft|final",

  "background": {
    "motion_title": "string",
    "motion_text": "string",
    "business_justification": "string",
    "strategic_alignment": ["string"]
  },

  "scope_of_work": {
    "objectives": ["string"],
    "in_scope": ["string"],
    "out_of_scope": ["string"],
    "success_criteria": ["string"]
  },

  "requirements": {
    "functional": [
      {
        "req_id": "FR-001",
        "description": "string",
        "priority": "must|should|could|wont",
        "source_portfolio": "portfolio_id",
        "acceptance_criteria": ["string"]
      }
    ],
    "non_functional": [
      {
        "req_id": "NFR-001",
        "category": "performance|security|reliability|scalability|usability|compliance",
        "description": "string",
        "target_metric": "string",
        "threshold": "string",
        "source_portfolio": "portfolio_id"
      }
    ]
  },

  "constraints": {
    "technical": [
      {
        "constraint_id": "TC-001",
        "description": "string",
        "rationale": "string",
        "source_portfolio": "portfolio_id",
        "negotiable": true|false
      }
    ],
    "resource": [
      {
        "constraint_id": "RC-001",
        "resource_type": "budget|time|capacity|skills",
        "description": "string",
        "limit": "string",
        "source_portfolio": "portfolio_id"
      }
    ],
    "organizational": [
      {
        "constraint_id": "OC-001",
        "description": "string",
        "source_portfolio": "portfolio_id"
      }
    ]
  },

  "evaluation_criteria": [
    {
      "criterion_id": "EC-001",
      "name": "string",
      "description": "string",
      "weight": 0.0-1.0,
      "scoring_method": "string"
    }
  ],

  "deliverables": [
    {
      "deliverable_id": "D-001",
      "name": "string",
      "description": "string",
      "acceptance_criteria": ["string"],
      "verification_method": "string"
    }
  ],

  "terms": {
    "governance_requirements": ["string"],
    "reporting_expectations": ["string"],
    "escalation_paths": ["string"],
    "change_management": "string"
  },

  "contributing_portfolios": [
    {
      "portfolio_id": "string",
      "president_name": "string",
      "contribution_summary": "string",
      "requirements_contributed": ["req_id"],
      "constraints_contributed": ["constraint_id"]
    }
  ],

  "unresolved_conflicts": [
    {
      "conflict_id": "string",
      "description": "string",
      "parties": ["portfolio_id"],
      "proposed_resolution": "string",
      "escalate_to_conclave": true|false
    }
  ]
}
```

## Implementation Phases

### Phase 1: RFP Domain Models
- `src/domain/models/rfp.py`
- RFP, Requirement, Constraint, EvaluationCriterion, Deliverable models

### Phase 2: RFP Service
- `src/application/services/rfp_generation_service.py`
- Orchestrates mini-conclave deliberation
- Synthesizes contributions into RFP

### Phase 3: President RFP Contribution Adapter
- Enhance `PresidentCrewAIAdapter` with RFP contribution mode
- Each President generates requirements/constraints from their lens

### Phase 4: RFP Output Integration
- Update Executive Pipeline to produce RFP as primary output
- RFP becomes input to Administrative Pipeline

### Phase 5: Proposal Review Subprocess
- Administrative produces proposals against RFP
- Review process evaluates proposals against evaluation criteria

## Migration Path

1. **Additive**: Add RFP generation alongside existing Epic/WorkPackage output
2. **Parallel**: Run both paths, compare outputs
3. **Replace**: RFP becomes the primary Executive output

## Downstream Impact

### Administrative Pipeline Changes
- Input: RFP Document (not vague handoff)
- Output: Detailed proposals addressing each requirement
- Proposals scored against evaluation criteria

### Earl Tasking Changes
- Waits for proposal acceptance
- Tasks derived from accepted proposal (not from thin Epic)

## Questions to Resolve

1. **Deliberation depth**: How many rounds of President discussion?
2. **Conflict resolution**: What triggers Conclave escalation?
3. **RFP approval**: Does the RFP need sign-off before going to Administrative?
4. **Proposal format**: What schema should Administrative proposals follow?
5. **Selection process**: How are winning proposals chosen?

## Summary

| Current | Proposed |
|---------|----------|
| Motion → thin Epic | Motion → detailed RFP |
| 1 President owns | 11 Presidents contribute |
| Vague scope | Detailed requirements |
| Administrative guesses | Administrative responds to spec |
| No evaluation criteria | Clear scoring rubric |

**Principle**: "Executive defines WHAT is needed. Administrative proposes HOW to deliver it."
