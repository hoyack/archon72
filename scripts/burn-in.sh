#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Archon 72 - Burn-In Test Script
# ═══════════════════════════════════════════════════════════════
# Runs tests multiple times to detect flaky/non-deterministic tests.
# Even ONE failure indicates a flaky test that needs investigation.
#
# Usage:
#   ./scripts/burn-in.sh              # Default 10 iterations
#   ./scripts/burn-in.sh 50           # 50 iterations
#   ./scripts/burn-in.sh 100 --smoke  # 100 iterations, smoke only
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
ITERATIONS=${1:-10}
SMOKE_ONLY=false
FAILED_ITERATION=0

# Parse additional args
shift 2>/dev/null || true
for arg in "$@"; do
    case $arg in
        --smoke)
            SMOKE_ONLY=true
            ;;
        --help)
            echo "Usage: $0 [ITERATIONS] [OPTIONS]"
            echo ""
            echo "Arguments:"
            echo "  ITERATIONS   Number of test iterations (default: 10)"
            echo ""
            echo "Options:"
            echo "  --smoke      Run smoke tests only (faster)"
            echo "  --help       Show this help message"
            echo ""
            echo "Exit codes:"
            echo "  0  All iterations passed (no flaky tests)"
            echo "  1  At least one iteration failed (flaky test detected)"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     Archon 72 - Burn-In Test Loop${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Iterations: ${YELLOW}$ITERATIONS${NC}"
echo -e "Mode: ${YELLOW}$([ "$SMOKE_ONLY" = true ] && echo "Smoke tests only" || echo "Full test suite")${NC}"
echo ""

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

START_TIME=$(date +%s)

# Build pytest command
if [ "$SMOKE_ONLY" = true ]; then
    PYTEST_ARGS="-m smoke"
else
    PYTEST_ARGS="-m 'not slow and not chaos and not load and not requires_api_keys'"
fi

# Run burn-in loop
for i in $(seq 1 $ITERATIONS); do
    echo -e "${BLUE}────────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}  Burn-in iteration $i/$ITERATIONS${NC}"
    echo -e "${BLUE}────────────────────────────────────────────────────────────────${NC}"

    if ! poetry run pytest tests/unit/ \
        $PYTEST_ARGS \
        --tb=short \
        -q \
        --timeout=60; then

        FAILED_ITERATION=$i
        echo ""
        echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  FLAKY TEST DETECTED!${NC}"
        echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "Test failed on iteration ${YELLOW}$i${NC} of $ITERATIONS"
        echo ""
        echo "This indicates a non-deterministic test that:"
        echo "  - May have race conditions"
        echo "  - May depend on external state"
        echo "  - May have timing-dependent assertions"
        echo "  - May have order-dependent execution"
        echo ""
        echo "Investigation steps:"
        echo "  1. Re-run with verbose output: pytest tests/unit -v --tb=long"
        echo "  2. Check test isolation: pytest tests/unit --forked"
        echo "  3. Run single test repeatedly: pytest tests/path/to/test.py -v --count=10"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}  ✓ Iteration $i passed${NC}"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Burn-in PASSED: All $ITERATIONS iterations successful!${NC}"
echo -e "${GREEN}  Duration: ${DURATION}s${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "No flaky tests detected. Tests are stable and ready for CI."
