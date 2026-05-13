# Web UI API Contracts

**Date**: 2026-05-10
**Phase**: 1 - Design & Contracts
**Purpose**: Define REST API contracts for Web UI module browsing and management

## Overview

These endpoints support the web UI for browsing, searching, and managing modules. All endpoints require OIDC authentication except static assets.

**Base URL**: `https://registry.example.com/api`
**Authentication**: Session cookie (OIDC) or Bearer token
**Content-Type**: `application/json`

---

## Authentication Endpoints

### GET /auth/login

**Purpose**: Initiate OIDC login flow

**Authentication**: Not required

**Request**:
```http
GET /auth/login HTTP/1.1
Host: registry.example.com
```

**Response** (302 Redirect):
```http
HTTP/1.1 302 Found
Location: https://oidc-provider.example.com/authorize?client_id=...&redirect_uri=...&response_type=code&scope=openid+profile+email+groups
```

---

### GET /auth/callback

**Purpose**: OIDC callback endpoint (handles authorization code)

**Authentication**: Not required (public callback)

**Query Parameters**:
- `code` (string): Authorization code from OIDC provider
- `state` (string): CSRF protection state

**Request**:
```http
GET /auth/callback?code=AUTH_CODE&state=STATE_VALUE HTTP/1.1
Host: registry.example.com
```

**Response** (302 Redirect with session cookie):
```http
HTTP/1.1 302 Found
Location: /
Set-Cookie: session=eyJhbGc...; HttpOnly; Secure; SameSite=Lax; Max-Age=3600
```

---

### POST /auth/logout

**Purpose**: Terminate user session

**Authentication**: Required (session cookie)

**Request**:
```http
POST /auth/logout HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "message": "Logged out successfully"
}
```

**Response Headers**:
```http
Set-Cookie: session=; HttpOnly; Secure; SameSite=Lax; Max-Age=0
```

---

### GET /auth/me

**Purpose**: Get current user information

**Authentication**: Required (session cookie)

**Request**:
```http
GET /auth/me HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "user": {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "email": "engineer@example.com",
    "name": "Jane Engineer",
    "groups": ["platform-team-developers", "all-engineers"]
  },
  "permissions": {
    "platform-team": ["read", "write"],
    "data-team": ["read"]
  }
}
```

---

## Module Browsing

### GET /api/modules

**Purpose**: List modules with filtering and pagination

**Authentication**: Required

**Authorization**: Returns only modules from namespaces user has read access to

**Query Parameters**:
- `namespace` (string, optional): Filter by namespace
- `search` (string, optional): Search across name and description
- `page` (integer, default: 1): Page number
- `per_page` (integer, default: 20, max: 100): Results per page

**Request**:
```http
GET /api/modules?search=vpc&page=1&per_page=20 HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "modules": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "namespace": "platform-team",
      "name": "vpc",
      "provider": "aws",
      "description": "AWS VPC module with public/private subnets",
      "latest_version": "1.2.3",
      "version_count": 5,
      "total_downloads": 1247,
      "last_updated": "2026-05-10T11:00:00Z"
    },
    {
      "id": "cc0e8400-e29b-41d4-a716-446655440000",
      "namespace": "network-team",
      "name": "vpc-peering",
      "provider": "aws",
      "description": "VPC peering connection module",
      "latest_version": "2.1.0",
      "version_count": 8,
      "total_downloads": 523,
      "last_updated": "2026-05-09T14:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 3,
    "total_count": 47
  }
}
```

**Spec Alignment**:
- FR-007: System MUST provide web interface for browsing modules
- FR-008: System MUST provide search functionality
- FR-025: System MUST prevent unauthorized namespace access

---

### GET /api/modules/:namespace/:name/:provider

**Purpose**: Get detailed module information

**Authentication**: Required

**Authorization**: User must have read access to namespace

**Path Parameters**:
- `namespace`: Namespace identifier
- `name`: Module name
- `provider`: Provider name

**Request**:
```http
GET /api/modules/platform-team/vpc/aws HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "module": {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "namespace": "platform-team",
    "name": "vpc",
    "provider": "aws",
    "description": "AWS VPC module with public/private subnets",
    "source_url": "https://github.com/org/terraform-aws-vpc",
    "created_at": "2026-05-01T10:00:00Z",
    "versions": [
      {
        "version": "1.2.3",
        "published_at": "2026-05-10T11:00:00Z",
        "download_count": 845,
        "last_download_at": "2026-05-10T12:30:00Z"
      },
      {
        "version": "1.2.2",
        "published_at": "2026-05-05T09:00:00Z",
        "download_count": 302,
        "last_download_at": "2026-05-08T16:00:00Z"
      },
      {
        "version": "1.0.0",
        "published_at": "2026-05-01T10:00:00Z",
        "download_count": 100,
        "last_download_at": "2026-05-03T11:00:00Z",
        "deprecated": true,
        "deprecation_reason": "No downloads in 90+ days"
      }
    ],
    "latest_version": "1.2.3",
    "total_downloads": 1247
  }
}
```

