# Test Framework Architecture

**Cognitive Memory System - Backend Test Suite**

---

## Overview

This document describes the test framework architecture for the cognitive-memory backend system. The framework is built on **pytest** and provides comprehensive utilities for testing MCP tools, database operations, and AI integrations.

---

## Architecture

### Directory Structure

```
tests/
├── conftest.py                 # Pytest configuration and base fixtures
├── support/                   # Test infrastructure
│   ├── helpers/               # Utility functions
│   │   ├── __init__.py
│   │   ├── assertions.py      # Custom assertions
│   │   ├── database.py        # Database helpers
│   │   ├── mocks.py           # Mock utilities
│   │   └── generators.py      # Test data generators
│   └── factories/             # Test data factories
│       ├── __init__.py
│       ├── node_factory.py    # Graph node factory
│       ├── edge_factory.py    # Graph edge factory
│       ├── insight_factory.py # L2 insight factory
│       └── episode_factory.py # Episode factory
├── unit/                      # Unit tests
├── integration/               # Integration tests
├── fixtures/                  # Test fixtures
└── e2e/                       # End-to-end tests (if applicable)
```

### Core Components

#### 1. **Support/Helpers** - Utility Functions

**Assertions (`support/helpers/assertions.py`)**
- `assert_database_state()` - Validate database table state
- `assert_json_response()` - Validate JSON response structure
- `assert_node_data()` - Validate node data structure
- `assert_edge_data()` - Validate edge data structure

**Database Helpers (`support/helpers/database.py`)**
- `create_test_node()` - Create test graph node
- `create_test_edge()` - Create test graph edge
- `create_test_insight()` - Create test L2 insight
- `create_test_episode()` - Create test episode
- `get_table_counts()` - Get counts for all tables
- `cleanup_test_data()` - Clean up test data

**Mock Utilities (`support/helpers/mocks.py`)**
- `mock_postgres_connection()` - Mock database connection
- `mock_openai_embedding()` - Mock OpenAI embedding response
- `mock_anthropic_response()` - Mock Anthropic AI response
- `mock_graph_node()` - Mock graph node data
- `mock_graph_edge()` - Mock graph edge data
- `mock_l2_insight()` - Mock L2 insight data
- `mock_episode()` - Mock episode data

**Generators (`support/helpers/generators.py`)**
- `generate_test_node()` - Generate test node data
- `generate_test_edge()` - Generate test edge data
- `generate_test_insight()` - Generate test insight data
- `generate_test_episode()` - Generate test episode data
- `generate_test_dataset()` - Generate complete test dataset

#### 2. **Support/Factories** - Data Factories

**NodeFactory (`support/factories/node_factory.py`)**
```python
from tests.support.factories import NodeFactory

# Create a single node
factory = NodeFactory()
node = factory.create(conn, label="Agent", name="TestAgent")

# Create multiple nodes
nodes = factory.create_batch(conn, count=5, label="Technology")

# Context manager with auto-cleanup
with NodeFactory() as factory:
    node = factory.create(conn, label="Project")
    # Cleanup happens automatically
```

**EdgeFactory (`support/factories/edge_factory.py`)**
```python
from tests.support.factories import EdgeFactory

# Create an edge
factory = EdgeFactory()
edge = factory.create(conn, source_name="NodeA", target_name="NodeB", relation="USES")

# Context manager with auto-cleanup
with EdgeFactory() as factory:
    edge = factory.create(conn, source_name="I/O", target_name="Python", relation="USES")
```

**InsightFactory (`support/factories/insight_factory.py`)**
```python
from tests.support.factories import InsightFactory

# Create an insight with specific memory strength
factory = InsightFactory()
insight = factory.create(conn, content="Test insight", memory_strength=0.8)
```

**EpisodeFactory (`support/factories/episode_factory.py`)**
```python
from tests.support.factories import EpisodeFactory

# Create an episode with specific reward
factory = EpisodeFactory()
episode = factory.create(conn, query="What is AI?", reward=0.5)
```

