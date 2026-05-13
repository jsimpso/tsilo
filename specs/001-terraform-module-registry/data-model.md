# Data Model: Private Terraform Module Registry

**Date**: 2026-05-10
**Phase**: 1 - Design & Contracts
**Purpose**: Define database schema, entities, relationships, and validation rules

## Entity Relationship Overview

```text
┌──────────────┐       ┌─────────────────┐       ┌──────────────────┐
│   Namespace  │◄──────│  Module         │◄──────│  ModuleVersion   │
│              │       │                 │       │                  │
│ - name       │  1:N  │ - namespace_id  │  1:N  │ - module_id      │
│              │       │ - name          │       │ - version        │
│              │       │ - provider      │       │ - inputs         │
└──────┬───────┘       └─────────────────┘       │ - outputs        │
       │                                          │ - readme         │
       │                                          │ - package_url    │
       │ N:M                                      └────────┬─────────┘
       │                                                   │
       │                                                   │ 1:N
       │                                                   │
┌──────▼────────────────┐                         ┌───────▼──────────┐
│ NamespacePermission   │                         │ DownloadMetric   │
│                       │                         │                  │
│ - namespace_id        │                         │ - version_id     │
│ - group_name          │                         │ - download_count │
│ - permission_level    │                         │ - last_download  │
└───────────────────────┘                         └──────────────────┘

                              ┌──────────────────────┐
                              │  User                │
                              │                      │
                              │ - id                 │
                              │ - email              │
                              │ - groups[]           │
                              │ - created_at         │
                              └──────┬───────────────┘
                                     │
                         ┌───────────┴───────────┐
                         │ 1:N                   │ 1:N
                         │                       │
             ┌───────────▼───────────┐   ┌───────▼──────────────────┐
             │  APIToken             │   │  OAuthAuthorizationCode  │
             │                       │   │                          │
             │ - token_hash          │   │ - code                   │
             │ - user_id             │   │ - user_id                │
             │ - scopes[]            │   │ - code_challenge (PKCE)  │
             │ - expires_at          │   │ - redirect_uri           │
             └───────────────────────┘   │ - expires_at (10 min)    │
                                         └──────────────────────────┘
```

## Core Entities

### Namespace

Logical container for modules representing teams, projects, or organizational units.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| name | VARCHAR(100) | UNIQUE, NOT NULL | Namespace identifier (e.g., "platform-team") |
| display_name | VARCHAR(200) | NULL | Human-readable name |
| description | TEXT | NULL | Namespace description |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Validation Rules**:
- name must match pattern: `^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$`
- name must be lowercase
- name cannot contain consecutive hyphens
- name is immutable after creation

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `name`

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "platform-team",
  "display_name": "Platform Engineering Team",
  "description": "Core infrastructure modules",
  "created_at": "2026-05-10T10:00:00Z",
  "updated_at": "2026-05-10T10:00:00Z"
}
```

---

### Module

Represents a Terraform module identified by namespace, name, and provider.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| namespace_id | UUID | FOREIGN KEY(Namespace.id), NOT NULL | Parent namespace |
| name | VARCHAR(100) | NOT NULL | Module name (e.g., "vpc") |
| provider | VARCHAR(50) | NOT NULL | Provider name (e.g., "aws", "gcp") |
| description | TEXT | NULL | Module description |
| source_url | VARCHAR(500) | NULL | Source repository URL |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Validation Rules**:
- Combination of (namespace_id, name, provider) must be unique
- name must match pattern: `^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$`
- provider must match pattern: `^[a-z0-9-]+$`
- name and provider are immutable after creation

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `(namespace_id, name, provider)`
- INDEX on `namespace_id` for filtering by namespace
- INDEX on `name` for search queries

**Example**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "namespace_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "vpc",
  "provider": "aws",
  "description": "AWS VPC module with public/private subnets",
  "source_url": "https://github.com/org/terraform-aws-vpc",
  "created_at": "2026-05-10T10:30:00Z",
  "updated_at": "2026-05-10T10:30:00Z"
}
```

---

### ModuleVersion

Represents a specific version of a module with metadata, documentation, and package location.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| module_id | UUID | FOREIGN KEY(Module.id), NOT NULL | Parent module |
| version | VARCHAR(50) | NOT NULL | Semantic version (e.g., "1.2.3") |
| inputs | JSONB | NOT NULL, DEFAULT '[]' | Input variable definitions |
| outputs | JSONB | NOT NULL, DEFAULT '[]' | Output value definitions |
| readme | TEXT | NULL | README documentation (Markdown) |
| package_url | VARCHAR(1000) | NOT NULL | S3/storage URL for module package |
| package_size_bytes | BIGINT | NOT NULL | Package size in bytes |
| checksum_sha256 | VARCHAR(64) | NOT NULL | SHA256 checksum of package |
| published_by | UUID | FOREIGN KEY(User.id), NULL | User who published this version |
| published_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Publication timestamp |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Validation Rules**:
- Combination of (module_id, version) must be unique
- version must be valid semantic version: `^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$`
- version is immutable after creation
- inputs must be array of objects with keys: name, type, description, default, required
- outputs must be array of objects with keys: name, description
- package_size_bytes must be > 0
- checksum_sha256 must be 64 hex characters

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `(module_id, version)`
- INDEX on `module_id` for listing versions
- INDEX on `published_at` for ordering

