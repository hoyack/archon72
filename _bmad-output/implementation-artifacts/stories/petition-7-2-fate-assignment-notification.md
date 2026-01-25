# Story 7.2: Fate Assignment Notification

Status: done

## Story

As an **Observer**,
I want to be notified when my petition receives its fate,
So that I know the outcome without polling.

## Acceptance Criteria

1. **AC1: Notification Content on Fate Assignment**
   - **Given** I submitted a petition and provided notification preferences
   - **When** the petition is fated (ACKNOWLEDGED, REFERRED, or ESCALATED)
   - **Then** I receive a notification containing:
     - `petition_id`
     - `fate` (the terminal state)
     - `fate_reason` (if ACKNOWLEDGED)
     - `fate_timestamp`
     - Link to view full details
   - **And** notification is delivered via configured channel (email, webhook, in-app)

2. **AC2: Long-Poll Immediate Return**
   - **Given** I have a long-poll connection open
   - **When** the petition is fated
   - **Then** the long-poll returns immediately with the new state

3. **AC3: Notification Preferences**
   - **Given** I am submitting a petition
   - **When** I include notification preferences in the request
   - **Then** the system stores my preferences
   - **And** uses them when delivering fate notifications

4. **AC4: Constitutional Compliance**
   - **And** all notifications are witnessed events (CT-12)
   - **And** notification failures are logged but don't block fate assignment
   - **And** RFC 7807 error responses for invalid preferences (D7)

## Tasks / Subtasks

- [x] Task 1: Create Notification Preferences Domain Model (AC: 3)
  - [x] 1.1: Create `NotificationPreference` dataclass in `src/domain/models/notification_preference.py`
  - [x] 1.2: Support channels: `webhook`, `in_app` (email deferred to future)
  - [x] 1.3: Include `webhook_url`, `enabled` flag, `created_at`
  - [x] 1.4: Add unit tests for model invariants

- [x] Task 2: Create Notification Preference Repository (AC: 3)
  - [x] 2.1: Create `NotificationPreferenceRepositoryProtocol` port in `src/application/ports/`
  - [x] 2.2: Methods: `save(petition_id, preference)`, `get_by_petition_id(petition_id)`
  - [x] 2.3: Create stub implementation in `src/infrastructure/stubs/`
  - [x] 2.4: Add migration for `petition_notification_preferences` table
  - [x] 2.5: Add unit tests for repository

- [x] Task 3: Extend Petition Submission Request (AC: 3)
  - [x] 3.1: Add optional `notification_preferences` field to `PetitionSubmissionRequest`
  - [x] 3.2: Validate webhook_url format (must be HTTPS)
  - [x] 3.3: Store preferences on petition creation
  - [x] 3.4: Add unit tests for request validation

- [x] Task 4: Create Fate Notification Event (AC: 1, 4)
  - [x] 4.1: Create `FateNotificationSent` event in `src/domain/events/notification.py`
  - [x] 4.2: Include: petition_id, fate, fate_reason, timestamp, channel, delivery_status
  - [x] 4.3: Ensure event is witnessed per CT-12
  - [x] 4.4: Add unit tests for event

- [x] Task 5: Create Fate Notification Service (AC: 1, 2, 4)
  - [x] 5.1: Create `FateNotificationServiceProtocol` port in `src/application/ports/`
  - [x] 5.2: Implement `FateNotificationService` in `src/application/services/`
  - [x] 5.3: Methods: `notify_fate_assigned(petition_id, fate, fate_reason, timestamp)`
  - [x] 5.4: Deliver via configured channels (webhook, in-app)
  - [x] 5.5: Notify long-poll waiters via StatusTokenRegistry
  - [x] 5.6: Log failures but don't block (fire-and-forget with retry queue)
  - [x] 5.7: Add unit tests for service

- [x] Task 6: Integrate with Fate Assignment Flow (AC: 1, 2)
  - [x] 6.1: Hook notification service into `PetitionSubmissionService` on fate transition
  - [x] 6.2: Trigger StatusTokenRegistry state change notification
  - [x] 6.3: Emit `FateNotificationSent` event after delivery attempt
  - [x] 6.4: Add integration tests

- [x] Task 7: Create Webhook Delivery Adapter (AC: 1)
  - [x] 7.1: Create `WebhookDeliveryAdapterProtocol` port
  - [x] 7.2: Implement stub with configurable success/failure
  - [x] 7.3: HTTP POST to webhook_url with JSON payload
  - [x] 7.4: Retry logic: 3 attempts with exponential backoff
  - [x] 7.5: Add unit tests for adapter

- [x] Task 8: Add Prometheus Metrics (AC: 1, 4)
  - [x] 8.1: `petition_fate_notification_sent_total` counter (labels: fate, channel, status)
  - [x] 8.2: `petition_fate_notification_delivery_latency_seconds` histogram
  - [x] 8.3: `petition_fate_notification_retry_total` counter

## Documentation Checklist

