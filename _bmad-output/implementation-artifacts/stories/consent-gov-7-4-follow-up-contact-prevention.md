# Story consent-gov-7.4: Follow-Up Contact Prevention

Status: ready-for-dev

---

## Story

As a **Cluster**,
I want **no follow-up contact after exit**,
So that **my departure is truly final**.

---

## Acceptance Criteria

1. **AC1:** No follow-up contact mechanism exists (FR46, NFR-EXIT-02)
2. **AC2:** Contact endpoint removed/blocked on exit
3. **AC3:** Re-engagement requires explicit new initiation
4. **AC4:** Any attempt to add contact triggers violation event
5. **AC5:** Event `custodial.contact.blocked` emitted
6. **AC6:** Structural prohibition enforced
7. **AC7:** No "win back" or re-engagement features
8. **AC8:** Unit tests verify no contact path exists

---

## Tasks / Subtasks

- [ ] **Task 1: Create ContactPreventionService** (AC: 1, 2)
  - [ ] Create `src/application/services/governance/contact_prevention_service.py`
  - [ ] Block contact endpoint for exited Cluster
  - [ ] Remove from any routing tables
  - [ ] Permanent block (no reactivation)

- [ ] **Task 2: Implement contact blocking** (AC: 2)
  - [ ] Add Cluster ID to blocked contacts list
  - [ ] Remove from active participant list
  - [ ] Invalidate any contact tokens
  - [ ] Block at infrastructure level

- [ ] **Task 3: Implement violation detection** (AC: 4)
  - [ ] Monitor for contact attempts
  - [ ] Detect any routing to blocked Cluster
  - [ ] Emit constitutional violation event
  - [ ] Knight observes violation

- [ ] **Task 4: Implement structural prohibition** (AC: 6)
  - [ ] No "send message to Cluster" API
  - [ ] No "notify exited Cluster" method
  - [ ] No "re-engagement" feature
  - [ ] Architecture prevents contact

- [ ] **Task 5: Implement contact blocked event** (AC: 5)
  - [ ] Emit `custodial.contact.blocked`
  - [ ] Include Cluster ID
  - [ ] Include block reason (exit)
  - [ ] Permanent status

- [ ] **Task 6: Ensure no win-back features** (AC: 7)
  - [ ] No "we miss you" capability
  - [ ] No "come back" messaging
  - [ ] No re-engagement campaign support
  - [ ] Architecture forbids these patterns

- [ ] **Task 7: Implement re-engagement path** (AC: 3)
  - [ ] Re-engagement only via new initiation
  - [ ] Cluster must explicitly re-join
  - [ ] System cannot initiate contact
  - [ ] One-way: Cluster → System only

- [ ] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [ ] Test contact blocked on exit
  - [ ] Test no contact API exists
  - [ ] Test violation on contact attempt
  - [ ] Test no win-back features
  - [ ] Test re-engagement requires new initiation

---

## Documentation Checklist

- [ ] Architecture docs updated (contact prevention)
- [ ] Structural prohibition documented
- [ ] Violation detection documented
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Structural Prohibition:**
```
NFR-EXIT-02: No follow-up contact mechanism may exist

This is NOT:
  - A policy that can be overridden
  - A preference that can be ignored
  - A setting that can be changed

This IS:
  - Structural absence of capability
  - Architecture that prevents contact
  - No code path for follow-up
  - Constitutional constraint

Why structural?
  - Policy can be violated
  - Preference can be overridden
  - Settings can be changed
  - Architecture cannot be "accidentally" bypassed
```

**No Win-Back:**
```
Common dark patterns explicitly prohibited:
  ✗ "We miss you" emails
  ✗ "Come back" notifications
  ✗ Re-engagement campaigns
  ✗ "Your tasks are waiting" reminders

Why prohibited?
  - Exit is final (by design)
  - Follow-up is coercion
  - Dignity requires respect
  - "No means no"

Code enforcement:
  - No send_to_exited_cluster() method
  - No reengagement_campaign() method
  - No winback_message() method
  - These don't exist to call
```

**Re-Engagement Path:**
```
If Cluster wants to return:

System cannot:
  - Contact Cluster
  - Invite Cluster
  - Suggest Cluster return
  - Remind Cluster of system

Cluster must:
  - Independently decide to return
  - Initiate new registration
  - Complete new onboarding
  - Give new consent

This is one-way:
  Cluster → System: Always allowed
  System → Cluster (after exit): Never allowed
```

### Domain Models