**Input Schema (JSONB)**:
```json
[
  {
    "name": "vpc_cidr",
    "type": "string",
    "description": "CIDR block for VPC",
    "default": "10.0.0.0/16",
    "required": false
  },
  {
    "name": "availability_zones",
    "type": "list(string)",
    "description": "List of AZs to deploy into",
    "required": true
  }
]
```

**Output Schema (JSONB)**:
```json
[
  {
    "name": "vpc_id",
    "description": "ID of the created VPC"
  },
  {
    "name": "private_subnet_ids",
    "description": "List of private subnet IDs"
  }
]
```

**Example**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "module_id": "660e8400-e29b-41d4-a716-446655440000",
  "version": "1.2.3",
  "inputs": [...],
  "outputs": [...],
  "readme": "# AWS VPC Module\n\nCreates a VPC...",
  "package_url": "s3://tsilo-modules/platform-team/vpc/aws/1.2.3/module.tar.gz",
  "package_size_bytes": 4096,
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "published_by": "880e8400-e29b-41d4-a716-446655440000",
  "published_at": "2026-05-10T11:00:00Z",
  "created_at": "2026-05-10T11:00:00Z"
}
```

---

### NamespacePermission

Maps groups to namespaces with permission levels (read, write).

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| namespace_id | UUID | FOREIGN KEY(Namespace.id), NOT NULL | Target namespace |
| group_name | VARCHAR(200) | NOT NULL | OIDC group identifier |
| permission_level | ENUM | NOT NULL | Permission level: 'read', 'write' |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Validation Rules**:
- Combination of (namespace_id, group_name, permission_level) must be unique
- permission_level must be one of: 'read', 'write'
- group_name must not be empty

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `(namespace_id, group_name, permission_level)`
- INDEX on `namespace_id` for permission lookups
- INDEX on `group_name` for user permission queries

**Permission Semantics**:
- `read`: Can download modules, view module metadata, search modules
- `write`: Includes read permissions + can upload modules, publish versions

**Example**:
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "namespace_id": "550e8400-e29b-41d4-a716-446655440000",
  "group_name": "platform-team-developers",
  "permission_level": "read",
  "created_at": "2026-05-10T09:00:00Z",
  "updated_at": "2026-05-10T09:00:00Z"
}
```

---

### User

Represents an authenticated user from OIDC provider.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| oidc_sub | VARCHAR(500) | UNIQUE, NOT NULL | OIDC subject claim (unique user ID) |
| email | VARCHAR(320) | NOT NULL | User email address |
| name | VARCHAR(200) | NULL | User display name |
| groups | JSONB | NOT NULL, DEFAULT '[]' | Array of group memberships |
| last_login_at | TIMESTAMP | NULL | Last login timestamp |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Account creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Validation Rules**:
- oidc_sub is immutable after creation (primary identity)
- email must be valid email format
- groups must be array of strings

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `oidc_sub`
- INDEX on `email` for lookups

**Example**:
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "oidc_sub": "google-oauth2|123456789",
  "email": "engineer@example.com",
  "name": "Jane Engineer",
  "groups": ["platform-team-developers", "all-engineers"],
  "last_login_at": "2026-05-10T12:00:00Z",
  "created_at": "2026-05-09T08:00:00Z",
  "updated_at": "2026-05-10T12:00:00Z"
}
```

---

### APIToken

Credentials for CI/CD pipeline authentication with scope limitations.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| token_hash | VARCHAR(128) | UNIQUE, NOT NULL | SHA256 hash of token value |
| user_id | UUID | FOREIGN KEY(User.id), NOT NULL | Token owner |
| name | VARCHAR(200) | NOT NULL | Human-readable token name |
| scopes | JSONB | NOT NULL, DEFAULT '[]' | Array of namespace scopes |
| last_used_at | TIMESTAMP | NULL | Last usage timestamp |
| expires_at | TIMESTAMP | NOT NULL | Token expiration timestamp |
| revoked_at | TIMESTAMP | NULL | Revocation timestamp (if revoked) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp |

**Validation Rules**:
- token_hash is immutable after creation
- scopes must be array of objects: `[{"namespace": "name", "permission": "read"|"write"}]`
- expires_at must be in the future at creation time
- Token is valid only if: expires_at > NOW() AND revoked_at IS NULL

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `token_hash`
- INDEX on `user_id` for listing user tokens
- INDEX on `expires_at` for cleanup queries

**Scopes Schema (JSONB)**:
```json
[
  {
    "namespace": "platform-team",
    "permission": "read"
  },
  {
    "namespace": "data-team",
    "permission": "write"
  }
]
```

**Example**:
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "token_hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
  "user_id": "880e8400-e29b-41d4-a716-446655440000",
  "name": "CI/CD Pipeline - Production",
  "scopes": [...],
  "last_used_at": "2026-05-10T11:30:00Z",
  "expires_at": "2027-05-10T00:00:00Z",
  "revoked_at": null,
  "created_at": "2026-05-10T10:00:00Z"
}
```

