# Test Design: Epic 1 - Witnessed Event Store

**Date:** 2026-01-06
**Author:** Grand Architect
**Status:** Draft

---

## Executive Summary

**Scope:** Epic-level test design for Epic 1: Witnessed Event Store

**Risk Summary:**

- Total risks identified: 12
- High-priority risks (≥6): 5
- Critical categories: SEC (3), DATA (2), TECH (2), OPS (2), PERF (2), BUS (1)

**Coverage Summary:**

- P0 scenarios: 18 (~36 hours)
- P1 scenarios: 22 (~22 hours)
- P2/P3 scenarios: 15 (~8 hours)
- **Total effort**: ~66 hours (~8 days)

---

## Risk Assessment

### High-Priority Risks (Score ≥6)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner | Timeline |
|---------|----------|-------------|-------------|--------|-------|------------|-------|----------|
| R-001 | SEC | Unwitnessed event bypass - attacker inserts event without witness | 2 | 3 | 6 | DB trigger `validate_witness_attribution()` enforces at lowest level; RT-1 atomic write pattern | Dev | Done (Story 1-4) |
| R-002 | DATA | Hash chain broken - event inserted with wrong prev_hash | 2 | 3 | 6 | DB trigger `verify_hash_chain()` rejects; `verify_chain()` function for audit | Dev | Done (Story 1-2) |
| R-003 | SEC | Agent signature forgery - fake agent signature accepted | 2 | 3 | 6 | Ed25519 verification in DB trigger; key registry with historical keys | Dev | Done (Story 1-3) |
| R-004 | DATA | Append-only violation - UPDATE/DELETE succeeds | 2 | 3 | 6 | DB triggers prevent UPDATE/DELETE/TRUNCATE; PREVENT_DELETE mixin | Dev | Done (Story 1-1) |
| R-005 | OPS | Sequence gap - concurrent inserts create gaps | 2 | 3 | 6 | BIGSERIAL guarantees; gap detection in Story 1-5 | Dev | Story 1-5 |

### Medium-Priority Risks (Score 3-4)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner |
|---------|----------|-------------|-------------|--------|-------|------------|-------|
| R-006 | PERF | Write latency >100ms (NFR1 violation) | 2 | 2 | 4 | Benchmark tests; DB index optimization | Dev |
| R-007 | TECH | Supabase trigger limitations | 2 | 2 | 4 | Spike story 1-7 validates approach | Dev |
| R-008 | SEC | Witness key compromise undetected | 1 | 3 | 3 | Key rotation; witness signature verification | Dev |
| R-009 | OPS | Clock drift >5s undetected | 2 | 2 | 4 | TimeAuthorityService logging (Story 1-5) | Dev |
| R-010 | TECH | HSM dev/prod mode mismatch | 1 | 3 | 3 | RT-1 mode watermark inside signature | Dev |

### Low-Priority Risks (Score 1-2)

| Risk ID | Category | Description | Probability | Impact | Score | Action |
|---------|----------|-------------|-------------|--------|-------|--------|
| R-011 | BUS | Genesis hash constant wrong | 1 | 2 | 2 | Hardcoded constant validated in tests |
| R-012 | PERF | Hash computation overhead | 1 | 1 | 1 | Monitor; SHA-256 is fast |

### Risk Category Legend

- **TECH**: Technical/Architecture (flaws, integration, scalability)
- **SEC**: Security (access controls, auth, data exposure)
- **PERF**: Performance (SLA violations, degradation, resource limits)
- **DATA**: Data Integrity (loss, corruption, inconsistency)
- **BUS**: Business Impact (UX harm, logic errors, revenue)
- **OPS**: Operations (deployment, config, monitoring)

---

## Test Coverage Plan

### P0 (Critical) - Run on every commit

