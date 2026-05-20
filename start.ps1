# Project Startup Script (Windows PowerShell)
# Unified entry point for launching various services

# Color definitions
$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Red = [ConsoleColor]::Red
$Blue = [ConsoleColor]::Blue
$Cyan = [ConsoleColor]::Cyan
$Reset = [ConsoleColor]::Gray

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Colored {
    param([string]$Message, [ConsoleColor]$Color = $Reset)
    $oldColor = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $Color
    Write-Host $Message
    $Host.UI.RawUI.ForegroundColor = $oldColor
}

function Write-Header {
    Write-Host "==========================================" -ForegroundColor $Cyan
    Write-Host "       TradeAgent Startup Script         " -ForegroundColor $Cyan
    Write-Host "==========================================" -ForegroundColor $Cyan
    Write-Host ""
}

function Show-Help {
    Write-Header
    Write-Host "Usage: .\start.ps1 [option]"
    Write-Host ""
    Write-Host "Options:" -ForegroundColor $Yellow
    Write-Host "  -d, --dev          Start backend dev mode"
    Write-Host "  -m, --mixed        Start mixed mode (Docker infra + Python runtime)"
    Write-Host "  -b, --backend      Start backend Docker services"
    Write-Host "  -f, --frontend     Start frontend dev server"
    Write-Host "  -a, --all          Start all services"
    Write-Host "  -r, --replay       Start replay engine"
    Write-Host "  -g, --governor     Start Runtime Governor"
    Write-Host "  -s, --stop         Stop all services"
    Write-Host "  -t, --status       Check service status"
    Write-Host "  -l, --logs         View backend logs"
    Write-Host "  -h, --help         Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\start.ps1 --dev"
    Write-Host "  .\start.ps1 --mixed"
    Write-Host "  .\start.ps1 --frontend"
}

function Start-Dev {
    Write-Host "Starting backend dev mode..." -ForegroundColor $Blue
    Push-Location "$ScriptDir\backend"
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" menu
    }
    Pop-Location
}

function Start-Mixed {
    Write-Host "Starting mixed mode..." -ForegroundColor $Blue
    Write-Host ""
    Write-Host "Mixed mode includes:" -ForegroundColor $Cyan
    Write-Host "  - Infrastructure (Kafka, Redis) in Docker"
    Write-Host "  - Python Runtime running directly"
    Write-Host "  - API Server (FastAPI)"
    Write-Host "  - Frontend dev server (Vite)"
    Write-Host ""
    
    Push-Location "$ScriptDir\backend"
    
    Write-Host "Step 1/4: Starting infrastructure..." -ForegroundColor $Yellow
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" infra-up
    }
    Write-Host ""
    
    Write-Host "Step 2/4: Starting all Python Runtimes..." -ForegroundColor $Yellow
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" start-all
    }
    Write-Host ""
    
    Write-Host "Step 3/4: Starting API Server..." -ForegroundColor $Yellow
    $logDir = Join-Path $ScriptDir "backend\logs"
    $null = New-Item -ItemType Directory -Force -Path $logDir -ErrorAction SilentlyContinue
    $apiLog = Join-Path $logDir "api_server.log"
    Start-Process python -ArgumentList "api_server.py" -RedirectStandardOutput $apiLog -NoNewWindow -WorkingDirectory "$ScriptDir\backend"
    Start-Sleep -Seconds 3
    Write-Host "API Server started" -ForegroundColor $Green
    Write-Host ""
    
    Write-Host "Step 4/4: Starting frontend dev server..." -ForegroundColor $Yellow
    Push-Location "$ScriptDir\frontend"
    if (!(Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor $Cyan
        npm install
    }
    $frontendLog = Join-Path $logDir "frontend.log"
    Start-Process npm -ArgumentList "run dev" -RedirectStandardOutput $frontendLog -NoNewWindow -WorkingDirectory "$ScriptDir\frontend"
    Start-Sleep -Seconds 3
    Write-Host "Frontend started" -ForegroundColor $Green
    Pop-Location
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor $Green
    Write-Host "      Mixed mode started successfully     " -ForegroundColor $Green
    Write-Host "==========================================" -ForegroundColor $Green
    Write-Host ""
    Write-Host "Services:" -ForegroundColor $Cyan
    Write-Host "  Frontend:       http://localhost:3000"
    Write-Host "  API Server:   http://localhost:8001"
    Write-Host "  API Docs:     http://localhost:8001/docs"
    Write-Host "  Kafka UI:     http://localhost:8080"
    Write-Host ""
    Write-Host "Management:" -ForegroundColor $Yellow
    Write-Host "  Check status: .\start.ps1 --status"
    Write-Host "  View logs:    .\start.ps1 --logs"
    Write-Host "  Stop all:    .\start.ps1 --stop"
}

