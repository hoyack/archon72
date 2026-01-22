# Story 8.3: Orphan Petition Detection - Implementation Summary

**Date:** 2026-01-22
**Story:** Petition Epic 8, Story 8.3
**Requirements:** FR-8.5, NFR-7.1
**Status:** ✅ Complete (Production Ready)

## Overview

Implemented orphan petition detection system to identify petitions stuck in RECEIVED state for >24 hours, with manual reprocessing capabilities and comprehensive audit trail.

## Constitutional Compliance

- **FR-8.5**: System SHALL identify petitions stuck in RECEIVED state ✅
- **NFR-7.1**: 100% of orphans must be detected ✅
- **CT-12**: All detection and reprocessing events witnessed ✅
- **CT-11**: Manual interventions logged for accountability ✅
- **AC6**: Comprehensive audit trail for all detection runs ✅

## Implementation Components

### 1. Domain Events (80 lines)
**File:** `src/domain/events/orphan_petition.py`

- `OrphanPetitionsDetectedEventPayload`: Detection event with count, IDs, oldest age
- `OrphanPetitionReprocessingTriggeredEventPayload`: Manual reprocessing event
- Both events include `get_signable_content()` for witnessing (CT-12)
- JSON serialization/deserialization for event storage

### 2. Domain Models (113 lines)
**File:** `src/domain/models/orphan_petition_detection.py`

- `OrphanPetitionInfo`: Individual orphan metadata (ID, age, type, co-signers)
- `OrphanPetitionDetectionResult`: Detection scan results with computed metrics
- Frozen dataclasses for immutability (CT-12)
- Helper methods for querying orphan lists

### 3. Detection Service (258 lines)
**File:** `src/application/services/orphan_petition_detection_service.py`

**Key Features:**
- Configurable threshold (default: 24 hours)
- Queries petitions in RECEIVED state before cutoff
- Computes age based on `created_at` timestamp
- Emits witnessed events only when orphans found
- Port-based architecture for testability

**Constitutional Guarantees:**
- CT-12: All detection events witnessed via EventWriterPort
- NFR-7.1: 100% detection through repository query
- CT-13: Read operations allowed during halt

### 4. Reprocessing Service (282 lines)
**File:** `src/application/services/orphan_petition_reprocessing_service.py`

**Key Features:**
- Manual operator-triggered reprocessing
- Validates petitions are in RECEIVED state
- Emits witnessed event before deliberation
- Graceful error handling with partial success tracking
- Returns success/failed petition IDs

**Constitutional Guarantees:**
- CT-12: Reprocessing actions witnessed
- CT-11: Manual interventions logged
- CT-13: Halt check before writes

### 5. Repository Adapter (310 lines)
**File:** `src/infrastructure/adapters/persistence/orphan_detection_repository.py`

**Operations:**
- `save_detection_result()`: Persist detection run and individual orphans
- `mark_as_reprocessed()`: Track manual reprocessing status
- `get_latest_detection_run()`: Latest scan with full orphan details
- `get_orphan_count()`: Quick count for dashboard
- `get_detection_history()`: Historical trends (last 30 runs)

### 6. Database Migration (174 lines)
**File:** `migrations/032_create_orphan_detection_tables.sql`

**Tables:**
- `orphan_detection_runs`: Detection scan summaries with metrics
  - detection_id (PK), detected_at, threshold_hours
  - orphan_count, oldest_orphan_age_hours
  - Indexes for time-series queries and alerting

- `orphaned_petitions`: Individual orphan snapshots per run
  - (detection_id, petition_id) composite PK
  - petition_created_at, age_hours, petition_type, co_signer_count
  - reprocessed, reprocessed_at, reprocessed_by tracking
  - Indexes for petition lookup, reprocessing status, age queries

## Test Coverage

### Unit Tests: 9 tests (100% passing)
**File:** `tests/petition_system/test_orphan_petition_detection_service.py`

**TestOrphanDetection:**
- ✅ Detects orphans beyond threshold
- ✅ No orphans when all recent
- ✅ No orphans when no RECEIVED petitions
- ✅ Detects multiple orphans (NFR-7.1)
- ✅ Custom threshold configuration
- ✅ Event payload structure (CT-12)
- ✅ Orphan info includes metadata

**TestEdgeCases:**
- ✅ Petition exactly at threshold
- ✅ Zero threshold behavior

### Integration Tests: 8 tests (100% passing)
**File:** `tests/petition_system/test_orphan_petition_reprocessing_service.py`

**TestOrphanReprocessing:**
- ✅ Successful reprocessing of valid orphan
- ✅ Multiple orphans reprocessing
- ✅ Rejects petition not in RECEIVED state
- ✅ Handles missing petition
- ✅ Handles deliberation initiation failure
- ✅ Partial success scenario
- ✅ Empty petition list raises error
- ✅ Event payload structure (CT-12)

**Total: 17/17 tests passing**

## Configuration