**Criteria**: Blocks core journey + High risk (≥6) + No workaround

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| Append-only enforcement (FR102) | Integration | R-004 | 3 | Dev | UPDATE/DELETE/TRUNCATE blocked |
| Hash chain verification (FR82) | Integration | R-002 | 4 | Dev | Chain integrity, prev_hash validation |
| Agent signature validation (FR74) | Integration | R-003 | 3 | Dev | Ed25519 verification, invalid rejection |
| Witness attribution atomic (FR4-5, RT-1) | Integration | R-001 | 4 | Dev | Atomic write, no witness = blocked |
| Event domain model validation | Unit | R-004 | 4 | Dev | DeletePreventionMixin, frozen dataclass |

**Total P0**: 18 tests, ~36 hours

### P1 (High) - Run on PR to main

**Criteria**: Important features + Medium risk (3-4) + Common workflows

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| Dual timestamps (FR6-7) | Integration | R-005, R-009 | 4 | Dev | local_timestamp, authority_timestamp, sequence |
| Clock drift detection | Unit | R-009 | 3 | Dev | TimeAuthorityService threshold |
| Hash chain continuity | Integration | R-002 | 3 | Dev | verify_chain() function |
| Key registry operations | Integration | R-008 | 4 | Dev | Agent/witness key lookup, historical keys |
| Event factory create_with_hash | Unit | - | 3 | Dev | Hash computation, prev_hash logic |
| Sequence gap detection | Integration | R-005 | 3 | Dev | Observer query helpers |
| HSM mode watermark | Unit | R-010 | 2 | Dev | SignableContent RT-1 pattern |

**Total P1**: 22 tests, ~22 hours

### P2 (Medium) - Run nightly/weekly

**Criteria**: Secondary features + Low risk (1-2) + Edge cases

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| Genesis hash constant | Unit | R-011 | 2 | Dev | GENESIS_HASH validation |
| Algorithm version fields | Unit | - | 2 | Dev | hash_alg_version, sig_alg_version |
| Event payload immutability | Unit | - | 2 | Dev | MappingProxyType frozen |
| Canonical JSON serialization | Unit | - | 3 | Dev | Deterministic ordering |
| Error message formats | Unit | - | 3 | Dev | FR-prefixed codes |
| InMemoryWitnessPool round-robin | Unit | - | 3 | Dev | Selection strategy |

**Total P2**: 15 tests, ~8 hours

### P3 (Low) - Run on-demand

**Criteria**: Nice-to-have + Exploratory + Performance benchmarks

| Requirement | Test Level | Test Count | Owner | Notes |
|-------------|------------|------------|-------|-------|
| Write latency benchmark | Performance | 2 | Dev | NFR1 <100ms validation |
| Hash computation benchmark | Performance | 2 | Dev | SHA-256 overhead |
| Concurrent insert stress test | Performance | 2 | Dev | Sequence uniqueness under load |

**Total P3**: 6 tests, ~6 hours

---

## Execution Order

### Smoke Tests (<5 min)

**Purpose**: Fast feedback, catch build-breaking issues

- [x] Event domain model instantiation (30s)
- [x] Hash computation basic (30s)
- [x] Signature generation basic (30s)
- [x] Witness model validation (30s)
- [x] Import boundary check (1min)

**Total**: 5 scenarios

### P0 Tests (<10 min)

**Purpose**: Critical path validation

- [x] Event INSERT succeeds with valid data
- [x] UPDATE rejected with FR102 error
- [x] DELETE rejected with FR102 error
- [x] Hash chain verification passes for valid chain
- [x] Hash chain verification fails for broken chain
- [x] Agent signature valid → accepted
- [x] Agent signature invalid → rejected FR74
- [x] Witness attribution present → accepted
- [x] Witness attribution missing → rejected FR5
- [x] Atomic write with witness succeeds
- [x] Atomic write without witness blocked (RT-1)

**Total**: 11 scenarios (subset of 18 P0 tests)

### P1 Tests (<30 min)

**Purpose**: Important feature coverage

- [ ] Dual timestamps on event creation
- [ ] Sequence uniqueness with concurrent inserts
- [ ] Clock drift warning when >5s
- [ ] Clock drift table populated
- [ ] Key registry lookup by agent_id
- [ ] Historical key lookup for old events
- [ ] Genesis event has correct prev_hash
- [ ] Sequence gap detection returns gaps

