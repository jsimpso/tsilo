# Terraform Registry Protocol API Contracts

**Date**: 2026-05-10
**Phase**: 1 - Design & Contracts
**Purpose**: Define REST API contracts for Terraform Module Registry Protocol compliance
**Reference**: docs/registry_api.md (Terraform Module Registry Protocol specification)

## Overview

This registry implements the Terraform Module Registry Protocol, enabling `terraform init` to download modules. All endpoints follow the protocol specification with additional authentication and authorization requirements.

**Base URL**: `https://registry.example.com`
**Protocol Version**: Terraform 0.12+
**Authentication**: Bearer token (OIDC or API token) in `Authorization` header

---

## Service Discovery

### GET /.well-known/terraform.json

**Purpose**: Terraform service discovery endpoint (required by protocol)

**Authentication**: Not required (public endpoint)

**Request**:
```http
GET /.well-known/terraform.json HTTP/1.1
Host: registry.example.com
```

**Response** (200 OK):
```json
{
  "modules.v1": "/v1/modules/"
}
```

**Response Headers**:
```http
Content-Type: application/json
Cache-Control: public, max-age=3600
```

**Spec Alignment**: FR-002 - System MUST respond to module discovery requests

**Implementation Notes**:
- Static endpoint, can be cached for 1 hour
- No authentication required (protocol requirement)
- Must return exact structure specified by Terraform

---

## Module Version Listing

### GET /v1/modules/:namespace/:name/:provider/versions

**Purpose**: List all available versions for a module

**Authentication**: Required (Bearer token)

**Authorization**: User must have read access to the namespace

**Path Parameters**:
- `namespace` (string): Namespace identifier (e.g., "platform-team")
- `name` (string): Module name (e.g., "vpc")
- `provider` (string): Provider name (e.g., "aws")

**Request**:
```http
GET /v1/modules/platform-team/vpc/aws/versions HTTP/1.1
Host: registry.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response** (200 OK):
```json
{
  "modules": [
    {
      "versions": [
        {
          "version": "2.0.0"
        },
        {
          "version": "1.2.3"
        },
        {
          "version": "1.2.2"
        },
        {
          "version": "1.0.0"
        }
      ]
    }
  ]
}
```

**Response Headers**:
```http
Content-Type: application/json
Cache-Control: private, max-age=300
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
```

**Error Responses**:

- **401 Unauthorized**: Missing or invalid authentication token
```json
{
  "errors": [
    {
      "status": "401",
      "title": "Unauthorized",
      "detail": "Valid authentication token required"
    }
  ]
}
```

- **403 Forbidden**: User lacks read permission for namespace
```json
{
  "errors": [
    {
      "status": "403",
      "title": "Forbidden",
      "detail": "You do not have read access to namespace 'platform-team'"
    }
  ]
}
```

- **404 Not Found**: Module does not exist
```json
{
  "errors": [
    {
      "status": "404",
      "title": "Not Found",
      "detail": "Module 'platform-team/vpc/aws' not found"
    }
  ]
}
```

**Spec Alignment**:
- FR-003: System MUST respond to module version listing requests with all available versions in descending order
- FR-020: System MUST reject unauthenticated requests
- FR-021: System MUST reject requests from users lacking permissions

**Implementation Notes**:
- Versions MUST be returned in descending semantic version order
- Cache response for 5 minutes (versions rarely change)
- Rate limit per user: 1000 requests/hour
- Log request for metrics (module popularity)

---

## Module Download

### GET /v1/modules/:namespace/:name/:provider/:version/download

**Purpose**: Provide download URL for a specific module version

**Authentication**: Required (Bearer token)

**Authorization**: User must have read access to the namespace

**Path Parameters**:
- `namespace` (string): Namespace identifier
- `name` (string): Module name
- `provider` (string): Provider name
- `version` (string): Semantic version (e.g., "1.2.3")

**Request**:
```http
GET /v1/modules/platform-team/vpc/aws/1.2.3/download HTTP/1.1
Host: registry.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response** (204 No Content with X-Terraform-Get header):
```http
HTTP/1.1 204 No Content
X-Terraform-Get: https://s3.amazonaws.com/tsilo-modules/platform-team/vpc/aws/1.2.3/module.tar.gz?X-Amz-Algorithm=...
Cache-Control: no-store
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 998
```

**Alternative Response** (302 Redirect):
```http
HTTP/1.1 302 Found
Location: https://s3.amazonaws.com/tsilo-modules/platform-team/vpc/aws/1.2.3/module.tar.gz?X-Amz-Algorithm=...
```

**Error Responses**:

- **401 Unauthorized**: Missing or invalid authentication token
```json
{
  "errors": [
    {
      "status": "401",
      "title": "Unauthorized",
      "detail": "Valid authentication token required"
    }
  ]
}
```

- **403 Forbidden**: User lacks read permission for namespace
```json
{
  "errors": [
    {
      "status": "403",
      "title": "Forbidden",
      "detail": "You do not have read access to namespace 'platform-team'"
    }
  ]
}
```

- **404 Not Found**: Module version does not exist
```json
{
  "errors": [
    {
      "status": "404",
      "title": "Not Found",
      "detail": "Version '1.2.3' of module 'platform-team/vpc/aws' not found"
    }
  ]
}
```

**Spec Alignment**:
- FR-004: System MUST respond to module download requests with download URL or direct module package
- FR-006: System MUST serve module packages in Terraform CLI compatible format
- SC-001: Download must complete within 5 seconds for modules under 10MB

**Implementation Notes**:
- Return pre-signed S3 URL (valid for 15 minutes)
- Increment download counter asynchronously (don't block response)
- Update last_download_at timestamp for metrics
- Log download event with user, namespace, module, version for observability
- Package format: .tar.gz with module files at root level
- DO NOT cache this endpoint (need to track each download)

**Package Structure**:
```text
module.tar.gz
├── main.tf
├── variables.tf
├── outputs.tf
├── README.md
└── (other .tf files)
```

---

## Module Upload

### POST /v1/modules/:namespace/:name/:provider/:version

**Purpose**: Upload a new module version

**Authentication**: Required (Bearer token)

**Authorization**: User must have write access to the namespace

**Path Parameters**:
- `namespace` (string): Namespace identifier
- `name` (string): Module name
- `provider` (string): Provider name
- `version` (string): Semantic version

**Request**:
```http
POST /v1/modules/platform-team/vpc/aws/1.2.3 HTTP/1.1
Host: registry.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary
Content-Length: 4096

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="module.tar.gz"
Content-Type: application/gzip

<binary data>
------WebKitFormBoundary--
```

**Response** (201 Created):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "namespace": "platform-team",
  "name": "vpc",
  "provider": "aws",
  "version": "1.2.3",
  "inputs": [
    {
      "name": "vpc_cidr",
      "type": "string",
      "description": "CIDR block for VPC",
      "default": "10.0.0.0/16",
      "required": false
    }
  ],
  "outputs": [
    {
      "name": "vpc_id",
      "description": "ID of the created VPC"
    }
  ],
  "package_url": "s3://tsilo-modules/platform-team/vpc/aws/1.2.3/module.tar.gz",
  "package_size_bytes": 4096,
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "published_at": "2026-05-10T11:00:00Z"
}
```

**Error Responses**:

- **400 Bad Request**: Invalid module package or version format
```json
{
  "errors": [
    {
      "status": "400",
      "title": "Bad Request",
      "detail": "Invalid semantic version format: '1.0'. Expected format: MAJOR.MINOR.PATCH"
    }
  ]
}
```

- **401 Unauthorized**: Missing or invalid authentication token
```json
{
  "errors": [
    {
      "status": "401",
      "title": "Unauthorized",
      "detail": "Valid authentication token required"
    }
  ]
}
```

- **403 Forbidden**: User lacks write permission for namespace
```json
{
  "errors": [
    {
      "status": "403",
      "title": "Forbidden",
      "detail": "You do not have write access to namespace 'platform-team'"
    }
  ]
}
```

- **409 Conflict**: Version already exists
```json
{
  "errors": [
    {
      "status": "409",
      "title": "Conflict",
      "detail": "Version '1.2.3' of module 'platform-team/vpc/aws' already exists"
    }
  ]
}
```

- **413 Payload Too Large**: Module package exceeds size limit
```json
{
  "errors": [
    {
      "status": "413",
      "title": "Payload Too Large",
      "detail": "Module package size 105906176 bytes exceeds limit of 104857600 bytes (100 MB)"
    }
  ]
}
```

**Spec Alignment**:
- FR-026: System MUST accept module uploads via web UI or API
- FR-027: System MUST validate semantic version numbers
- FR-028: System MUST reject duplicate version uploads
- FR-031: System MUST extract input variables and output values
- FR-033: System MUST validate module package structure
- SC-004: Module uploads complete within 30 seconds for packages under 50MB

**Validation Rules**:
1. Version format must be valid semantic version (MAJOR.MINOR.PATCH)
2. Package must be valid .tar.gz or .zip archive
3. Package must contain at least one .tf file
4. Package size must be <= 100 MB (configurable)
5. All .tf files must be valid Terraform syntax
6. Extract and parse variables.tf for inputs
7. Extract and parse outputs.tf for outputs
8. Extract README.md if present

**Implementation Notes**:
- Upload to S3 with server-side encryption
- Calculate SHA256 checksum during upload
- Parse Terraform files to extract inputs/outputs
- Create DownloadMetric record initialized to 0
- Return detailed validation errors (which file failed, what error)

---

## Rate Limiting

All endpoints implement rate limiting per user/token:

**Limits**:
- Unauthenticated: 100 requests/hour (service discovery only)
- Authenticated (read operations): 1000 requests/hour
- Authenticated (write operations): 100 requests/hour

**Headers** (included in all responses):
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 998
X-RateLimit-Reset: 1683723600
```

