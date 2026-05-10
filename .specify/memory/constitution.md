<!--
Sync Impact Report:
- Version: 1.0.0 (initial constitution establishment)
- Modified principles: N/A (initial creation)
- Added sections: All core principles, Security & Performance Standards, Development Workflow
- Removed sections: N/A
- Templates requiring updates:
  ✅ plan-template.md - Constitution Check section aligns with principles
  ✅ spec-template.md - User scenarios align with UX consistency principle
  ✅ tasks-template.md - Test-first workflow aligns with TDD principle
- Follow-up TODOs: None
-->

# Tsilo Constitution

## Core Principles

### I. Codebase & Dependency Management

**MUST** maintain a single codebase tracked in version control with multiple deployments.
**MUST** explicitly declare all dependencies via package managers (requirements.txt, package.json, etc.).
**MUST** never rely on implicit system-wide packages or undeclared dependencies.
**MUST** use isolated dependency environments (virtual environments, containers).

**Rationale**: Ensures reproducible builds across all environments and eliminates "works on my machine" issues. A single codebase with explicit dependencies guarantees that development, staging, and production environments run identical code.

### II. Configuration & Environment Parity

**MUST** store all configuration in environment variables, never in code.
**MUST** keep development, staging, and production environments as similar as possible.
**MUST** use the same backing services (databases, caches, queues) across all environments.
**MUST NOT** commit secrets, API keys, or environment-specific values to version control.

**Rationale**: Configuration as environment variables enables seamless deployment across environments. Environment parity minimizes bugs that only appear in production and enables continuous deployment with confidence.

### III. Code Quality Standards (NON-NEGOTIABLE)

**MUST** adhere to PEP 8 standards for Python code.
**MUST** enforce linting and formatting via automated tools (ruff, black, prettier).
**MUST** maintain code coverage metrics and require coverage reports for all PRs.
**MUST** pass all linting checks before code review.
**MUST** use type hints in Python (mypy) and TypeScript for type safety.

**Rationale**: Consistent code quality prevents technical debt, improves readability, and reduces cognitive load during code reviews. Automated enforcement eliminates subjective style debates and catches common errors before runtime.

### IV. Test-First Development (NON-NEGOTIABLE)

**MUST** write tests before implementation (TDD mandatory).
**MUST** follow Red-Green-Refactor cycle: Write failing test → Implement → Refactor.
**MUST** require user approval of test scenarios before implementation begins.
**MUST** include contract tests for all API endpoints.
**MUST** include integration tests for multi-component interactions.
**MUST** ensure all tests pass before merging to main branch.

**Rationale**: TDD ensures code is testable by design, reduces defects, and provides living documentation. Pre-approved tests align implementation with user expectations and prevent scope creep.

### V. Stateless Processes & Backing Services

**MUST** execute the application as stateless processes.
**MUST** treat backing services (databases, caches, message queues) as attached resources.
**MUST** ensure processes share nothing and store persistent data in backing services.
**MUST** enable horizontal scaling by avoiding in-process state.

**Rationale**: Stateless processes enable horizontal scaling, improve fault tolerance, and simplify deployment. Treating backing services as attachable resources allows swapping providers without code changes.

### VI. Build, Release, Run Separation

**MUST** strictly separate build, release, and run stages.
**MUST** create immutable releases combining build artifacts with configuration.
**MUST** tag every release with unique identifiers (semantic versioning).
**MUST** enable rollback to any previous release.

**Rationale**: Strict separation prevents runtime code modifications and enables reliable rollbacks. Immutable releases with unique IDs ensure reproducibility and auditability.

### VII. Observability & Logs

**MUST** treat logs as event streams written to stdout/stderr.
**MUST** never manage log files within the application.
**MUST** implement structured logging (JSON format preferred).
**MUST** include correlation IDs for request tracing.
**MUST** expose health check and metrics endpoints (/health, /metrics).

**Rationale**: Logs as event streams decouple applications from log routing. Structured logging enables efficient querying and analysis. Health checks and metrics enable proactive monitoring and alerting.

### VIII. Disposability & Graceful Degradation

**MUST** maximize robustness with fast startup and graceful shutdown.
**MUST** handle SIGTERM signals for graceful shutdown.
**MUST** ensure processes can be started or stopped at any moment.
**MUST** implement circuit breakers for external service failures.
**MUST** provide meaningful error messages and fallback behaviors.