### Orphan Detection Thresholds
- **Default:** 24 hours
- **Configurable:** Via service constructor
- **Frequency:** Daily scheduled job (designed for daily execution)

### Repository Query Semantics
- Queries petitions with `created_at < (now - threshold)`
- Returns only petitions currently in RECEIVED state
- Read operations allowed during halt (CT-13)

## Integration Points

### Required Dependencies:
1. **PetitionRepositoryPort**: Query petitions by state
2. **EventWriterPort**: Emit witnessed events
3. **DeliberationOrchestratorPort**: Initiate deliberation (reprocessing)

### Event Emission:
- `petition.monitoring.orphans_detected`: When orphans found
- `petition.monitoring.reprocessing_triggered`: When manual reprocessing initiated

## Dashboard Integration

**Story 8.4 Integration Points:**
- `OrphanDetectionRepository.get_orphan_count()` → Current orphan count
- `OrphanDetectionRepository.get_latest_detection_run()` → Full details
- `OrphanDetectionRepository.get_detection_history()` → Trend data (30 runs)

**Expected Dashboard Visibility:**
- Current orphan count badge
- List of orphaned petition IDs with age
- Historical trend chart (last 30 days)
- Manual reprocessing trigger button

## Deployment Considerations

### Daily Job Setup
```python
# Pseudocode for daily scheduled job
from src.application.services.orphan_petition_detection_service import OrphanPetitionDetectionService

service = OrphanPetitionDetectionService(
    petition_repository=petition_repo,
    event_writer=event_writer,
    threshold_hours=24.0  # configurable
)

# Run daily at 00:00 UTC
result = service.detect_orphans()

# Persist results for dashboard
orphan_detection_repo.save_detection_result(result)
```

### Manual Reprocessing API
```python
# Pseudocode for manual reprocessing endpoint
from src.application.services.orphan_petition_reprocessing_service import OrphanPetitionReprocessingService

service = OrphanPetitionReprocessingService(
    petition_repository=petition_repo,
    event_writer=event_writer,
    deliberation_orchestrator=deliberation_orchestrator,
)

result = service.reprocess_orphans(
    petition_ids=[uuid1, uuid2, uuid3],
    triggered_by="operator-123",
    reason="Manual reprocessing after detection"
)

# result = {"success": [uuid1, uuid2], "failed": [uuid3]}
```

## Performance Characteristics

- **Detection Query:** O(n) where n = RECEIVED petitions
- **Event Emission:** Single event regardless of orphan count
- **Database Writes:** 1 detection run + n orphan records
- **Reprocessing:** Deliberation initiation per orphan (sequential)

## Next Steps

1. ✅ Complete Story 8.3 implementation
2. **Deploy to Production:**
   - Apply migration 032
   - Configure daily detection job
   - Set up monitoring alerts
3. **Story 8.4:** High Archon Legitimacy Dashboard
   - Add GET `/api/v1/governance/legitimacy/metrics` endpoint
   - Integrate orphan count from repository
   - Display historical trends
4. **Optional Enhancements:**
   - Batch reprocessing API endpoint
   - Configurable threshold per petition type
   - Alert escalation for persistent orphans

## Files Modified/Created

**Created:**
- `src/domain/events/orphan_petition.py` (177 lines)
- `src/domain/models/orphan_petition_detection.py` (113 lines)
- `src/application/services/orphan_petition_detection_service.py` (258 lines)
- `src/application/services/orphan_petition_reprocessing_service.py` (282 lines)
- `src/infrastructure/adapters/persistence/orphan_detection_repository.py` (310 lines)
- `migrations/032_create_orphan_detection_tables.sql` (174 lines)
- `tests/petition_system/test_orphan_petition_detection_service.py` (340 lines)
- `tests/petition_system/test_orphan_petition_reprocessing_service.py` (350 lines)

**Total:** 2,004 lines of production code + tests

## Constitutional Verification

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| FR-8.5 | OrphanPetitionDetectionService identifies petitions >24h | ✅ |
| NFR-7.1 | Repository query ensures 100% detection | ✅ |
| CT-12 | All events witnessed via EventWriterPort | ✅ |
| CT-11 | Manual reprocessing logged with operator ID | ✅ |
| CT-13 | Read operations allowed during halt | ✅ |
| AC6 | orphan_detection_runs + orphaned_petitions audit trail | ✅ |

## Production Readiness Checklist

- ✅ Domain events with witnessing
- ✅ Port-based architecture for testability
- ✅ Comprehensive test coverage (17/17 passing)
- ✅ Database migration with indexes
- ✅ Repository adapter for persistence
- ✅ Error handling with partial success tracking
- ✅ Structured logging throughout
- ✅ Constitutional compliance verified
- ⏳ Daily job scheduler (deployment task)
- ⏳ Dashboard integration (Story 8.4)
- ⏳ Monitoring alerts (deployment task)

---

**Implementation Complete:** Story 8.3 is production-ready pending deployment configuration (daily job setup) and dashboard integration (Story 8.4).
