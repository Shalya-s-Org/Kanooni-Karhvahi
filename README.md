# Kanooni Karhvahi (कानूनी कार्यवाही)
> **A Multilingual Legal-Document Companion for India**

Kanooni Karhvahi is an open, transparent, document-grounded legal comprehension system designed to bridge the accessibility gap in Indian legal documents. It converts complex agreements, legal notices, and court orders into simplified language across major Indian languages while strictly avoiding legal advice, predicting outcomes, or hallucinating citations.

---

## Architecture Overview

- **Frontend (`apps/web`)**: React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui primitives, React Router, TanStack Query.
- **Backend API (`services/api`)**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic.
- **Worker (`services/worker`)**: Python, Celery, Redis.
- **Data Tier**: PostgreSQL 16 with `pgvector` extension for semantic embeddings and document storage.
- **Infrastructure (`infrastructure/`)**: Docker Compose, PostgreSQL init scripts, Nginx configuration.

---

## Quickstart

### Prerequisites
- Node.js >= 20.x
- Python >= 3.11
- Docker & Docker Compose (optional for local running, recommended for containerized stack)

### 1. Environment Setup
Copy the example environment configuration:
```bash
cp .env.example .env
```

### 2. Running with Docker Compose
To launch the entire stack (PostgreSQL with pgvector, Redis, API, Worker, and Web):
```bash
docker compose up --build
```
- **Web App**: http://localhost:5173
- **API Swagger Docs**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/api/v1/health

---

### 3. Running Locally (Without Docker)

#### Backend (API)
```bash
cd services/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -e .
uvicorn app.main:app --reload --port 8000
```

#### Celery Worker
```bash
cd services/worker
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -e .
celery -A worker.celery_app worker --loglevel=info
```

#### Frontend (Web)
```bash
cd apps/web
npm install
npm run dev
```

---

## Running Tests

### Backend Tests
```bash
cd services/api
pytest
```

### Frontend Build & Typecheck
```bash
cd apps/web
npm run build
```

---

