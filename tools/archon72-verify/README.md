# archon72-verify

Open-source verification toolkit for Archon 72 event chain (FR47, FR49).

## Installation

```bash
pip install archon72-verify
```

Or install from source:

```bash
git clone https://github.com/archon72/archon72-verify.git
cd archon72-verify
pip install -e .
```

## Quick Start

### Verify Hash Chain

```bash
# Verify events 1-1000 from the API
archon72-verify check-chain --from 1 --to 1000

# Verify from local file (offline mode)
archon72-verify check-chain --file events.json --from 1 --to 100
```

### Check for Sequence Gaps

```bash
# Check gaps via API
archon72-verify check-gaps --from 1 --to 1000

# Check gaps in local database (FR122, FR123)
archon72-verify check-gaps --local-db ./events.db
archon72-verify check-gaps --local-db ./events.db --format json
```

### Verify Event Signature

```bash
archon72-verify verify-signature 550e8400-e29b-41d4-a716-446655440000
```

### Verify Historical Query Proof (FR89)

```bash
# Verify proof that historical query is part of canonical chain
archon72-verify verify-proof --as-of 1000

# Verify from local file (offline mode)
archon72-verify verify-proof --file proof.json --as-of 1000
```

### Local Database Management (FR122, FR123)

Observers can maintain a local SQLite database for offline verification:

```bash
# Initialize local database
archon72-verify init-db ./events.db

# Sync events from API to local database
archon72-verify sync --local-db ./events.db --api-url https://api.archon72.com
archon72-verify sync --local-db ./events.db --batch-size 500

# Fill gaps by fetching missing events
archon72-verify fill-gaps --local-db ./events.db --api-url https://api.archon72.com
```

## Python Library Usage

```python
import asyncio
from archon72_verify import ObserverClient, ChainVerifier

async def main():
    # Fetch events
    client = ObserverClient()
    events = await client.get_events(1, 1000)
    await client.close()

    # Verify chain
    verifier = ChainVerifier()
    result = verifier.verify_chain(events)

    if result.is_valid:
        print(f"Chain valid: {result.events_verified} events verified")
    else:
        print(f"Chain invalid at sequence {result.first_invalid_sequence}")
        print(f"Error: {result.error_message}")

asyncio.run(main())
```

### Local Database API

```python
from archon72_verify import ObserverDatabase, ChainVerifier

# Initialize and populate database
with ObserverDatabase("./events.db") as db:
    db.init_schema()

    # Insert events
    for event in events:
        db.insert_event(event)

    # Check for sequence gaps (FR122)
    gaps = db.find_gaps()
    for start, end in gaps:
        print(f"Missing events: {start} to {end}")

    # Get event count and range
    count = db.get_event_count()
    min_seq, max_seq = db.get_sequence_range()

# Verify local database chain
verifier = ChainVerifier()
result = verifier.verify_database("./events.db")

if result.is_valid:
    print(f"Database verified: {result.events_verified} events")
else:
    print(f"Verification failed: {result.error_message}")
    if result.gaps_found:
        print(f"Gaps detected: {result.gaps_found}")
```

## Verification Specification

The toolkit implements verification per the Archon 72 constitutional requirements:

- **FR47**: Open-source verification toolkit
- **FR49**: Chain verification, signature verification, gap detection
- **FR62**: Raw event data sufficient for independent hash computation
- **FR63**: Exact hash algorithm, encoding, field ordering
- **FR122**: Local database gap detection for observers
- **FR123**: Gap range reporting (start, end sequences)

### Hash Computation

Content hash is computed as SHA-256 over canonical JSON:

```python
hashable = {
    "event_type": event["event_type"],
    "payload": event["payload"],
    "signature": event["signature"],
    "witness_id": event["witness_id"],
    "witness_signature": event["witness_signature"],
    "local_timestamp": event["local_timestamp"],
}
if event.get("agent_id"):
    hashable["agent_id"] = event["agent_id"]

canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
content_hash = hashlib.sha256(canonical.encode()).hexdigest()
```

### Genesis Anchor

Sequence 1 must have `prev_hash` equal to 64 zeros (`"0" * 64`).

## License

MIT License - see [LICENSE](LICENSE) for details.
