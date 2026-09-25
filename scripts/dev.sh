#!/usr/bin/env bash
set -e

echo "=========================================="
echo "Starting Kanooni Karhvahi (Dev Stack)"
echo "=========================================="

python3 --version
node -v

echo ""
echo "To start with Docker Compose:"
echo "  docker compose up --build"
echo ""
echo "To start locally:"
echo "  (cd services/api && uvicorn app.main:app --reload --port 8000) &"
echo "  (cd apps/web && npm run dev)"