---

### OAuthAuthorizationCode

Temporary storage for OAuth 2.0 authorization codes used in Terraform CLI login flow with PKCE.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| code | VARCHAR(128) | UNIQUE, NOT NULL | Authorization code (random, URL-safe) |
| user_id | UUID | FOREIGN KEY(User.id), NOT NULL | User who authorized the request |
| client_id | VARCHAR(200) | NOT NULL | OAuth client identifier (e.g., "terraform-cli") |
| redirect_uri | VARCHAR(1000) | NOT NULL | Callback URL for code delivery |
| code_challenge | VARCHAR(128) | NOT NULL | PKCE code challenge (SHA256 hash) |
| code_challenge_method | VARCHAR(10) | NOT NULL | PKCE method (always "S256") |
| scopes | JSONB | NOT NULL, DEFAULT '[]' | Requested scopes (namespace permissions) |
| used_at | TIMESTAMP | NULL | Timestamp when code was exchanged for token |
| expires_at | TIMESTAMP | NOT NULL | Code expiration (10 minutes from creation) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Code creation timestamp |

**Validation Rules**:
- code must be cryptographically random, URL-safe, at least 32 characters
- code is single-use (used_at must be NULL when exchanging)
- code_challenge_method must be "S256" (other methods not supported)
- expires_at must be created_at + 10 minutes
- Code is valid only if: used_at IS NULL AND expires_at > NOW()

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `code`
- INDEX on `expires_at` for cleanup queries
- INDEX on `user_id` for user audit

**PKCE Validation**:
```python
# When exchanging code for token
stored_challenge = authorization_code.code_challenge
provided_verifier = request.code_verifier

# Compute challenge from verifier
computed_challenge = base64url(sha256(provided_verifier))

# Verify match
if computed_challenge != stored_challenge:
    raise InvalidGrantError("Code verifier does not match challenge")
```

**Example**:
```json
{
  "id": "cc0e8400-e29b-41d4-a716-446655440000",
  "code": "SplxlOBeZQQYbYS6WxSbIA",
  "user_id": "880e8400-e29b-41d4-a716-446655440000",
  "client_id": "terraform-cli",
  "redirect_uri": "http://localhost:10000/",
  "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "code_challenge_method": "S256",
  "scopes": [],
  "used_at": null,
  "expires_at": "2026-05-10T13:10:00Z",
  "created_at": "2026-05-10T13:00:00Z"
}
```

**Cleanup Strategy**:
- Expired codes deleted after 24 hours (used_at NULL AND expires_at < NOW() - INTERVAL '24 hours')
- Used codes deleted after 7 days (used_at IS NOT NULL AND used_at < NOW() - INTERVAL '7 days')
- Periodic cleanup job runs hourly

---

### DownloadMetric

Tracks usage data for module versions including download counts and timestamps.

**Fields**:
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Unique identifier |
| version_id | UUID | FOREIGN KEY(ModuleVersion.id), NOT NULL | Module version being tracked |
| download_count | BIGINT | NOT NULL, DEFAULT 0 | Total download count |
| last_download_at | TIMESTAMP | NULL | Timestamp of most recent download |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Record creation timestamp |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp |

**Validation Rules**:
- One record per version_id (unique constraint)
- download_count must be >= 0
- last_download_at must be <= NOW()

**Indexes**:
- PRIMARY KEY on `id`
- UNIQUE INDEX on `version_id`
- INDEX on `last_download_at` for finding stale versions

**Update Pattern**:
```sql
-- Increment on each download
UPDATE download_metric
SET download_count = download_count + 1,
    last_download_at = NOW(),
    updated_at = NOW()
WHERE version_id = ?;
```

