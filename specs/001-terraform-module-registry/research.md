# Research: Private Terraform Module Registry

**Date**: 2026-05-10
**Phase**: 0 - Outline & Research
**Purpose**: Document technology decisions, research findings, and best practices

## Technology Stack Decisions

### Web Framework: FastAPI

**Decision**: Use FastAPI as the web framework

**Rationale**:
- Native async/await support for high-performance I/O operations
- Automatic OpenAPI documentation generation (useful for API contracts)
- Built-in request/response validation via Pydantic
- Excellent performance characteristics (comparable to Node.js, Go)
- Strong typing support aligns with constitution's type safety requirements
- Minimal dependencies philosophy matches project constraints
- Built-in dependency injection for testability

**Alternatives Considered**:
- **Flask**: More established but lacks async support and built-in validation
- **Django**: Too heavyweight with many features (ORM, admin, templates) not needed
- **Starlette**: Lower-level; FastAPI built on Starlette provides better developer experience

**Best Practices**:
- Use APIRouter for organizing endpoints by domain (registry, modules, auth)
- Implement dependency injection for database sessions and auth
- Use Pydantic models for all request/response validation
- Mount static files for frontend assets
- Use middleware for cross-cutting concerns (auth, logging, rate limiting)

### Dependency Management: uv

**Decision**: Use uv for Python dependency management

**Rationale**:
- Extremely fast (10-100x faster than pip)
- Compatible with pyproject.toml standards
- Deterministic dependency resolution
- Built-in virtual environment management
- Lock file support for reproducible builds (aligns with constitution)

**Alternatives Considered**:
- **pip + pip-tools**: Standard but slow, manual workflow
- **Poetry**: Good but slower than uv, more opinionated project structure
- **PDM**: Modern but less performant than uv

**Best Practices**:
- Use pyproject.toml for dependency declarations
- Generate uv.lock for reproducible builds
- Use dependency groups for dev/test/prod separation
- Pin versions explicitly for stability

### Task Runner: just

**Decision**: Use just as the task runner/command interface

**Rationale**:
- Simple, platform-independent command runner
- Clear syntax (similar to make but better)
- No special syntax to learn (just shell commands)
- Supports environment variables and cross-platform commands
- Provides self-documenting commands (just --list)

**Alternatives Considered**:
- **make**: Platform-specific issues, complex syntax
- **invoke**: Python-based but adds dependency
- **bash scripts**: Not cross-platform, no discoverability

**Best Practices**:
- Define common tasks: build, test, lint, format, run-dev, migrate
- Use environment variables for configuration
- Document each command with comments
- Group related tasks logically

### Packaging: Rockcraft (OCI Images)

**Decision**: Package application as Ubuntu Rock (OCI-compliant image)

**Rationale**:
- Ubuntu-optimized container images with security patches
- Minimal base images (chisel support for smaller footprint)
- Pebble service manager for graceful shutdown (constitution requirement)
- Native integration with Juju charms
- Follows OCI standards for portability

**Best Practices from Documentation**:
- Use ubuntu:22.04 or later as base
- Include pebble service definitions for process management
- Declare all runtime dependencies explicitly
- Use multi-stage builds if needed for smaller images
- Configure health checks for Pebble

**Rock Structure**:
```yaml
# rockcraft.yaml
name: tsilo
base: ubuntu@22.04
version: "1.0"
summary: Private Terraform Module Registry
description: |
  Private registry for Terraform modules with OIDC auth and web UI
platforms:
  amd64:
services:
  tsilo:
    override: replace
    command: /bin/uvicorn tsilo.main:app --host 0.0.0.0 --port 8000
    startup: enabled
    on-check-failure:
      web: restart
parts:
  tsilo:
    plugin: python
    source: .
    python-packages:
      - .
    stage-packages:
      - python3.11
```

### Deployment: Charmcraft (Juju Charms)

**Decision**: Package as 12-factor Juju charm

**Rationale**:
- Native 12-factor application support
- Declarative configuration management (environment variables)
- Integration with backing services (PostgreSQL, S3)
- Lifecycle management (install, configure, upgrade, scale)
- Secrets management for OIDC credentials
- Relation-based service discovery

