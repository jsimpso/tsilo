# Feature Specification: Private Terraform Module Registry

**Feature Branch**: `001-terraform-module-registry`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "Build an application that acts as a private registry for Terraform modules with Terraform CLI compatibility, web UI for browsing, OIDC authentication, multi-tenancy via namespaces, versioning support, and observability metrics."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Terraform CLI Module Download (Priority: P1)

As a DevOps engineer, I need to download Terraform modules from the private registry using standard Terraform CLI commands (`terraform init`) so that my infrastructure code can reference internal modules without changing my workflow.

**Why this priority**: This is the core value proposition - Terraform CLI compatibility. Without this, the registry cannot function as a Terraform module source.

**Independent Test**: Can be fully tested by running `terraform init` with a module source pointing to the registry and verifying the module downloads successfully. Delivers immediate value by enabling private module distribution.

**Acceptance Scenarios**:

1. **Given** a module exists in the registry at `namespace/module-name/provider`, **When** I run `terraform init` with source = `registry.example.com/namespace/module-name/provider`, **Then** Terraform downloads the module and I can use it in my configuration
2. **Given** multiple versions of a module exist (e.g., 1.0.0, 1.1.0, 2.0.0), **When** I specify version = "~> 1.0" in my Terraform code, **Then** the registry returns the latest compatible version (1.1.0)
3. **Given** I reference a module that doesn't exist, **When** I run `terraform init`, **Then** I receive a clear error message indicating the module was not found
4. **Given** I am authenticated to the registry, **When** I request a module from a namespace I have access to, **Then** the download succeeds
5. **Given** I am not authenticated or lack permissions, **When** I request a module, **Then** I receive an authentication/authorization error

---

### User Story 2 - Web UI Module Discovery (Priority: P1)

As a DevOps engineer, I need to browse and search for available modules through a web interface so that I can discover what modules are available and understand how to use them before adding them to my Terraform code.

**Why this priority**: Discovery is essential for module adoption. Engineers need to find modules and read documentation before they can use them.

**Independent Test**: Can be fully tested by accessing the web UI, searching for modules, viewing module details including documentation, inputs, and outputs. Delivers value by enabling self-service module discovery.

**Acceptance Scenarios**:

1. **Given** I am authenticated to the web UI, **When** I navigate to the homepage, **Then** I see a list of modules I have access to across all my authorized namespaces
2. **Given** I am on the homepage, **When** I enter a search term (e.g., "vpc"), **Then** I see all modules matching that term with their namespace, name, and description
3. **Given** I click on a module from the search results, **When** the module detail page loads, **Then** I see the module's README documentation, input variables with descriptions and types, and output values with descriptions
4. **Given** I am viewing a module detail page, **When** I look at version information, **Then** I see all available versions with release dates and can switch between versions to view version-specific documentation
5. **Given** I am viewing a module, **When** I need to use it, **Then** I see clear usage examples showing the correct Terraform syntax with the registry URL

---

### User Story 3 - Module Upload and Versioning (Priority: P2)

As a module author, I need to upload new modules and publish new versions of existing modules so that I can share my infrastructure code with my team and maintain backward compatibility.

**Why this priority**: Content management is required for the registry to have modules, but it's secondary to consumption (P1 stories). Teams can manually upload initial modules to test consumption flows first.

**Independent Test**: Can be fully tested by uploading a module via the web UI or API, verifying it appears in searches, and downloading it via Terraform CLI. Delivers value by enabling teams to publish internal modules.

**Acceptance Scenarios**:

1. **Given** I have permissions to publish to a namespace, **When** I upload a module package with a valid semantic version (e.g., 1.0.0), **Then** the module is stored and becomes available for download
2. **Given** a module version already exists (e.g., 1.0.0), **When** I attempt to upload the same version again, **Then** I receive an error indicating the version already exists
3. **Given** I upload a new version (e.g., 1.1.0) of an existing module, **When** the upload completes, **Then** both versions remain available and Terraform CLI users can reference either version
4. **Given** I upload a module, **When** the system processes it, **Then** inputs and outputs are automatically extracted and displayed in the web UI
5. **Given** I upload a module with a README file, **When** viewing the module in the web UI, **Then** the README is rendered as documentation

---

### User Story 4 - Namespace and Permission Management (Priority: P2)

As a platform administrator, I need to control who can publish modules to specific namespaces and who can download modules from those namespaces so that I can enforce organizational boundaries and maintain security.

**Why this priority**: Multi-tenancy and security are critical for organizational use, but the basic registry functions (download, browse, upload) can be tested first with a single namespace or open permissions.

**Independent Test**: Can be fully tested by creating namespaces, assigning users to groups, configuring namespace permissions based on groups, and verifying access control works for both downloads and uploads.

**Acceptance Scenarios**:

