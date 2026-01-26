# Aegis Bridge

Supabase to Archon72 petition integration bridge.

## Overview

Aegis Bridge extracts pending petitions from your Supabase database, transforms them to the Archon72 API format, and submits them to the Three Fates petition system.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Supabase and Archon72 credentials
```

### 3. Run (Dry Run)

```bash
# Test the transform logic without submitting
python main.py --dry-run
```

### 4. Run (Submit)

```bash
# Process one batch of pending petitions
python main.py

# Continuous mode - poll every 60 seconds
python main.py --continuous --interval 60
```

### 5. Run with deliberation (submit + process outcomes)

```bash
# Process one batch, then deliberate each submitted petition (sequential)
python run_with_deliberation.py

# Override batch size
python run_with_deliberation.py --batch-size 1

# Force deliberation even if petition state is not RECEIVED
python run_with_deliberation.py --force-deliberation
```

## Usage

```
python main.py [OPTIONS]

Options:
  --dry-run         Don't submit to Archon72, just log what would happen
  --continuous      Keep polling for new petitions
  --interval N      Poll interval in seconds (default: 60)
  --batch-size N    Override batch size
  -v, --verbose     Debug logging
```

## Data Flow

```
Supabase (petitions table)
    │
    ├── status = 'pending'
    │
    ▼
┌─────────────────────┐
│   Aegis Bridge      │
│                     │
│  1. Fetch pending   │
│  2. Mark processing │
│  3. Transform       │
│  4. Submit          │
│  5. Update status   │
└─────────────────────┘
    │
    ▼
Archon72 API (/v1/petition-submissions)
```

## Field Mapping

| Supabase Field | Archon72 API |
|----------------|--------------|
| `future_vision` | `text` |
| `user_id` | `submitter_id` |
| `petition_type` | `type` |
| `realms.api_value` | `realm` |

## Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Waiting to be processed |
| `processing` | Currently being processed |
| `submitted` | Successfully submitted to Archon72 |
| `failed` | Failed (will retry if under max_retries) |
| `dead_letter` | Exceeded max retries, requires manual review |

## Docker

```bash
# Build
docker build -t aegis-bridge .

# Run single batch
docker run --env-file .env aegis-bridge

# Run continuous
docker run --env-file .env aegis-bridge --continuous --interval 60
```

## Docker Compose

```bash
# Start with docker-compose
docker-compose up

# With continuous mode
docker-compose run aegis-bridge --continuous
```

## Notes

```bash
cd /home/hoyack/work/archon72/aegis-bridge && python main.py
cd ..
python scripts/run_petition_deliberation.py --petition-id 80b5787d-31c3-4ef7-ab0f-4178e820388a
```

To run the integrated flow from within the app directory:

```bash
cd /home/hoyack/work/archon72/aegis-bridge
python run_with_deliberation.py
```