**Example**:
```json
{
  "id": "bb0e8400-e29b-41d4-a716-446655440000",
  "version_id": "770e8400-e29b-41d4-a716-446655440000",
  "download_count": 1247,
  "last_download_at": "2026-05-10T12:30:00Z",
  "created_at": "2026-05-10T11:00:00Z",
  "updated_at": "2026-05-10T12:30:00Z"
}
```

---

## Relationships

### One-to-Many

1. **Namespace → Module** (1:N)
   - One namespace contains many modules
   - Foreign key: `Module.namespace_id → Namespace.id`
   - Cascade: DELETE namespace → DELETE all modules (with warning)

2. **Module → ModuleVersion** (1:N)
   - One module has many versions
   - Foreign key: `ModuleVersion.module_id → Module.id`
   - Cascade: DELETE module → DELETE all versions

3. **ModuleVersion → DownloadMetric** (1:1)
   - Each version has one metric record
   - Foreign key: `DownloadMetric.version_id → ModuleVersion.id`
   - Cascade: DELETE version → DELETE metric

4. **User → ModuleVersion** (1:N)
   - One user publishes many versions
   - Foreign key: `ModuleVersion.published_by → User.id`
   - Cascade: SET NULL on user deletion (preserve versions)

5. **User → APIToken** (1:N)
   - One user owns many API tokens
   - Foreign key: `APIToken.user_id → User.id`
   - Cascade: DELETE user → DELETE tokens

6. **User → OAuthAuthorizationCode** (1:N)
   - One user generates many authorization codes during login flows
   - Foreign key: `OAuthAuthorizationCode.user_id → User.id`
   - Cascade: DELETE user → DELETE auth codes

### Many-to-Many

1. **Namespace ↔ Group** (N:M via NamespacePermission)
   - Many namespaces can grant permissions to many groups
   - Groups are not stored in database (come from OIDC)
   - Join table: `NamespacePermission`

---

## Database Migration Strategy

### Alembic Configuration

Use Alembic for all schema changes with these conventions:

1. **Migration Naming**: `YYYYMMDD_HHMM_description.py`
2. **Reversibility**: All migrations must be reversible (implement `downgrade()`)
3. **Data Migrations**: Separate data migrations from schema migrations
4. **Testing**: Test migrations on copy of production data before applying

### Initial Schema Migration

```python
# alembic/versions/20260510_1000_initial_schema.py
def upgrade():
    # Create namespaces table
    op.create_table(
        'namespaces',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create modules table
    op.create_table(
        'modules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('namespace_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['namespace_id'], ['namespaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('namespace_id', 'name', 'provider')
    )

    # Create indexes
    op.create_index('idx_modules_namespace', 'modules', ['namespace_id'])
    op.create_index('idx_modules_name', 'modules', ['name'])

    # ... (continue for all tables)

def downgrade():
    op.drop_table('modules')
    op.drop_table('namespaces')
    # ... (reverse order)
```

---

## Data Integrity Rules

### Constraints

1. **Immutability**: namespace.name, module.name, module.provider, moduleversion.version cannot be updated
2. **Uniqueness**: (namespace.name), (namespace_id, module.name, module.provider), (module_id, version)
3. **Referential Integrity**: All foreign keys with appropriate cascade rules
4. **Version Format**: Semantic versioning regex validation
5. **Naming Patterns**: Lowercase alphanumeric with hyphens only

### Business Rules

1. **Version Immutability**: Once published, a version cannot be modified or deleted
2. **Namespace Deletion**: Requires manual intervention (prevent accidental data loss)
3. **Permission Inheritance**: Write permission implies read permission
4. **Token Expiration**: Automatically enforced at validation time
5. **Metric Initialization**: Create DownloadMetric record when ModuleVersion is created

---

## Performance Considerations

### Query Optimization

1. **Module Listing**: Index on (namespace_id, name) for fast filtering
2. **Version Lookups**: Index on (module_id, version) for direct access
3. **Permission Checks**: Index on (namespace_id, group_name) for auth queries
4. **Search**: Full-text search index on module.name, module.description (PostgreSQL GIN index)
5. **Metrics**: Index on last_download_at for deprecation queries

### Caching Strategy

1. **Module Metadata**: Cache for 5 minutes (frequently accessed, rarely changes)
2. **Permissions**: Cache for 1 minute (security-sensitive, changes occasionally)
3. **Version Lists**: Cache for 5 minutes (Terraform CLI frequently requests)
4. **Download URLs**: Generate on-demand (pre-signed URLs, short-lived)

### Data Retention

1. **Metrics**: Retain download metrics indefinitely (small footprint)
2. **API Tokens**: Auto-delete expired tokens after 90 days
3. **User Records**: Soft delete (set deleted_at) to preserve audit trail
4. **Module Versions**: Never delete (backward compatibility requirement)