- [x] Architecture docs updated (if patterns/structure changed)
- [x] API docs updated (if endpoints/contracts changed)
- [x] README updated (if setup/usage changed)
- [x] Inline comments added for complex logic
- [ ] N/A - no documentation impact

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Event-Driven Pattern:** Follow existing event emission in `src/domain/events/petition.py`
- Events are dataclasses with `@dataclass(frozen=True)`
- All events witnessed per CT-12 via EventWriterService

**Service Pattern:** Reference `src/application/services/status_token_service.py`
- Protocol-based interfaces
- Stub implementations for testing

**Webhook Pattern:** Reference `src/api/routes/observer.py` for async HTTP patterns
- Use `httpx.AsyncClient` for webhook delivery
- Configurable timeouts

**Constitutional Constraints:**
- CT-12: All notifications witnessed
- FR-7.3: System SHALL notify Observer on fate assignment
- D7: RFC 7807 error format

### Project Structure Notes

**Files to Create:**
- `src/domain/models/notification_preference.py` - Preference domain model
- `src/domain/events/notification.py` - Notification events
- `src/application/ports/notification_preference_repository.py` - Repository port
- `src/application/ports/fate_notification_service.py` - Service port
- `src/application/ports/webhook_delivery_adapter.py` - Webhook adapter port
- `src/application/services/fate_notification_service.py` - Service implementation
- `src/infrastructure/stubs/notification_preference_repository_stub.py` - Repository stub
- `src/infrastructure/stubs/webhook_delivery_adapter_stub.py` - Webhook stub
- `migrations/036_create_notification_preferences.sql` - Migration
- `tests/unit/domain/models/test_notification_preference.py`
- `tests/unit/application/services/test_fate_notification_service.py`
- `tests/integration/test_fate_notification_integration.py`

**Files to Modify:**
- `src/api/models/petition_submission.py` - Add notification_preferences field
- `src/api/routes/petition_submission.py` - Store preferences on submission
- `src/application/services/petition_state_machine_service.py` - Hook notification on fate
- `src/infrastructure/monitoring/metrics.py` - Add notification metrics
- `src/infrastructure/stubs/status_token_registry_stub.py` - Ensure integration with notifications

**Naming Conventions:**
- Domain models: frozen dataclass with `@dataclass(frozen=True)`
- Services: `*Service` suffix, protocol-based dependency injection
- Stubs: `*Stub` suffix in `infrastructure/stubs/`

### References

- [Source: petition-system-epics.md - Epic 7, Story 7.2]
- [Source: architecture.md - ADR-11 API Versioning]
- [Source: src/application/services/status_token_service.py - Service pattern]
- [Source: src/infrastructure/stubs/status_token_registry_stub.py - Registry for long-poll notification]

### Technical Implementation Guidance

**Notification Payload Format:**
```json
{
  "petition_id": "uuid",
  "fate": "ACKNOWLEDGED|REFERRED|ESCALATED",
  "fate_reason": "ALREADY_RESOLVED|OUT_OF_SCOPE|...",
  "fate_timestamp": "2026-01-22T12:00:00Z",
  "details_url": "/api/v1/petition-submissions/{petition_id}"
}
```

**Webhook Delivery Flow:**
1. Petition fated (state transition)
2. Notification service triggered
3. Lookup notification preferences by petition_id
4. If webhook configured: POST to webhook_url
5. If in_app configured: store in notification queue (future)
6. Always: notify StatusTokenRegistry for long-poll waiters
7. Emit FateNotificationSent event

**Retry Strategy:**
- Attempt 1: immediate
- Attempt 2: after 5 seconds
- Attempt 3: after 30 seconds
- After 3 failures: log and move to dead letter queue

**Long-Poll Integration:**
```python
# In fate transition handler:
await status_token_registry.notify_state_change(petition_id, new_version)
# This wakes all long-poll waiters immediately
```

### Previous Story Intelligence

Story 7.1 created the foundation for this story:
- `StatusToken` domain model for version tracking
- `StatusTokenRegistryStub` for long-poll waiter management
- Long-poll endpoint that responds to state changes
- The `notify_state_change()` method is already implemented

Key integration point: Call `status_token_registry.notify_state_change()` when fate is assigned.

### Git Intelligence Summary

Recent commits (petition system):
- Story 7.1: Status Token for Long-Poll (just completed)
- Story 8.4: High Archon Legitimacy Dashboard
- Story 8.3: Orphan Petition Detection

Key patterns from recent work:
- Pydantic v2 models with custom serializers
- Protocol-based service interfaces
- In-memory stubs for development
- Fire-and-forget event emission with graceful degradation

### Project Context Reference

See `docs/project-context.md` for:
- Import boundaries (domain -> application -> infrastructure)
- Testing requirements (unit + integration)
- Error handling patterns

### Performance Requirements

- Notification delivery should not block fate assignment
- Webhook timeout: 10 seconds max
- Long-poll notification latency: < 100ms (leverages Story 7.1)

## Dev Agent Record

### Agent Model Used

(To be filled by dev agent)

### Debug Log References

N/A - not started

### Completion Notes List

(To be filled during implementation)

### File List

**Files Created:**
(To be filled during implementation)

**Files Modified:**
(To be filled during implementation)

**Test Summary:**
(To be filled during implementation)