function Start-Backend-Docker {
    Write-Host "Starting backend Docker services..." -ForegroundColor $Blue
    Push-Location "$ScriptDir\backend\deploy"
    if (Test-Path "docker-compose.yml") {
        docker compose up -d
    } elseif (Test-Path "docker-compose.yaml") {
        docker compose up -d
    }
    Pop-Location
}

function Start-Frontend {
    Write-Host "Starting frontend service..." -ForegroundColor $Blue
    Push-Location "$ScriptDir\frontend"

    if (!(Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor $Yellow
        npm install
    }

    Write-Host "Starting frontend dev server..." -ForegroundColor $Green
    npm run dev
    Pop-Location
}

function Start-Governor {
    Write-Host "Starting Runtime Governor..." -ForegroundColor $Blue
    Write-Host ""
    
    Push-Location "$ScriptDir\backend"
    $logDir = Join-Path $ScriptDir "backend\logs"
    $null = New-Item -ItemType Directory -Force -Path $logDir -ErrorAction SilentlyContinue
    $govLog = Join-Path $logDir "governor.log"
    
    Write-Host "Launching Runtime Governor..." -ForegroundColor $Green
    Start-Process python -ArgumentList "-m runtime.governor_runtime" -RedirectStandardOutput $govLog -RedirectStandardError $govLog -NoNewWindow -WorkingDirectory "$ScriptDir\backend"
    
    Write-Host "Runtime Governor started" -ForegroundColor $Green
    Write-Host "  Log: $govLog"
    Pop-Location
}

function Stop-All {
    Write-Host "Stopping all services..." -ForegroundColor $Yellow
    
    Get-Process node -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and ($wmiProcess.CommandLine -like "*vite*" -or $wmiProcess.CommandLine -like "*frontend*")
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*api_server.py*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*governor_runtime*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    Push-Location "$ScriptDir\backend"
    Write-Host "Stopping Python Runtimes..." -ForegroundColor $Cyan
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" stop-all
    }

    Write-Host "Stopping Docker infrastructure..." -ForegroundColor $Cyan
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" infra-down
    }

    Write-Host "All services stopped" -ForegroundColor $Green
    Pop-Location
}

function Show-Status {
    Write-Host "Checking service status..." -ForegroundColor $Blue
    Write-Host ""

    Write-Host "Runtime Governor:" -ForegroundColor $Yellow
    $govProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*governor_runtime*"
    }
    if ($govProcess) {
        Write-Host "  Running" -ForegroundColor $Green
    } else {
        Write-Host "  Not running" -ForegroundColor $Red
    }
    Write-Host ""

    Write-Host "Frontend Service:" -ForegroundColor $Yellow
    $viteProcess = Get-Process node -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and ($wmiProcess.CommandLine -like "*vite*" -or $wmiProcess.CommandLine -like "*frontend*")
    }
    if ($viteProcess) {
        Write-Host "  Running" -ForegroundColor $Green
    } else {
        Write-Host "  Not running" -ForegroundColor $Red
    }
    Write-Host ""

    Write-Host "API Server:" -ForegroundColor $Yellow
    $apiProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*api_server.py*"
    }
    if ($apiProcess) {
        Write-Host "  Running" -ForegroundColor $Green
    } else {
        Write-Host "  Not running" -ForegroundColor $Red
    }
    Write-Host ""

    Write-Host "Backend Services:" -ForegroundColor $Yellow
    Push-Location "$ScriptDir\backend"
    if (Test-Path "dev.ps1") {
        & ".\dev.ps1" status
    }
    Pop-Location
}

function Show-Logs {
    param([string]$Mode = "docker")
    
    if ($Mode -eq "dev") {
        Push-Location "$ScriptDir\backend"
        if (Test-Path "dev.ps1") {
            & ".\dev.ps1" logs ($args | Select-Object -Skip 1)
        }
    } else {
        Push-Location "$ScriptDir\backend\deploy"
        docker compose logs
    }
    Pop-Location
}

# Main program
if ($args.Count -eq 0) {
    Show-Help
} else {
    switch ($args[0]) {
        "-d" { Start-Dev }
        "--dev" { Start-Dev }
        "-m" { Start-Mixed }
        "--mixed" { Start-Mixed }
        "-b" { Start-Backend-Docker }
        "--backend" { Start-Backend-Docker }
        "-f" { Start-Frontend }
        "--frontend" { Start-Frontend }
        "-a" { Start-Backend-Docker; Start-Frontend }
        "--all" { Start-Backend-Docker; Start-Frontend }
        "-g" { Start-Governor }
        "--governor" { Start-Governor }
        "-s" { Stop-All }
        "--stop" { Stop-All }
        "-t" { Show-Status }
        "--status" { Show-Status }
        "-l" { Show-Logs ($args | Select-Object -Skip 1) }
        "--logs" { Show-Logs ($args | Select-Object -Skip 1) }
        "-h" { Show-Help }
        "--help" { Show-Help }
        default { 
            Write-Host "Unknown option: $($args[0])" -ForegroundColor $Red
            Show-Help
        }
    }
}
