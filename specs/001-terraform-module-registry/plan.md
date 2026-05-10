# Implementation Plan: Private Terraform Module Registry

**Branch**: `master` | **Date**: 2026-05-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-terraform-module-registry/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build a private Terraform module registry that implements the Terraform Module Registry Protocol, enabling teams to host and version internal modules. The application provides both a REST API for Terraform CLI compatibility and a modern web UI for module discovery and documentation browsing. Multi-tenancy is achieved through namespaces with OIDC-based authentication and group-based authorization. The system tracks usage metrics and supports CI/CD pipeline authentication.

**Technical Approach**: FastAPI-based web service packaged as Ubuntu Rock (OCI image) with Juju charm deployment. Stateless application design with PostgreSQL backing store, vanilla HTML/CSS/JS frontend served by FastAPI, OIDC integration for authentication, and object storage for module packages.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI (web framework), uvicorn (ASGI server), SQLAlchemy (ORM), Pydantic (validation), minimal additional libraries
**Storage**: PostgreSQL (metadata, permissions, metrics), S3-compatible object storage (module packages)
**Testing**: pytest (unit/integration), httpx (API testing), coverage.py (coverage metrics)
**Target Platform**: Linux server (Ubuntu 22.04+ via Rock/Charm deployment)
**Project Type**: Web service with REST API + HTML frontend
**Performance Goals**: 1000+ req/s for module downloads, <200ms p95 API latency, 100+ concurrent downloads
**Constraints**: <200ms p95 API response time, <50ms database query performance, stateless processes for horizontal scaling
**Scale/Scope**: Support 100+ teams/namespaces, 1000+ modules, 10000+ module versions, 100+ concurrent users
**Build/Package**: Rockcraft (OCI image), Charmcraft (Juju charm), uv (dependency management), just (task runner)
**Frontend**: Vanilla HTML, CSS, JavaScript (no frameworks - served by FastAPI static files)
**Authentication**: OIDC (OpenID Connect) for web UI, API tokens for CI/CD
**Deployment**: 12-factor application via Juju charm on Ubuntu

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

**Required Gates**:

- [ ] **Codebase & Dependencies**: All dependencies explicitly declared in requirements files
- [ ] **Configuration**: Environment variables used for all config (no hardcoded values)
- [ ] **Code Quality**: Linting (ruff/black/prettier) and type checking (mypy) configured
- [ ] **Test-First**: TDD workflow documented; tests written before implementation
- [ ] **Stateless Design**: Application processes share no state; backing services identified
- [ ] **Build/Release/Run**: Separate stages defined; semantic versioning planned
- [ ] **Observability**: Structured logging planned; /health and /metrics endpoints specified
- [ ] **Disposability**: Graceful shutdown handling (SIGTERM) and circuit breakers planned
- [ ] **Port Binding**: Self-contained web server (no external server dependency)
- [ ] **Concurrency**: Horizontal scaling approach documented; process model defined
- [ ] **Admin Processes**: One-off admin tasks identified and environment parity ensured
- [ ] **UX Consistency**: UI patterns, responsive design, WCAG 2.1 AA compliance, error handling documented
- [ ] **Security**: OIDC authentication, input validation, rate limiting, HTTPS/TLS planned
- [ ] **Performance**: API latency (<200ms p95), DB query performance (<50ms), caching strategy defined
- [ ] **Workflow**: CI/CD pipeline, code review process, branch protection, test coverage (≥80%) planned

