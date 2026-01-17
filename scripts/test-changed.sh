#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Archon 72 - Selective Test Runner
# ═══════════════════════════════════════════════════════════════
# Runs only tests affected by changed files.
# Useful for fast feedback during development.
#
# Usage:
#   ./scripts/test-changed.sh           # Test changes vs HEAD~1
#   ./scripts/test-changed.sh main      # Test changes vs main branch
#   ./scripts/test-changed.sh --staged  # Test staged changes only
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
COMPARE_REF="HEAD~1"
STAGED_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --staged)
            STAGED_ONLY=true
            ;;
        --help)
            echo "Usage: $0 [REF] [OPTIONS]"
            echo ""
            echo "Arguments:"
            echo "  REF          Git ref to compare against (default: HEAD~1)"
            echo "               Examples: main, develop, HEAD~5, abc123"
            echo ""
            echo "Options:"
            echo "  --staged     Only consider staged changes"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            if [ "$arg" != "" ] && [[ ! "$arg" =~ ^-- ]]; then
                COMPARE_REF="$arg"
            fi
            ;;
    esac
done

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     Archon 72 - Selective Test Runner${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Get changed files
if [ "$STAGED_ONLY" = true ]; then
    echo -e "Mode: ${YELLOW}Staged changes only${NC}"
    CHANGED_FILES=$(git diff --cached --name-only)
else
    echo -e "Comparing against: ${YELLOW}$COMPARE_REF${NC}"
    CHANGED_FILES=$(git diff --name-only "$COMPARE_REF" 2>/dev/null || git diff --name-only HEAD~1)
fi

if [ -z "$CHANGED_FILES" ]; then
    echo ""
    echo -e "${YELLOW}No changed files detected.${NC}"
    echo "Nothing to test."
    exit 0
fi

echo ""
echo "Changed files:"
echo "$CHANGED_FILES" | while read -r file; do
    echo "  - $file"
done
echo ""

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Collect affected test files
AFFECTED_TESTS=""

# Check for changed source files
CHANGED_SRC=$(echo "$CHANGED_FILES" | grep "^src/" || true)
if [ -n "$CHANGED_SRC" ]; then
    echo -e "${BLUE}Analyzing changed source files...${NC}"

    for src_file in $CHANGED_SRC; do
        # Extract module path (e.g., src/domain/governance/task/model.py -> domain/governance/task)
        if [[ "$src_file" =~ ^src/(.+)/[^/]+\.py$ ]]; then
            MODULE_PATH="${BASH_REMATCH[1]}"

            # Look for corresponding test files
            TEST_PATTERN="tests/**/*${MODULE_PATH##*/}*.py"
            MATCHING_TESTS=$(find tests -name "*$(basename $MODULE_PATH)*.py" -o -name "test_$(basename ${src_file%.py}).py" 2>/dev/null || true)

            if [ -n "$MATCHING_TESTS" ]; then
                AFFECTED_TESTS="$AFFECTED_TESTS $MATCHING_TESTS"
            fi
        fi
    done
fi

# Check for directly changed test files
CHANGED_TESTS=$(echo "$CHANGED_FILES" | grep "^tests/.*test_.*\.py$" || true)
if [ -n "$CHANGED_TESTS" ]; then
    echo -e "${BLUE}Found directly changed test files${NC}"
    AFFECTED_TESTS="$AFFECTED_TESTS $CHANGED_TESTS"
fi

# Deduplicate
AFFECTED_TESTS=$(echo "$AFFECTED_TESTS" | tr ' ' '\n' | sort -u | tr '\n' ' ')

if [ -z "$AFFECTED_TESTS" ] || [ "$AFFECTED_TESTS" = " " ]; then
    echo ""
    echo -e "${YELLOW}No test files affected by changes.${NC}"
    echo ""
    echo "Changed files don't map to any tests. Consider running:"
    echo "  - Full test suite: poetry run pytest tests/"
    echo "  - Smoke tests: poetry run pytest tests/ -m smoke"
    exit 0
fi

# Count affected tests
TEST_COUNT=$(echo "$AFFECTED_TESTS" | wc -w)
echo ""
echo -e "Found ${GREEN}$TEST_COUNT${NC} affected test file(s):"
echo "$AFFECTED_TESTS" | tr ' ' '\n' | while read -r test; do
    [ -n "$test" ] && echo "  - $test"
done
echo ""

# Run affected tests
echo -e "${YELLOW}Running affected tests...${NC}"
echo ""

if poetry run pytest $AFFECTED_TESTS \
    -v \
    --tb=short \
    --timeout=60; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Selective tests PASSED!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
else
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  Selective tests FAILED${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    exit 1
fi
