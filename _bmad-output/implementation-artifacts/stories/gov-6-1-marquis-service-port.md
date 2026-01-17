# Story GOV-6.1: Define Marquis Service Port (Advisory Branch)

Status: pending

## Story

As a **developer**,
I want **an abstract port defining Marquis advisory capabilities**,
So that **expert testimony has clear boundaries**.

## Acceptance Criteria

### AC1: Protocol Implements PermissionEnforcerProtocol

**Given** a `MarquisServiceProtocol` is defined in `src/application/ports/marquis_service.py`
**When** the protocol is instantiated
**Then** it enforces permission checks via the PermissionEnforcerProtocol
**And** only Archons with `original_rank: Marquis` can invoke Marquis methods

### AC2: Advisory Methods

**Given** the Marquis advisory role (FR-GOV-17)
**When** methods are specified
**Then** it includes:
  - `provide_testimony(domain: str, question: str)` - Provide expert testimony on domain
  - `issue_advisory(topic: str, recommendation: str)` - Issue non-binding advisory
  - `analyze_risk(proposal: str)` - Analyze risks in a proposal
  - `get_expertise_domains()` - Return list of expertise domains (Science, Ethics, Language, Knowledge)

### AC3: Explicitly Excluded Methods

**Given** the Marquis constraints (FR-GOV-18)
**When** the protocol is reviewed
**Then** it explicitly EXCLUDES (documented as comments):
  - `introduce_motion()` - PROHIBITED (King function)
  - `define_execution()` - PROHIBITED (President function)
  - `execute_task()` - PROHIBITED (Duke/Earl function)
  - `judge_compliance()` - PROHIBITED (Prince function) - especially on domains where advisory was given
  - `witness()` - PROHIBITED (Knight function)

### AC4: Domain Model Types

**Given** Marquis operations require specific data types
**When** domain models are created
**Then** they include:
  - `Advisory` - Advisory issued by Marquis (non-binding)
  - `Testimony` - Expert testimony on a specific question
  - `RiskAnalysis` - Risk analysis of a proposal
  - `ExpertiseDomain` - Enum of expertise domains

### AC5: Non-Binding Nature Enforcement

**Given** advisories are non-binding (FR-GOV-18)
**When** an advisory is issued
**Then** it is explicitly marked as `binding: false`
**And** recipients must acknowledge but need not obey
**And** contrary decisions must document reasoning

### AC6: Expertise Domain Mapping

**Given** the 15 Marquis Archons in archons-base.json
**When** expertise domains are mapped
**Then** they align with the 4 advisory domains:
  - Science (Orias, Gamigin, Amy)
  - Ethics (Vine, Seere, Dantalion, Aim)
  - Language (Crocell, Alloces, Caim)
  - Knowledge (Foras, Barbatos, Stolas, Orobas, Ipos)

## Tasks / Subtasks

- [ ] Task 1: Create Marquis Service Port (AC: 1, 2, 3, 5)
  - [ ] 1.1 Create `src/application/ports/marquis_service.py`
  - [ ] 1.2 Define `MarquisServiceProtocol` abstract base class
  - [ ] 1.3 Add `provide_testimony()` abstract method
  - [ ] 1.4 Add `issue_advisory()` abstract method with non-binding enforcement
  - [ ] 1.5 Add `analyze_risk()` abstract method
  - [ ] 1.6 Add `get_expertise_domains()` abstract method
  - [ ] 1.7 Add explicitly excluded methods as comments (per FR-GOV-18)

- [ ] Task 2: Create Domain Models (AC: 4, 6)
  - [ ] 2.1 Create `ExpertiseDomain` Enum (SCIENCE, ETHICS, LANGUAGE, KNOWLEDGE)
  - [ ] 2.2 Create `Advisory` frozen dataclass with binding=False
  - [ ] 2.3 Create `Testimony` frozen dataclass with domain, question, response
  - [ ] 2.4 Create `RiskAnalysis` frozen dataclass with proposal, risks, recommendations
  - [ ] 2.5 Add `to_dict()` serialization methods to all models

- [ ] Task 3: Create Expertise Domain Mapping (AC: 6)
  - [ ] 3.1 Create mapping of Marquis Archons to expertise domains
  - [ ] 3.2 Create `get_marquis_for_domain(domain)` helper function
  - [ ] 3.3 Validate mapping against archons-base.json

- [ ] Task 4: Unit Tests (AC: 1-6)
  - [ ] 4.1 Create `tests/unit/application/ports/test_marquis_service.py`
  - [ ] 4.2 Test domain model creation and immutability
  - [ ] 4.3 Test non-binding enforcement
  - [ ] 4.4 Test expertise domain mapping