**Spec Alignment**:
- FR-009: System MUST display module detail pages
- FR-010: System MUST display all available versions
- FR-038: System MUST flag old versions as deprecated

---

### GET /api/modules/:namespace/:name/:provider/:version

**Purpose**: Get specific version details including inputs, outputs, and README

**Authentication**: Required

**Authorization**: User must have read access to namespace

**Path Parameters**:
- `namespace`: Namespace identifier
- `name`: Module name
- `provider`: Provider name
- `version`: Semantic version

**Request**:
```http
GET /api/modules/platform-team/vpc/aws/1.2.3 HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "version": {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "module_id": "660e8400-e29b-41d4-a716-446655440000",
    "version": "1.2.3",
    "inputs": [
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
    ],
    "outputs": [
      {
        "name": "vpc_id",
        "description": "ID of the created VPC"
      },
      {
        "name": "private_subnet_ids",
        "description": "List of private subnet IDs"
      }
    ],
    "readme": "# AWS VPC Module\n\nCreates a VPC with public and private subnets...",
    "usage_example": "module \"vpc\" {\n  source  = \"registry.example.com/platform-team/vpc/aws\"\n  version = \"1.2.3\"\n\n  vpc_cidr = \"10.0.0.0/16\"\n  availability_zones = [\"us-east-1a\", \"us-east-1b\"]\n}",
    "package_size_bytes": 4096,
    "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "published_by": {
      "id": "880e8400-e29b-41d4-a716-446655440000",
      "name": "Jane Engineer",
      "email": "engineer@example.com"
    },
    "published_at": "2026-05-10T11:00:00Z",
    "download_count": 845,
    "last_download_at": "2026-05-10T12:30:00Z"
  }
}
```

**Spec Alignment**:
- FR-009: Display README documentation, inputs with types/descriptions, outputs with descriptions
- FR-011: Allow switching between versions
- FR-012: Provide usage examples
- FR-036: Display download metrics

---

## Namespace Management

### GET /api/namespaces

**Purpose**: List namespaces user has access to

**Authentication**: Required

**Request**:
```http
GET /api/namespaces HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "namespaces": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "platform-team",
      "display_name": "Platform Engineering Team",
      "description": "Core infrastructure modules",
      "module_count": 15,
      "permissions": ["read", "write"],
      "created_at": "2026-04-01T10:00:00Z"
    },
    {
      "id": "dd0e8400-e29b-41d4-a716-446655440000",
      "name": "data-team",
      "display_name": "Data Engineering Team",
      "description": "Data pipeline modules",
      "module_count": 8,
      "permissions": ["read"],
      "created_at": "2026-04-15T14:00:00Z"
    }
  ]
}
```

---

### POST /api/namespaces

**Purpose**: Create a new namespace (admin only)

**Authentication**: Required

**Authorization**: User must be in admin group

**Request**:
```http
POST /api/namespaces HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
Content-Type: application/json

{
  "name": "security-team",
  "display_name": "Security Engineering Team",
  "description": "Security and compliance modules"
}
```

**Response** (201 Created):
```json
{
  "namespace": {
    "id": "ee0e8400-e29b-41d4-a716-446655440000",
    "name": "security-team",
    "display_name": "Security Engineering Team",
    "description": "Security and compliance modules",
    "module_count": 0,
    "created_at": "2026-05-10T13:00:00Z"
  }
}
```

---

### GET /api/namespaces/:namespace/permissions

**Purpose**: List permissions for a namespace

**Authentication**: Required

**Authorization**: User must have admin access or be in the namespace

**Request**:
```http
GET /api/namespaces/platform-team/permissions HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "permissions": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "group_name": "platform-team-developers",
      "permission_level": "read",
      "created_at": "2026-04-01T10:00:00Z"
    },
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "group_name": "platform-team-leads",
      "permission_level": "write",
      "created_at": "2026-04-01T10:00:00Z"
    }
  ]
}
```

---

## Metrics & Analytics

### GET /api/metrics/overview

**Purpose**: Get system-wide metrics (admin only)

**Authentication**: Required

**Authorization**: User must be in admin group

**Request**:
```http
GET /api/metrics/overview HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "metrics": {
    "total_modules": 156,
    "total_versions": 1024,
    "total_namespaces": 23,
    "total_downloads": 45678,
    "downloads_last_30_days": 12345,
    "active_users_last_30_days": 89,
    "top_modules": [
      {
        "namespace": "platform-team",
        "name": "vpc",
        "provider": "aws",
        "downloads": 1247
      },
      {
        "namespace": "platform-team",
        "name": "eks-cluster",
        "provider": "aws",
        "downloads": 876
      }
    ],
    "namespace_usage": [
      {
        "namespace": "platform-team",
        "module_count": 15,
        "version_count": 89,
        "total_downloads": 8765
      },
      {
        "namespace": "data-team",
        "module_count": 8,
        "version_count": 45,
        "total_downloads": 3421
      }
    ]
  }
}
```