**Total**: 8 scenarios (subset of 22 P1 tests)

### P2/P3 Tests (<60 min)

**Purpose**: Full regression coverage

- [ ] All edge cases
- [ ] Performance benchmarks
- [ ] Stress tests

**Total**: 21 scenarios

---

## Resource Estimates

### Test Development Effort

| Priority | Count | Hours/Test | Total Hours | Notes |
|----------|-------|------------|-------------|-------|
| P0 | 18 | 2.0 | 36 | Critical security + data integrity |
| P1 | 22 | 1.0 | 22 | Standard coverage |
| P2 | 15 | 0.5 | 8 | Simple scenarios |
| P3 | 6 | 1.0 | 6 | Performance tests |
| **Total** | **61** | **-** | **~72** | **~9 days** |

### Prerequisites

**Test Data:**

- `EventFactory` - Creates valid Event instances with computed hashes
- `AgentKeyFactory` - Generates Ed25519 key pairs for testing
- `WitnessFactory` - Creates Witness instances with valid keys

**Tooling:**

- pytest + pytest-asyncio for async tests
- DevHSM for cryptographic operations
- In-memory PostgreSQL or test container

**Environment:**

- Local dev environment with Makefile targets
- CI pipeline with PostgreSQL service

---

## Quality Gate Criteria

### Pass/Fail Thresholds

- **P0 pass rate**: 100% (no exceptions)
- **P1 pass rate**: ≥95% (waivers required for failures)
- **P2/P3 pass rate**: ≥90% (informational)
- **High-risk mitigations**: 100% complete or approved waivers

### Coverage Targets

- **Critical paths**: ≥80%
- **Security scenarios (SEC)**: 100%
- **Data integrity (DATA)**: 100%
- **Business logic**: ≥70%

### Non-Negotiable Requirements

- [x] All P0 tests pass
- [x] No high-risk (≥6) items unmitigated
- [x] Security tests (SEC category) pass 100%
- [ ] Story 1-5 (Dual Time Authority) completes P1 coverage

---

## Mitigation Plans

### R-001: Unwitnessed Event Bypass (Score: 6) - MITIGATED

**Mitigation Strategy:** DB trigger `validate_witness_attribution()` checks witness_id NOT NULL and witness_signature NOT NULL on every INSERT. AtomicEventWriter ensures witness selection before event creation.

**Owner:** Dev
**Timeline:** Done (Story 1-4)
**Status:** Complete
**Verification:** Integration tests in `test_witness_attribution_integration.py`

### R-002: Hash Chain Broken (Score: 6) - MITIGATED

**Mitigation Strategy:** DB trigger `verify_hash_chain_on_insert()` computes expected prev_hash and rejects mismatches. `verify_chain()` SQL function audits full chain.

**Owner:** Dev
**Timeline:** Done (Story 1-2)
**Status:** Complete
**Verification:** Integration tests in `test_hash_chain_integration.py`

### R-003: Agent Signature Forgery (Score: 6) - MITIGATED

**Mitigation Strategy:** Ed25519 signature verification in application layer via SigningService. Key registry maintains public keys with validity periods.

**Owner:** Dev
**Timeline:** Done (Story 1-3)
**Status:** Complete
**Verification:** Integration tests in `test_agent_signing_integration.py`

### R-004: Append-Only Violation (Score: 6) - MITIGATED

**Mitigation Strategy:** DB triggers `prevent_event_update` and `prevent_event_delete` block UPDATE/DELETE. `REVOKE TRUNCATE` prevents TRUNCATE. Domain model uses DeletePreventionMixin.

**Owner:** Dev
**Timeline:** Done (Story 1-1)
**Status:** Complete
**Verification:** Integration tests in `test_event_store_integration.py`

### R-005: Sequence Gap (Score: 6) - IN PROGRESS

**Mitigation Strategy:** BIGSERIAL guarantees unique monotonic sequences. TimeAuthorityService validates sequence continuity. Observer query helpers expose gap detection.