## Dev Notes

### Critical Architecture Requirements

**Constitutional Truths to Honor:**
- **CT-11:** Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12:** Witnessing creates accountability → All advisories must be witnessed

**Government PRD Requirements:**
- **FR-GOV-17:** Marquis Authority - Provide expert testimony and risk analysis, issue non-binding advisories
- **FR-GOV-18:** Marquis Constraints - Advisories must be acknowledged but not obeyed; cannot judge domains where advisory was given

### Hexagonal Architecture Compliance

**Files to Create:**

| Layer | Path | Purpose |
|-------|------|---------|
| Application/Port | `src/application/ports/marquis_service.py` | Marquis Service Protocol |
| Tests | `tests/unit/application/ports/test_marquis_service.py` | Unit tests |

**Import Rules (CRITICAL):**
```python
# ALLOWED in application/ports/marquis_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from src.application.ports.permission_enforcer import (
    PermissionContext,
    PermissionEnforcerProtocol,
)

# FORBIDDEN
from src.infrastructure import ...  # VIOLATION!
from src.api import ...             # VIOLATION!
```

### Permission Matrix Integration

Per `config/permissions/rank-matrix.yaml` v2.0:
```yaml
Marquis:
  original_rank: "Marquis"
  aegis_rank: "director"
  branch: "advisory"
  allowed_actions:
    - advise
    - deliberate
    - ratify
  prohibited_actions:
    - introduce_motion
    - define_execution
    - execute
    - judge  # Cannot judge domains they advised on
    - witness
  constraints:
    - "Advisories must be acknowledged but are not binding"
    - "Cannot judge domains where advisory was given"
    - "Expertise domains: Science, Ethics, Language, Knowledge"
```

### Domain Model Design

```python
class ExpertiseDomain(Enum):
    """Expertise domains for Marquis advisors."""
    SCIENCE = "science"      # Orias, Gamigin, Amy
    ETHICS = "ethics"        # Vine, Seere, Dantalion, Aim
    LANGUAGE = "language"    # Crocell, Alloces, Caim
    KNOWLEDGE = "knowledge"  # Foras, Barbatos, Stolas, Orobas, Ipos

@dataclass(frozen=True)
class Advisory:
    """A non-binding advisory issued by a Marquis.

    Per FR-GOV-18: Advisories must be acknowledged but not obeyed.
    """
    advisory_id: UUID
    issued_by: str  # Marquis Archon ID
    domain: ExpertiseDomain
    topic: str
    recommendation: str
    rationale: str
    binding: bool = False  # ALWAYS False per FR-GOV-18
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_by: tuple[str, ...] = field(default_factory=tuple)  # Archon IDs

@dataclass(frozen=True)
class Testimony:
    """Expert testimony provided by a Marquis.

    Testimony is formal expert opinion on a specific question.
    """
    testimony_id: UUID
    provided_by: str  # Marquis Archon ID
    domain: ExpertiseDomain
    question: str
    response: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    provided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### Marquis-to-Domain Mapping

Based on archons-base.json (15 Marquis Archons):
```python
MARQUIS_DOMAIN_MAPPING = {
    # Science Domain
    "orias": ExpertiseDomain.SCIENCE,
    "gamigin": ExpertiseDomain.SCIENCE,
    "amy": ExpertiseDomain.SCIENCE,

    # Ethics Domain
    "vine": ExpertiseDomain.ETHICS,
    "seere": ExpertiseDomain.ETHICS,
    "dantalion": ExpertiseDomain.ETHICS,
    "aim": ExpertiseDomain.ETHICS,

    # Language Domain
    "crocell": ExpertiseDomain.LANGUAGE,
    "alloces": ExpertiseDomain.LANGUAGE,
    "caim": ExpertiseDomain.LANGUAGE,

    # Knowledge Domain
    "foras": ExpertiseDomain.KNOWLEDGE,
    "barbatos": ExpertiseDomain.KNOWLEDGE,
    "stolas": ExpertiseDomain.KNOWLEDGE,
    "orobas": ExpertiseDomain.KNOWLEDGE,
    "ipos": ExpertiseDomain.KNOWLEDGE,
}
```

### References

- [Source: _bmad-output/planning-artifacts/government-epics.md#Epic 6: Marquis Service]
- [Source: config/permissions/rank-matrix.yaml#Marquis]
- [Source: docs/archons-base.json#Marquis Archons (15)]
- [Source: docs/new-requirements.md#FR-GOV-17, FR-GOV-18]
- [Source: src/application/ports/permission_enforcer.py#PermissionEnforcerProtocol]
