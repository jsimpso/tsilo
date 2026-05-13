# Quickstart Guide: Private Terraform Module Registry

**Date**: 2026-05-10
**Phase**: 1 - Design & Contracts
**Purpose**: Get developers started quickly with development, testing, and deployment

## Overview

This guide will help you:
1. Set up your development environment
2. Run the application locally
3. Run tests
4. Build and deploy the application

**Prerequisites**:
- Python 3.11 or newer
- PostgreSQL 14 or newer
- S3-compatible object storage (MinIO for local development)
- OIDC provider configured (or use mock for development)

**Estimated time**: 30 minutes

---

## Quick Start (Local Development)

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/org/tsilo.git
cd tsilo

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Copy environment template
cp .env.example .env

# Edit .env with your local configuration
nano .env
```

### 2. Start Development Services

```bash
# Start PostgreSQL and MinIO using Docker Compose
just dev-services

# Wait for services to be ready
just wait-for-services

# Run database migrations
just migrate
```

### 3. Run the Application

```bash
# Start development server with auto-reload
just dev

# Application is now running at:
# - API: http://localhost:8000
# - Web UI: http://localhost:8000/
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

### 4. Verify Installation

```bash
# In a new terminal, check health
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","checks":{"database":"ok","storage":"ok"},"version":"1.0.0"}
```

---

## Environment Configuration

### Required Environment Variables

Edit `.env` file:

```bash
# Application
APP_NAME=tsilo
APP_VERSION=1.0.0
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://tsilo:password@localhost:5432/tsilo

# Object Storage (S3)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=tsilo-modules
S3_REGION=us-east-1

# OIDC Authentication
OIDC_DISCOVERY_URL=https://your-oidc-provider.com/.well-known/openid-configuration
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=http://localhost:8000/auth/callback

# Development Mode (use mock auth)
DEV_MODE=true
DEV_MOCK_USER_EMAIL=dev@example.com
DEV_MOCK_USER_GROUPS=["platform-team-developers","platform-team-leads"]

# Security
SECRET_KEY=your-secret-key-generate-with-openssl-rand-hex-32
SESSION_COOKIE_SECURE=false  # Set to true in production
ALLOWED_ORIGINS=http://localhost:8000

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_HOUR_UNAUTHENTICATED=100
RATE_LIMIT_PER_HOUR_READ=1000
RATE_LIMIT_PER_HOUR_WRITE=100
```

### Development vs Production

**Development** (.env):
- `DEV_MODE=true` - Enables mock authentication
- `LOG_LEVEL=DEBUG` - Verbose logging
- `SESSION_COOKIE_SECURE=false` - HTTP cookies allowed
- Local PostgreSQL and MinIO

**Production** (via Juju charm config):
- `DEV_MODE=false` - Real OIDC authentication
- `LOG_LEVEL=INFO` - Standard logging
- `SESSION_COOKIE_SECURE=true` - HTTPS only cookies
- Managed PostgreSQL and S3

---

## Development Workflow

### Using `just` Commands

The `justfile` provides convenient commands:

```bash
# Development
just dev                 # Start development server with auto-reload
just dev-services        # Start PostgreSQL + MinIO in Docker
just stop-services       # Stop development services

# Testing
just test                # Run all tests
just test-unit           # Run unit tests only
just test-integration    # Run integration tests only
just test-contract       # Run contract tests (Terraform protocol)
just test-coverage       # Run tests with coverage report

# Code Quality
just lint                # Run ruff linter
just format              # Format code with black
just typecheck           # Run mypy type checker
just check               # Run all quality checks (lint + format + typecheck)

# Database
just migrate             # Run database migrations
just migrate-create      # Create new migration: just migrate-create "add_field"
just migrate-rollback    # Rollback last migration

# Building
just build               # Build OCI image with Rockcraft
just build-charm         # Build Juju charm with Charmcraft

# Cleanup
just clean               # Remove build artifacts
just clean-all           # Remove build artifacts and .venv
```

### Running Tests

```bash
# Run all tests
just test

# Run specific test file
pytest tests/unit/test_models.py

# Run tests matching pattern
pytest -k "test_module_version"

# Run with coverage
just test-coverage

# Run contract tests against local server
just dev &  # Start server in background
just test-contract
```

### Database Migrations

