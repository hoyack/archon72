# Story 8.5: META Petition Routing

**Epic:** Epic 8 - Legitimacy Metrics & Governance
**Story ID:** petition-8-5-meta-petition-routing
**Priority:** P2
**Status:** complete

## User Story

As a **system**,
I want META petitions (about the petition system itself) routed to High Archon,
So that system-level concerns receive appropriate attention without deliberation deadlock.

## Requirements Coverage

### Functional Requirements
- **FR-10.4:** META petitions (about petition system) SHALL route to High Archon [P2]

### Non-Functional Requirements
- **NFR-5.6:** Authorization check completes quickly (<50ms) (from Story 8.4)
- **NFR-1.1:** Petition intake latency p99 < 200ms (unchanged for META)

### Constitutional Triggers
- **CT-12:** Witnessing creates accountability - META routing events are witnessed
- **CT-13:** Explicit consent - High Archon explicitly handles META petitions

### Threat Mitigations
- **META-1:** Petition about petition system to deadlock - Meta-petition type + expedited High Archon review

## Dependencies

### Prerequisites
- Story 8.4: High Archon Legitimacy Dashboard (complete)
  - `get_high_archon_id` authentication helper
  - High Archon role validation
- Story 1.1: Petition Submission REST Endpoint (complete)
  - Petition intake pipeline
- Story 1.2: Petition Received Event Emission (complete)
  - Event witnessing infrastructure

### Integration Points
- Petition submission pipeline (petition type detection)
- High Archon authentication (from Story 8.4)
- Event system for META petition events
- Job queue for High Archon queue management

## Acceptance Criteria

### AC1: META Petition Type Support

**Given** the petition system supports multiple petition types
**When** a petition is submitted with `petition_type = "META"`
**Then** the system accepts the petition
**And** the petition is assigned state `RECEIVED`
**And** the petition is flagged for High Archon routing

**Given** a petition is submitted with `petition_type = "GENERAL"` or other non-META type
**When** the petition contains system-related keywords (optional detection)
**Then** the petition proceeds through normal deliberation
**And** no automatic META classification is applied

### AC2: Deliberation Bypass for META Petitions

**Given** a petition with `petition_type = "META"` is submitted
**When** the petition enters the intake pipeline
**Then** it bypasses normal Three Fates deliberation
**And** it is routed directly to the High Archon queue
**And** a `MetaPetitionReceived` event is emitted containing:
  - `petition_id` - The petition identifier
  - `submitter_id` - Who submitted the META petition
  - `petition_text` - Brief description (first 500 chars)
  - `received_at` - Timestamp of receipt
  - `routing_reason` - "EXPLICIT_META_TYPE"

### AC3: High Archon Queue Management

**Given** META petitions are routed to High Archon
**When** a High Archon reviews the queue
**Then** GET `/api/v1/governance/meta-petitions` returns:
  - List of pending META petitions
  - Each petition includes: `petition_id`, `submitter_id`, `petition_text`, `received_at`, `status`
  - Sorted by `received_at` (oldest first for FIFO)

**Given** I do not have HIGH_ARCHON role
**When** I attempt to access the META petition queue
**Then** the system returns HTTP 403 Forbidden

### AC4: High Archon META Petition Resolution

**Given** a High Archon reviews a META petition
**When** they decide on disposition via POST `/api/v1/governance/meta-petitions/{petition_id}/resolve`
**Then** they can select one of:
  - `ACKNOWLEDGE` - Acknowledge the concern with rationale
  - `CREATE_ACTION` - Create a governance action item
  - `FORWARD` - Forward to specific governance body (with target)

**Given** disposition is selected
**Then** a `MetaPetitionResolved` event is emitted containing:
  - `petition_id` - The resolved petition
  - `disposition` - ACKNOWLEDGE, CREATE_ACTION, or FORWARD
  - `rationale` - High Archon's rationale (required)
  - `high_archon_id` - Who resolved it
  - `resolved_at` - Timestamp
  - `forward_target` - If FORWARD, the target governance body

**And** the petition state transitions to a terminal state

### AC5: META Petition Observability

**Given** META petition routing is operational
**When** META petitions are submitted or resolved
**Then** Prometheus metrics are updated:
  - `meta_petitions_received_total` (counter)
  - `meta_petitions_pending` (gauge)
  - `meta_petitions_resolved_total{disposition="ACKNOWLEDGE|CREATE_ACTION|FORWARD"}` (counter)
  - `meta_petition_resolution_time_seconds` (histogram)

**And** structured logs capture routing decisions

