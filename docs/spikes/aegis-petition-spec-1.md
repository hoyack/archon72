# Aegis Petition Bridge Specification

**Spike:** AEGIS-PETITION-SPEC-1
**Status:** Draft
**Created:** 2026-01-22
**Author:** System Architect

## Overview

This specification defines the integration between the external Aegis Petition UX (backed by Supabase) and the Archon72 Three Fates petition system. The bridge extracts pending petitions from Supabase, transforms them to the Archon72 API format, queues them for reliable delivery, and updates the source records with processing status.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Supabase DB   │────▶│  Aegis Bridge   │────▶│   Message Queue │────▶│  Archon72 API   │
│  (Source Data)  │     │   (Extract &    │     │  (Kafka/Redis)  │     │ /v1/petition-   │
│                 │◀────│    Transform)   │◀────│                 │     │   submissions   │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │                       │
        │                       │                       │                       │
        ▼                       ▼                       ▼                       ▼
   Source of Truth         Orchestrator            Reliability            Destination
```

## Data Flow

### Phase 1: Extract

1. Connect to Supabase via REST API or client library
2. Query for petitions with `status = 'pending'`
3. Apply pagination for large result sets
4. Lock records to prevent duplicate processing (optimistic locking)

### Phase 2: Transform

1. Map Supabase fields to Archon72 API schema
2. Validate transformed payload
3. Determine petition type from content or metadata
4. Generate idempotency key for deduplication

### Phase 3: Queue

1. Publish transformed petition to message queue
2. Include metadata for tracking and retry logic
3. Acknowledge successful queue insertion

### Phase 4: Consume & Submit

1. Consumer pulls messages from queue
2. POST to Archon72 API endpoint
3. Handle success/failure responses
4. Implement retry with exponential backoff

### Phase 5: Update Source

1. Update Supabase record with processing status
2. Store Archon72 petition_id for cross-reference
3. Record any error details for failed submissions

---

## Source Data Schema (Supabase)

### Input Table: `petitions`

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Submitter identity |
| `future_vision` | TEXT | Petition content |
| `status` | TEXT | `pending`, `processing`, `submitted`, `failed` |
| `reviewed_by` | UUID | Archon72 reviewer (populated after review) |
| `reviewed_at` | TIMESTAMP | When reviewed by Archon72 |
| `review_notes` | TEXT | Notes from Archon72 processing |
| `submitted_at` | TIMESTAMP | Original submission time |
| `updated_at` | TIMESTAMP | Last modification |
| `previously_declined` | BOOLEAN | Re-submission flag |
| `responsibility_declared` | BOOLEAN | User acknowledgment |
| `signature` | TEXT | Ed25519 signature (base64) |
| `current_step` | INTEGER | UI workflow step |

### New Fields (to add)

| Field | Type | Description |
|-------|------|-------------|
| `archon72_petition_id` | UUID | Cross-reference to Archon72 |
| `archon72_state` | TEXT | Current Archon72 state |
| `archon72_submitted_at` | TIMESTAMP | When sent to Archon72 |
| `petition_type` | TEXT | GENERAL, GRIEVANCE, etc. |
| `processing_error` | TEXT | Last error message if failed |
| `retry_count` | INTEGER | Number of retry attempts |

---

## Transformation Mapping

### Field Mapping

```python
def transform_petition(supabase_record: dict) -> dict:
    """Transform Supabase petition to Archon72 API format."""
    return {
        "type": determine_petition_type(supabase_record),
        "text": supabase_record["future_vision"],
        "submitter_id": supabase_record["user_id"],
        "realm": "aegis",  # Fixed realm for external petitions
        # Optional: notification preferences if webhook configured
    }
```

### Petition Type Determination

| Condition | Type |
|-----------|------|
| Contains "cessation" or "shutdown" keywords | `CESSATION` |
| Contains "complaint", "concern", "issue" keywords | `GRIEVANCE` |
| Contains "collaboration", "partnership" keywords | `COLLABORATION` |
| Contains "petition system", "meta" keywords | `META` |
| Default | `GENERAL` |

Alternatively, add a `petition_type` dropdown to the Aegis UX for explicit selection.

---

## Queue Technology Evaluation

### Option 1: Redis Streams (Recommended for MVP)

**Pros:**
- Simple setup, likely already in infrastructure
- Built-in consumer groups for reliable delivery
- Low latency
- Supports message acknowledgment

**Cons:**
- Less durable than Kafka for high-volume scenarios
- No built-in dead letter queue (must implement)

**Configuration:**
```yaml
redis:
  host: localhost
  port: 6379
  stream_name: aegis-petitions
  consumer_group: archon72-bridge
  max_retries: 3
  retry_delay_seconds: [5, 30, 300]  # Exponential backoff