```bash
# Create a new migration
just migrate-create "add_module_tags"

# Review the generated migration
nano alembic/versions/YYYYMMDD_HHMM_add_module_tags.py

# Apply migration
just migrate

# Rollback if needed
just migrate-rollback
```

---

## Testing the Application

### 1. Create a Namespace

```bash
# Using httpie (install: pip install httpie)
http POST http://localhost:8000/api/namespaces \
  name=platform-team \
  display_name="Platform Team" \
  description="Core infrastructure modules" \
  Cookie:session=dev-session

# Response: {"namespace": {"id": "...", "name": "platform-team", ...}}
```

### 2. Upload a Module

```bash
# Create a simple test module
mkdir -p /tmp/test-module
cat > /tmp/test-module/main.tf <<EOF
variable "name" {
  type        = string
  description = "Name of the resource"
}

output "result" {
  value       = "Hello, \${var.name}!"
  description = "Greeting message"
}
EOF

cat > /tmp/test-module/README.md <<EOF
# Test Module

Simple test module for demonstration.
EOF

# Package the module
cd /tmp
tar -czf test-module.tar.gz test-module/

# Upload via API
http POST http://localhost:8000/v1/modules/platform-team/test/local/1.0.0 \
  file@test-module.tar.gz \
  Cookie:session=dev-session
```

### 3. Download with Terraform

```bash
# Create a Terraform configuration
mkdir -p /tmp/terraform-test
cat > /tmp/terraform-test/main.tf <<EOF
module "test" {
  source  = "localhost:8000/platform-team/test/local"
  version = "1.0.0"

  name = "World"
}

output "message" {
  value = module.test.result
}
EOF

# Configure Terraform to use local registry
cat > /tmp/terraform-test/.terraformrc <<EOF
credentials "localhost:8000" {
  token = "dev-token"
}
EOF

# Initialize and apply
cd /tmp/terraform-test
terraform init
terraform apply -auto-approve

# Expected output: message = "Hello, World!"
```

### 4. Browse Web UI

Open browser to `http://localhost:8000`:

1. **Homepage**: See module list (platform-team/test/local appears)
2. **Search**: Type "test" in search box
3. **Module Details**: Click module to see README, inputs, outputs
4. **Metrics**: View download count (should be 1 after Terraform download)

---

## Building and Deployment

### Build OCI Image (Rock)

```bash
# Build with Rockcraft
just build

# Expected output:
# Created rock tsilo_1.0.0_amd64.rock

# Import into Docker for testing
sudo rockcraft.skopeo --insecure-policy copy oci-archive:tsilo_1.0.0_amd64.rock docker-daemon:tsilo:1.0.0

# Run locally
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e S3_ENDPOINT_URL=https://... \
  tsilo:1.0.0
```

### Build Juju Charm

```bash
# Build charm
just build-charm

# Expected output:
# Created charm tsilo_ubuntu-22.04-amd64.charm

# Deploy to Juju model
juju deploy ./tsilo_ubuntu-22.04-amd64.charm \
  --resource tsilo-image=tsilo:1.0.0

# Relate to PostgreSQL
juju deploy postgresql-k8s
juju relate tsilo postgresql-k8s

# Configure
juju config tsilo \
  oidc-discovery-url=https://... \
  oidc-client-id=... \
  oidc-client-secret=...

# Check status
juju status --relations
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
psql postgresql://tsilo:password@localhost:5432/tsilo -c "SELECT 1;"

# View logs
docker logs tsilo-postgres
```

### S3/MinIO Connection Issues

```bash
# Check MinIO is running
docker ps | grep minio

# Test connection
curl http://localhost:9000/minio/health/live

# Create bucket manually
docker exec tsilo-minio mc mb local/tsilo-modules
```

### OIDC Authentication Issues

```bash
# Use development mode to bypass OIDC
export DEV_MODE=true
export DEV_MOCK_USER_EMAIL=test@example.com
export DEV_MOCK_USER_GROUPS='["platform-team-developers"]'

# Restart application
just dev
```

### Application Logs

```bash
# View structured logs
tail -f logs/tsilo.log | jq .

# Filter by level
tail -f logs/tsilo.log | jq 'select(.level == "ERROR")'

# Filter by module
tail -f logs/tsilo.log | jq 'select(.module == "tsilo.api.registry")'
```

---

## Development Tips

### Hot Reload

FastAPI auto-reloads on code changes when running `just dev`. No restart needed for:
- Python code changes
- Template changes
- Static file changes (CSS, JS)