**Spec Alignment**:
- FR-037: Provide system-wide metrics for administrators

---

### GET /api/metrics/modules/:namespace/:name/:provider

**Purpose**: Get detailed metrics for a specific module

**Authentication**: Required

**Authorization**: User must have read access to namespace

**Request**:
```http
GET /api/metrics/modules/platform-team/vpc/aws HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "module": {
    "namespace": "platform-team",
    "name": "vpc",
    "provider": "aws"
  },
  "metrics": {
    "total_downloads": 1247,
    "downloads_by_version": [
      {
        "version": "1.2.3",
        "download_count": 845,
        "last_download_at": "2026-05-10T12:30:00Z"
      },
      {
        "version": "1.2.2",
        "download_count": 302,
        "last_download_at": "2026-05-08T16:00:00Z"
      },
      {
        "version": "1.0.0",
        "download_count": 100,
        "last_download_at": "2026-05-03T11:00:00Z",
        "deprecated": true
      }
    ],
    "downloads_over_time": [
      {
        "date": "2026-05-10",
        "count": 42
      },
      {
        "date": "2026-05-09",
        "count": 38
      }
    ]
  }
}
```

**Spec Alignment**:
- FR-034: Track download counts for each version
- FR-035: Record timestamps of recent downloads
- FR-036: Display download metrics in web UI

---

## API Token Management

### GET /api/tokens

**Purpose**: List user's API tokens

**Authentication**: Required

**Request**:
```http
GET /api/tokens HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (200 OK):
```json
{
  "tokens": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "name": "CI/CD Pipeline - Production",
      "scopes": [
        {
          "namespace": "platform-team",
          "permission": "read"
        }
      ],
      "last_used_at": "2026-05-10T11:30:00Z",
      "expires_at": "2027-05-10T00:00:00Z",
      "created_at": "2026-05-10T10:00:00Z"
    }
  ]
}
```

---

### POST /api/tokens

**Purpose**: Create a new API token

**Authentication**: Required

**Request**:
```http
POST /api/tokens HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
Content-Type: application/json

{
  "name": "CI/CD Pipeline - Staging",
  "scopes": [
    {
      "namespace": "platform-team",
      "permission": "read"
    },
    {
      "namespace": "data-team",
      "permission": "read"
    }
  ],
  "expires_in_days": 365
}
```

**Response** (201 Created):
```json
{
  "token": {
    "id": "bb0e8400-e29b-41d4-a716-446655440000",
    "name": "CI/CD Pipeline - Staging",
    "token_value": "tsilo_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
    "scopes": [
      {
        "namespace": "platform-team",
        "permission": "read"
      },
      {
        "namespace": "data-team",
        "permission": "read"
      }
    ],
    "expires_at": "2027-05-10T00:00:00Z",
    "created_at": "2026-05-10T13:00:00Z"
  },
  "warning": "Save this token now. You won't be able to see it again!"
}
```

**Note**: `token_value` is only returned once at creation time

---

### DELETE /api/tokens/:id

**Purpose**: Revoke an API token

**Authentication**: Required

**Authorization**: User must own the token

**Request**:
```http
DELETE /api/tokens/bb0e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: registry.example.com
Cookie: session=eyJhbGc...
```

**Response** (204 No Content)

**Spec Alignment**:
- FR-017: Support authentication for CI/CD via API tokens

---

## Response Format Standards

### Success Responses

All successful responses return data in a consistent structure:

```json
{
  "resource_name": { /* resource data */ },
  "meta": { /* optional metadata */ }
}
```

### Error Responses

All errors use JSON:API error format:

```json
{
  "errors": [
    {
      "status": "400",
      "title": "Bad Request",
      "detail": "Validation failed: name cannot be empty",
      "source": {
        "pointer": "/data/attributes/name"
      }
    }
  ]
}
```

### Pagination

Paginated responses include pagination metadata:

```json
{
  "resources": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_count": 94
  }
}
```

---

## Frontend Integration Notes

### Session Management

- Session cookie is httpOnly, secure, SameSite=Lax
- Cookie expires after 1 hour of inactivity
- Refresh token flow extends session automatically
- Logout clears session cookie

### CSRF Protection

- All POST/PUT/DELETE requests require CSRF token
- CSRF token provided in meta tag: `<meta name="csrf-token" content="...">`
- Include in requests via header: `X-CSRF-Token: ...`

### Loading States

UI must show loading indicators for async operations:
- Module list loading
- Search in progress
- Module detail loading
- Version switching

### Error Handling

UI must display user-friendly error messages:
- Network errors: "Unable to connect. Please try again."
- 403 errors: "You don't have permission to access this resource."
- 404 errors: "Module not found. It may have been deleted."
- 500 errors: "Something went wrong. Please try again later."

**Spec Alignment**:
- FR-013: Responsive design
- FR-014: Modern, sleek UI with consistent navigation
- XII. UX Consistency: Loading states, error messages with actionable guidance