### AC6: Event Witnessing for META Petitions

**Given** META petition events must be witnessed (CT-12)
**When** `MetaPetitionReceived` or `MetaPetitionResolved` events are emitted
**Then** they are written to the event store
**And** they include Blake3 content hash
**And** they are part of the hash chain

## Technical Design

### Domain Models

#### PetitionType Extension

```python
class PetitionType(Enum):
    """Type of petition submitted to the system (FR-10.1, FR-10.4).

    Types:
        GENERAL: General governance petition
        CESSATION: Request for system cessation review
        GRIEVANCE: Complaint about system behavior
        COLLABORATION: Request for inter-realm collaboration
        META: Petition about the petition system itself (FR-10.4)
    """

    GENERAL = "GENERAL"
    CESSATION = "CESSATION"
    GRIEVANCE = "GRIEVANCE"
    COLLABORATION = "COLLABORATION"
    META = "META"  # NEW: Routes directly to High Archon
```

#### META Petition Event Models

```python
@dataclass(frozen=True)
class MetaPetitionReceived:
    """Event when META petition is routed to High Archon queue (FR-10.4)."""
    event_id: UUID
    petition_id: UUID
    submitter_id: UUID
    petition_text_preview: str  # First 500 chars
    received_at: datetime
    routing_reason: str  # "EXPLICIT_META_TYPE"


@dataclass(frozen=True)
class MetaPetitionResolved:
    """Event when High Archon resolves a META petition."""
    event_id: UUID
    petition_id: UUID
    disposition: MetaDisposition
    rationale: str
    high_archon_id: UUID
    resolved_at: datetime
    forward_target: Optional[str]  # If disposition == FORWARD


class MetaDisposition(StrEnum):
    """High Archon disposition options for META petitions."""
    ACKNOWLEDGE = "ACKNOWLEDGE"
    CREATE_ACTION = "CREATE_ACTION"
    FORWARD = "FORWARD"
```

#### High Archon Queue Item

```python
@dataclass(frozen=True)
class MetaPetitionQueueItem:
    """Item in High Archon's META petition queue."""
    petition_id: UUID
    submitter_id: UUID
    petition_text: str
    received_at: datetime
    status: MetaPetitionStatus  # PENDING, RESOLVED


class MetaPetitionStatus(StrEnum):
    """Status of META petition in High Archon queue."""
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
```

### Service Layer

#### MetaPetitionRoutingService

```python
class MetaPetitionRoutingService:
    """Routes META petitions to High Archon queue (FR-10.4).

    This service:
    1. Detects META petition type
    2. Bypasses normal deliberation
    3. Enqueues to High Archon queue
    4. Emits MetaPetitionReceived event
    """

    def should_route_to_high_archon(self, petition: Petition) -> bool:
        """Check if petition should bypass deliberation."""
        return petition.petition_type == PetitionType.META

    async def route_meta_petition(
        self,
        petition: Petition,
    ) -> MetaPetitionReceived:
        """Route META petition to High Archon queue.

        Args:
            petition: The META petition to route.

        Returns:
            MetaPetitionReceived event.

        Raises:
            ValueError: If petition is not META type.
        """
        if not self.should_route_to_high_archon(petition):
            raise ValueError(f"Cannot route non-META petition: {petition.petition_type}")

        # Enqueue to High Archon queue
        await self.queue_repo.enqueue_meta_petition(petition)

        # Emit event
        event = MetaPetitionReceived(
            event_id=uuid7(),
            petition_id=petition.petition_id,
            submitter_id=petition.submitter_id,
            petition_text_preview=petition.petition_text[:500],
            received_at=datetime.now(timezone.utc),
            routing_reason="EXPLICIT_META_TYPE",
        )

        await self.event_writer.write_event(event)
        return event
```

#### MetaPetitionResolutionService

