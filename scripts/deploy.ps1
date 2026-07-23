<#
  PropX Estate — one-command deploy / update (Windows / Docker Desktop)

  What it does, in order:
    1. Backup       — database + uploads + .env  (skip with -SkipBackup)
    2. Build+restart— rebuilds the api and web images, restarts the stack
    3. Verify       — polls /health until the API answers 200

  If the backup fails, the deploy is ABORTED and nothing is touched.
  If the app does not come back healthy, the script says so loudly.

  USAGE:
      powershell -ExecutionPolicy Bypass -File "scripts\deploy.ps1"
      powershell -ExecutionPolicy Bypass -File "scripts\deploy.ps1" -SkipBackup

  NOTE: a deploy causes ~30-60 seconds of downtime for everyone using the
  link. Prefer lunchtime / after office hours.
#>
[CmdletBinding()]
param(
    [switch]$SkipBackup,
    [int]$HealthTimeoutSec = 150
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HealthUrl   = "http://127.0.0.1:8001/health"
$ComposeBase = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")

function Say($msg, $color = "Gray") { Write-Host $msg -ForegroundColor $color }
function Assert-LastOk($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" }
}

Push-Location $ProjectRoot
$startedAt = Get-Date

try {
    Say ""
    Say "=========================================" Cyan
    Say "  PropX Estate - deploy" Cyan
    Say "=========================================" Cyan
    try {
        $commit = (& git log -1 --oneline 2>$null)
        if ($commit) { Say "  code: $commit" DarkGray }
    } catch { }
    Say ""

    # ---- 1. backup ------------------------------------------------------
    if ($SkipBackup) {
        Say "[1/3] Backup SKIPPED (-SkipBackup)" Yellow
    } else {
        Say "[1/3] Backing up database + uploads..." Cyan
        & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "backup.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "Backup failed - deploy ABORTED. Nothing changed; the app is still running as before."
        }
        Say "      backup done" Green
    }

    # ---- 2. build + restart ---------------------------------------------
    Say ""
    Say "[2/3] Building images and restarting containers..." Cyan
    Say "      (the link is briefly unavailable from here)" DarkGray
    $upArgs = $ComposeBase + @("up", "-d", "--build")
    & docker @upArgs
    Assert-LastOk "docker compose up"

    # ---- 3. verify -------------------------------------------------------
    Say ""
    Say "[3/3] Waiting for the API to report healthy..." Cyan
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
    $healthy  = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch { }   # not up yet -- keep polling
    }
    if (-not $healthy) {
        throw "API did not become healthy within $HealthTimeoutSec seconds."
    }

    $secs = [int]((Get-Date) - $startedAt).TotalSeconds
    Say ""
    Say "=========================================" Green
    Say "  DEPLOY OK  (${secs}s)" Green
    Say "=========================================" Green

    # Public URL, best-effort (read from .env)
    try {
        $envFile = Join-Path $ProjectRoot ".env"
        if (Test-Path $envFile) {
            $m = Select-String -Path $envFile -Pattern '^\s*VITE_API_URL\s*=\s*(.+)$' | Select-Object -First 1
            if ($m) { Say ("  Live at: " + $m.Matches[0].Groups[1].Value.Trim()) Green }
        }
    } catch { }

    # Funnel sanity check, best-effort
    try {
        $f = & tailscale funnel status 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $f) {
            Say "  NOTE: could not confirm Tailscale Funnel is on (run: tailscale funnel status)" Yellow
        }
    } catch { }

    Say "  Tip: if anyone still sees the old version, Ctrl+F5 once." DarkGray
    Say ""
    exit 0
}
catch {
    Say ""
    Say "=========================================" Red
    Say "  DEPLOY FAILED" Red
    Say "=========================================" Red
    Say ("  " + $_.Exception.Message) Red
    Say ""
    Say "  See what went wrong:" Yellow
    Say "    docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50 api" Yellow
    Say ""
    Say "  Your backup is in C:\PropX-Backups (restore steps: top of scripts\backup.ps1)." DarkGray
    Say ""
    exit 1
}
finally {
    Pop-Location
}
