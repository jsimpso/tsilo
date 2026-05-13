# Tasks: Private Terraform Module Registry

**Input**: Design documents from `/specs/001-terraform-module-registry/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/terraform-registry-api.md, contracts/web-ui-api.md, research.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5, US6)
- File paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure per plan.md

- [ ] T001 Create project directory structure: src/tsilo/, tests/{contract,integration,unit}/, charm/
- [ ] T002 [P] Initialize Python project with uv: create pyproject.toml with FastAPI, uvicorn, SQLAlchemy, Pydantic, authlib, python-jose, structlog, slowapi, alembic, boto3 dependencies
- [ ] T003 [P] Create justfile with commands: install, dev, test, lint, format, migrate, build-rock, build-charm
- [ ] T004 [P] Configure code quality tools in pyproject.toml: ruff (linting), black (formatting), mypy (type checking)
- [ ] T005 [P] Create .env.example with all required environment variables: DATABASE_URL, S3_BUCKET, OIDC_CLIENT_ID, OIDC_ISSUER, etc.
- [ ] T006 [P] Create rockcraft.yaml for OCI image packaging with pebble service definition
- [ ] T007 [P] Create charmcraft.yaml for Juju charm packaging with PostgreSQL and S3 relations
- [ ] T008 [P] Create .gitignore for Python, environments, build artifacts

**Checkpoint**: Project structure and tooling ready for development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T009 Create database configuration in src/tsilo/config.py: load all settings from environment variables (12-factor)
- [x] T010 Setup SQLAlchemy base and session management in src/tsilo/models/__init__.py
- [x] T011 Initialize Alembic for database migrations in src/alembic/: env.py, alembic.ini configuration
- [x] T012 [P] Create Namespace model in src/tsilo/models/namespace.py: id, name, display_name, description, timestamps, validation
- [x] T013 [P] Create Module model in src/tsilo/models/module.py: id, namespace_id, name, provider, description, source_url, timestamps
- [x] T014 [P] Create ModuleVersion model in src/tsilo/models/version.py: id, module_id, version, inputs, outputs, readme, package_url, checksums, published_by, published_at
- [x] T015 [P] Create NamespacePermission model in src/tsilo/models/permission.py: id, namespace_id, group_name, permission_level (read/write)
- [x] T016 [P] Create User model in src/tsilo/models/user.py: id, oidc_sub, email, name, groups (JSONB), last_login_at, timestamps
- [x] T017 [P] Create APIToken model in src/tsilo/models/api_token.py: id, token_hash, user_id, name, scopes (JSONB), expires_at, revoked_at, last_used_at
- [x] T018 [P] Create OAuthAuthorizationCode model in src/tsilo/models/oauth_code.py: id, code, user_id, client_id, redirect_uri, code_challenge, code_challenge_method, scopes, used_at, expires_at
- [x] T019 [P] Create DownloadMetric model in src/tsilo/models/metric.py: id, version_id, download_count, last_download_at, timestamps
- [x] T020 Create initial database migration in src/alembic/versions/20260510_1000_initial_schema.py: all 8 tables with indexes and constraints
- [x] T021 Setup S3 storage service in src/tsilo/services/storage_service.py: upload_module, generate_download_url using boto3
- [x] T022 Setup OIDC authentication service in src/tsilo/services/auth_service.py: OAuth client configuration, token validation using authlib
- [x] T023 Create authentication middleware in src/tsilo/middleware/auth.py: Bearer token validation, session cookie validation, user context injection
- [x] T024 [P] Create rate limiting middleware in src/tsilo/middleware/rate_limit.py: per-user limits (1000/hour read, 100/hour write) using slowapi
- [x] T025 [P] Create logging middleware in src/tsilo/middleware/logging.py: structured JSON logging with correlation IDs using structlog
- [x] T026 Create permission service in src/tsilo/services/permission_service.py: check_read_access, check_write_access based on user groups and namespace permissions
- [x] T027 Create FastAPI application entry point in src/tsilo/main.py: app initialization, middleware registration, CORS, security headers
- [x] T028 [P] Create health check endpoint in src/tsilo/api/metrics.py: GET /health with database and S3 connectivity checks
- [x] T029 [P] Create Prometheus metrics endpoint in src/tsilo/api/metrics.py: GET /metrics with request counters, latency histograms, download counts

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Terraform CLI Module Download (Priority: P1) 🎯 MVP

**Goal**: Enable `terraform init` to download modules from the registry

**Independent Test**: Run `terraform init` with source pointing to registry, verify module downloads successfully. Test version constraints (~> 1.0), verify authentication works, test error cases (missing module, no permissions).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T030 [P] [US1] Contract test for service discovery in tests/contract/test_service_discovery.py: verify /.well-known/terraform.json returns correct modules.v1 and login.v1 structure
- [x] T031 [P] [US1] Contract test for version listing in tests/contract/test_version_listing.py: verify versions returned in descending order, authentication required
- [x] T032 [P] [US1] Contract test for module download in tests/contract/test_module_download.py: verify download URL generation, download counter increment, authentication/authorization
- [x] T033 [P] [US1] Integration test for Terraform CLI download flow in tests/integration/test_terraform_download.py: end-to-end test with real Terraform CLI

### Implementation for User Story 1

- [x] T034 [P] [US1] Create Pydantic schemas for Terraform protocol in src/tsilo/schemas/terraform.py: VersionsResponse, DownloadResponse, ServiceDiscovery
- [x] T035 [US1] Implement service discovery endpoint in src/tsilo/api/registry.py: GET /.well-known/terraform.json (no auth required, cacheable)
- [x] T036 [US1] Implement version listing endpoint in src/tsilo/api/registry.py: GET /v1/modules/:namespace/:name/:provider/versions with permission check, semantic version sorting
- [x] T037 [US1] Create module version service in src/tsilo/services/version_service.py: list_versions, get_version, semantic version comparison
- [x] T038 [US1] Implement module download endpoint in src/tsilo/api/registry.py: GET /v1/modules/:namespace/:name/:provider/:version/download with pre-signed S3 URL generation
- [x] T039 [US1] Create metrics service in src/tsilo/services/metrics_service.py: increment_download_count (async, non-blocking), update_last_download_at
- [x] T040 [US1] Add error handling for 404 (module not found), 403 (no permission), 401 (not authenticated)
- [x] T041 [US1] Add structured logging for all download events: user_id, namespace, module, provider, version, timestamp

**Checkpoint**: Terraform CLI can successfully download modules via `terraform init`

---

## Phase 4: User Story 2 - Web UI Module Discovery (Priority: P1) 🎯 MVP

**Goal**: Provide web interface for browsing and searching modules

**Independent Test**: Access web UI, search for modules, view module details with documentation, inputs, outputs. Test responsive design on mobile viewport. Verify only authorized modules appear.

### Tests for User Story 2 ⚠️

- [x] T042 [P] [US2] Integration test for web UI auth flow in tests/integration/test_web_auth.py: OIDC login, callback, session cookie, logout
- [x] T043 [P] [US2] Integration test for module browsing in tests/integration/test_module_browsing.py: list modules, search, filter by namespace, pagination
- [x] T044 [P] [US2] Integration test for module detail page in tests/integration/test_module_detail.py: README rendering, inputs/outputs display, version switching

### Implementation for User Story 2

- [x] T045 [P] [US2] Create Pydantic schemas for web UI API in src/tsilo/schemas/module.py: ModuleListResponse, ModuleDetailResponse, VersionDetailResponse with pagination
- [x] T046 [P] [US2] Create base HTML template in src/tsilo/templates/base.html: modern layout, navigation, responsive CSS, CSRF meta tag
- [x] T047 [US2] Implement OIDC login endpoints in src/tsilo/api/auth.py: GET /auth/login (redirect to OIDC), GET /auth/callback (handle code, create session), POST /auth/logout, GET /auth/me
- [x] T048 [US2] Implement module listing endpoint in src/tsilo/api/modules.py: GET /api/modules with search, namespace filter, pagination (only authorized namespaces)
- [x] T049 [US2] Create module service in src/tsilo/services/module_service.py: list_modules, search_modules, get_module_with_versions, filter by user permissions
- [x] T050 [US2] Implement module detail endpoint in src/tsilo/api/modules.py: GET /api/modules/:namespace/:name/:provider with version list and metrics
- [x] T051 [US2] Implement version detail endpoint in src/tsilo/api/modules.py: GET /api/modules/:namespace/:name/:provider/:version with inputs, outputs, README
- [x] T052 [P] [US2] Create static homepage in src/tsilo/static/index.html: module search, featured modules, recent activity
- [x] T053 [P] [US2] Create module list JavaScript in src/tsilo/static/js/main.js: fetch modules, render cards, search filtering, pagination
- [x] T054 [P] [US2] Create module detail JavaScript in src/tsilo/static/js/module-detail.js: fetch version details, render README (Markdown), display inputs/outputs tables, version switcher
- [x] T055 [P] [US2] Create responsive CSS in src/tsilo/static/css/styles.css: modern design, mobile-first, CSS Grid layout, loading states, error messages
- [x] T056 [US2] Add usage example generation: auto-generate Terraform code snippet showing registry URL syntax for each module version
- [x] T057 [US2] Add CSRF protection middleware in src/tsilo/middleware/auth.py: validate X-CSRF-Token header for POST/PUT/DELETE requests

**Checkpoint**: Web UI fully functional for browsing and searching modules with modern, responsive design

---

## Phase 5: User Story 3 - Module Upload and Versioning (Priority: P2)

**Goal**: Enable module authors to upload new modules and versions

**Independent Test**: Upload module package via web UI or API, verify it appears in search, download via Terraform CLI. Test duplicate version rejection, semantic version validation, input/output extraction.

### Tests for User Story 3 ⚠️

- [x] T058 [P] [US3] Contract test for module upload in tests/contract/test_module_upload.py: verify multipart upload, version validation, duplicate rejection, permission enforcement
- [x] T059 [P] [US3] Integration test for upload-download cycle in tests/integration/test_upload_download.py: upload module, verify S3 storage, download via Terraform CLI

### Implementation for User Story 3

- [x] T060 [P] [US3] Create Terraform module parser in src/tsilo/services/module_parser.py: extract inputs from variables.tf, extract outputs from outputs.tf, extract README.md
- [x] T061 [US3] Implement module upload endpoint in src/tsilo/api/registry.py: POST /v1/modules/:namespace/:name/:provider/:version with multipart file upload
- [x] T062 [US3] Create module version service methods in src/tsilo/services/version_service.py: create_version, validate_semver, check_version_exists, parse_module_package
- [x] T063 [US3] Implement package validation: verify .tar.gz format, check for .tf files, validate Terraform syntax, check size limit (100MB)
- [x] T064 [US3] Integrate S3 upload: upload to s3://bucket/:namespace/:name/:provider/:version/module.tar.gz with server-side encryption
- [x] T065 [US3] Calculate and store SHA256 checksum during upload for package integrity
- [x] T066 [US3] Create DownloadMetric record initialized to 0 when ModuleVersion created
- [x] T067 [US3] Add detailed validation error responses: which file failed, what syntax error, actionable guidance
- [x] T068 [P] [US3] Create module upload form in web UI: namespace selector, module name/provider input, version input, file upload, validation feedback
- [x] T069 [US3] Add module upload JavaScript in src/tsilo/static/js/upload.js: file validation, progress indicator, error display, success confirmation

**Checkpoint**: Module authors can upload new modules and versions; modules immediately available for download

---

## Phase 6: User Story 4 - Namespace and Permission Management (Priority: P2)

**Goal**: Control access to namespaces via OIDC group-based permissions

**Independent Test**: Create namespace, configure permissions for groups, verify users in groups can read/write, users without permissions get 403 errors, unauthorized modules don't appear in searches.

### Tests for User Story 4 ⚠️

- [x] T070 [P] [US4] Integration test for namespace isolation in tests/integration/test_namespace_isolation.py: verify user can't access unauthorized namespaces, permissions enforced on all endpoints
- [x] T071 [P] [US4] Integration test for permission management in tests/integration/test_permission_management.py: create/update/delete permissions, verify access control updates

### Implementation for User Story 4

- [x] T072 [P] [US4] Create Pydantic schemas for namespace API in src/tsilo/schemas/namespace.py: NamespaceCreate, NamespaceResponse, PermissionResponse
- [x] T073 [US4] Implement namespace listing endpoint in src/tsilo/api/namespaces.py: GET /api/namespaces (only namespaces user has access to)
- [x] T074 [US4] Create namespace service in src/tsilo/services/namespace_service.py: list_user_namespaces, create_namespace, get_namespace_permissions
- [x] T075 [US4] Implement namespace creation endpoint in src/tsilo/api/namespaces.py: POST /api/namespaces (admin only, validate name pattern)
- [x] T076 [US4] Implement permission listing endpoint in src/tsilo/api/namespaces.py: GET /api/namespaces/:namespace/permissions
- [x] T077 [US4] Enhance permission service in src/tsilo/services/permission_service.py: add create_permission, delete_permission, list_namespace_permissions
- [x] T078 [US4] Update module listing to filter by user permissions: only show modules from authorized namespaces
- [x] T079 [US4] Update search to respect namespace permissions: exclude unauthorized modules from results
- [x] T080 [P] [US4] Create namespace management UI in web UI: list namespaces, create namespace form, permission management interface (admin only)
- [x] T081 [US4] Add permission check to all module operations: download (read), upload (write), view metadata (read)

**Checkpoint**: Multi-tenancy fully enforced; namespace permissions control all access

---

## Phase 7: User Story 5 - CI/CD Pipeline Authentication (Priority: P3)

**Goal**: Enable authentication from CI/CD pipelines and Terraform CLI login

**Independent Test**: Configure CI/CD pipeline with API token, run `terraform init` in pipeline, verify module downloads. Test `terraform login` command with OAuth flow, verify token issued, test PKCE validation.

### Tests for User Story 5 ⚠️

- [x] T082 [P] [US5] Contract test for OAuth authorization in tests/contract/test_oauth_authorization.py: verify authorization endpoint redirect, state parameter, PKCE challenge
- [x] T083 [P] [US5] Contract test for OAuth token exchange in tests/contract/test_oauth_token.py: verify code verifier validation, token issuance, error cases
- [x] T084 [P] [US5] Integration test for Terraform CLI login in tests/integration/test_terraform_login.py: full OAuth flow with PKCE, verify token works for module download
- [x] T085 [P] [US5] Integration test for API token authentication in tests/integration/test_api_token_auth.py: create token, use in Terraform CLI credentials, download module

### Implementation for User Story 5

- [x] T086 [P] [US5] Create Pydantic schemas for OAuth in src/tsilo/schemas/oauth.py: AuthorizationRequest, TokenRequest, TokenResponse, PKCE validation
- [x] T087 [P] [US5] Create Pydantic schemas for API tokens in src/tsilo/schemas/api_token.py: TokenCreate, TokenResponse with scopes
- [x] T088 [US5] Update service discovery endpoint in src/tsilo/api/registry.py: add login.v1 configuration with OAuth endpoints and ports [10000, 10010]
- [x] T089 [US5] Implement OAuth authorization endpoint in src/tsilo/api/auth.py: GET /oauth/authorization with PKCE code_challenge, redirect to login, prompt user approval
- [x] T090 [US5] Create OAuth service in src/tsilo/services/oauth_service.py: generate_authorization_code, validate_pkce_challenge, store_auth_code with expiration (10 min)
- [x] T091 [US5] Implement OAuth token endpoint in src/tsilo/api/auth.py: POST /oauth/token with code_verifier validation, single-use code enforcement
- [x] T092 [US5] Implement PKCE validation in OAuth service: compute SHA256(code_verifier), compare to stored code_challenge, reject mismatch
- [x] T093 [US5] Create APIToken on successful OAuth exchange: no expiration (expires_in: null), include user's namespace permissions in scopes
- [x] T094 [US5] Implement API token listing endpoint in src/tsilo/api/tokens.py: GET /api/tokens (user's tokens only)
- [x] T095 [US5] Implement API token creation endpoint in src/tsilo/api/tokens.py: POST /api/tokens with namespace scopes, return token_value (once only)
- [x] T096 [US5] Create token service in src/tsilo/services/token_service.py: generate_token (cryptographically random), hash_token (SHA256), validate_token_scopes
- [x] T097 [US5] Implement API token revocation endpoint in src/tsilo/api/tokens.py: DELETE /api/tokens/:id (set revoked_at timestamp)
- [x] T098 [US5] Update authentication middleware to support Bearer tokens from API tokens and OAuth
- [x] T099 [US5] Create OAuth authorization code cleanup job: delete expired/used codes hourly (expires_at < NOW() - 24h OR used_at < NOW() - 7d)
- [x] T100 [P] [US5] Create API token management UI in web UI: list tokens, create token with scope selection, revoke tokens, display token value once with warning

**Checkpoint**: CI/CD pipelines can authenticate with API tokens; Terraform CLI login via OAuth 2.0 + PKCE works

---

## Phase 8: User Story 6 - Observability and Usage Metrics (Priority: P3)

**Goal**: Track and display download metrics for modules

**Independent Test**: Download module via Terraform CLI, wait for metrics update (<1 minute), view module detail page, verify download count and last download timestamp. View system-wide metrics dashboard.

### Tests for User Story 6 ⚠️

- [x] T101 [P] [US6] Integration test for metrics tracking in tests/integration/test_metrics_tracking.py: download module, verify download_count incremented, last_download_at updated
- [x] T102 [P] [US6] Integration test for metrics display in tests/integration/test_metrics_display.py: verify metrics API returns accurate data, test deprecation flag for old versions

### Implementation for User Story 6

- [x] T103 [P] [US6] Create Pydantic schemas for metrics in src/tsilo/schemas/metrics.py: MetricsOverview, ModuleMetrics, DownloadTrend
- [x] T104 [US6] Enhance metrics service in src/tsilo/services/metrics_service.py: get_module_metrics, get_system_metrics, flag_deprecated_versions (90+ days no downloads)
- [x] T105 [US6] Implement system metrics endpoint in src/tsilo/api/metrics.py: GET /api/metrics/overview (admin only) with total_modules, total_downloads, top_modules, namespace_usage
- [x] T106 [US6] Implement module metrics endpoint in src/tsilo/api/metrics.py: GET /api/metrics/modules/:namespace/:name/:provider with downloads_by_version, downloads_over_time
- [x] T107 [US6] Update module detail endpoint to include download metrics: total_downloads, last_download_at for each version
- [x] T108 [US6] Add deprecation flag to version responses: mark versions with last_download_at > 90 days ago as deprecated
- [x] T109 [US6] Create metrics calculation job: aggregate download counts, identify deprecated versions, update cache (runs hourly)
- [x] T110 [P] [US6] Create metrics dashboard UI in web UI: system overview charts, top modules table, namespace usage breakdown (admin only)
- [x] T111 [P] [US6] Add download metrics to module detail page: version-level download counts, last download timestamps, deprecation warnings
- [x] T112 [US6] Update Prometheus metrics endpoint with module-specific metrics: download counts per module, deprecation flags, version distribution

**Checkpoint**: Download metrics tracked and displayed; deprecated versions identified; system-wide observability available

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T113 [P] Create comprehensive README.md: project overview, features, architecture diagram, deployment guide, development setup
- [x] T114 [P] Create quickstart documentation validation: follow quickstart.md steps, verify all commands work
- [x] T115 [P] Add comprehensive unit tests in tests/unit/: test_models.py (validation, relationships), test_services.py (business logic), test_schemas.py (Pydantic validation)
- [x] T116 Performance optimization: add database query optimization (select only needed columns, eager loading), implement caching for module metadata (5 min), permissions (1 min)
- [x] T117 Security audit: verify input validation on all endpoints, test rate limiting enforcement, verify HTTPS/TLS in production, check for SQL injection vulnerabilities
- [x] T118 [P] Implement charm lifecycle hooks in charm/src/charm.py: install, config-changed (update env vars), upgrade, scale (horizontal scaling support)
- [x] T119 [P] Add database relation in charm: integrate with PostgreSQL charm, handle connection string injection
- [x] T120 [P] Add S3 relation in charm: integrate with S3 charm or external S3, handle credentials injection
- [x] T121 Add graceful shutdown handling in src/tsilo/main.py: SIGTERM handler, drain connections, complete in-flight requests
- [x] T122 Add circuit breakers for external dependencies: OIDC provider, S3 storage (fail gracefully, return 503 with retry-after)
- [x] T123 Create data seeding script for development: sample namespaces, modules, versions, users, permissions
- [x] T124 Run full contract test suite against Terraform CLI: verify all protocol endpoints work with real Terraform 1.5+
- [x] T125 Verify WCAG 2.1 AA compliance for web UI: keyboard navigation, screen reader support, color contrast, focus indicators
- [x] T126 Add API documentation: generate OpenAPI spec from FastAPI, serve at /docs with authentication examples
- [x] T127 Final constitution compliance review: verify all 12-factor principles implemented, checklist in plan.md passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 (Phase 3): Terraform CLI Download - No dependencies on other stories
  - US2 (Phase 4): Web UI Discovery - No dependencies on other stories
  - US3 (Phase 5): Module Upload - Can integrate with US1/US2 but independently testable
  - US4 (Phase 6): Namespace Permissions - Can integrate with US1/US2/US3 but independently testable
  - US5 (Phase 7): CI/CD Auth - Depends on US1 for testing, but OAuth endpoints independent
  - US6 (Phase 8): Metrics - Depends on US1 for download tracking, but metrics infrastructure independent
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 (upload then download) but independently testable
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Affects US1/US2/US3 access control but independently testable
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) - Uses US1 for testing downloads but OAuth flow independent
- **User Story 6 (P3)**: Can start after Foundational (Phase 2) - Tracks US1 downloads but metrics infrastructure independent

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services (data layer first)
- Services before endpoints (business logic before API)
- Core implementation before UI integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T002, T003, T004, T005, T006, T007, T008 can run in parallel
- **Foundational (Phase 2)**: T012-T019 (all models), T024-T025 (middleware), T028-T029 (observability) can run in parallel
- **User Story Tests**: All tests within a story marked [P] can run in parallel
- **User Story Models**: All models within a story marked [P] can run in parallel
- **User Story UI**: All UI components marked [P] can run in parallel
- **Once Foundational completes**: All user stories (US1-US6) can start in parallel by different team members

---

## Parallel Example: Foundational Phase

```bash
# Launch all model creation tasks together:
Task T012: "Create Namespace model in src/tsilo/models/namespace.py"
Task T013: "Create Module model in src/tsilo/models/module.py"
Task T014: "Create ModuleVersion model in src/tsilo/models/version.py"
Task T015: "Create NamespacePermission model in src/tsilo/models/permission.py"
Task T016: "Create User model in src/tsilo/models/user.py"
Task T017: "Create APIToken model in src/tsilo/models/api_token.py"
Task T018: "Create OAuthAuthorizationCode model in src/tsilo/models/oauth_code.py"
Task T019: "Create DownloadMetric model in src/tsilo/models/metric.py"