```python
class MetaPetitionResolutionService:
    """High Archon resolution of META petitions."""

    async def resolve_meta_petition(
        self,
        petition_id: UUID,
        disposition: MetaDisposition,
        rationale: str,
        high_archon_id: UUID,
        forward_target: Optional[str] = None,
    ) -> MetaPetitionResolved:
        """Resolve META petition with disposition.

        Args:
            petition_id: The petition to resolve.
            disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD.
            rationale: High Archon's rationale (required).
            high_archon_id: ID of the resolving High Archon.
            forward_target: Target governance body if FORWARD.

        Returns:
            MetaPetitionResolved event.

        Raises:
            NotFoundError: If petition not in queue.
            ValidationError: If rationale is empty.
            ValidationError: If FORWARD without target.
        """
        # Validate
        if not rationale or len(rationale.strip()) < 10:
            raise ValidationError("Rationale must be at least 10 characters")

        if disposition == MetaDisposition.FORWARD and not forward_target:
            raise ValidationError("Forward target required for FORWARD disposition")

        # Mark resolved in queue
        await self.queue_repo.mark_resolved(petition_id)

        # Transition petition state to terminal
        await self.petition_repo.transition_to_acknowledged(
            petition_id,
            reason="META_RESOLVED_BY_HIGH_ARCHON",
        )

        # Emit event
        event = MetaPetitionResolved(
            event_id=uuid7(),
            petition_id=petition_id,
            disposition=disposition,
            rationale=rationale,
            high_archon_id=high_archon_id,
            resolved_at=datetime.now(timezone.utc),
            forward_target=forward_target,
        )

        await self.event_writer.write_event(event)
        return event
```

### Database Schema

#### High Archon META Queue Table

```sql
-- Migration 032: META petition routing tables
-- Story 8.5: FR-10.4

-- Table: meta_petition_queue
-- Tracks META petitions awaiting High Archon review

CREATE TABLE IF NOT EXISTS meta_petition_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    petition_id UUID NOT NULL REFERENCES petitions(petition_id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RESOLVED')),
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,  -- High Archon who resolved
    disposition TEXT CHECK (disposition IN ('ACKNOWLEDGE', 'CREATE_ACTION', 'FORWARD')),
    rationale TEXT,
    forward_target TEXT,

    CONSTRAINT unique_petition_in_queue UNIQUE (petition_id)
);

-- Index for pending queue queries (sorted by age)
CREATE INDEX idx_meta_queue_pending ON meta_petition_queue(enqueued_at)
    WHERE status = 'PENDING';

-- Index for resolved queries
CREATE INDEX idx_meta_queue_resolved ON meta_petition_queue(resolved_at DESC)
    WHERE status = 'RESOLVED';
```

### API Endpoints

#### GET /api/v1/governance/meta-petitions

```python
@router.get("/governance/meta-petitions")
async def get_meta_petition_queue(
    high_archon_id: UUID = Depends(get_high_archon_id),
    status: Optional[MetaPetitionStatus] = Query(default=MetaPetitionStatus.PENDING),
    limit: int = Query(default=50, le=100),
) -> MetaPetitionQueueResponse:
    """Get High Archon's META petition queue.

    Requires HIGH_ARCHON role (FR-10.4).
    """
    pass
```

#### POST /api/v1/governance/meta-petitions/{petition_id}/resolve

```python
@router.post("/governance/meta-petitions/{petition_id}/resolve")
async def resolve_meta_petition(
    petition_id: UUID,
    request: MetaPetitionResolutionRequest,
    high_archon_id: UUID = Depends(get_high_archon_id),
) -> MetaPetitionResolutionResponse:
    """Resolve a META petition with disposition.

    Requires HIGH_ARCHON role (FR-10.4).

    Request body:
        disposition: ACKNOWLEDGE, CREATE_ACTION, or FORWARD
        rationale: Required explanation
        forward_target: Required if disposition is FORWARD
    """
    pass
```

### Integration with Petition Intake

```python
# In petition intake pipeline (Story 1.1)

async def submit_petition(self, submission: PetitionSubmission) -> Petition:
    """Submit petition with META routing check."""

    # Create petition
    petition = await self._create_petition(submission)

    # Check for META routing (FR-10.4)
    if self.meta_routing_service.should_route_to_high_archon(petition):
        # Bypass deliberation, route to High Archon
        await self.meta_routing_service.route_meta_petition(petition)
        # Emit PetitionReceived event (still witnessed)
        await self._emit_petition_received(petition)
        return petition

    # Normal flow: queue for deliberation
    await self._queue_for_deliberation(petition)
    await self._emit_petition_received(petition)
    return petition
```

## Testing Strategy

### Unit Tests (Target: 25+ tests)

1. **META Type Detection** (5 tests)
   - Test META type recognized
   - Test non-META types not routed
   - Test should_route_to_high_archon logic
   - Test PetitionType enum includes META
   - Test API enum includes META

2. **Routing Logic** (6 tests)
   - Test META petition enqueued to High Archon queue
   - Test deliberation bypassed for META
   - Test MetaPetitionReceived event structure
   - Test routing_reason field
   - Test petition_text_preview truncation
   - Test event witnessing

