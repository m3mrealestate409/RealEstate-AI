<#
  PropX Estate — daily backup (Windows / Docker Desktop)

  Backs up, into a timestamped folder:
    1. the PostgreSQL database  (pg_dump, custom format)
    2. the uploads folder       (documents/images tenants uploaded)
    3. the .env file            (secrets — needed to restore)

  Old backups beyond $KeepDays are deleted automatically.

  RUN MANUALLY:
      powershell -ExecutionPolicy Bypass -File "scripts\backup.ps1"

  RESTORE (if the laptop ever dies) — from a backup folder:
      docker cp db.dump chaahat_db:/tmp/db.dump
      docker exec chaahat_db pg_restore -U chaahat -d chaahat_engine --clean --if-exists /tmp/db.dump
      docker cp uploads/. chaahat_api:/app/uploads

  NOTE: the backup folder contains SECRETS (.env). Keep it private — do not put
  it in a public/shared location without thinking.
#>

$ErrorActionPreference = "Stop"

# ----------------------- settings (change if needed) -----------------------
$BackupRoot   = "C:\PropX-Backups"   # where backups are stored (outside the repo)
$KeepDays     = 14                   # delete backups older than this many days
$DbContainer  = "chaahat_db"
$ApiContainer = "chaahat_api"
$DbUser       = "chaahat"
$DbName       = "chaahat_engine"
# ---------------------------------------------------------------------------

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$stamp       = Get-Date -Format "yyyy-MM-dd_HHmm"
$dest        = Join-Path $BackupRoot $stamp

New-Item -ItemType Directory -Force -Path $dest | Out-Null
$log = Join-Path $BackupRoot "backup.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

function Assert-LastOk($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" }
}

try {
    Log "=== Backup start -> $dest ==="

    # --- 1. database ---------------------------------------------------
    docker exec $DbContainer pg_dump -U $DbUser -d $DbName -F c -f /tmp/db.dump
    Assert-LastOk "pg_dump"

    docker cp "${DbContainer}:/tmp/db.dump" (Join-Path $dest "db.dump")
    Assert-LastOk "docker cp (database)"

    docker exec $DbContainer rm -f /tmp/db.dump | Out-Null

    $dbBytes = (Get-Item (Join-Path $dest "db.dump")).Length
    # A real dump is never this small — catch a silently-empty backup.
    if ($dbBytes -lt 4096) { throw "Database dump looks empty ($dbBytes bytes)" }
    Log ("Database OK   ({0:N2} MB)" -f ($dbBytes / 1MB))

    # --- 2. uploads ----------------------------------------------------
    docker cp "${ApiContainer}:/app/uploads" (Join-Path $dest "uploads")
    Assert-LastOk "docker cp (uploads)"
    Log "Uploads OK"

    # --- 3. .env (secrets; required for a restore) ---------------------
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        Copy-Item $envFile (Join-Path $dest "env.backup")
        Log ".env OK"
    } else {
        Log "WARNING: .env not found at $envFile"
    }

    # --- 4. retention ---------------------------------------------------
    Get-ChildItem $BackupRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}_\d{4}$' -and
                       $_.CreationTime -lt (Get-Date).AddDays(-$KeepDays) } |
        ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force
            Log "Deleted old backup: $($_.Name)"
        }

    Log "=== Backup DONE ==="
    exit 0
}
catch {
    Log "!!! BACKUP FAILED: $($_.Exception.Message)"
    exit 1
}