```

### Option 2: RabbitMQ

**Pros:**
- Mature, well-documented
- Built-in dead letter exchanges
- Flexible routing patterns
- Good for moderate volumes

**Cons:**
- Additional infrastructure to manage
- More complex than Redis for simple use cases

**Configuration:**
```yaml
rabbitmq:
  host: localhost
  port: 5672
  exchange: aegis-petitions
  queue: archon72-submissions
  dlq: archon72-submissions-dlq
  prefetch_count: 10
```

### Option 3: Apache Kafka

**Pros:**
- Highly durable, persistent log
- Excellent for high-volume scenarios
- Built-in partitioning and replication
- Event sourcing friendly

**Cons:**
- Heavyweight for small-scale use
- Operational complexity
- Overkill for < 10k messages/day

**Configuration:**
```yaml
kafka:
  bootstrap_servers: localhost:9092
  topic: aegis-petitions
  consumer_group: archon72-bridge
  auto_offset_reset: earliest
  enable_auto_commit: false
```

### Recommendation

**Start with Redis Streams** for MVP. Simple, fast, and sufficient for expected volume. Migrate to RabbitMQ or Kafka if:
- Volume exceeds 100k petitions/day
- Multi-datacenter replication needed
- Complex routing requirements emerge

---

## Message Schema

### Queue Message Format

```json
{
  "message_id": "uuid-v4",
  "idempotency_key": "aegis-{supabase_petition_id}",
  "timestamp": "2026-01-22T18:00:00Z",
  "source": {
    "system": "aegis",
    "petition_id": "2b22c0de-06f7-4dde-b3d3-afcfbf88fadd",
    "user_id": "a22d0b05-ce83-45f4-a8ba-bcdd1b6d70e1"
  },
  "payload": {
    "type": "GRIEVANCE",
    "text": "I submit this petition to request formal acknowledgment...",
    "submitter_id": "a22d0b05-ce83-45f4-a8ba-bcdd1b6d70e1",
    "realm": "aegis"
  },
  "metadata": {
    "retry_count": 0,
    "max_retries": 3,
    "original_submitted_at": "2026-01-22T02:00:53.394Z"
  }
}
```

---

## API Integration

### Submit to Archon72

```
POST /v1/petition-submissions
Host: archon72-api:8000
Content-Type: application/json
X-Idempotency-Key: aegis-{supabase_petition_id}

{
  "type": "GRIEVANCE",
  "text": "I submit this petition to request formal acknowledgment...",
  "submitter_id": "a22d0b05-ce83-45f4-a8ba-bcdd1b6d70e1",
  "realm": "aegis"
}
```

### Response Handling

| Status | Action |
|--------|--------|
| `201 Created` | Success - update Supabase with `archon72_petition_id` |
| `400 Bad Request` | Permanent failure - mark as failed, do not retry |
| `429 Too Many Requests` | Transient - requeue with backoff per `Retry-After` |
| `503 Service Unavailable` | Transient - requeue with backoff |
| `5xx` | Transient - requeue with exponential backoff |

### Update Supabase

**On Success:**
```sql
UPDATE petitions SET
  status = 'submitted',
  archon72_petition_id = '{petition_id from response}',
  archon72_state = 'RECEIVED',
  archon72_submitted_at = NOW(),
  processing_error = NULL,
  updated_at = NOW()
WHERE id = '{supabase_petition_id}';
```

**On Permanent Failure:**
```sql
UPDATE petitions SET
  status = 'failed',
  processing_error = '{error detail}',
  retry_count = retry_count + 1,
  updated_at = NOW()
