#!/bin/bash
# Test Validation Script
# Validates test files without requiring pytest to be installed

set -e

echo "================================"
echo "Test File Validation"
echo "================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

VALIDATION_PASSED=0
VALIDATION_FAILED=0

# Validate Python syntax
echo -e "${YELLOW}[1/5] Validating Python Syntax${NC}"
echo "----------------------------------------"

for test_file in tests/test_*.py; do
    if [ -f "$test_file" ]; then
        if python3 -m py_compile "$test_file" 2>/dev/null; then
            echo -e "${GREEN}✓ $test_file - Valid syntax${NC}"
            VALIDATION_PASSED=$((VALIDATION_PASSED + 1))
        else
            echo -e "${RED}✗ $test_file - Syntax error${NC}"
            VALIDATION_FAILED=$((VALIDATION_FAILED + 1))
        fi
    fi
done
echo ""

# Count test files
echo -e "${YELLOW}[2/5] Counting Test Files${NC}"
echo "----------------------------------------"
TEST_COUNT=$(ls -1 tests/test_*.py 2>/dev/null | wc -l)
echo "Total test files: $TEST_COUNT"
echo ""

# Check for priority markers
echo -e "${YELLOW}[3/5] Checking Priority Markers${NC}"
echo "----------------------------------------"
P0_COUNT=$(grep -r "@pytest.mark.p0" tests/test_*.py | wc -l)
P1_COUNT=$(grep -r "@pytest.mark.p1" tests/test_*.py | wc -l)
P2_COUNT=$(grep -r "@pytest.mark.p2" tests/test_*.py | wc -l)
P3_COUNT=$(grep -r "@pytest.mark.p3" tests/test_*.py | wc -l)

echo "P0 tests: $P0_COUNT"
echo "P1 tests: $P1_COUNT"
echo "P2 tests: $P2_COUNT"
echo "P3 tests: $P3_COUNT"
echo ""

# Check for Given-When-Then structure
echo -e "${YELLOW}[4/5] Checking Test Structure${NC}"
echo "----------------------------------------"
GWT_COUNT=$(grep -r "GIVEN\|WHEN\|THEN" tests/test_*.py | wc -l)
echo "Tests with Given-When-Then structure: $GWT_COUNT"
echo ""

# Validate test file naming
echo -e "${YELLOW}[5/5] Validating Test File Naming${NC}"
echo "----------------------------------------"
for test_file in tests/test_*.py; do
    if [ -f "$test_file" ]; then
        basename "$test_file"
    fi
done
echo ""

# Summary
echo "================================"
echo "Validation Summary"
echo "================================"
echo ""
echo -e "Valid files: ${GREEN}$VALIDATION_PASSED${NC}"
echo -e "Failed files: ${RED}$VALIDATION_FAILED${NC}"
echo ""

if [ $VALIDATION_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All test files validated successfully${NC}"
    echo ""
    echo "Test files are ready for execution."
    echo "Note: Run 'pytest' with proper environment to execute tests."
    exit 0
else
    echo -e "${RED}✗ Some test files failed validation${NC}"
    exit 1
fi