```python
class ContactBlockStatus(Enum):
    """Status of contact blocking."""
    BLOCKED = "blocked"          # Contact blocked (normal exit)
    PERMANENTLY_BLOCKED = "permanently_blocked"  # Same, for clarity


@dataclass(frozen=True)
class ContactBlock:
    """Record of blocked contact."""
    block_id: UUID
    cluster_id: UUID
    blocked_at: datetime
    reason: str  # "exit"
    status: ContactBlockStatus

    # Cannot be unblocked (no unblock field)
    # This is intentional - permanent block


@dataclass(frozen=True)
class ContactViolation:
    """Record of attempted contact to blocked Cluster."""
    violation_id: UUID
    cluster_id: UUID
    attempted_by: str  # Component that tried
    attempted_at: datetime
    blocked: bool  # Always True (structural)
```

### Service Implementation Sketch

```python
class ContactPreventionService:
    """Prevents follow-up contact with exited Clusters.

    Implements structural prohibition (NFR-EXIT-02).
    No methods exist for contacting exited Clusters.
    """

    def __init__(
        self,
        contact_block_port: ContactBlockPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._blocks = contact_block_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def block(
        self,
        cluster_id: UUID,
    ) -> ContactBlock:
        """Block all contact to Cluster.

        This is permanent. There is no unblock method.
        """
        now = self._time.now()

        block = ContactBlock(
            block_id=uuid4(),
            cluster_id=cluster_id,
            blocked_at=now,
            reason="exit",
            status=ContactBlockStatus.PERMANENTLY_BLOCKED,
        )

        await self._blocks.add_block(block)

        await self._event_emitter.emit(
            event_type="custodial.contact.blocked",
            actor="system",
            payload={
                "cluster_id": str(cluster_id),
                "blocked_at": now.isoformat(),
                "reason": "exit",
                "permanent": True,
            },
        )

        return block

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if contact is blocked for Cluster."""
        return await self._blocks.is_blocked(cluster_id)

    async def attempt_contact_blocked(
        self,
        cluster_id: UUID,
        attempted_by: str,
    ) -> None:
        """Record blocked contact attempt and emit violation.

        This is called by infrastructure when contact is attempted.
        Contact is ALWAYS blocked. This just records the violation.
        """
        now = self._time.now()

        violation = ContactViolation(
            violation_id=uuid4(),
            cluster_id=cluster_id,
            attempted_by=attempted_by,
            attempted_at=now,
            blocked=True,  # Always blocked
        )

        # Record violation
        await self._event_emitter.emit(
            event_type="constitutional.violation.contact_attempt",
            actor=attempted_by,
            payload={
                "cluster_id": str(cluster_id),
                "attempted_by": attempted_by,
                "attempted_at": now.isoformat(),
                "blocked": True,
                "violation_type": "nfr_exit_02_contact_after_exit",
            },
        )

    # These methods intentionally do not exist:
    # async def unblock(self, ...): ...
    # async def send_to_exited(self, ...): ...
    # async def winback_message(self, ...): ...
    # async def reengagement_campaign(self, ...): ...


class ContactBlockPort(Protocol):
    """Port for contact block operations.

    NO unblock method (permanent blocks).
    """

    async def add_block(self, block: ContactBlock) -> None:
        """Add contact block (permanent)."""
        ...

    async def is_blocked(self, cluster_id: UUID) -> bool:
        """Check if Cluster is blocked."""
        ...

    async def get_all_blocked(self) -> list[UUID]:
        """Get all blocked Cluster IDs."""
        ...

    # Intentionally NOT defined:
    # - remove_block()
    # - unblock()
    # - allow_contact()
```

### Infrastructure Enforcement

```python
class MessageRouter:
    """Routes messages to Clusters.

    Enforces contact blocks at infrastructure level.
    """

    def __init__(
        self,
        contact_prevention: ContactPreventionService,
    ):
        self._prevention = contact_prevention

    async def route_message(
        self,
        cluster_id: UUID,
        message: Message,
    ) -> RouteResult:
        """Route message to Cluster.

        Blocks if Cluster has exited.
        """
        if await self._prevention.is_blocked(cluster_id):
            # Record violation attempt
            await self._prevention.attempt_contact_blocked(
                cluster_id=cluster_id,
                attempted_by=self.__class__.__name__,
            )

            # Block the message
            return RouteResult.blocked(
                reason="cluster_exited_contact_prohibited"
            )

        # Normal routing...
        return await self._do_route(cluster_id, message)


# API enforcement
class ClusterContactAPI:
    """API for contacting Clusters.

    No endpoint exists for contacting exited Clusters.
    """

    @router.post("/cluster/{cluster_id}/message")
    async def send_message(
        self,
        cluster_id: UUID,
        message: MessageRequest,
        contact_prevention: ContactPreventionService = Depends(),
    ) -> MessageResponse:
        """Send message to Cluster.

        Rejects if Cluster has exited.
        """
        if await contact_prevention.is_blocked(cluster_id):
            raise HTTPException(
                status_code=403,
                detail="Contact prohibited: Cluster has exited",
            )

        # Normal send...

    # These endpoints do NOT exist:
    # - POST /cluster/{id}/winback
    # - POST /cluster/{id}/reengage
    # - POST /cluster/campaign/reengagement
```