**Owner:** Dev
**Timeline:** Story 1-5 (ready-for-dev)
**Status:** In Progress
**Verification:** Integration tests planned in `test_time_authority_integration.py`

---

## Assumptions and Dependencies

### Assumptions

1. PostgreSQL 16 supports all required trigger functionality
2. Ed25519 signatures are 64 bytes (88 base64 chars)
3. DevHSM adequately simulates production HSM for testing
4. SHA-256 hash computation is deterministic across environments

### Dependencies

1. Story 1-5 completion - Required for P1 coverage of dual timestamps
2. PostgreSQL test container - Required for integration tests
3. DevHSM implementation - Required for signature tests

### Risks to Plan

- **Risk**: Supabase trigger spike (Story 1-7) reveals limitations
  - **Impact**: May need alternative enforcement approach
  - **Contingency**: Application-layer validation with compensating controls

---

## Current Test Coverage Status

### Completed Tests (Stories 1-1 through 1-4)

| Test File | Count | Status |
|-----------|-------|--------|
| `tests/unit/domain/test_event.py` | 15+ | ✅ Done |
| `tests/unit/domain/test_hash_utils.py` | 10+ | ✅ Done |
| `tests/unit/domain/test_signing.py` | 8+ | ✅ Done |
| `tests/unit/domain/test_agent_key.py` | 8+ | ✅ Done |
| `tests/unit/domain/test_witness.py` | 16 | ✅ Done |
| `tests/unit/application/test_witness_service.py` | 11 | ✅ Done |
| `tests/unit/application/test_atomic_event_writer.py` | 10 | ✅ Done |
| `tests/unit/infrastructure/test_witness_pool.py` | 14 | ✅ Done |
| `tests/unit/infrastructure/test_hsm_dev.py` | 10+ | ✅ Done |
| `tests/integration/test_event_store_integration.py` | 5+ | ✅ Done |
| `tests/integration/test_hash_chain_integration.py` | 5+ | ✅ Done |
| `tests/integration/test_agent_signing_integration.py` | 5+ | ✅ Done |
| `tests/integration/test_witness_attribution_integration.py` | 9 | ✅ Done |
| `tests/integration/test_import_boundary_integration.py` | 5+ | ✅ Done |

**Total existing tests**: 120+

### Tests Needed (Story 1-5)

| Test File | Count | Status |
|-----------|-------|--------|
| `tests/unit/application/test_time_authority_service.py` | 5 | ⏳ Pending |
| `tests/integration/test_time_authority_integration.py` | 6 | ⏳ Pending |

**Tests to add**: ~11

---

## Follow-on Workflows (Manual)

- Run `*atdd` to generate failing P0 tests (separate workflow; not auto-run).
- Run `*automate` for broader coverage once implementation exists.
- Run `code-review` after Story 1-5 completion.

---

## Approval

**Test Design Approved By:**

- [ ] Product Manager: _____ Date: _____
- [ ] Tech Lead: _____ Date: _____
- [ ] QA Lead: _____ Date: _____

**Comments:**

---

## Appendix

### Knowledge Base References

- `risk-governance.md` - Risk classification framework
- `probability-impact.md` - Risk scoring methodology
- `test-levels-framework.md` - Test level selection
- `test-priorities-matrix.md` - P0-P3 prioritization

### Related Documents

- PRD: `docs/prd.md`, `docs/conclave-prd.md`
- Epic: `_bmad-output/planning-artifacts/epics.md#Epic 1`
- Architecture: `_bmad-output/planning-artifacts/architecture.md`
- Project Context: `_bmad-output/project-context.md`

### Constitutional References

- **CT-11**: Silent failure destroys legitimacy → HALT OVER DEGRADE
- **CT-12**: Witnessing creates accountability → Unwitnessed actions invalid
- **CT-13**: Integrity outranks availability → Availability may be sacrificed
- **FR1-FR8**: Core event store requirements
- **RT-1**: HSM mode runtime verification pattern

---

**Generated by**: BMad TEA Agent - Test Architect Module
**Workflow**: `_bmad/bmm/testarch/test-design`
**Version**: 4.0 (BMad v6)