**Complexity Tracking**: Document any principle violations in the Complexity Tracking table below

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
tsilo/
├── src/
│   ├── tsilo/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── config.py            # Environment-based configuration
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── module.py
│   │   │   ├── version.py
│   │   │   ├── namespace.py
│   │   │   ├── permission.py
│   │   │   ├── user.py
│   │   │   └── metric.py
│   │   ├── api/                 # FastAPI routers/endpoints
│   │   │   ├── __init__.py
│   │   │   ├── registry.py      # Terraform registry protocol endpoints
│   │   │   ├── modules.py       # Module CRUD endpoints
│   │   │   ├── namespaces.py    # Namespace management
│   │   │   ├── auth.py          # Authentication endpoints
│   │   │   └── metrics.py       # Observability endpoints
│   │   ├── services/            # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── module_service.py
│   │   │   ├── version_service.py
│   │   │   ├── storage_service.py    # S3/object storage interface
│   │   │   ├── auth_service.py       # OIDC integration
│   │   │   ├── permission_service.py
│   │   │   └── metrics_service.py
│   │   ├── schemas/             # Pydantic models for validation
│   │   │   ├── __init__.py
│   │   │   ├── module.py
│   │   │   ├── version.py
│   │   │   └── terraform.py     # Terraform protocol schemas
│   │   ├── middleware/          # FastAPI middleware
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── rate_limit.py
│   │   │   └── logging.py
│   │   ├── static/              # Vanilla HTML/CSS/JS frontend
│   │   │   ├── index.html
│   │   │   ├── css/
│   │   │   │   └── styles.css
│   │   │   └── js/
│   │   │       ├── main.js
│   │   │       ├── search.js
│   │   │       └── module-detail.js
│   │   └── templates/           # Jinja2 templates (minimal - mostly static files)
│   │       └── base.html
│   └── alembic/                 # Database migrations
│       ├── versions/
│       └── env.py
├── tests/
│   ├── contract/                # Terraform protocol contract tests
│   │   ├── test_service_discovery.py
│   │   ├── test_version_listing.py
│   │   └── test_module_download.py
│   ├── integration/             # Multi-component integration tests
│   │   ├── test_upload_download.py
│   │   ├── test_auth_flow.py
│   │   └── test_namespace_isolation.py
│   └── unit/                    # Unit tests
│       ├── test_models.py
│       ├── test_services.py
│       └── test_schemas.py
├── rockcraft.yaml               # OCI image definition
├── charmcraft.yaml              # Juju charm definition
├── charm/                       # Charm implementation
│   ├── src/
│   │   └── charm.py
│   └── config.yaml
├── pyproject.toml               # uv project configuration
├── justfile                     # Task runner definitions
├── .env.example                 # Environment variable template
└── README.md
```

**Structure Decision**: Single Python project with FastAPI serving both API and static frontend files. All source code in `src/tsilo/` following Python package conventions. Frontend uses vanilla HTML/CSS/JS served as static files from FastAPI. Packaging/deployment artifacts (rockcraft.yaml, charmcraft.yaml, charm/) at repository root. Tests organized by type (contract, integration, unit) mirroring the spec's testing requirements.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations. All design decisions align with 12-factor principles:

- ✅ Single codebase with explicit dependencies (uv + pyproject.toml)
- ✅ Configuration via environment variables
- ✅ Stateless processes (FastAPI + PostgreSQL backing services)
- ✅ Port binding (self-contained uvicorn server)
- ✅ Horizontal scaling (stateless design)
- ✅ Build/release/run separation (Rockcraft + Charmcraft)
- ✅ Structured logging and /health, /metrics endpoints
- ✅ Graceful shutdown (SIGTERM handling in charm)
- ✅ Admin processes (alembic migrations, data seeding)
- ✅ Modern UX with vanilla HTML/CSS/JS (minimal dependencies)
- ✅ OIDC authentication, input validation, rate limiting
- ✅ Test-first development (pytest with contract/integration/unit layers)

---

## Phase 0: Research - COMPLETE ✅

**Artifacts**:
- [research.md](research.md) - Technology decisions and best practices

**Key Decisions**:
- FastAPI web framework with minimal dependencies
- PostgreSQL for metadata, S3 for packages
- Vanilla HTML/CSS/JS for frontend
- uv for dependency management, just for task running
- Rockcraft for OCI images, Charmcraft for deployment
- pytest with httpx for contract testing
- SQLAlchemy + Alembic for database
- authlib for OIDC, structlog for logging

---

## Phase 1: Design - COMPLETE ✅

**Artifacts**:
- [data-model.md](data-model.md) - Complete database schema with 7 entities
- [contracts/terraform-registry-api.md](contracts/terraform-registry-api.md) - Terraform protocol endpoints
- [contracts/web-ui-api.md](contracts/web-ui-api.md) - Web UI API endpoints
- [quickstart.md](quickstart.md) - Developer onboarding guide

**Key Deliverables**:
- 7 database tables: Namespace, Module, ModuleVersion, NamespacePermission, User, APIToken, DownloadMetric
- Terraform protocol compliance: service discovery, version listing, module download, module upload
- Web UI APIs: authentication, module browsing, namespace management, metrics, token management
- Complete development workflow with just commands
- Database migration strategy with Alembic
- Performance considerations and caching strategy

---

## Constitution Check - Final Validation ✅

### Required Gates - All Passing

- [x] **Codebase & Dependencies**: All dependencies declared in pyproject.toml (uv managed)
- [x] **Configuration**: All config via environment variables (.env template provided)
- [x] **Code Quality**: ruff (linting), black (formatting), mypy (type checking) configured
- [x] **Test-First**: TDD workflow documented; contract/integration/unit test structure defined
- [x] **Stateless Design**: FastAPI stateless; PostgreSQL + S3 as backing services
- [x] **Build/Release/Run**: Rockcraft (build), Charmcraft (release), uvicorn (run) - separate stages
- [x] **Observability**: structlog for JSON logs, /health and /metrics endpoints specified
- [x] **Disposability**: Pebble service manager for SIGTERM handling, circuit breakers planned for OIDC/S3
- [x] **Port Binding**: Uvicorn self-contained server on port 8000
- [x] **Concurrency**: Stateless processes enable horizontal scaling via Juju units
- [x] **Admin Processes**: Alembic migrations, data seeding scripts in same environment
- [x] **UX Consistency**: Vanilla HTML/CSS/JS with responsive design, loading states, error messages documented
- [x] **Security**: OIDC auth, input validation (Pydantic), rate limiting (slowapi), HTTPS/TLS in production
- [x] **Performance**: <200ms p95 API latency target, <50ms DB queries, caching strategy defined
- [x] **Workflow**: pytest for CI/CD, code review process, coverage ≥80% target

**All constitution gates passed. Design ready for implementation.**

---

## Next Steps

This plan is complete and ready for task generation:

```bash
# Generate implementation tasks
/speckit-tasks

# Or proceed directly to implementation
/speckit-implement
```

**Phase 2 Deliverables** (via `/speckit-tasks`):
- tasks.md with dependency-ordered implementation tasks
- Tasks organized by user story (P1 → P2 → P3)
- Clear separation: Setup → Foundational → User Stories → Polish