WHERE id = '{supabase_petition_id}';
```

---

## Component Design

### 1. Extractor Service

**Responsibility:** Poll Supabase for pending petitions

```python
class PetitionExtractor:
    """Extract pending petitions from Supabase."""

    def __init__(self, supabase_client, queue_publisher):
        self.supabase = supabase_client
        self.queue = queue_publisher

    async def extract_pending(self, batch_size: int = 100) -> int:
        """
        Extract pending petitions and publish to queue.

        Returns number of petitions queued.
        """
        # 1. Query pending petitions
        petitions = await self.supabase.table("petitions") \
            .select("*") \
            .eq("status", "pending") \
            .limit(batch_size) \
            .execute()

        # 2. Mark as processing (optimistic lock)
        ids = [p["id"] for p in petitions.data]
        await self.supabase.table("petitions") \
            .update({"status": "processing"}) \
            .in_("id", ids) \
            .execute()

        # 3. Transform and queue
        for petition in petitions.data:
            message = self.transform(petition)
            await self.queue.publish(message)

        return len(petitions.data)

    def transform(self, petition: dict) -> dict:
        """Transform to queue message format."""
        return {
            "message_id": str(uuid4()),
            "idempotency_key": f"aegis-{petition['id']}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": {
                "system": "aegis",
                "petition_id": petition["id"],
                "user_id": petition["user_id"],
            },
            "payload": {
                "type": self.determine_type(petition),
                "text": petition["future_vision"],
                "submitter_id": petition["user_id"],
                "realm": "aegis",
            },
            "metadata": {
                "retry_count": 0,
                "max_retries": 3,
                "original_submitted_at": petition["submitted_at"],
            },
        }
```

### 2. Consumer Service

**Responsibility:** Process queued petitions and submit to Archon72

```python
class PetitionConsumer:
    """Consume petitions from queue and submit to Archon72."""

    def __init__(self, queue_consumer, archon72_client, supabase_client):
        self.queue = queue_consumer
        self.archon72 = archon72_client
        self.supabase = supabase_client

    async def process_message(self, message: dict) -> None:
        """Process a single petition message."""
        try:
            # Submit to Archon72
            response = await self.archon72.submit_petition(
                payload=message["payload"],
                idempotency_key=message["idempotency_key"],
            )

            # Update Supabase on success
            await self.update_success(
                petition_id=message["source"]["petition_id"],
                archon72_petition_id=response["petition_id"],
                archon72_state=response["state"],
            )

            # Acknowledge message
            await self.queue.ack(message)

        except TransientError as e:
            # Requeue with backoff
            await self.handle_retry(message, e)

        except PermanentError as e:
            # Mark as failed, don't retry
            await self.update_failure(
                petition_id=message["source"]["petition_id"],
                error=str(e),
            )
            await self.queue.ack(message)  # Remove from queue
```

### 3. Status Sync Service (Optional)

**Responsibility:** Periodically sync Archon72 petition status back to Supabase

```python
class StatusSyncService:
    """Sync Archon72 petition status to Supabase."""

    async def sync_statuses(self) -> None:
        """
        Query Supabase for submitted petitions and
        update their status from Archon72.
        """
        # Get petitions that need status sync
        petitions = await self.supabase.table("petitions") \
            .select("id, archon72_petition_id") \
            .eq("status", "submitted") \
            .not_is("archon72_petition_id", None) \
            .execute()

        for petition in petitions.data:
            # Query Archon72 for current status
            status = await self.archon72.get_petition_status(
                petition["archon72_petition_id"]
            )

            # Update Supabase
            await self.supabase.table("petitions") \
                .update({
                    "archon72_state": status["state"],
                    "reviewed_at": status.get("updated_at"),
                    "review_notes": status.get("fate_reason"),
                }) \
                .eq("id", petition["id"]) \
                .execute()
```

---

## Configuration

### Environment Variables

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # Service role key for server-side access

# Archon72 API
ARCHON72_API_URL=http://archon72-api:8000
ARCHON72_API_TIMEOUT=30

# Queue (Redis)
REDIS_URL=redis://localhost:6379
REDIS_STREAM=aegis-petitions
REDIS_CONSUMER_GROUP=archon72-bridge

# Processing
BATCH_SIZE=100
POLL_INTERVAL_SECONDS=60
MAX_RETRIES=3
RETRY_BACKOFF_SECONDS=5,30,300
```

### Config File