# Then sequentially:
Task T020: "Create initial migration" (depends on all models)
```

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T030: "Contract test for service discovery in tests/contract/test_service_discovery.py"
Task T031: "Contract test for version listing in tests/contract/test_version_listing.py"
Task T032: "Contract test for module download in tests/contract/test_module_download.py"
Task T033: "Integration test for Terraform CLI in tests/integration/test_terraform_download.py"

# Launch schema creation:
Task T034: "Create Pydantic schemas for Terraform protocol in src/tsilo/schemas/terraform.py"

# Then implement endpoints sequentially (share same file):
Task T035: "Service discovery endpoint in src/tsilo/api/registry.py"
Task T036: "Version listing endpoint in src/tsilo/api/registry.py"
Task T038: "Module download endpoint in src/tsilo/api/registry.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Terraform CLI Download)
4. **STOP and VALIDATE**: Test `terraform init` independently
5. Complete Phase 4: User Story 2 (Web UI Discovery)
6. **STOP and VALIDATE**: Test web UI browsing independently
7. Deploy/demo MVP (P1 functionality complete)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Terraform CLI works!)
3. Add User Story 2 → Test independently → Deploy/Demo (Web UI works!)
4. Add User Story 3 → Test independently → Deploy/Demo (Uploads work!)
5. Add User Story 4 → Test independently → Deploy/Demo (Multi-tenancy enforced!)
6. Add User Story 5 → Test independently → Deploy/Demo (CI/CD auth works!)
7. Add User Story 6 → Test independently → Deploy/Demo (Metrics visible!)
8. Polish → Production-ready

### Parallel Team Strategy

With 3+ developers:

1. Team completes Setup + Foundational together (required for all)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (Terraform CLI) - P1
   - **Developer B**: User Story 2 (Web UI) - P1
   - **Developer C**: User Story 3 (Upload) - P2
3. After P1 complete:
   - **Developer A**: User Story 5 (CI/CD Auth) - P3
   - **Developer B**: User Story 6 (Metrics) - P3
   - **Developer C**: User Story 4 (Permissions) - P2
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label (US1-US6) maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests written before implementation (TDD requirement from constitution)
- Commit after each task or logical group of parallel tasks
- Stop at any checkpoint to validate story independently
- File paths follow structure from plan.md: src/tsilo/, tests/, rockcraft.yaml, charmcraft.yaml, charm/
- All configuration via environment variables (.env) per 12-factor principles
- Database migrations use Alembic with reversible up/down
- All endpoints include structured logging, error handling, rate limiting
- OAuth PKCE implementation follows .specify/docs/login_protocol.md specification
- Web UI uses vanilla HTML/CSS/JS per plan.md technical constraints
