# Production Startup Script - CPU Version
# Usage: .\start.ps1 [option]

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Cyan = [ConsoleColor]::Cyan

Write-Host ""
Write-Host "==========================================" -ForegroundColor $Cyan
Write-Host "  TradeAgent - Production Startup (CPU)  " -ForegroundColor $Cyan
Write-Host "==========================================" -ForegroundColor $Cyan
Write-Host ""

function Start-CpuServices {
    Write-Host "Starting CPU version services..." -ForegroundColor $Green
    Set-Location (Join-Path $ScriptDir "deploy")
    docker compose up -d
    Write-Host ""
    Write-Host "Services started:" -ForegroundColor $Green
    Write-Host "  API: http://localhost:8001"
    Write-Host "  Kafka UI: http://localhost:8080"
    Write-Host "  Grafana: http://localhost:3000 (admin/admin)"
    Write-Host "  Prometheus: http://localhost:9090"
    Set-Location $ScriptDir
}

function Stop-AllServices {
    Write-Host "Stopping all services..." -ForegroundColor $Yellow
    Set-Location (Join-Path $ScriptDir "deploy")
    docker compose down
    Write-Host "Services stopped" -ForegroundColor $Green
    Set-Location $ScriptDir
}

function Show-ServiceStatus {
    Write-Host "Service Status:" -ForegroundColor $Cyan
    Set-Location (Join-Path $ScriptDir "deploy")
    docker compose ps
    Set-Location $ScriptDir
}

function Start-GpuServices {
    Write-Host "Starting GPU version services..." -ForegroundColor $Green
    Set-Location (Join-Path $ScriptDir "docker")
    docker compose -f docker-compose.gpu.yml up -d
    Write-Host ""
    Write-Host "GPU Services started:" -ForegroundColor $Green
    Write-Host "  GPU API: http://localhost:8001"
    Write-Host "  Kafka UI: http://localhost:8080"
    Set-Location $ScriptDir
}

if ($args.Count -eq 0) {
    Start-CpuServices
} else {
    switch ($args[0]) {
        "start" { Start-CpuServices }
        "stop" { Stop-AllServices }
        "status" { Show-ServiceStatus }
        "gpu" { Start-GpuServices }
        default {
            Write-Host "Usage: .\start.ps1 {start|stop|status|gpu}"
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  start   - Start CPU version (default)"
            Write-Host "  stop    - Stop all services"
            Write-Host "  status  - Show service status"
            Write-Host "  gpu     - Start GPU version"
        }
    }
}
