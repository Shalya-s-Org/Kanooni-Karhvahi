# Kanooni Karhvahi - Database Design

The database uses PostgreSQL 16 with the `pgvector` extension enabled.

---

## Extensions
- `uuid-ossp`: For generating secure, non-sequential UUID primary keys.
- `vector`: Enables vector embeddings (e.g., 768 or 1536 dimensions) for semantic retrieval.

---

## Planned Core Entities (For Future Milestones)

```mermaid
erDiagram
    DOCUMENT {
        uuid id PK
        string original_filename
        string file_path
        string mime_type
        integer file_size
        string status
        datetime created_at
        datetime expires_at
    }

    DOCUMENT_METADATA {
        uuid id PK
        uuid document_id FK
        string document_type
        string jurisdiction
        jsonb extracted_entities
        string summary_plain_en
    }

    CLAUSE {
        uuid id PK
        uuid document_id FK
        integer clause_number
        text original_text
        text simplified_text
        string risk_level
        jsonb statutory_references
    }

    DOCUMENT_CHUNK {
        uuid id PK
        uuid document_id FK
        text chunk_text
        vector embedding
        jsonb chunk_metadata
    }

    DOCUMENT ||--|| DOCUMENT_METADATA : has
    DOCUMENT ||--o{ CLAUSE : contains
    DOCUMENT ||--o{ DOCUMENT_CHUNK : vectorizes
```

---

## Migrations
Alembic manages all schema revisions under `services/api/alembic/`.
Run migrations using:
```bash
alembic upgrade head
```