**Best Practices from Documentation**:
- Use ops framework for charm implementation
- Define relations for PostgreSQL and S3 backing services
- Use charm config for environment variables (12-factor)
- Implement proper lifecycle hooks (install, config-changed, upgrade)
- Add health checks and status reporting
- Support horizontal scaling via unit relations

**Charm Structure**:
```yaml
# charmcraft.yaml
type: charm
bases:
  - build-on:
      - name: ubuntu
        channel: "22.04"
    run-on:
      - name: ubuntu
        channel: "22.04"
parts:
  charm:
    plugin: python
    source: charm/
    python-packages:
      - ops
resources:
  tsilo-image:
    type: oci-image
    description: OCI image for Tsilo registry
```

## Database: PostgreSQL

**Decision**: Use PostgreSQL for metadata storage

**Rationale**:
- Robust support for concurrent operations
- ACID compliance for data integrity
- JSON/JSONB support for flexible schema (module metadata)
- Excellent performance for read-heavy workloads
- Strong ecosystem (SQLAlchemy ORM support)
- Well-supported in Juju ecosystem

**Alternatives Considered**:
- **SQLite**: Not suitable for concurrent writes, deployment complexity
- **MySQL**: Less robust JSON support, weaker consistency guarantees

**Schema Design Considerations**:
- Use separate tables for Module, ModuleVersion, Namespace, Permission, Metric
- Index on namespace + module name for fast lookups
- Index on version for range queries
- JSONB for flexible module metadata (inputs, outputs)
- Foreign key constraints for referential integrity

**Best Practices**:
- Use Alembic for schema migrations
- Connection pooling for performance
- Read replicas for scalability (future)
- Query optimization (<50ms requirement from constitution)

## Object Storage: S3-Compatible

**Decision**: Use S3-compatible object storage for module packages

**Rationale**:
- Decouples package storage from application state (stateless requirement)
- Horizontal scaling friendly
- Standard API (boto3, MinIO, Ceph)
- Cost-effective for large binary files
- Built-in durability and availability

**Alternatives Considered**:
- **Filesystem**: Not horizontally scalable, backup complexity
- **Database BLOBs**: Poor performance for large files

**Best Practices**:
- Use bucket per namespace or organized key structure
- Pre-signed URLs for direct downloads (reduces proxy load)
- Implement lifecycle policies for versioning
- Enable versioning for data durability

## Frontend: Vanilla HTML/CSS/JavaScript

**Decision**: Use vanilla HTML, CSS, JavaScript (no frameworks)

**Rationale**:
- Minimal dependencies aligns with project constraints
- Fast page loads (no framework overhead)
- Simpler debugging and maintenance
- Progressive enhancement approach
- Easier to meet WCAG 2.1 AA requirements (constitution)

**Alternatives Considered**:
- **React/Vue/Svelte**: Unnecessary complexity for read-heavy UI
- **HTMX**: Adds dependency, overkill for simple interactions

**Architecture**:
- Static HTML files served by FastAPI
- CSS Grid/Flexbox for responsive layout (no CSS frameworks)
- Fetch API for async data loading
- ES6 modules for code organization
- Web Components for reusable UI elements (optional)

**Best Practices**:
- Semantic HTML for accessibility
- CSS custom properties for theming
- Progressive enhancement (works without JS)
- Responsive design with CSS media queries
- Clear loading states and error messages (constitution requirement)

## Authentication: OIDC

**Decision**: OpenID Connect for web UI authentication

**Rationale**:
- Industry standard for web SSO
- Group membership support via standard claims
- Works with common providers (Keycloak, Auth0, Okta, etc.)
- Token-based authentication for API access
- Support for service accounts (CI/CD requirement)

**Flow Design**:
- Authorization Code Flow for web UI
- Client Credentials Flow for CI/CD tokens
- Group claims mapped to namespace permissions

**Libraries**:
- `authlib` for OIDC client implementation
- `python-jose` for JWT validation
- FastAPI dependency injection for auth middleware

**Best Practices**:
- Store tokens in httponly cookies (web UI)
- Use short-lived access tokens with refresh tokens
- Implement token revocation
- Rate limit auth endpoints (constitution requirement)

