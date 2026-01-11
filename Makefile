# Makefile for Cognitive Memory Test Framework

.PHONY: help install test test-unit test-integration test-e2e test-parallel test-coverage test-watch clean lint format

# Default target
help:
	@echo "Cognitive Memory Test Framework - Available Commands:"
	@echo ""
	@echo "Setup Commands:"
	@echo "  install       Install test dependencies"
	@echo "  install-dev   Install development dependencies"
	@echo ""
	@echo "Test Commands:"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  test-e2e      Run end-to-end tests only"
	@echo "  test-parallel Run tests in parallel"
	@echo "  test-coverage Run tests with coverage report"
	@echo "  test-watch    Run tests in watch mode"
	@echo ""
	@echo "Quality Commands:"
	@echo "  lint          Run linting (ruff, mypy)"
	@echo "  format        Format code (black, isort)"
	@echo "  typecheck     Run type checking"
	@echo ""
	@echo "Utility Commands:"
	@echo "  clean         Clean test artifacts"
	@echo "  setup-env     Create .env from .env.example"

# Setup
install:
	@echo "Installing test dependencies..."
	pip install pytest pytest-asyncio pytest-cov pytest-mock pytest-xdist

install-dev:
	@echo "Installing development dependencies..."
	pip install -e .[test]
	pre-commit install

setup-env:
	@echo "Setting up environment..."
	@if [ ! -f .env.development ]; then \
		cp .env.example .env.development; \
		echo "Created .env.development from .env.example"; \
		echo "Please update with your actual values"; \
	else \
		echo ".env.development already exists"; \
	fi

# Test Commands
test:
	@echo "Running all tests..."
	pytest

test-unit:
	@echo "Running unit tests..."
	pytest -m "not integration"

test-integration:
	@echo "Running integration tests..."
	pytest -m integration

test-e2e:
	@echo "Running end-to-end tests..."
	pytest tests/e2e/

test-parallel:
	@echo "Running tests in parallel..."
	pytest -n auto

test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=mcp_server --cov-report=html --cov-report=term --cov-report=xml

test-watch:
	@echo "Running tests in watch mode..."
	ptw --runner "pytest -x"

test-debug:
	@echo "Running tests with debug output..."
	pytest -v -s --capture=no

test-specific:
	@echo "Running specific test file..."
	@read -p "Enter test file path: " file; \
	pytest $$file -v

# Quality Commands
lint:
	@echo "Running linting..."
	ruff check .
	mypy mcp_server/

format:
	@echo "Formatting code..."
	black .
	ruff check --fix .
	isort .

typecheck:
	@echo "Running type checking..."
	mypy mcp_server/

# Utility
clean:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf test-results/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test-clean:
	@echo "Cleaning test database..."
	@read -p "Enter database URL: " db_url; \
	DATABASE_URL=$$db_url python -c "import psycopg2; conn = psycopg2.connect($$db_url); cur = conn.cursor(); cur.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;'); conn.commit(); conn.close();"

# CI/CD Commands (for GitHub Actions)
ci-test:
	@echo "Running CI test suite..."
	pytest --cov=mcp_server --cov-report=xml --cov-fail-under=80 -m "not slow"

ci-lint:
	@echo "Running CI linting..."
	ruff check .
	mypy mcp_server/

# Database Commands
db-reset:
	@echo "Resetting test database..."
	@read -p "Enter database URL: " db_url; \
	DATABASE_URL=$$db_url python scripts/migrate.py --env test

db-migrate:
	@echo "Running migrations on test database..."
	@read -p "Enter database URL: " db_url; \
	DATABASE_URL=$$db_url python scripts/migrate.py --env test

# Docker Commands
docker-test:
	@echo "Running tests in Docker..."
	docker-compose -f docker-compose.test.yml up --build

# Help for specific test types
test-help:
	@echo "Test Marker Guide:"
	@echo "  -m integration    : Integration tests requiring database"
	@echo "  -m 'not integration' : Unit tests only"
	@echo "  -m asyncio        : Async tests"
	@echo "  -m slow           : Slow tests (>5s)"
	@echo ""
	@echo "Example commands:"
	@echo "  pytest -m integration          : Run integration tests"
	@echo "  pytest -m 'not integration'   : Run unit tests only"
	@echo "  pytest -m 'not slow'          : Exclude slow tests"
	@echo "  pytest tests/test_file.py     : Run specific file"
