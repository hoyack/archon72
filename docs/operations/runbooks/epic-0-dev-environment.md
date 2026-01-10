# Developer Environment Setup

Last Updated: 2026-01-08
Version: 1.0
Owner: Development Team

## Purpose

Procedures for setting up and troubleshooting the Archon 72 Conclave Backend development environment, including HSM stub configuration and pre-commit hooks.

## Prerequisites

- [ ] Python 3.11+ installed
- [ ] Docker and Docker Compose installed
- [ ] Git configured with SSH keys
- [ ] Access to repository

## Trigger Conditions

When to execute this runbook:

- New developer onboarding
- Development environment issues
- Pre-commit hook failures
- HSM stub configuration problems

## Procedure

### Step 1: Clone and Setup

- [ ] Clone the repository
- [ ] Create Python virtual environment
- [ ] Install dependencies

```bash
# Clone repository
git clone git@github.com:archon72/conclave-backend.git
cd conclave-backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
```

**Verification:**

- Expected outcome: All dependencies install without errors
- Command to verify: `pip list | grep archon`

### Step 2: Configure Environment

- [ ] Copy environment template
- [ ] Configure local database connection
- [ ] Configure Redis connection
- [ ] Set HSM mode to development

```bash
# Copy environment template
cp .env.example .env

# Edit .env with local settings
# HSM_MODE=development  (uses software HSM stub)
# DATABASE_URL=postgresql://...
# REDIS_URL=redis://...
```

**Verification:**

- Expected outcome: Environment file configured
- Command to verify: `cat .env | grep -v SECRET`

### Step 3: Start Infrastructure

- [ ] Start local PostgreSQL
- [ ] Start local Redis
- [ ] Verify connectivity

```bash
# Using Docker Compose
docker-compose up -d postgres redis

# Verify
docker-compose ps
```

**Verification:**

- Expected outcome: Containers running
- Command to verify: `docker-compose ps`

### Step 4: Initialize Database

- [ ] Run database migrations
- [ ] Verify tables created

```bash
# Run migrations
make db-migrate

# Or manually
alembic upgrade head
```

**Verification:**

- Expected outcome: Migrations applied successfully
- Command to verify: `make db-check`

### Step 5: Configure HSM Stub

The development environment uses a software HSM stub for signing operations.

- [ ] HSM_MODE is set to "development" in .env
- [ ] Development keys are generated on first run
- [ ] Watermark identifies dev signatures

```bash
# Verify HSM mode
grep HSM_MODE .env
# Should show: HSM_MODE=development

# Test HSM stub
make test-hsm-stub
```

**Verification:**

- Expected outcome: HSM stub signs and verifies correctly
- Watermark: Dev signatures include "DEV-STUB" watermark

### Step 6: Install Pre-commit Hooks

- [ ] Install pre-commit
- [ ] Configure hooks
- [ ] Test hooks work

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files to verify
pre-commit run --all-files
```

**Verification:**

- Expected outcome: Hooks installed, initial run passes
- Command to verify: `pre-commit run --all-files`

### Step 7: Run Tests

- [ ] Run unit tests
- [ ] Run integration tests (requires Docker)

```bash
# Unit tests
make test-unit

# Integration tests
make test-integration

# All tests
make test
```

**Verification:**

- Expected outcome: All tests pass
- Command to verify: `make test`

### Step 8: Start Development Server

- [ ] Start FastAPI development server
- [ ] Verify health endpoints

```bash
# Start server
make dev

# Or manually
uvicorn src.api.main:app --reload
```

**Verification:**

- Expected outcome: Server starts on port 8000
- Command to verify: `curl http://localhost:8000/health`

---

## Troubleshooting

### Pre-commit Hook Failures

#### Import Boundary Violations

```
Import boundary violation detected in src/api/...
```

**Fix:** Review import and ensure it follows hexagonal architecture:
- API layer cannot import from infrastructure directly
- Domain layer cannot import from any other layer
- See: `scripts/check_imports.py`

#### Type Check Failures

```
mypy found errors in ...
```

**Fix:** Add type annotations or fix type mismatches. Run `mypy src/` for details.

### HSM Stub Issues

#### Signature Verification Fails

```
SignatureVerificationError: Invalid signature
```

**Check:**
1. HSM_MODE is "development"
2. Keys haven't been regenerated mid-session
3. Test data hasn't been modified

```bash
# Regenerate dev keys
rm -rf .dev_keys/
make test-hsm-stub
```

#### Missing Watermark

All development signatures MUST include watermark. If watermark missing:

1. Verify HSM_MODE=development
2. Check HSM stub implementation in `src/infrastructure/adapters/security/hsm_dev.py`

### Database Issues

#### Connection Refused

```
psycopg2.OperationalError: connection refused
```

**Check:**
1. Docker container is running: `docker-compose ps`
2. DATABASE_URL is correct in .env
3. Port isn't blocked by firewall

#### Migration Failures

```
alembic.util.exc.CommandError: Can't locate revision
```

**Fix:**
```bash
# Reset migrations (dev only!)
docker-compose down -v
docker-compose up -d postgres
make db-migrate
```

### Redis Issues

#### Connection Timeout

```
redis.exceptions.ConnectionError: Error connecting to redis
```

**Check:**
1. Redis container is running
2. REDIS_URL is correct
3. Redis port (6379) is accessible

---

## Escalation

| Condition | Escalate To | Contact |
|-----------|-------------|---------|
| Build system issues | Build Engineer | [TBD] |
| Architecture questions | System Architect | [TBD] |
| Security/HSM questions | Security Lead | [TBD] |

## References

- [Project README](../../../README.md)
- [Architecture Decision Records](../../../docs/adr/)
- [Contributing Guide](../../../CONTRIBUTING.md)
- Epic 0: Project Foundation stories