## Terraform CLI Login: OAuth 2.0 with PKCE

**Decision**: Implement Terraform CLI login protocol using OAuth 2.0 Authorization Code flow with PKCE extension

**Rationale**:
- Required for `terraform login` command support (FR-017a)
- PKCE (Proof Key for Code Exchange) protects against authorization code interception
- OAuth 2.0 is standard protocol with well-tested implementations
- Enables secure CLI authentication without embedding secrets in CLI
- Terraform CLI expects specific OAuth endpoints and service discovery

**Protocol Specification**:
- Reference: `.specify/docs/login_protocol.md` (Terraform Login Protocol)
- Reference: Terraform Remote Service Discovery (/.well-known/terraform.json)

**Flow Design**:
1. **Service Discovery**: Terraform CLI queries `/.well-known/terraform.json` to discover OAuth endpoints
2. **Authorization Request**: CLI opens browser to `/oauth/authorization` with PKCE code_challenge
3. **User Authentication**: User logs in via OIDC (reuses existing web UI auth)
4. **Authorization Grant**: User approves Terraform CLI access
5. **Code Exchange**: CLI exchanges authorization code for access token at `/oauth/token`
6. **PKCE Validation**: Server validates code_verifier matches code_challenge
7. **Token Issuance**: Server issues long-lived access token (no expiration)

**Security Features**:
- **PKCE**: Prevents authorization code interception attacks
  - CLI generates random `code_verifier` (43-128 characters)
  - Computes `code_challenge` = BASE64URL(SHA256(code_verifier))
  - Sends challenge to authorization endpoint
  - Sends verifier to token endpoint
  - Server validates SHA256(verifier) == challenge
- **Single-use codes**: Authorization codes valid for 10 minutes, one-time use only
- **State parameter**: CSRF protection via random state value
- **Localhost redirect**: OAuth callback to http://localhost:10000/ (configurable ports 10000-10010)

**Implementation Libraries**:
- `authlib` - OAuth 2.0 server implementation with PKCE support
- `python-jose` - JWT token generation (if using JWT for tokens)
- `secrets` module - Cryptographically secure random code generation

**Endpoints**:
- `GET /.well-known/terraform.json` - Service discovery with login.v1 configuration
- `GET /oauth/authorization` - OAuth authorization endpoint (redirects to login, then to localhost)
- `POST /oauth/token` - Token endpoint (exchanges code for access token)

**Database Storage**:
- **OAuthAuthorizationCode** entity stores temporary authorization codes
  - Fields: code, user_id, client_id, redirect_uri, code_challenge, code_challenge_method, scopes
  - Expires after 10 minutes
  - Single-use (marked as used_at after exchange)
  - Cleanup job deletes expired/used codes periodically

**Token Management**:
- Access tokens stored as APIToken entities (reuses existing infrastructure)
- Tokens do not expire (`expires_in: null`) per Terraform CLI expectation
- User can revoke tokens via web UI
- Token includes all namespace permissions user has access to

**CI/CD Integration**:
- Tokens obtained via `terraform login` can be used in CI/CD pipelines
- Alternative: Use Terraform CLI configuration file credentials section
  - Static token in `.terraformrc`: `credentials "registry.example.com" { token = "..." }`
  - Dynamic token via credentials_helper for advanced workflows
- Both methods use same APIToken authentication mechanism

**Alternatives Considered**:
- **Password Grant**: Only supported by Terraform for app.terraform.io, not for third-party registries
- **Client Credentials**: Not supported by Terraform CLI for registry authentication
- **Device Code Flow**: Not supported by Terraform CLI

**Best Practices**:
- Port range 10000-10010 allows up to 11 concurrent login attempts
- Authorization codes expire quickly (10 minutes) to limit attack window
- PKCE code_verifier must be at least 43 characters (recommended 128)
- Use S256 method (SHA256) for code_challenge, not "plain"
- Clean up expired authorization codes regularly (hourly job)
- Log all token issuance events for audit trail

## Testing Strategy

**Decision**: pytest with contract, integration, and unit test layers

