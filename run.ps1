# run.ps1 - Local dev launcher (ASCII labels avoid PowerShell [ ] parsing in double quotes)
# Usage: .\run.ps1
#        .\run.ps1 -Port 8001 -NoReload

param(
    [int]$Port = 8000,
    [switch]$NoReload
)

Set-Location $PSScriptRoot

# 1. Load .env into process env (overrides machine/user OPENAI_API_KEY etc.)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#\s][^=]+?)\s*=\s*(.*)$") {
            [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
        }
    }
    Write-Host "OK: .env loaded" -ForegroundColor Green
}
else {
    Write-Host "WARN: .env not found. Run: Copy-Item .env.example .env" -ForegroundColor Yellow
    exit 1
}

# 2. Free port if something is listening
$occupied = netstat -ano 2>$null | Select-String ":$Port.*LISTENING"
if ($occupied) {
    Write-Host "WARN: port $Port in use, trying to stop listener..." -ForegroundColor Yellow
    $occupied | ForEach-Object {
        if ($_ -match "LISTENING\s+(\d+)") {
            $listenPid = [int]$Matches[1]
            Stop-Process -Id $listenPid -Force -ErrorAction SilentlyContinue
            Write-Host "  stopped PID $listenPid" -ForegroundColor Gray
        }
    }
    Start-Sleep -Seconds 2
}

# 3. Show config (avoid $args / $PID - they are automatic variables)
$key = $env:OPENAI_API_KEY
if (-not $key) { $key = "" }
$prefixLen = [Math]::Min(12, $key.Length)
$keyPrefix = if ($prefixLen -gt 0) { $key.Substring(0, $prefixLen) + "..." } else { "(empty)" }

$db = $env:DATABASE_URL
if (-not $db) { $db = "" }
$dbLen = [Math]::Min(50, $db.Length)
$dbShow = if ($dbLen -gt 0) { $db.Substring(0, $dbLen) + "..." } else { "(empty)" }

Write-Host "OK: LLM Key  : $keyPrefix" -ForegroundColor Green
Write-Host "OK: LLM URL  : $($env:OPENAI_BASE_URL)" -ForegroundColor Green
Write-Host "OK: Database : $dbShow" -ForegroundColor Green
Write-Host ""
Write-Host "  http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
Write-Host ""

# 4. Ensure runtime deps exist in current python environment
$depCheck = python -c "import uvicorn, fastapi, sqlalchemy, openai; from Crypto.Cipher import AES" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: missing runtime dependencies in current python env, installing..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed. Please check your python environment." -ForegroundColor Red
        exit 1
    }
}

# 5. Start uvicorn (use $uvicornArgs, not $args)
$uvicornArgs = @("app.main:app", "--host", "0.0.0.0", "--port", "$Port")
if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

python -m uvicorn @uvicornArgs
