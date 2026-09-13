$ErrorActionPreference = "Stop"

Write-Host "Daily Intelligence Newspaper - bootstrap" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "Created .env from .env.example." -ForegroundColor Yellow
    Write-Host "Edit DATABASE_URL before running the setup check." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host "Activate later with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run app with: uvicorn app.main:app --reload"