1. **Given** I am a platform administrator, **When** I create a new namespace (e.g., "platform-team"), **Then** the namespace is available for module storage
2. **Given** a namespace exists, **When** I configure OIDC group-based permissions (e.g., "platform-team-write" can publish, "platform-team-read" can download), **Then** users in those groups have the specified permissions
3. **Given** I am a user in the "platform-team-write" group, **When** I attempt to upload a module to the "platform-team" namespace, **Then** the upload succeeds
4. **Given** I am a user NOT in any authorized group for a namespace, **When** I attempt to upload or download modules from that namespace, **Then** I receive an authorization error
5. **Given** I am viewing the web UI, **When** I am not authorized for a namespace, **Then** modules in that namespace do not appear in my search results or browse lists

---

### User Story 5 - CI/CD Pipeline Authentication (Priority: P3)

As a DevOps engineer, I need to authenticate to the registry from CI/CD pipelines so that automated infrastructure deployments can download modules without interactive login.

**Why this priority**: Automation is important but can initially use manual processes or environment-based credentials. Core functionality (P1-P2) should be working first.

**Independent Test**: Can be fully tested by configuring a CI/CD pipeline with appropriate credentials, running `terraform init` in the pipeline, and verifying the module downloads successfully.

**Acceptance Scenarios**:

1. **Given** I have generated API credentials or tokens for my CI/CD pipeline, **When** the pipeline runs `terraform init` with credentials configured, **Then** the module downloads successfully
2. **Given** my pipeline credentials are scoped to specific namespaces, **When** the pipeline attempts to download modules from authorized namespaces, **Then** downloads succeed
3. **Given** my pipeline credentials are scoped to specific namespaces, **When** the pipeline attempts to download modules from unauthorized namespaces, **Then** the download fails with an authorization error
4. **Given** I need to rotate credentials, **When** I generate new credentials and revoke old ones, **Then** pipelines using old credentials fail and pipelines using new credentials succeed

---

### User Story 6 - Observability and Usage Metrics (Priority: P3)

As a module author or platform administrator, I need to view download metrics for modules including download counts and last download dates so that I can identify unused module versions for deprecation and understand module adoption.

**Why this priority**: Observability provides operational insight but is not required for core registry functionality. Teams can operate without metrics initially.

**Independent Test**: Can be fully tested by downloading modules via Terraform CLI, waiting for metrics to update, then viewing metrics in the web UI and verifying download counts and timestamps are accurate.

**Acceptance Scenarios**:

1. **Given** a module version has been downloaded, **When** I view the module detail page, **Then** I see the total download count for that version
2. **Given** a module version was downloaded recently, **When** I view the module metrics, **Then** I see the timestamp of the most recent download
3. **Given** I am viewing a module with multiple versions, **When** I look at version metrics, **Then** I can compare download counts across versions to identify which versions are actively used
4. **Given** an old module version has not been downloaded in 90 days, **When** I view the metrics, **Then** this version is clearly flagged as potentially deprecated
5. **Given** I am a platform administrator, **When** I access system-wide metrics, **Then** I see overall download counts, most popular modules, and namespace usage statistics

---

### Edge Cases

- What happens when a user uploads a module with an invalid semantic version format (e.g., "v1", "latest", "1.0")?
- How does the system handle module packages with missing required metadata (no inputs/outputs defined)?
- What happens when a Terraform CLI request specifies a version constraint that matches no available versions?
- How does the system handle concurrent uploads of the same module version by different users?
- What happens when a namespace is deleted but modules in that namespace are still referenced in active Terraform code?
- How does authentication work when OIDC provider is temporarily unavailable?
- What happens when module documentation (README) contains malicious content or very large files?
- How does the system handle requests for modules from namespaces that don't exist?

## Requirements *(mandatory)*

### Functional Requirements

**Registry API & Terraform CLI Compatibility**:

- **FR-001**: System MUST implement the Terraform Module Registry Protocol as documented in docs/registry_api.md
- **FR-002**: System MUST respond to module discovery requests (GET /.well-known/terraform.json) with service metadata
- **FR-003**: System MUST respond to module version listing requests (GET /:namespace/:name/:provider/versions) with all available versions in descending order
- **FR-004**: System MUST respond to module download requests (GET /:namespace/:name/:provider/:version/download) with a download URL or direct module package
- **FR-005**: System MUST accept and validate semantic version constraints from Terraform CLI (e.g., "~> 1.0", ">= 1.0.0, < 2.0.0")
- **FR-006**: System MUST serve module packages in a format compatible with Terraform CLI (typically .tar.gz or .zip archives)

**Web UI**:

- **FR-007**: System MUST provide a web interface for browsing all modules the authenticated user has access to
- **FR-008**: System MUST provide search functionality across module names, descriptions, and namespaces
- **FR-009**: System MUST display module detail pages showing README documentation, input variables with names/types/descriptions, and output values with names/descriptions
- **FR-010**: System MUST display all available versions for each module with version numbers and release dates
- **FR-011**: System MUST allow switching between versions to view version-specific documentation and metadata
- **FR-012**: System MUST provide usage examples showing the correct registry URL syntax for Terraform code
- **FR-013**: System MUST implement responsive design supporting both desktop and mobile viewports
- **FR-014**: System MUST provide a modern, sleek user interface with consistent navigation patterns

