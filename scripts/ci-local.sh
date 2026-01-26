#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Archon 72 - Local CI Mirror Script
# ═══════════════════════════════════════════════════════════════
# Mirrors the GitHub Actions CI pipeline locally for debugging
# and pre-push validation.
#
# Usage:
#   ./scripts/ci-local.sh           # Full pipeline
#   ./scripts/ci-local.sh --quick   # Skip burn-in
#   ./scripts/ci-local.sh --lint    # Lint only
#   ./scripts/ci-local.sh --test    # Tests only
# ═══════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
QUICK_MODE=false
LINT_ONLY=false
TEST_ONLY=false

for arg in "$@"; do
    case $arg in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --lint)
            LINT_ONLY=true
            shift
            ;;
        --test)
            TEST_ONLY=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick    Skip burn-in stage (3 iterations instead of 10)"
            echo "  --lint     Run lint checks only"
            echo "  --test     Run tests only (skip lint)"
            echo "  --help     Show this help message"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     Archon 72 - Local CI Pipeline${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Track timing
START_TIME=$(date +%s)

# ═══════════════════════════════════════════════════════════════
# STAGE 1: LINT
# ═══════════════════════════════════════════════════════════════
if [ "$TEST_ONLY" = false ]; then
    echo -e "${YELLOW}[1/4] Running lint checks...${NC}"

    echo "  → ruff check"
    if ! poetry run ruff check src/ tests/; then
        echo -e "${RED}FAILED: ruff check found issues${NC}"
        exit 1
    fi

    echo "  → ruff format --check"
    if ! poetry run ruff format --check src/ tests/; then
        echo -e "${RED}FAILED: Code formatting issues found${NC}"
        echo "  Run 'poetry run ruff format src/ tests/' to fix"
        exit 1
    fi

    echo "  → mypy (type checking)"
    poetry run mypy src/ || echo -e "${YELLOW}  Warning: mypy found type issues (non-blocking)${NC}"

    echo -e "${GREEN}  ✓ Lint checks passed${NC}"
    echo ""

    if [ "$LINT_ONLY" = true ]; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  Local lint completed in ${DURATION}s${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
        exit 0
    fi
fi

# ═══════════════════════════════════════════════════════════════
# STAGE 2: TESTS
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}[2/4] Running test suite...${NC}"

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

if ! poetry run pytest tests/unit/ \
    -v \
    --tb=short \
    -m "not slow and not chaos and not load and not requires_api_keys" \
    --timeout=60; then
    echo -e "${RED}FAILED: Tests failed${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ Tests passed${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# STAGE 3: BURN-IN (reduced iterations locally)
# ═══════════════════════════════════════════════════════════════
if [ "$QUICK_MODE" = true ]; then
    BURN_IN_ITERATIONS=3
else
    BURN_IN_ITERATIONS=5
fi

echo -e "${YELLOW}[3/4] Running burn-in loop (${BURN_IN_ITERATIONS} iterations)...${NC}"

for i in $(seq 1 $BURN_IN_ITERATIONS); do
    echo -e "  ${BLUE}Burn-in iteration $i/$BURN_IN_ITERATIONS${NC}"

    if ! poetry run pytest tests/unit/ \
        -m "smoke or not slow" \
        --tb=line \
        -q \
        --timeout=60 2>/dev/null; then
        echo -e "${RED}FAILED: Test failed on iteration $i (flaky test detected)${NC}"
        exit 1
    fi
done

echo -e "${GREEN}  ✓ Burn-in passed (no flaky tests)${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# STAGE 4: COVERAGE REPORT
# ═══════════════════════════════════════════════════════════════
echo -e "${YELLOW}[4/4] Generating coverage report...${NC}"

poetry run pytest tests/unit/ \
    -m "not slow and not chaos and not load and not requires_api_keys" \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    -q \
    --timeout=60 || true

echo -e "${GREEN}  ✓ Coverage report generated (htmlcov/index.html)${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Local CI pipeline PASSED in ${DURATION}s${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Safe to push to remote!"