3. **Resolution Logic** (8 tests)
   - Test ACKNOWLEDGE disposition
   - Test CREATE_ACTION disposition
   - Test FORWARD disposition with target
   - Test FORWARD requires target
   - Test rationale required
   - Test rationale minimum length
   - Test MetaPetitionResolved event structure
   - Test petition state transition

4. **Queue Management** (6 tests)
   - Test enqueue operation
   - Test mark_resolved operation
   - Test pending queue query
   - Test FIFO ordering
   - Test resolved queue query
   - Test unique petition constraint

### Integration Tests (Target: 15+ tests)

1. **End-to-End META Flow** (5 tests)
   - Test submit META petition → routing → queue
   - Test High Archon queue retrieval
   - Test META resolution → terminal state
   - Test event witnessing in hash chain
   - Test Prometheus metrics

2. **Authentication/Authorization** (4 tests)
   - Test queue access requires HIGH_ARCHON
   - Test resolution requires HIGH_ARCHON
   - Test 403 for non-High Archon
   - Test audit logging

3. **Database Integration** (3 tests)
   - Test queue table operations
   - Test unique constraint
   - Test index performance

4. **Pipeline Integration** (3 tests)
   - Test META petition intake path
   - Test non-META petition normal path
   - Test concurrent META submissions

### Mock vs Real Dependencies

- **Mock:** Event writer (in unit tests)
- **Real:** Database, event system (in integration tests)
- **Stub:** MetaPetitionRoutingService for API tests

## Configuration

### Environment Variables

```bash
# META petition configuration
META_PETITION_ENABLED=true
META_PETITION_TEXT_PREVIEW_LENGTH=500
```

## Migration

**Migration 032: Create META petition routing infrastructure**

- Add `META` to petition_type enum
- Create `meta_petition_queue` table
- Add indexes for queue queries

## Prometheus Metrics

```python
# Counters
meta_petitions_received_total
meta_petitions_resolved_total{disposition="ACKNOWLEDGE|CREATE_ACTION|FORWARD"}

# Gauges
meta_petitions_pending

# Histograms
meta_petition_resolution_time_seconds
```

## Success Criteria

### Functional Completeness
- [ ] META petition type added to enum
- [ ] META petitions bypass deliberation
- [ ] High Archon queue management works
- [ ] Three disposition options functional
- [ ] Event witnessing complete

### Non-Functional Compliance
- [ ] **FR-10.4:** META petitions route to High Archon
- [ ] **META-1:** Prevents deadlock from system-about-system petitions
- [ ] Unit test coverage > 90%
- [ ] Integration tests cover all scenarios

### Constitutional Compliance
- [ ] **CT-12:** All events witnessed and immutable
- [ ] **CT-13:** High Archon explicit consent for handling

## Implementation Tasks

### Phase 1: Domain Models (1-2 hours)
1. Add `META` to `PetitionType` enum
2. Create `MetaPetitionReceived` event model
3. Create `MetaPetitionResolved` event model
4. Create `MetaDisposition` enum
5. Create `MetaPetitionQueueItem` model
6. Unit tests for models

### Phase 2: Database & Repository (1-2 hours)
7. Create migration 032 (META queue table)
8. Implement `MetaPetitionQueueRepository`
9. Repository unit tests

### Phase 3: Services (2-3 hours)
10. Implement `MetaPetitionRoutingService`
11. Implement `MetaPetitionResolutionService`
12. Integrate routing with petition intake pipeline
13. Service unit tests

### Phase 4: API Endpoints (1-2 hours)
14. Implement GET `/api/v1/governance/meta-petitions`
15. Implement POST `/api/v1/governance/meta-petitions/{petition_id}/resolve`
16. Add API models
17. API unit tests

### Phase 5: Event Emission & Metrics (1 hour)
18. Integrate with EventWriterService
19. Add Prometheus metrics
20. Add structured logging

### Phase 6: Integration Tests (1-2 hours)
21. End-to-end META flow tests
22. Authentication tests
23. Pipeline integration tests

## Notes

- META petition routing is P2 priority - core deliberation features take precedence
- Detection is explicit (petition_type = META), not keyword-based
- High Archon queue is separate from King escalation queue
- Resolution creates terminal state (ACKNOWLEDGED) for petition

## Related Stories

- **Story 8.4:** High Archon Legitimacy Dashboard (authentication reuse)
- **Story 1.1:** Petition Submission REST Endpoint (intake integration)
- **Story 6.1:** King Escalation Queue (similar queue pattern)

---

**Story Status:** Ready for Implementation
**Risk Level:** Low (well-defined routing pattern, builds on existing infrastructure)
