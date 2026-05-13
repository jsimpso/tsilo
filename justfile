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

# Format with ruff
fmt:
    uv run ruff format src/ tests/

# Check formatting without modifying
fmt-check:
    uv run ruff format --check src/ tests/

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

# Start development services (Postgres, MinIO, Keycloak)
dev-up:
    podman compose up -d
    @echo "Waiting for services to be healthy..."
    @sleep 2
    @podman compose ps --format 'table {{`{{.Name}}`}}\t{{`{{.Status}}`}}'
    @echo ""
    @echo "Services:"
    @echo "  Postgres:         localhost:5432  (tsilo/tsilo)"
    @echo "  MinIO Console:    http://localhost:9001  (minioadmin/minioadmin)"
    @echo "  Keycloak Admin:   http://localhost:8080/admin  (admin/admin)"
    @echo "  Keycloak Realm:   http://localhost:8080/realms/tsilo"
    @echo ""
    @echo "Test users (password = username):"
    @echo "  admin@tsilo.local  (groups: tsilo-admins, tsilo-users)"
    @echo "  dev@tsilo.local    (groups: tsilo-users)"

# Stop development services
dev-down:
    podman compose down

# Stop development services and remove volumes
dev-reset:
    podman compose down -v

# Show development service logs
dev-logs *ARGS:
    podman compose logs {{ ARGS }}

# Show development service status
dev-ps:
    podman compose ps