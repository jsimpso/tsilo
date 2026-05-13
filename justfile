# Tsilo - Private Terraform Module Registry

set dotenv-load

default:
    @just --list

# Run the development server
serve *ARGS:
    uvicorn tsilo.main:app --reload --host 0.0.0.0 --port 8000 {{ ARGS }}

# Run all tests (unit + contract)
test *ARGS:
    python -m pytest tests/unit/ tests/contract/ {{ ARGS }}

# Run unit tests only
test-unit *ARGS:
    python -m pytest tests/unit/ {{ ARGS }}

# Run contract tests only
test-contract *ARGS:
    python -m pytest tests/contract/ {{ ARGS }}

# Run integration tests (requires running services)
test-integration *ARGS:
    python -m pytest tests/integration/ {{ ARGS }}

# Run tests with verbose output
test-verbose:
    python -m pytest tests/unit/ tests/contract/ -v --tb=short

# Run tests with coverage
test-coverage:
    python -m pytest tests/unit/ tests/contract/ --cov=tsilo --cov-report=term-missing

# Lint with ruff
lint:
    ruff check src/ tests/

# Format with black
fmt:
    black src/ tests/

# Check formatting without modifying
fmt-check:
    black --check src/ tests/

# Type check with mypy
typecheck:
    mypy src/tsilo/

# Run all checks (lint + format check + type check + tests)
check: lint fmt-check typecheck test

# Run database migrations
db-migrate *ARGS:
    alembic upgrade head {{ ARGS }}

# Create a new migration
db-revision MESSAGE:
    alembic revision --autogenerate -m "{{ MESSAGE }}"

# Seed development database
db-seed:
    python -m scripts.seed_data