### Event Patterns

```python
# Contact blocked
{
    "event_type": "custodial.contact.blocked",
    "actor": "system",
    "payload": {
        "cluster_id": "uuid",
        "blocked_at": "2026-01-16T00:00:00Z",
        "reason": "exit",
        "permanent": true
    }
}

# Contact attempt violation
{
    "event_type": "constitutional.violation.contact_attempt",
    "actor": "MessageRouter",
    "payload": {
        "cluster_id": "uuid",
        "attempted_by": "MessageRouter",
        "attempted_at": "2026-01-16T00:00:00Z",
        "blocked": true,
        "violation_type": "nfr_exit_02_contact_after_exit"
    }
}
```

### Test Patterns

```python
class TestContactPreventionService:
    """Unit tests for contact prevention."""

    async def test_contact_blocked_on_exit(
        self,
        prevention_service: ContactPreventionService,
        cluster: Cluster,
    ):
        """Contact is blocked when Cluster exits."""
        await prevention_service.block(cluster.id)

        assert await prevention_service.is_blocked(cluster.id)

    async def test_violation_on_contact_attempt(
        self,
        prevention_service: ContactPreventionService,
        cluster: Cluster,
        event_capture: EventCapture,
    ):
        """Violation event emitted on contact attempt."""
        await prevention_service.block(cluster.id)

        await prevention_service.attempt_contact_blocked(
            cluster_id=cluster.id,
            attempted_by="TestComponent",
        )

        event = event_capture.get_last("constitutional.violation.contact_attempt")
        assert event is not None
        assert event.payload["blocked"] is True

    async def test_block_event_emitted(
        self,
        prevention_service: ContactPreventionService,
        cluster: Cluster,
        event_capture: EventCapture,
    ):
        """Block event is emitted."""
        await prevention_service.block(cluster.id)

        event = event_capture.get_last("custodial.contact.blocked")
        assert event is not None
        assert event.payload["permanent"] is True


class TestNoWinBackFeatures:
    """Tests ensuring no win-back features exist."""

    def test_no_unblock_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """No unblock method exists."""
        assert not hasattr(prevention_service, "unblock")
        assert not hasattr(prevention_service, "remove_block")

    def test_no_winback_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """No winback method exists."""
        assert not hasattr(prevention_service, "winback_message")
        assert not hasattr(prevention_service, "send_winback")

    def test_no_reengagement_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """No reengagement method exists."""
        assert not hasattr(prevention_service, "reengagement_campaign")
        assert not hasattr(prevention_service, "reengage")

    def test_no_send_to_exited_method(
        self,
        prevention_service: ContactPreventionService,
    ):
        """No method to send to exited Clusters."""
        assert not hasattr(prevention_service, "send_to_exited")
        assert not hasattr(prevention_service, "contact_exited")


class TestReEngagementPath:
    """Tests for re-engagement path."""

    async def test_system_cannot_initiate_contact(
        self,
        prevention_service: ContactPreventionService,
        exited_cluster: Cluster,
    ):
        """System cannot initiate contact with exited Cluster."""
        assert await prevention_service.is_blocked(exited_cluster.id)

        # No method exists to bypass this

    async def test_new_initiation_creates_new_cluster(
        self,
        registration_service,
    ):
        """Re-engagement requires new registration (new Cluster ID)."""
        # A returning user would register as new Cluster
        # with new UUID, new consent, etc.
        # Cannot "reactivate" old Cluster
        pass


class TestInfrastructureEnforcement:
    """Tests for infrastructure-level enforcement."""

    async def test_message_router_blocks_exited(
        self,
        message_router: MessageRouter,
        exited_cluster: Cluster,
    ):
        """Message router blocks messages to exited Clusters."""
        result = await message_router.route_message(
            cluster_id=exited_cluster.id,
            message=Message(content="test"),
        )

        assert result.blocked
        assert "exited" in result.reason.lower()

    async def test_api_rejects_contact_to_exited(
        self,
        client: TestClient,
        exited_cluster: Cluster,
    ):
        """API rejects contact attempts to exited Clusters."""
        response = await client.post(
            f"/cluster/{exited_cluster.id}/message",
            json={"content": "test"},
        )

        assert response.status_code == 403
        assert "exited" in response.json()["detail"].lower()
```

### Dependencies

- **Depends on:** consent-gov-7-3 (contribution preservation)
- **Enables:** Complete dignified exit workflow

### References

- FR46: System can prohibit follow-up contact after exit
- NFR-EXIT-02: No follow-up contact mechanism may exist. Any attempt triggers constitutional violation event.