**Rationale**:
- pytest is Python standard with excellent FastAPI support
- Aligns with constitution's TDD requirements
- Supports async tests (needed for FastAPI)
- Rich plugin ecosystem (coverage, fixtures, markers)

**Test Layers**:

1. **Contract Tests** (tests/contract/)
   - Validate Terraform Module Registry Protocol compliance
   - Test against protocol specification (docs/registry_api.md)
   - Use httpx for HTTP testing
   - Mock external dependencies

2. **Integration Tests** (tests/integration/)
   - Test multi-component interactions
   - Use testcontainers for PostgreSQL
   - Test auth flows end-to-end
   - Test namespace isolation

3. **Unit Tests** (tests/unit/)
   - Test individual functions/classes
   - Mock external dependencies
   - Fast execution (<1s total)
   - High coverage (>80% requirement)

**Libraries**:
- `pytest` - test framework
- `pytest-asyncio` - async test support
- `httpx` - async HTTP client for API tests
- `pytest-cov` - coverage reporting
- `pytest-mock` - mocking support
- `faker` - test data generation

**Best Practices**:
- Write tests before implementation (TDD - constitution requirement)
- Use fixtures for common setup
- Parametrize tests for multiple scenarios
- Run contract tests against real Terraform CLI
- CI/CD integration for automated testing

## Code Quality Tools

**Decision**: ruff + black + mypy

**Rationale**:
- Constitution requires PEP 8 compliance and type checking
- ruff is extremely fast (100x faster than pylint)
- black provides deterministic formatting
- mypy provides static type checking

**Configuration**:
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
```

**Integration**:
- Pre-commit hooks for automatic formatting
- CI/CD checks enforce all tools pass
- just lint command for manual execution

## Logging & Observability

**Decision**: structlog for structured logging, Prometheus metrics

**Rationale**:
- Constitution requires structured logging (JSON format)
- Constitution requires /health and /metrics endpoints
- structlog provides excellent structured logging for Python
- Prometheus standard for metrics in Kubernetes/Juju

**Implementation**:
- Use structlog for application logging
- Include correlation IDs in all log entries
- Export metrics via /metrics endpoint
- Custom metrics for module downloads, auth events
- Health check endpoint for liveness/readiness probes

**Metrics to Track**:
- Request latency (p50, p95, p99)
- Request count by endpoint
- Error rates
- Module download counts
- Active user sessions
- Database connection pool stats

## Rate Limiting

**Decision**: slowapi (FastAPI rate limiting middleware)

**Rationale**:
- Constitution requires rate limiting on public endpoints
- Simple middleware-based approach
- Supports various strategies (fixed window, sliding window)
- Per-IP and per-user limiting

**Configuration**:
- 100 requests/minute for unauthenticated endpoints
- 1000 requests/minute for authenticated users
- Separate limits for download vs upload operations

## Summary of Clarifications Resolved

All technical choices were explicitly specified by the user:
- ✅ Language: Python 3.11+
- ✅ Web framework: FastAPI
- ✅ Frontend: Vanilla HTML/CSS/JS
- ✅ Packaging: Rockcraft
- ✅ Deployment: Charmcraft (Juju charm)
- ✅ Dependency management: uv
- ✅ Task runner: just
- ✅ Testing: pytest

Additional decisions made based on requirements and best practices:
- ✅ Database: PostgreSQL (robust, JSON support, well-supported)
- ✅ Object storage: S3-compatible (stateless, scalable)
- ✅ ORM: SQLAlchemy (Python standard, good FastAPI integration)
- ✅ Validation: Pydantic (built into FastAPI)
- ✅ Migrations: Alembic (SQLAlchemy companion)
- ✅ OIDC library: authlib (comprehensive, well-maintained)
- ✅ Testing: httpx, pytest-asyncio, testcontainers
- ✅ Code quality: ruff, black, mypy
- ✅ Logging: structlog
- ✅ Metrics: Prometheus format
- ✅ Rate limiting: slowapi

## Next Steps

Proceed to Phase 1:
1. Create detailed data model (data-model.md)
2. Define API contracts (contracts/)
3. Write quickstart guide (quickstart.md)
4. Re-evaluate constitution gates with concrete design