Restart required for:
- Environment variable changes
- Database schema changes (run migrations)
- Dependency changes (run `uv pip install -e ".[dev]"`)

### Debugging

```bash
# Run with debugger
python -m debugpy --listen 5678 --wait-for-client -m uvicorn tsilo.main:app --reload

# Or use VS Code launch configuration (see .vscode/launch.json)
```

### Database Inspection

```bash
# Connect to database
psql postgresql://tsilo:password@localhost:5432/tsilo

# List tables
\dt

# Describe table
\d modules

# Query data
SELECT namespace_id, name, provider FROM modules;
```

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Generate Sample Data

```bash
# Run seed script
python scripts/seed_data.py

# Creates:
# - 3 namespaces
# - 10 modules
# - 30 module versions
# - Sample permissions
```

---

## Next Steps

Once you have the application running:

1. **Read the Specs**:
   - [spec.md](spec.md) - Feature requirements
   - [data-model.md](data-model.md) - Database schema
   - [contracts/](contracts/) - API contracts

2. **Review Constitution**:
   - [.specify/memory/constitution.md](../../.specify/memory/constitution.md) - Project principles

3. **Start Development**:
   - Pick a user story from spec.md
   - Write tests first (TDD requirement)
   - Implement functionality
   - Run quality checks: `just check`
   - Submit PR with tests and documentation

4. **Deploy to Staging**:
   - Build rock and charm
   - Deploy to Juju staging environment
   - Run integration tests against staging
   - Verify OIDC authentication works

---

## Common Tasks

### Add a New API Endpoint

```bash
# 1. Define contract in contracts/
nano contracts/web-ui-api.md

# 2. Write contract test
nano tests/contract/test_new_endpoint.py

# 3. Run test (should fail - TDD)
pytest tests/contract/test_new_endpoint.py

# 4. Create Pydantic schema
nano src/tsilo/schemas/new_schema.py

# 5. Implement endpoint
nano src/tsilo/api/new_endpoint.py

# 6. Add to router
nano src/tsilo/main.py

# 7. Run tests (should pass)
just test-contract

# 8. Check code quality
just check
```

### Add a New Database Table

```bash
# 1. Update data model documentation
nano data-model.md

# 2. Create migration
just migrate-create "add_new_table"

# 3. Edit migration
nano alembic/versions/YYYYMMDD_HHMM_add_new_table.py

# 4. Create SQLAlchemy model
nano src/tsilo/models/new_model.py

# 5. Apply migration
just migrate

# 6. Write model tests
nano tests/unit/test_new_model.py

# 7. Run tests
just test-unit
```

### Update Frontend

```bash
# 1. Edit HTML
nano src/tsilo/static/index.html

# 2. Update CSS
nano src/tsilo/static/css/styles.css

# 3. Update JavaScript
nano src/tsilo/static/js/main.js

# 4. Test in browser (auto-reloads)
open http://localhost:8000

# 5. Test responsiveness (mobile view)
# DevTools > Toggle device toolbar

# 6. Test accessibility
# Run WAVE browser extension
# Check keyboard navigation
```

---

## Resources

- **Terraform Registry Protocol**: [docs/registry_api.md](../../docs/registry_api.md)
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Rockcraft Guide**: https://documentation.ubuntu.com/rockcraft
- **Charmcraft Guide**: https://documentation.ubuntu.com/charmcraft
- **SQLAlchemy ORM**: https://docs.sqlalchemy.org/en/20/orm/
- **pytest Documentation**: https://docs.pytest.org/

---

## Getting Help

- **Issues**: https://github.com/org/tsilo/issues
- **Discussions**: https://github.com/org/tsilo/discussions
- **Team Chat**: #tsilo-dev on Slack

---

## Production Deployment Checklist

Before deploying to production:

- [ ] All tests passing (`just test`)
- [ ] Code quality checks pass (`just check`)
- [ ] Test coverage ≥ 80% (`just test-coverage`)
- [ ] Database migrations tested on staging
- [ ] OIDC provider configured and tested
- [ ] S3 bucket created with proper permissions
- [ ] PostgreSQL database provisioned
- [ ] Environment variables configured in charm
- [ ] SSL/TLS certificates configured
- [ ] Rate limiting configured appropriately
- [ ] Monitoring and alerting set up
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan documented
- [ ] Security review completed
- [ ] Performance testing completed
- [ ] Documentation updated
