<#
.SYNOPSIS
    Dependency Hub — First-time development environment setup.

.DESCRIPTION
    Verifies prerequisites, creates the Python virtual environment,
    installs backend and frontend dependencies, and validates environment
    templates. Safe to re-run (idempotent).

.NOTES
    Run from the repository root:
        .\scripts\setup.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n[SETUP] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red }

# ─── Prerequisites ────────────────────────────────────────────────────────────

Write-Step "Checking Docker"
try {
    $dockerVersion = docker --version 2>&1
    Write-Ok "Docker: $dockerVersion"
} catch {
    Write-Fail "Docker not found. Install Docker Desktop from https://docker.com"
    exit 1
}

Write-Step "Checking Python"
try {
    $pyVersion = python --version 2>&1
    Write-Ok "Python: $pyVersion"
} catch {
    Write-Fail "Python not found. Install Python 3.12+ from https://python.org"
    exit 1
}

Write-Step "Checking Node.js"
try {
    $nodeVersion = node --version 2>&1
    Write-Ok "Node.js: $nodeVersion"
} catch {
    Write-Fail "Node.js not found. Install Node.js 20+ from https://nodejs.org"
    exit 1
}

# ─── Backend: virtual environment ─────────────────────────────────────────────

Write-Step "Setting up Python virtual environment"
$VenvPath = Join-Path $Root "database\.venv"

if (Test-Path $VenvPath) {
    Write-Ok "Virtual environment already exists at database\.venv"
} else {
    Push-Location (Join-Path $Root "database")
    python -m venv .venv
    Write-Ok "Created database\.venv"
    Pop-Location
}

Write-Step "Installing backend dependencies"
$PipExe = Join-Path $Root "database\.venv\Scripts\pip.exe"
& $PipExe install -r (Join-Path $Root "database\backend\requirements.txt") --quiet
Write-Ok "Backend dependencies installed"

# ─── Frontend: npm install ────────────────────────────────────────────────────

Write-Step "Installing frontend dependencies"
Push-Location (Join-Path $Root "frontend")
npm install --silent
Write-Ok "Frontend dependencies installed"
Pop-Location

# ─── Environment templates ────────────────────────────────────────────────────

Write-Step "Checking environment files"

$BackendEnv = Join-Path $Root "database\.env"
$BackendExample = Join-Path $Root "database\.env.example"
if (-not (Test-Path $BackendEnv)) {
    Copy-Item $BackendExample $BackendEnv
    Write-Warn "Created database\.env from example. Edit it and set real credentials."
} else {
    Write-Ok "database\.env exists"
}

$FrontendEnv = Join-Path $Root "frontend\.env"
$FrontendExample = Join-Path $Root "frontend\.env.example"
if (-not (Test-Path $FrontendEnv)) {
    Copy-Item $FrontendExample $FrontendEnv
    Write-Warn "Created frontend\.env from example. Default URL works for local dev."
} else {
    Write-Ok "frontend\.env exists"
}

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit database\.env and set POSTGRES_PASSWORD, JWT_SECRET, ENCRYPTION_MASTER_KEY"
Write-Host "  2. Run: .\scripts\start.ps1"
