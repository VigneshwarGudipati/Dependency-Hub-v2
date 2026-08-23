<#
.SYNOPSIS
    Dependency Hub — Verification and health check script.

.DESCRIPTION
    Checks Docker, PostgreSQL, backend health endpoints, runs backend tests,
    and validates the frontend build and lint. Reports PASS/FAIL for each.

.NOTES
    Run from the repository root:
        .\scripts\verify.ps1

    Requires PostgreSQL to be running for database-dependent tests.
    Start with: .\scripts\start.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $PSScriptRoot
$Results = @()

function Write-Step { param($msg) Write-Host "`n[VERIFY] $msg" -ForegroundColor Cyan }
function Pass { param($label) $script:Results += @{ Label=$label; Status="PASS" }; Write-Host "  [PASS] $label" -ForegroundColor Green }
function Fail { param($label, $reason) $script:Results += @{ Label=$label; Status="FAIL"; Reason=$reason }; Write-Host "  [FAIL] $label - $reason" -ForegroundColor Red }
function Skip { param($label, $reason) $script:Results += @{ Label=$label; Status="SKIP"; Reason=$reason }; Write-Host "  [SKIP] $label - $reason" -ForegroundColor Yellow }

# ─── Docker ───────────────────────────────────────────────────────────────────
Write-Step "Docker"
try {
    docker info *>$null 2>&1
    if ($LASTEXITCODE -eq 0) { Pass "Docker daemon running" }
    else { Fail "Docker daemon" "docker info returned exit code $LASTEXITCODE" }
} catch { Fail "Docker daemon" $_.Exception.Message }

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
Write-Step "PostgreSQL container"
try {
    Push-Location $Root
    $pgStatus = docker compose ps --format json 2>&1 | ConvertFrom-Json | Where-Object { $_.Service -eq "postgres" }
    Pop-Location
    if ($pgStatus -and $pgStatus.State -eq "running") {
        Pass "PostgreSQL container running"
    } else {
        Fail "PostgreSQL container" "State: $($pgStatus.State). Run: docker compose up -d"
    }
} catch {
    Fail "PostgreSQL container" $_.Exception.Message
}

# ─── Backend health ───────────────────────────────────────────────────────────
Write-Step "Backend health endpoints"
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 5 -ErrorAction Stop
    if ($health.status -eq "ok") { Pass "/health" }
    else { Fail "/health" "status=$($health.status)" }
} catch { Fail "/health" "Backend not responding. Start with: .\scripts\start.ps1" }

try {
    $dbHealth = Invoke-RestMethod -Uri "http://localhost:8000/health/database" -Method GET -TimeoutSec 5 -ErrorAction Stop
    if ($dbHealth.status -eq "healthy") { Pass "/health/database" }
    else { Fail "/health/database" "status=$($dbHealth.status)" }
} catch { Fail "/health/database" "Could not reach endpoint" }

try {
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/ready" -Method GET -TimeoutSec 5 -ErrorAction Stop
    if ($ready.status -eq "ok") { Pass "/ready" }
    else { Fail "/ready" "status=$($ready.status)" }
} catch { Fail "/ready" "Could not reach endpoint" }

# ─── Database-layer tests ─────────────────────────────────────────────────────
Write-Step "Database-layer tests (database/tests/)"
$PytestExe = Join-Path $Root "database\.venv\Scripts\pytest.exe"
try {
    Push-Location (Join-Path $Root "database")
    $env:PYTHONPATH = "backend"
    $output = & $PytestExe -v --tb=no -q 2>&1
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Pass "Database-layer tests" }
    else { Fail "Database-layer tests" "Exit code $LASTEXITCODE - PostgreSQL may be offline" }
} catch {
    Pop-Location
    Fail "Database-layer tests" $_.Exception.Message
}

# ─── API-layer tests ──────────────────────────────────────────────────────────
Write-Step "API-layer tests (database/backend/tests/)"
try {
    Push-Location (Join-Path $Root "database")
    $env:PYTHONPATH = "backend"
    $output = & $PytestExe backend/tests/ -v --tb=no -q 2>&1
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Pass "API-layer tests" }
    else { Fail "API-layer tests" "Exit code $LASTEXITCODE - most tests require live PostgreSQL" }
} catch {
    Pop-Location
    Fail "API-layer tests" $_.Exception.Message
}

# ─── Live OSV Integration test ────────────────────────────────────────────────
Write-Step "Live OSV Integration test (database/tests/integration/test_e2e_osv.py)"
try {
    Push-Location (Join-Path $Root "database")
    $env:PYTHONPATH = "backend"
    $output = & $PytestExe tests/integration/test_e2e_osv.py -v --tb=no -q 2>&1
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Pass "Live OSV Integration test" }
    else { Fail "Live OSV Integration test" "Exit code $LASTEXITCODE - requires internet access" }
} catch {
    Pop-Location
    Fail "Live OSV Integration test" $_.Exception.Message
}

# ─── Frontend build ───────────────────────────────────────────────────────────
Write-Step "Frontend build"
try {
    Push-Location (Join-Path $Root "frontend")
    $buildOut = npm run build 2>&1
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Pass "Frontend build (npm run build)" }
    else { Fail "Frontend build" "Exit code $LASTEXITCODE"; Write-Host ($buildOut | Select-Object -Last 20 | Out-String) }
} catch {
    Pop-Location
    Fail "Frontend build" $_.Exception.Message
}

# ─── Frontend lint ────────────────────────────────────────────────────────────
Write-Step "Frontend lint"
try {
    Push-Location (Join-Path $Root "frontend")
    $lintOut = npm run lint 2>&1
    Pop-Location
    if ($LASTEXITCODE -eq 0) { Pass "Frontend lint (npm run lint)" }
    else { Fail "Frontend lint" "Exit code $LASTEXITCODE"; Write-Host ($lintOut | Select-Object -Last 20 | Out-String) }
} catch {
    Pop-Location
    Fail "Frontend lint" $_.Exception.Message
}

# ─── Security: no secrets in tracked files ────────────────────────────────────
Write-Step "Security: secrets not tracked"
try {
    $trackedSecrets = git -C $Root ls-files 2>&1 | Where-Object { $_ -match "\.env$|\.pem$|\.key$" }
    if ($trackedSecrets) {
        Fail "Secret files tracked by git" ($trackedSecrets -join ", ")
    } else {
        Pass "No secret files tracked by git"
    }
} catch {
    Skip "Git secrets check" "Git not initialized yet"
}

# ─── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor DarkGray
Write-Host " VERIFICATION SUMMARY" -ForegroundColor White
Write-Host "═══════════════════════════════════════" -ForegroundColor DarkGray

$passed = ($Results | Where-Object { $_.Status -eq "PASS" }).Count
$failed = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
$skipped = ($Results | Where-Object { $_.Status -eq "SKIP" }).Count

foreach ($r in $Results) {
    $color = switch ($r.Status) { "PASS" { "Green" } "FAIL" { "Red" } "SKIP" { "Yellow" } }
    $line = "  [$($r.Status)] $($r.Label)"
    if ($r.Reason) { $line += " - $($r.Reason)" }
    Write-Host $line -ForegroundColor $color
}

Write-Host ""
Write-Host "  Passed: $passed  Failed: $failed  Skipped: $skipped" -ForegroundColor White

if ($failed -eq 0) {
    Write-Host "`n  STRUCTURE CLEAN - READY FOR DEVELOPMENT" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n  BLOCKED - $failed check(s) failed. See above." -ForegroundColor Red
    exit 1
}
