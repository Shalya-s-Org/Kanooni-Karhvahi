# Kanooni Karhvahi - Windows Development Startup Script
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Kanooni Karhvahi (Dev Environment)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python and Node
python --version
node -v

Write-Host "`nTo start the backend API:" -ForegroundColor Yellow
Write-Host "  cd services/api"
Write-Host "  python -m venv .venv; .venv\Scripts\activate; pip install -e ."
Write-Host "  uvicorn app.main:app --reload --port 8000"

Write-Host "`nTo start the frontend:" -ForegroundColor Yellow
Write-Host "  cd apps/web"
Write-Host "  npm install"
Write-Host "  npm run dev"

Write-Host "`nOr with Docker Compose:" -ForegroundColor Yellow
Write-Host "  docker compose up --build"