**Rationale**: Fast startup and graceful shutdown enable rapid scaling and resilient deployments. Circuit breakers prevent cascading failures and improve system stability.

### IX. Port Binding & Service Export

**MUST** export services via port binding (self-contained web servers).
**MUST NOT** rely on runtime injection of webservers (e.g., mod_wsgi).
**MUST** enable one application to become the backing service for another via URL routing.

**Rationale**: Port binding makes the application completely self-contained and enables it to serve as a backing service for other applications. Eliminates dependency on specific runtime environments.

### X. Concurrency & Scalability

**MUST** scale out via the process model (horizontal scaling).
**MUST** design workloads to run in concurrent processes (web, workers, schedulers).
**MUST** avoid threading for concurrency (prefer process-based parallelism).
**MUST** design for at least 1000 requests/second under normal load.

**Rationale**: Process-level concurrency leverages OS process management and enables fine-grained resource allocation. Horizontal scaling provides linear performance improvements.

### XI. Admin Processes

**MUST** run administrative and management tasks as one-off processes.
**MUST** run admin processes in identical environments as long-running processes.
**MUST** ship admin code with application code to avoid synchronization issues.
**MUST** use the same dependency isolation for admin scripts.

**Rationale**: Running admin tasks in the same environment prevents drift between one-off scripts and application code. Shipping admin code together prevents version mismatches.

### XII. User Experience Consistency (NON-NEGOTIABLE)

**MUST** implement consistent UI patterns across all user-facing interfaces.
**MUST** provide modern, responsive design supporting desktop and mobile viewports.
**MUST** follow WCAG 2.1 Level AA accessibility guidelines.
**MUST** ensure all interactive elements have clear visual feedback.
**MUST** provide loading states and progress indicators for async operations.
**MUST** implement comprehensive error messages with actionable guidance.
**MUST** maintain consistent navigation patterns and information architecture.

**Rationale**: Consistent UX reduces cognitive load, improves user satisfaction, and reduces support burden. Accessibility compliance ensures the application is usable by all users. Clear feedback and error handling builds user trust.

## Security & Performance Standards

**MUST** implement OIDC authentication for web UI access.
**MUST** enforce authorization based on group membership and namespace permissions.
**MUST** validate and sanitize all user inputs to prevent injection attacks.
**MUST** implement rate limiting on all public endpoints.
**MUST** use HTTPS/TLS for all network communication.
**MUST** scan dependencies for known vulnerabilities (automated CVE scanning).
**MUST** respond to API requests within 200ms (p95 latency target).
**MUST** maintain database query performance under 50ms for common operations.
**MUST** implement caching strategies for frequently accessed data.
**MUST** perform security reviews for all authentication and authorization changes.

**Rationale**: Security is non-negotiable for multi-tenant systems. Performance targets ensure responsive user experience. Proactive vulnerability scanning reduces exposure to known exploits.

## Development Workflow & Quality Gates

**MUST** require passing CI/CD pipeline before merging (tests, linting, type checking).
**MUST** perform code reviews for all changes (minimum one approver).
**MUST** enforce branch protection on main branch (no direct commits).
**MUST** require linear commit history (rebase or squash merge).
**MUST** include test coverage reports in PR checks (minimum 80% coverage).
**MUST** run integration tests in CI against ephemeral environments.
**MUST** perform automated security scanning (SAST) in CI pipeline.
**MUST** validate that PR descriptions reference related issues or user stories.
**MUST** ensure all new features include corresponding documentation updates.

**Rationale**: Quality gates prevent defects from reaching production. Code review distributes knowledge and improves design quality. Automated checks provide fast feedback and reduce review burden.

## Governance

This constitution supersedes all other development practices and coding conventions. All architectural decisions, code changes, and process modifications MUST comply with these principles. Deviations require explicit justification documented in a Complexity Tracking table (see plan-template.md).

**Amendment Process**:
- Constitution amendments require written proposal with rationale
- Amendments must include migration plan for existing code
- Version bump follows semantic versioning (MAJOR.MINOR.PATCH)
- All dependent templates (plan, spec, tasks) must be updated to reflect changes

**Compliance Review**:
- All pull requests MUST pass Constitution Check gates defined in plan-template.md
- Complex features requiring principle violations MUST document justification
- Quarterly reviews to assess principle adherence and identify technical debt
- Constitution serves as the canonical reference for all development decisions

**Version**: 1.0.0 | **Ratified**: 2026-05-10 | **Last Amended**: 2026-05-10