---

## Setup Instructions

### 1. Environment Configuration

Create `.env.development` in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/cognitive_memory_test

# OpenAI Configuration (for embedding tests)
OPENAI_API_KEY=your-openai-api-key

# Anthropic Configuration (for evaluation tests)
ANTHROPIC_API_KEY=your-anthropic-api-key

# Test Configuration
TEST_ENV=development
PYTEST_CURRENT_TEST=1
```

### 2. Install Dependencies

```bash
# Install test dependencies
pip install -e .[test]

# Or manually
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

### 3. Database Setup

```bash
# Create test database
createdb cognitive_memory_test

# Run migrations
python scripts/migrate.py --env test
```

---

## Running Tests

### Local Execution

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_get_node_by_name.py

# Run with coverage
pytest --cov=mcp_server --cov-report=html

# Run in parallel
pytest -n auto

# Run with verbose output
pytest -v

# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m "not integration"
```

### Test Markers

The framework uses pytest markers for test categorization:

```python
import pytest

@pytest.mark.integration
async def test_with_database(conn):
    """Test requiring real database connection."""
    pass

@pytest.mark.asyncio
async def test_async_operation():
    """Test using async/await."""
    pass

@pytest.mark.unit
async def test_pure_function():
    """Unit test with mocks."""
    pass
```

**Available Markers:**
- `@pytest.mark.integration` - Integration tests requiring database
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.slow` - Slow tests (exclude from quick runs)

### Debugging Tests

```bash
# Run with PDB on failure
pytest --pdb

# Drop into debugger on first failure
pytest --pdbcls=IPython.terminal.debugger:Pdb

# Capture output for debugging
pytest -s --capture=no
```

---

## Best Practices

### 1. Test Structure

Follow the **Given-When-Then** pattern:

```python
@pytest.mark.asyncio
async def test_get_node_by_name_success(conn):
    """Test retrieving an existing node by name returns full node data."""
    # GIVEN: A node exists in the database
    node_id = create_test_node(conn, label="Agent", name="TestAgent")

    # WHEN: I call get_node_by_name with the node name
    result = await handle_get_node_by_name({"name": "TestAgent"})

    # THEN: I receive the node data
    assert result["status"] == "success"
    assert result["node_id"] == node_id
    assert result["name"] == "TestAgent"
```

### 2. Test Isolation

Each test should be isolated and not depend on other tests:

```python
# ✅ GOOD - Self-contained
async def test_create_node(conn):
    node = create_test_node(conn, name="UniqueTestNode")
    assert node is not None

# ❌ BAD - Depends on previous test
async def test_update_node(conn):
    # Assumes test_create_node ran first
    node_id = get_last_created_node_id()
```

### 3. Auto-Cleanup

Use factories with context managers for automatic cleanup:

```python
# ✅ GOOD - Auto cleanup
async def test_with_factory(conn):
    with NodeFactory() as factory:
        node = factory.create(conn, label="Test")
        # Node automatically cleaned up

# ⚠️ MANUAL - Remember to cleanup
async def test_with_manual_cleanup(conn):
    factory = NodeFactory()
    node = factory.create(conn, label="Test")
    # Must remember to call factory.cleanup(conn)
```

### 4. Database Tests

Use the `conn` fixture for database tests:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_operation(conn):
    """This test uses a real database connection."""
    # Test automatically rolls back after completion
    result = await some_database_operation(conn)
    assert result is not None
```

### 5. Mock External Services

Mock OpenAI and Anthropic for tests that don't need real API calls:

```python
@pytest.mark.asyncio
async def test_with_mocked_openai(mock_openai_client):
    """This test uses mocked OpenAI client."""
    # Use the mock fixture for consistent behavior
    pass
```

---

## Pattern Examples

### Testing MCP Tools

```python
from tests.support.helpers import assert_json_response

