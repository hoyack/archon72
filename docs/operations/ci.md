# Archon 72 - CI/CD Pipeline Documentation

## Overview

The Archon 72 test pipeline uses GitHub Actions to ensure code quality and test stability. The pipeline runs on every push and pull request, with additional burn-in testing for PRs targeting main/develop branches.

## Pipeline Stages

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    LINT     │───▶│    TEST     │───▶│   BURN-IN   │───▶│   REPORT    │
│   <2 min    │    │  <10 min    │    │  <30 min    │    │   <2 min    │
│             │    │  (4 shards) │    │ (PRs only)  │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Stage 1: Lint (~2 minutes)

Code quality checks run first to catch issues early:

- **ruff check**: Linting for style and potential bugs
- **ruff format**: Code formatting verification
- **mypy**: Static type checking (non-blocking)

### Stage 2: Test (~10 minutes per shard)

Tests run in parallel across 4 shards for faster execution:

- **Sharding**: Tests are split alphabetically across 4 jobs
- **Scope**: Unit tests only (no external services)
- **Markers**: Slow, chaos, load, and external dependency tests are excluded by default
- **Coverage**: Each shard generates coverage reports

### Stage 3: Burn-In (~30 minutes)

Flaky test detection runs on PRs to main/develop:

- **Iterations**: 10 consecutive test runs
- **Failure Policy**: Even ONE failure indicates a flaky test
- **Trigger**: PRs to main/develop, scheduled weekly, manual dispatch

### Stage 4: Report

Aggregates results and uploads coverage:

- **Codecov**: Coverage reports combined and uploaded
- **Summary**: GitHub Actions summary with pass/fail status
- **Artifacts**: Test results available for download

## Running Locally

### Full CI Mirror

```bash
./scripts/ci-local.sh
```

This mirrors the CI pipeline locally:
1. Lint checks (ruff, mypy)
2. Test suite
3. Burn-in loop (5 iterations)
4. Coverage report

### Quick Mode (Skip Burn-In)

```bash
./scripts/ci-local.sh --quick
```

### Lint Only

```bash
./scripts/ci-local.sh --lint
```

### Test Only

```bash
./scripts/ci-local.sh --test
```

By default, external-dependency tests (integration/chaos/load/LLM/API) are skipped.
Use `--run-external` or `RUN_EXTERNAL_TESTS=1` when explicitly running those suites.

## Burn-In Testing

### What is Burn-In?

Burn-in testing runs the test suite multiple times to detect non-deterministic (flaky) tests. Even a single failure across all iterations indicates a problem.

### Run Locally

```bash
# Default 10 iterations
./scripts/burn-in.sh

# Custom iterations
./scripts/burn-in.sh 50

# Smoke tests only (faster)
./scripts/burn-in.sh 10 --smoke
```

### Common Causes of Flaky Tests

1. **Race conditions**: Tests depend on timing
2. **Shared state**: Tests don't clean up properly
3. **Order dependence**: Tests pass only in certain order
4. **External dependencies**: Network, file system, time

### Fixing Flaky Tests

1. Isolate the test: `pytest tests/path/to/test.py -v --count=10`
2. Check for shared state
3. Add explicit waits or synchronization
4. Mock external dependencies

## Selective Testing

Run only tests affected by your changes:

```bash
# Compare against last commit
./scripts/test-changed.sh

# Compare against main branch
./scripts/test-changed.sh main

# Test staged changes only
./scripts/test-changed.sh --staged
```

## Test Markers

The codebase uses pytest markers to categorize tests:

| Marker | Description | Default |
|--------|-------------|---------|
| `smoke` | Quick sanity checks | Included |
| `integration` | Full integration tests | Included |
| `slow` | Tests taking >30s | **Excluded** |
| `chaos` | Destructive/terminal tests | **Excluded** |
| `load` | Load/stress tests | **Excluded** |
| `requires_api_keys` | Need LLM API keys | **Excluded** |

### Running Specific Markers

```bash
# Smoke tests only
poetry run pytest -m smoke

# Integration tests
poetry run pytest -m integration

# Include slow tests
poetry run pytest -m "not chaos and not load"
```

## Artifacts

### Test Results

On failure, the following artifacts are uploaded:

- `junit-{shard}.xml`: JUnit test results
- `coverage-{shard}.xml`: Coverage data
- `.pytest_cache/`: Pytest cache for debugging
- `tests/**/*.log`: Any log files generated

### Retention

- **Failure artifacts**: 30 days
- **Coverage reports**: Available via Codecov

## Manual Triggers

### Trigger Full Pipeline

```bash
gh workflow run test.yml
```

### Trigger with Custom Burn-In

```bash
gh workflow run test.yml -f burn_in_iterations=50
```

## Environment Variables

The pipeline uses these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Service container |
| `REDIS_URL` | Redis connection string | Service container |
| `PYTHONPATH` | Python module path | Workspace root |

## Performance Targets

| Stage | Target | Actual |
|-------|--------|--------|
| Lint | <2 min | ~1-2 min |
| Test (per shard) | <10 min | ~5-8 min |
| Burn-in | <30 min | ~20-25 min |
| Total Pipeline | <45 min | ~35-40 min |

## Troubleshooting

### Tests Pass Locally But Fail in CI

1. Check environment differences (Python version, OS)
2. Look for timing-dependent tests
3. Check for hardcoded paths
4. Verify service dependencies

### Burn-In Failures

1. Run locally with more iterations: `./scripts/burn-in.sh 50`
2. Isolate failing test
3. Check for race conditions
4. Add proper test isolation

### Slow Pipeline

1. Check test count per shard
2. Consider adding more shards
3. Review slow tests (add `@pytest.mark.slow`)
4. Optimize test fixtures

## Badge

Add this to your README:

```markdown
[![Test Pipeline](https://github.com/hoyack/archon72/actions/workflows/test.yml/badge.svg)](https://github.com/hoyack/archon72/actions/workflows/test.yml)
```
