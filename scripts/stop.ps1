<#
.SYNOPSIS
    Dependency Hub — Stop development services safely.

.DESCRIPTION
    Stops the Docker Compose PostgreSQL container and cleans up any
    background PowerShell jobs created by start.ps1.

    SAFETY GUARANTEE: This script NEVER runs docker compose down -v.
    Database data volumes are preserved.

.NOTES
    Run from the repository root:
        .\scripts\stop.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n[STOP] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

# ─── Stop PowerShell background jobs ─────────────────────────────────────────
Write-Step "Stopping background jobs"
$jobs = Get-Job | Where-Object { $_.State -in @("Running", "NotStarted") }
if ($jobs) {
    $jobs | Stop-Job
    $jobs | Remove-Job -Force
    Write-Ok "Stopped $($jobs.Count) background job(s)"
} else {
    Write-Ok "No running background jobs found"
}

# ─── Stop Docker container (WITHOUT -v, volumes preserved) ───────────────────
Write-Step "Stopping PostgreSQL container"
Push-Location $Root
# Explicitly: down WITHOUT -v to preserve database volumes
docker compose stop
Write-Ok "PostgreSQL container stopped (data volume preserved)"
Pop-Location

Write-Host ""
Write-Host "All services stopped. Database data is intact." -ForegroundColor Green
Write-Host "To start again: .\scripts\start.ps1"