**Authentication & Authorization**:

- **FR-015**: System MUST authenticate web UI users via OIDC (OpenID Connect)
- **FR-016**: System MUST extract group membership from OIDC claims or external directory
- **FR-017**: System MUST support authentication for CI/CD pipelines via API tokens or service credentials
- **FR-018**: System MUST enforce namespace-level permissions based on group membership
- **FR-019**: System MUST distinguish between read permissions (download modules) and write permissions (upload modules) at the namespace level
- **FR-020**: System MUST reject unauthenticated requests for module downloads and uploads
- **FR-021**: System MUST reject requests from authenticated users who lack permissions for the target namespace

**Multi-Tenancy & Namespaces**:

- **FR-022**: System MUST organize modules into namespaces for logical separation between teams or projects
- **FR-023**: System MUST enforce unique module identifiers within a namespace using the pattern: namespace/name/provider
- **FR-024**: System MUST allow the same module name to exist in different namespaces
- **FR-025**: System MUST prevent users from accessing modules in namespaces they are not authorized for

**Module Upload & Versioning**:

- **FR-026**: System MUST accept module uploads via web UI or API
- **FR-027**: System MUST validate uploaded modules have valid semantic version numbers (MAJOR.MINOR.PATCH)
- **FR-028**: System MUST reject module uploads with version numbers that already exist for that module
- **FR-029**: System MUST support storing multiple versions of the same module simultaneously
- **FR-030**: System MUST preserve all published module versions to maintain backward compatibility for existing Terraform code
- **FR-031**: System MUST extract input variables and output values from uploaded modules
- **FR-032**: System MUST extract README or documentation files from uploaded modules
- **FR-033**: System MUST validate module package structure before accepting uploads

**Observability & Metrics**:

- **FR-034**: System MUST track download counts for each module version
- **FR-035**: System MUST record timestamps of the most recent download for each module version
- **FR-036**: System MUST display download metrics in the web UI on module detail pages
- **FR-037**: System MUST provide system-wide metrics for platform administrators including total downloads, most popular modules, and namespace usage
- **FR-038**: System MUST flag module versions that have not been downloaded recently (e.g., 90+ days) as potentially deprecated

### Key Entities

- **Module**: Represents a Terraform module identified by namespace, name, and provider (e.g., "platform/vpc/aws"). Contains metadata, documentation, and relationships to versions.

- **ModuleVersion**: Represents a specific version of a module (e.g., "1.2.3"). Contains semantic version number, input variables, output values, documentation, package location, upload timestamp, and download metrics.

- **Namespace**: Logical container for modules representing teams, projects, or organizational units (e.g., "platform-team", "data-team"). Contains name and permission mappings.

- **User**: Authenticated user with identity from OIDC provider, group memberships, and associated permissions.

- **NamespacePermission**: Maps groups to namespaces with permission levels (read, write). Determines who can download and upload modules in each namespace.

- **DownloadMetric**: Tracks usage data for module versions including download count, last download timestamp, and download history for trend analysis.

- **APIToken**: Credentials for CI/CD pipeline authentication with scope limitations and expiration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: DevOps engineers can successfully download modules using `terraform init` within 5 seconds for modules under 10MB
- **SC-002**: Users can discover and view module documentation through the web UI in under 10 seconds from search to documentation display
- **SC-003**: 95% of module searches return relevant results on the first page
- **SC-004**: Module uploads complete within 30 seconds for packages under 50MB
- **SC-005**: System supports at least 100 concurrent Terraform CLI downloads without performance degradation
- **SC-006**: Download metrics are updated and visible in the web UI within 1 minute of a download occurring
- **SC-007**: 90% of users can complete their first module download via Terraform CLI without consulting documentation beyond the module registry URL
- **SC-008**: System maintains backward compatibility - existing Terraform code continues to work when new module versions are published
- **SC-009**: Unauthorized access attempts are blocked 100% of the time with clear error messages
- **SC-010**: The web UI is accessible and usable on mobile devices with screens 375px width or larger

## Assumptions

- Users have basic familiarity with Terraform and understand concepts like modules, versions, and providers
- The OIDC provider is already configured and available for authentication
- OIDC provider includes group membership in standard claims or via a userinfo endpoint
- Module packages will be uploaded as standard Terraform module directory structures (with variables.tf, outputs.tf, main.tf, etc.)
- Semantic versioning conventions are followed by module authors
- The registry will be hosted on a private network or behind authentication - public anonymous access is not required
- Module sizes are typically under 50MB; very large modules (>100MB) are edge cases
- Modules contain documentation in README.md files using standard Markdown format
- Initial deployment will serve a single organization; federation across multiple registries is out of scope for v1
- Module integrity (checksum validation, signing) can be added in future iterations if needed
- Terraform CLI version 0.12 or newer will be used (modern module syntax)
