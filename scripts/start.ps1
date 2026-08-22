<#
.SYNOPSIS
    Dependency Hub — Start all development services.

.DESCRIPTION
    Starts PostgreSQL via Docker Compose, the FastAPI backend, and the
    Vite/TanStack Start frontend. Backend and frontend are started as
    background jobs so their logs are visible in the terminal.

.NOTES
    Run from the repository root:
        .\scripts\start.ps1

    Stop all services with:
        .\scripts\stop.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n[START] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
Write-Step "Starting PostgreSQL container"
Push-Location $Root
docker compose up -d
Write-Ok "PostgreSQL container started"
Pop-Location

# Give Postgres a moment to be ready
Write-Step "Waiting for PostgreSQL to be ready"
Start-Sleep -Seconds 3
Write-Ok "Ready"

# ─── Backend ──────────────────────────────────────────────────────────────────
Write-Step "Starting FastAPI backend (port 8000)"
$PythonExe = Join-Path $Root "database\.venv\Scripts\python.exe"

$BackendJob = Start-Job -ScriptBlock {
    param($root, $pythonExe)
    $env:PYTHONPATH = "backend"
    Set-Location (Join-Path $root "database")
    & $pythonExe -m uvicorn app.main:app --reload --port 8000
} -ArgumentList $Root, $PythonExe

Write-Ok "Backend started as background job $($BackendJob.Id)"
Write-Warn "Backend logs: Receive-Job -Id $($BackendJob.Id) -Keep"

# ─── Frontend ─────────────────────────────────────────────────────────────────
Write-Step "Starting frontend development server"
$FrontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location (Join-Path $root "frontend")
    npm run dev
} -ArgumentList $Root

Write-Ok "Frontend started as background job $($FrontendJob.Id)"
Write-Warn "Frontend logs: Receive-Job -Id $($FrontendJob.Id) -Keep"

# ─── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "All services are starting." -ForegroundColor Green
Write-Host "  Backend API:  http://localhost:8000/api/v1" -ForegroundColor White
Write-Host "  Swagger UI:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Frontend:     check Vite terminal output for port" -ForegroundColor White
Write-Host ""
Write-Host "To view logs: Receive-Job -Id <id> -Keep"
Write-Host "To stop:      .\scripts\stop.ps1"
Write-Host ""
Write-Host "Background jobs:" -ForegroundColor DarkGray
Write-Host "  Backend  Job ID: $($BackendJob.Id)"
Write-Host "  Frontend Job ID: $($FrontendJob.Id)"
