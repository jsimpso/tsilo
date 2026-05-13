# Tsilo - Private Terraform Module Registry

set dotenv-load

default:
    @just --list

# Create venv and install all dependencies (including dev tools)
setup:
    uv venv
    uv sync --all-extras

# Run the development server
serve *ARGS:
    uv run uvicorn tsilo.main:app --reload --host 0.0.0.0 --port 8000 {{ ARGS }}

# Run all tests (unit + contract)
test *ARGS:
    uv run pytest tests/unit/ tests/contract/ {{ ARGS }}

# Run unit tests only
test-unit *ARGS:
    uv run pytest tests/unit/ {{ ARGS }}

# Run contract tests only
test-contract *ARGS:
    uv run pytest tests/contract/ {{ ARGS }}

# Run integration tests (requires running services)
test-integration *ARGS:
    uv run pytest tests/integration/ {{ ARGS }}

# Run tests with verbose output
test-verbose:
    uv run pytest tests/unit/ tests/contract/ -v --tb=short

# Run tests with coverage
test-coverage:
    uv run pytest tests/unit/ tests/contract/ --cov=tsilo --cov-report=term-missing

# Lint with ruff
lint:
    uv run ruff check src/ tests/

# Format with black
fmt:
    uv run black src/ tests/

# Check formatting without modifying
fmt-check:
    uv run black --check src/ tests/

# Type check with mypy
typecheck:
    uv run mypy src/tsilo/

# Run all checks (lint + format check + type check + tests)
check: lint fmt-check typecheck test

# Run database migrations
db-migrate *ARGS:
    uv run alembic upgrade head {{ ARGS }}

# Create a new migration
db-revision MESSAGE:
    uv run alembic revision --autogenerate -m "{{ MESSAGE }}"

# Seed development database
db-seed:
    uv run python -m scripts.seed_data
