# debug_feishu.ps1 - Feishu bot local debug helper (ngrok)
# Requires: ngrok in PATH, local app running (.\run.ps1)
# Usage: .\debug_feishu.ps1
#        .\debug_feishu.ps1 -Port 8001

param([int]$Port = 8000)

Set-Location $PSScriptRoot

Write-Host "=== Feishu local debug ===" -ForegroundColor Cyan
Write-Host ""

# 1. ngrok
if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: ngrok not found. Install from https://ngrok.com/download" -ForegroundColor Red
    Write-Host "       Then: ngrok config add-authtoken <your_token>" -ForegroundColor Yellow
    exit 1
}
Write-Host "OK: ngrok found" -ForegroundColor Green

# 2. Local app health
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "OK: local app is up (port $Port)" -ForegroundColor Green
}
catch {
    Write-Host "ERROR: local app not running. Start with: .\run.ps1" -ForegroundColor Red
    exit 1
}

# 3. Start ngrok in a new window
Write-Host ""
Write-Host "Starting ngrok tunnel -> http://127.0.0.1:$Port ..." -ForegroundColor Yellow
Start-Process -FilePath "ngrok" -ArgumentList "http", "$Port" -WindowStyle Normal

Start-Sleep -Seconds 3

# 4. Public URL from ngrok API
try {
    $ngrokApi = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop
    $publicUrl = ($ngrokApi.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
    if (-not $publicUrl) { $publicUrl = $ngrokApi.tunnels[0].public_url }
}
catch {
    Write-Host "WARN: could not read ngrok API. Open http://127.0.0.1:4040" -ForegroundColor Yellow
    $publicUrl = "(see http://127.0.0.1:4040)"
}

$webhookUrl = "$publicUrl/api/v1/bot/feishu/events"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " ngrok URL : $publicUrl" -ForegroundColor White
Write-Host " Webhook   : $webhookUrl" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Feishu console: https://open.feishu.cn/app" -ForegroundColor Yellow
Write-Host " 1. Your app -> Events & callbacks -> Request URL" -ForegroundColor White
Write-Host " 2. Paste webhook URL above" -ForegroundColor White
Write-Host " 3. Subscribe: im.message.receive_v1" -ForegroundColor White
Write-Host " 4. Save (Feishu sends url_verification challenge)" -ForegroundColor White
Write-Host ""
Write-Host "Tools:" -ForegroundColor Yellow
Write-Host " - ngrok inspect: http://127.0.0.1:4040" -ForegroundColor White
Write-Host " - Swagger:        http://127.0.0.1:$Port/docs" -ForegroundColor White
Write-Host ""
Write-Host "Sample POST (copy into another PowerShell window):" -ForegroundColor Yellow
Write-Host '$body = ''{' -ForegroundColor Gray
Write-Host '  "schema": "2.0",' -ForegroundColor Gray
Write-Host '  "event": {' -ForegroundColor Gray
Write-Host '    "sender": {"sender_id": {"open_id": "ou_test"}},' -ForegroundColor Gray
Write-Host '    "message": {' -ForegroundColor Gray
Write-Host '      "message_id": "om_001",' -ForegroundColor Gray
Write-Host '      "chat_id": "oc_test",' -ForegroundColor Gray
Write-Host '      "chat_type": "p2p",' -ForegroundColor Gray
Write-Host '      "message_type": "text",' -ForegroundColor Gray
Write-Host '      "content": "{\"text\": \"deploy WMS to prod at 6pm\"}"' -ForegroundColor Gray
Write-Host '    }' -ForegroundColor Gray
Write-Host '  }' -ForegroundColor Gray
Write-Host '}''' -ForegroundColor Gray
Write-Host "Invoke-RestMethod -Uri `"http://127.0.0.1:$Port/api/v1/bot/feishu/events`" -Method POST -Body `$body -ContentType `"application/json`"" -ForegroundColor Gray
Write-Host ""