@pytest.mark.asyncio
async def test_mcp_tool_handler(conn):
    """Example: Testing an MCP tool handler."""
    # Setup
    tool_args = {"name": "TestNode"}

    # Execute
    result = await handle_get_node_by_name(tool_args)

    # Assert
    assert_json_response(result, ["status", "node_id"])
    assert result["status"] == "success"
```

### Testing Database Operations

```python
from tests.support.helpers.database import create_test_node, assert_database_state

@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_insert(conn):
    """Example: Testing database operations."""
    # Insert test data
    node_id = create_test_node(conn, label="Test", name="TestNode")

    # Verify
    nodes = assert_database_state(conn, "graph_nodes", expected_count=1)
    assert nodes[0]["name"] == "TestNode"
```

### Testing with Factories

```python
from tests.support.factories import NodeFactory, EdgeFactory

@pytest.mark.integration
@pytest.mark.asyncio
async def test_node_edge_relationship(conn):
    """Example: Testing related data creation."""
    with NodeFactory() as node_factory, EdgeFactory() as edge_factory:
        # Create nodes and edge
        source = node_factory.create(conn, label="Source")
        target = node_factory.create(conn, label="Target")
        edge = edge_factory.create(conn, source_name="Source", target_name="Target")

        # Verify relationships
        assert edge is not None
        # Auto-cleanup happens
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_graceful_error_handling():
    """Example: Testing error scenarios."""
    # Test non-existent data returns graceful null
    result = await handle_get_node_by_name({"name": "NonExistent"})

    assert result["status"] == "not_found"
    assert result["node"] is None
    assert "error" not in result  # No exception raised
```

---

## Configuration

### Pytest Configuration

Located in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "asyncio: marks tests as async",
    "integration: marks tests as integration tests requiring real database",
]
asyncio_mode = "auto"
```

### Coverage Configuration

```bash
# Generate HTML coverage report
pytest --cov=mcp_server --cov-report=html --cov-report=term

# Coverage thresholds
pytest --cov=mcp_server --cov-fail-under=80
```

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Verify database is running
pg_isready -h localhost -p 5432
```

**2. Async Test Failures**
```python
# Ensure test is marked as async
@pytest.mark.asyncio
async def test_async_operation():
    pass
```

**3. Import Errors**
```python
# Use absolute imports
from tests.support.helpers import create_test_node
from tests.support.factories import NodeFactory
```

**4. Test Data Leaking Between Tests**
```python
# Use factory context managers
with NodeFactory() as factory:
    node = factory.create(conn)
    # Auto-cleanup guaranteed
```

### Performance Tips

1. **Run Tests in Parallel**: Use `pytest -n auto`
2. **Mark Slow Tests**: Use `@pytest.mark.slow` for tests >5s
3. **Use Mocks**: Mock external services (OpenAI, Anthropic)
4. **Database Indexing**: Ensure proper indexes on test tables

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -e .[test]
      - name: Run tests
        run: |
          pytest --cov=mcp_server --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## Knowledge Base References

This framework follows best practices from:

- **Fixture Architecture** (`_bmad/bmm/testarch/knowledge/fixture-architecture.md`)
- **Data Factories** (`_bmad/bmm/testarch/knowledge/data-factories.md`)
- **Network-First Testing** (`_bmad/bmm/testarch/knowledge/network-first.md`)
- **Test Quality** (`_bmad/bmm/testarch/knowledge/test-quality.md`)
- **Component TDD** (`_bmad/bmm/testarch/knowledge/component-tdd.md`)

---

## Contributing

When adding new tests:

1. **Follow naming conventions**: `test_feature_name.py`
2. **Use appropriate markers**: `@pytest.mark.integration` for DB tests
3. **Add assertions**: Use custom assertions from `support/helpers/`
4. **Clean up**: Use factory context managers
5. **Document**: Add docstrings explaining test scenarios

---

**Generated:** 2026-01-11
**Framework Version:** 4.0 (BMad v6)
**Test Architecture:** Python/pytest backend-focused

---