```yaml
# config/aegis-bridge.yaml
supabase:
  url: ${SUPABASE_URL}
  service_key: ${SUPABASE_SERVICE_KEY}
  table: petitions

archon72:
  api_url: ${ARCHON72_API_URL}
  timeout_seconds: 30
  endpoints:
    submit: /v1/petition-submissions
    status: /v1/petition-submissions/{petition_id}

queue:
  type: redis  # redis | rabbitmq | kafka
  redis:
    url: ${REDIS_URL}
    stream: aegis-petitions
    consumer_group: archon72-bridge
    consumer_name: worker-1

processing:
  batch_size: 100
  poll_interval_seconds: 60
  max_retries: 3
  retry_backoff: [5, 30, 300]

logging:
  level: INFO
  format: json
```

---

## Error Handling

### Retry Strategy

| Error Type | Retry | Backoff |
|------------|-------|---------|
| Network timeout | Yes | Exponential: 5s, 30s, 5min |
| 429 Rate Limited | Yes | Use `Retry-After` header |
| 503 Queue Full | Yes | Use `Retry-After` header |
| 500 Server Error | Yes | Exponential: 5s, 30s, 5min |
| 400 Validation Error | No | Mark as permanently failed |
| 404 Not Found | No | Mark as permanently failed |

### Dead Letter Handling

After `max_retries` exceeded:
1. Move message to dead letter queue/stream
2. Update Supabase record with `status = 'dead_letter'`
3. Alert operations team for manual review

---

## Monitoring & Observability

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `aegis_petitions_extracted_total` | Counter | Petitions extracted from Supabase |
| `aegis_petitions_queued_total` | Counter | Petitions published to queue |
| `aegis_petitions_submitted_total` | Counter | Successful Archon72 submissions |
| `aegis_petitions_failed_total` | Counter | Failed submissions (by error type) |
| `aegis_petitions_retried_total` | Counter | Retry attempts |
| `aegis_queue_depth` | Gauge | Current queue depth |
| `aegis_processing_latency_seconds` | Histogram | End-to-end processing time |

### Health Checks

```
GET /health/aegis-bridge

{
  "status": "healthy",
  "components": {
    "supabase": "connected",
    "redis": "connected",
    "archon72": "reachable"
  },
  "queue_depth": 42,
  "last_extract_at": "2026-01-22T18:00:00Z",
  "last_submit_at": "2026-01-22T18:00:05Z"
}
```

---

## Deployment

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  aegis-bridge:
    build: ./aegis-bridge
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - ARCHON72_API_URL=http://archon72-api:8000
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - archon72-api
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

### Kubernetes (Production)

- Deploy as a Deployment with 2-3 replicas
- Use Redis Cluster or managed Redis for queue
- Configure HPA based on queue depth
- Use Secrets for Supabase credentials

---

## Testing Strategy

### Unit Tests

- Transformation logic
- Retry backoff calculations
- Message serialization/deserialization

### Integration Tests

- Supabase connection and queries
- Queue publish/consume cycle
- Archon72 API mocking

### End-to-End Tests

- Full flow: Supabase → Queue → Archon72 → Supabase update
- Error scenarios: network failures, API errors
- Idempotency verification

---

## Implementation Phases

### Phase 1: MVP (Week 1)

- [ ] Basic extractor with Supabase client
- [ ] Redis Streams queue integration
- [ ] Consumer with Archon72 submission
- [ ] Supabase status updates
- [ ] Basic error handling and retries

### Phase 2: Reliability (Week 2)

- [ ] Dead letter queue handling
- [ ] Idempotency key implementation
- [ ] Comprehensive retry logic
- [ ] Monitoring and metrics

### Phase 3: Operations (Week 3)

- [ ] Health check endpoints
- [ ] Alerting integration
- [ ] Status sync service
- [ ] Documentation and runbooks

---

## Open Questions

1. **Petition Type Selection:** Should we add a dropdown to Aegis UX or infer from content?
2. **Notification Preferences:** Should Aegis users configure webhook URLs?
3. **Rate Limiting:** What's the expected petition volume? Need to coordinate with Archon72 rate limits.
4. **Authentication:** Does Archon72 API require auth tokens for external systems?
5. **Status Webhook:** Should Archon72 push status updates to Aegis via webhook instead of polling?

---

## References

- [Archon72 Petition API Documentation](../sample-petition-payload.md)
- [Supabase JavaScript Client](https://supabase.com/docs/reference/javascript)
- [Redis Streams](https://redis.io/docs/data-types/streams/)