**Response** (429 Too Many Requests):
```json
{
  "errors": [
    {
      "status": "429",
      "title": "Too Many Requests",
      "detail": "Rate limit exceeded. Limit: 1000 requests/hour. Retry after: 2026-05-10T13:00:00Z"
    }
  ]
}
```

---

## Error Response Format

All errors follow JSON:API error format:

```json
{
  "errors": [
    {
      "status": "400",
      "title": "Bad Request",
      "detail": "Detailed error message here",
      "source": {
        "parameter": "version"
      }
    }
  ]
}
```

**Error Fields**:
- `status`: HTTP status code as string
- `title`: Short, human-readable summary
- `detail`: Detailed, actionable error message
- `source` (optional): Location of error (parameter, pointer, header)

---

## Security Headers

All responses include security headers:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

---

## CORS Configuration

API endpoints support CORS for browser-based clients:

```http
Access-Control-Allow-Origin: https://registry.example.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400
```

---

## Observability

### Request Logging

All requests are logged in structured JSON format:

```json
{
  "timestamp": "2026-05-10T11:00:00Z",
  "method": "GET",
  "path": "/v1/modules/platform-team/vpc/aws/versions",
  "status": 200,
  "duration_ms": 45,
  "user_id": "880e8400-e29b-41d4-a716-446655440000",
  "ip_address": "203.0.113.42",
  "user_agent": "Terraform/1.5.0",
  "request_id": "req_abc123"
}
```

### Metrics Endpoint

**GET /metrics**

Prometheus-format metrics for monitoring:

```text
# HELP tsilo_requests_total Total number of HTTP requests
# TYPE tsilo_requests_total counter
tsilo_requests_total{method="GET",endpoint="/v1/modules/{namespace}/{name}/{provider}/versions",status="200"} 1247

# HELP tsilo_request_duration_seconds HTTP request latency
# TYPE tsilo_request_duration_seconds histogram
tsilo_request_duration_seconds_bucket{method="GET",endpoint="/v1/modules/{namespace}/{name}/{provider}/versions",le="0.1"} 1200
tsilo_request_duration_seconds_bucket{method="GET",endpoint="/v1/modules/{namespace}/{name}/{provider}/versions",le="0.5"} 1245
tsilo_request_duration_seconds_bucket{method="GET",endpoint="/v1/modules/{namespace}/{name}/{provider}/versions",le="1.0"} 1247

# HELP tsilo_module_downloads_total Total number of module downloads
# TYPE tsilo_module_downloads_total counter
tsilo_module_downloads_total{namespace="platform-team",module="vpc",provider="aws"} 523

# HELP tsilo_active_sessions Current number of active user sessions
# TYPE tsilo_active_sessions gauge
tsilo_active_sessions 42
```

---

## Health Check

**GET /health**

Health check endpoint for liveness/readiness probes:

**Response** (200 OK):
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "storage": "ok"
  },
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "checks": {
    "database": "error: connection timeout",
    "storage": "ok"
  },
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

---

## Contract Testing

### Test Scenarios

All endpoints must pass these contract test scenarios:

1. **Service Discovery**
   - Returns correct JSON structure
   - Returns 200 status
   - No authentication required

2. **Version Listing**
   - Returns versions in descending order
   - Requires authentication
   - Enforces authorization
   - Returns 404 for non-existent modules

3. **Module Download**
   - Returns valid download URL
   - Increments download counter
   - Requires authentication
   - Enforces authorization
   - Returns 404 for non-existent versions

4. **Module Upload**
   - Accepts valid .tar.gz packages
   - Extracts inputs/outputs correctly
   - Rejects invalid versions
   - Rejects duplicate versions
   - Requires write permission

5. **Rate Limiting**
   - Enforces limits per user
   - Returns 429 when exceeded
   - Includes rate limit headers

6. **Error Handling**
   - Returns consistent error format
   - Provides actionable error messages
   - Includes appropriate status codes
