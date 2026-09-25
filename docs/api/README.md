# Kanooni Karhvahi - API Specification

All endpoints are versioned under `/api/v1`.

---

## Shared Response Format

All responses strictly conform to standard envelopes.

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### Failure Response
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested document was not found or has expired.",
    "retryable": false
  }
}
```

---

## Implemented Endpoints (Phase 1 Foundation)

### System Health
- **Endpoint**: `GET /api/v1/health`
- **Description**: Returns operational status of the API, database connectivity, and Redis connectivity.
- **Response**:
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "kanooni-karhvahi-api",
    "version": "0.1.0",
    "environment": "development",
    "database": {
      "connected": true,
      "message": "Database ping succeeded"
    },
    "redis": {
      "connected": true,
      "message": "Redis ping succeeded"
    }
  },
  "error": null
}
```

---

## Planned Endpoint Groups (Future Phases)

### 1. Documents (`/api/v1/documents`)
- `POST /upload` - Upload PDF/image (max 25MB), enforce TTL, trigger pipeline
- `GET /{id}` - Retrieve document metadata and processing status
- `DELETE /{id}` - Immediate cryptographic purge of document, text, and vector embeddings

### 2. Analysis (`/api/v1/analysis`)
- `GET /{document_id}` - Retrieve complete analysis (summary, simplified clauses, detected risks)
- `GET /{document_id}/entities` - Retrieve extracted dates, amounts, parties, and deadlines
- `GET /{document_id}/classification` - Retrieve document type (Agreement, Notice, Order, Petition)

### 3. Clauses (`/api/v1/clauses`)
- `GET /{document_id}` - Retrieve granular clause breakdown with plain-language simplification
- `POST /{clause_id}/explain` - On-demand deeper explanation of a specific ambiguous clause

### 4. Chat & Verification (`/api/v1/chat`)
- `POST /query` - Document-grounded Q&A with strict citations to clauses
- `GET /{document_id}/history` - Retrieve ephemeral chat thread for active session

### 5. Multilingual & Audio (`/api/v1/translation`)
- `POST /{document_id}/translate` - Translate summary/clauses into target Indian language
- `POST /{document_id}/audio-summary` - Generate spoken audio summary for accessibility

### 6. Reports (`/api/v1/reports`)
- `POST /{document_id}/export` - Export bilingual plain-language briefing PDF or printable summary

### 7. Sources (`/api/v1/sources`)
- `GET /statutes/{code}` - Lookup official statute sections cited in the document
