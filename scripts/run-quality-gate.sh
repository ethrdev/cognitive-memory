#!/bin/bash
# Quality Gate Pipeline Script
# Runs tests by priority and enforces quality gates

# Activate test virtual environment
source venv_test/bin/activate

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================"
echo "Quality Gate Pipeline"
echo "================================"
echo ""

# Configuration
PYTEST_ARGS="--tb=short --strict-markers -v"
COVERAGE_MIN=80

# Function to run tests by priority
run_priority_tests() {
    local priority=$1
    local description=$2
    
    echo -e "${YELLOW}Running ${priority} tests (${description})...${NC}"
    echo "----------------------------------------"
    
    if pytest tests/ -k "test_${priority}" ${PYTEST_ARGS}; then
        echo -e "${GREEN}✓ ${priority} tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ ${priority} tests failed${NC}"
        return 1
    fi
}

# Function to run coverage
run_coverage() {
    echo -e "${YELLOW}Running coverage analysis...${NC}"
    echo "----------------------------------------"
    
    coverage run -m pytest tests/
    coverage report --show-missing
    coverage xml
    
    current_coverage=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')
    
    if (( $(echo "$current_coverage >= $COVERAGE_MIN" | bc -l) )); then
        echo -e "${GREEN}✓ Coverage: ${current_coverage}% (min: ${COVERAGE_MIN}%)${NC}"
        return 0
    else
        echo -e "${RED}✗ Coverage: ${current_coverage}% (min: ${COVERAGE_MIN}%)${NC}"
        return 1
    fi
}

# Initialize counters
P0_PASSED=0
P1_PASSED=0
P2_PASSED=0
COVERAGE_PASSED=0

# Run P0 tests (Critical - must pass)
echo -e "${YELLOW}[1/4] P0 Critical Path Tests${NC}"
if run_priority_tests "p0" "Critical paths that must always work"; then
    P0_PASSED=1
fi
echo ""

# Run P1 tests (High - must pass for PR)
echo -e "${YELLOW}[2/4] P1 High Priority Tests${NC}"
if run_priority_tests "p1" "High priority features"; then
    P1_PASSED=1
fi
echo ""

# Run P2 tests (Medium - should pass)
echo -e "${YELLOW}[3/4] P2 Medium Priority Tests${NC}"
if run_priority_tests "p2" "Medium priority features"; then
    P2_PASSED=1
fi
echo ""

# Run coverage
echo -e "${YELLOW}[4/4] Coverage Analysis${NC}"
if run_coverage; then
    COVERAGE_PASSED=1
fi
echo ""

# Quality Gate Decision
echo "================================"
echo "Quality Gate Results"
echo "================================"
echo ""

if [ $P0_PASSED -eq 1 ] && [ $P1_PASSED -eq 1 ]; then
    echo -e "${GREEN}✓ QUALITY GATE PASSED${NC}"
    echo ""
    echo "All P0 and P1 tests passed."
    echo "Coverage: $(coverage report | grep TOTAL)"
    echo ""
    
    if [ $P2_PASSED -eq 1 ]; then
        echo -e "${GREEN}✓ Bonus: All P2 tests passed${NC}"
    else
        echo -e "${YELLOW}⚠ P2 tests failed (not required for PR)${NC}"
    fi
    
    if [ $COVERAGE_PASSED -eq 1 ]; then
        echo -e "${GREEN}✓ Coverage requirement met${NC}"
    else
        echo -e "${YELLOW}⚠ Coverage below minimum${NC}"
    fi
    
    exit 0
else
    echo -e "${RED}✗ QUALITY GATE FAILED${NC}"
    echo ""
    echo "Critical tests failed:"
    [ $P0_PASSED -eq 0 ] && echo -e "${RED}  ✗ P0 tests failed${NC}"
    [ $P1_PASSED -eq 0 ] && echo -e "${RED}  ✗ P1 tests failed${NC}"
    echo ""
    echo "Please fix failing tests before merging."
    exit 1
fi
