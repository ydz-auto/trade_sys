# Backend Development Service Manager (Windows PowerShell)
# Runtime architecture version

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonPath = "E:\02_code_build_envirenment\20251204_anaconda3\envs\tradeagent\python.exe"

$Green = [ConsoleColor]::Green
$Yellow = [ConsoleColor]::Yellow
$Red = [ConsoleColor]::Red
$Blue = [ConsoleColor]::Blue
$Cyan = [ConsoleColor]::Cyan
$Reset = [ConsoleColor]::Gray

$Runtimes = @{
    "ingestion" = "runtime.ingestion_runtime"
    "feature" = "runtime.feature_runtime"
    "signal" = "runtime.signal_runtime"
    "execution" = "runtime.execution_runtime"
    "portfolio" = "runtime.portfolio_runtime"
    "projection" = "runtime.projection_runtime"
    "correlation" = "runtime.correlation_runtime"
    "narrative" = "runtime.narrative_runtime"
    "regime" = "runtime.regime_runtime"
    "replay" = "runtime.replay_runtime"
}

$GpuRuntimes = @{
    "gpu-signal" = "runtime.signal_runtime"
}

$RuntimeNames = @{
    "ingestion" = "Data Ingestion Runtime"
    "feature" = "Feature Computation Runtime"
    "signal" = "Signal Generation Runtime"
    "execution" = "Order Execution Runtime"
    "portfolio" = "Portfolio Management Runtime"
    "projection" = "CQRS Projection Runtime"
    "correlation" = "Correlation Analysis Runtime"
    "narrative" = "AI Narrative Runtime"
    "regime" = "Market Regime Runtime"
    "replay" = "Replay Runtime"
    "gpu-signal" = "GPU Signal Runtime"
}

$LogDir = Join-Path $ScriptDir "logs"
$null = New-Item -ItemType Directory -Force -Path $LogDir -ErrorAction SilentlyContinue

function Write-Header {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor $Cyan
    Write-Host "  TradeAgent - Runtime Dev Service Manager" -ForegroundColor $Cyan
    Write-Host "==========================================" -ForegroundColor $Cyan
    Write-Host ""
}

function Show-Help {
    Write-Header
    Write-Host "Usage: .\dev.ps1 [command] [options]"
    Write-Host ""
    Write-Host "Runtime Management:" -ForegroundColor $Yellow
    Write-Host "  start <runtime>    Start a specific runtime"
    Write-Host "  stop <runtime>     Stop a specific runtime"
    Write-Host "  status [runtime]   Check runtime status"
    Write-Host "  logs <runtime>     View runtime logs"
    Write-Host ""
    Write-Host "Batch Operations:" -ForegroundColor $Yellow
    Write-Host "  start-all          Start all runtimes"
    Write-Host "  stop-all           Stop all runtimes"
    Write-Host ""
    Write-Host "Infrastructure:" -ForegroundColor $Yellow
    Write-Host "  infra-up           Start Kafka, Redis"
    Write-Host "  infra-down         Stop infrastructure"
    Write-Host "  infra-status       Check infrastructure status"
    Write-Host "  fix-kafka          Reset Kafka (delete all data)"
    Write-Host ""
    Write-Host "GPU Acceleration:" -ForegroundColor $Yellow
    Write-Host "  gpu-start <runtime> Start GPU-accelerated runtime"
    Write-Host "  gpu-status         Check GPU status"
    Write-Host "  gpu-test           Run GPU acceleration tests"
    Write-Host ""
    Write-Host "Other:" -ForegroundColor $Yellow
    Write-Host "  api                Start API server"
    Write-Host "  list               List all runtimes"
    Write-Host "  menu               Show interactive menu"
    Write-Host "  help               Show this help"
    Write-Host ""
    Write-Host "Available Runtimes:" -ForegroundColor $Cyan
    foreach ($key in $Runtimes.Keys) {
        Write-Host "  $key"
    }
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\dev.ps1 infra-up"
    Write-Host "  .\dev.ps1 start ingestion"
    Write-Host "  .\dev.ps1 start-all"
}

function List-Runtimes {
    Write-Host "Available Runtimes:" -ForegroundColor $Cyan
    Write-Host ""
    foreach ($key in $Runtimes.Keys) {
        $runtimePath = $Runtimes[$key]
        $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
            $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
        }
        if ($process) {
            Write-Host "  $key - Running" -ForegroundColor $Green
        } else {
            Write-Host "  $key - Stopped" -ForegroundColor $Red
        }
    }
}

function Start-Runtime {
    param([string]$Runtime)
    
    if ([string]::IsNullOrEmpty($Runtime)) {
        Write-Host "Error: Please specify a runtime name" -ForegroundColor $Red
        Write-Host "Use '.\dev.ps1 list' to see available runtimes"
        return 1
    }

    if (!$Runtimes.ContainsKey($Runtime)) {
        Write-Host "Error: Unknown runtime '$Runtime'" -ForegroundColor $Red
        Write-Host "Use '.\dev.ps1 list' to see available runtimes"
        return 1
    }

    $runtimePath = $Runtimes[$Runtime]
    $runtimeName = $RuntimeNames[$Runtime]
    $logFile = Join-Path $LogDir "$Runtime.log"
    
    $existingProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
    }
    
    if ($existingProcess) {
        Write-Host "$runtimeName already running" -ForegroundColor $Yellow
        return 0
    }

    Write-Host "Starting $runtimeName..." -ForegroundColor $Green
    $env:RUNTIME_NAME = $Runtime
    $env:LOG_DIR = $LogDir
    $process = Start-Process $PythonPath -ArgumentList "-m", $runtimePath -RedirectStandardOutput $logFile -NoNewWindow -WorkingDirectory $ScriptDir -PassThru
    Start-Sleep -Seconds 1

    $runningProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if ($runningProcess) {
        Write-Host "OK: $runtimeName started (PID: $($process.Id))" -ForegroundColor $Green
        Write-Host "  Log file: $logFile"
    } else {
        Write-Host "FAILED: $runtimeName could not start" -ForegroundColor $Red
        Write-Host "  Check log: Get-Content $logFile -Wait -Tail 50"
        return 1
    }
}

function Stop-Runtime {
    param([string]$Runtime)
    
    if ([string]::IsNullOrEmpty($Runtime)) {
        Write-Host "Error: Please specify a runtime name" -ForegroundColor $Red
        return 1
    }

    if (!$Runtimes.ContainsKey($Runtime)) {
        Write-Host "Error: Unknown runtime '$Runtime'" -ForegroundColor $Red
        return 1
    }

    $runtimePath = $Runtimes[$Runtime]
    $runtimeName = $RuntimeNames[$Runtime]

    $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
    }

    if (!$process) {
        Write-Host "$runtimeName not running" -ForegroundColor $Yellow
        return 0
    }

    Write-Host "Stopping $runtimeName..." -ForegroundColor $Yellow
    $process | Stop-Process -Force
    Start-Sleep -Seconds 1

    $stillRunning = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
        $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
    }
    
    if ($stillRunning) {
        Write-Host "FAILED: Could not stop $runtimeName" -ForegroundColor $Red
        return 1
    } else {
        Write-Host "OK: $runtimeName stopped" -ForegroundColor $Green
    }
}

function Show-Status {
    param([string]$Runtime)
    
    if (![string]::IsNullOrEmpty($Runtime)) {
        if (!$Runtimes.ContainsKey($Runtime)) {
            Write-Host "Error: Unknown runtime '$Runtime'" -ForegroundColor $Red
            return 1
        }
        
        $runtimePath = $Runtimes[$Runtime]
        $runtimeName = $RuntimeNames[$Runtime]
        
        Write-Host "$runtimeName Status:" -ForegroundColor $Cyan
        $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
            $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
        }
        if ($process) {
            Write-Host "  Status: Running" -ForegroundColor $Green
            $process | ForEach-Object { Write-Host "  PID: $($_.Id)" }
        } else {
            Write-Host "  Status: Stopped" -ForegroundColor $Red
        }
        
        $logFile = Join-Path $LogDir "$Runtime.log"
        if (Test-Path $logFile) {
            Write-Host "  Log: $logFile"
            Write-Host "  Last 10 lines:"
            Get-Content $logFile -Tail 10 | ForEach-Object { Write-Host "    $_" }
        }
    } else {
        Write-Host "All Runtimes Status:" -ForegroundColor $Cyan
        Write-Host ""
        foreach ($key in $Runtimes.Keys) {
            $runtimePath = $Runtimes[$key]
            $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
                $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
                $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
            }
            if ($process) {
                Write-Host "  [OK] $($RuntimeNames[$key])" -ForegroundColor $Green
            } else {
                Write-Host "  [  ] $($RuntimeNames[$key])" -ForegroundColor $Red
            }
        }
    }
}

function Show-Logs {
    param([string]$Runtime)
    
    if ([string]::IsNullOrEmpty($Runtime)) {
        Write-Host "Error: Please specify a runtime name" -ForegroundColor $Red
        return 1
    }

    if (!$Runtimes.ContainsKey($Runtime)) {
        Write-Host "Error: Unknown runtime '$Runtime'" -ForegroundColor $Red
        return 1
    }

    $logFile = Join-Path $LogDir "$Runtime.log"
    if (!(Test-Path $logFile)) {
        Write-Host "Log file not found: $logFile" -ForegroundColor $Yellow
        return 1
    }

    Write-Host "Viewing $($RuntimeNames[$Runtime]) logs (Ctrl+C to exit):" -ForegroundColor $Cyan
    Get-Content $logFile -Wait -Tail 50
}

function Start-All {
    Write-Host "Starting all Runtimes..." -ForegroundColor $Green
    Write-Host ""
    
    foreach ($key in $Runtimes.Keys) {
        Start-Runtime $key
        Write-Host ""
    }
    
    Write-Host "All Runtimes started" -ForegroundColor $Green
}

function Stop-All {
    Write-Host "Stopping all Runtimes..." -ForegroundColor $Yellow
    
    foreach ($key in $Runtimes.Keys) {
        $runtimePath = $Runtimes[$key]
        $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $wmiProcess = Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue
            $wmiProcess -and $wmiProcess.CommandLine -like "*$runtimePath*"
        }
        if ($process) {
            $process | Stop-Process -Force -ErrorAction SilentlyContinue
        }
    }
    
    Start-Sleep -Seconds 1
    Write-Host "All Runtimes stopped" -ForegroundColor $Green
}

function Infra-Up {
    Write-Host "Starting infrastructure (KRaft mode)..." -ForegroundColor $Green
    Set-Location (Join-Path $ScriptDir "deploy")
    
    Write-Host "Step 1/2: Starting services..." -ForegroundColor $Cyan
    docker compose up -d kafka redis
    
    Write-Host "Step 2/2: Waiting for services..." -ForegroundColor $Cyan
    $maxWait = 30
    $waited = 0
    $kafkaHealthy = 0
    $redisRunning = 0
    
    while ($waited -lt $maxWait) {
        if ($kafkaHealthy -eq 0) {
            $kafkaHealth = docker inspect --format='{{.State.Health.Status}}' kafka 2>$null
            if ($kafkaHealth -eq "healthy") {
                $kafkaHealthy = 1
                Write-Host "OK: Kafka ready" -ForegroundColor $Green
            }
        }
        
        if ($redisRunning -eq 0) {
            $redisStatus = docker inspect --format='{{.State.Status}}' redis 2>$null
            if ($redisStatus -eq "running") {
                $redisRunning = 1
                Write-Host "OK: Redis ready" -ForegroundColor $Green
            }
        }
        
        if ($kafkaHealthy -eq 1 -and $redisRunning -eq 1) {
            break
        }
        
        Write-Host "Waiting... ($waited/$maxWait)" -ForegroundColor $Yellow
        Start-Sleep -Seconds 2
        $waited += 2
    }
    
    Write-Host "Starting Kafka UI..." -ForegroundColor $Cyan
    docker compose up -d kafka-ui
    
    Write-Host ""
    Write-Host "Infrastructure started:" -ForegroundColor $Green
    Write-Host "  Kafka: localhost:9092"
    Write-Host "  Redis: localhost:6379"
    Write-Host "  Kafka UI: http://localhost:8080"
    
    Set-Location $ScriptDir
}

function Infra-Down {
    Write-Host "Stopping infrastructure..." -ForegroundColor $Yellow
    Set-Location (Join-Path $ScriptDir "deploy")
    docker compose down
    Write-Host "Infrastructure stopped" -ForegroundColor $Green
    Set-Location $ScriptDir
}

function Infra-Status {
    Write-Host "Infrastructure Status (KRaft mode):" -ForegroundColor $Cyan
    Set-Location (Join-Path $ScriptDir "deploy")
    try {
        docker compose ps kafka redis 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Not started"
        }
    } catch {
        Write-Host "Not started"
    }
    Set-Location $ScriptDir
}

function Start-API {
    Write-Host "Starting API server..." -ForegroundColor $Green
    Write-Host "API URL: http://localhost:8001" -ForegroundColor $Blue
    Write-Host "Press Ctrl+C to stop" -ForegroundColor $Yellow
    Write-Host ""
    & $PythonPath api_server.py
}

function Get-GpuStatus {
    Write-Host "GPU Acceleration Status:" -ForegroundColor $Cyan
    Write-Host ""
    
    $code = @"
import sys
sys.path.insert(0, '$ScriptDir'.Replace('\', '\\'))
try:
    from infrastructure.acceleration import get_accelerator_info
    info = get_accelerator_info()
    print(f'  Backend: {info["backend"]}')
    print(f'  Device: {info["device_type"]}')
    print(f'  Is GPU: {info["is_gpu"]}')
    print(f'  Device Info: {info["device_info"]}')
except ImportError as e:
    print(f'  Error: {e}')
    print('  PyTorch not installed. Run: pip install torch')
except Exception as e:
    print(f'  Error: {e}')
"@
    
    & $PythonPath -c $code
}

function Start-GpuRuntime {
    param([string]$Runtime)
    
    if ([string]::IsNullOrEmpty($Runtime)) {
        Write-Host "Error: Please specify a GPU runtime name" -ForegroundColor $Red
        Write-Host "Available: gpu-signal, gpu-optimization"
        return 1
    }
    
    if (!$GpuRuntimes.ContainsKey($Runtime)) {
        Write-Host "Error: Unknown GPU runtime '$Runtime'" -ForegroundColor $Red
        Write-Host "Available: gpu-signal, gpu-optimization"
        return 1
    }
    
    $runtimePath = $GpuRuntimes[$Runtime]
    $runtimeName = $RuntimeNames[$Runtime]
    $logFile = Join-Path $LogDir "$Runtime.log"
    
    Write-Host "Starting $runtimeName (GPU accelerated)..." -ForegroundColor $Green
    $env:RUNTIME_NAME = $Runtime
    $env:LOG_DIR = $LogDir
    $env:TORCH_DEVICE = "cuda"
    $process = Start-Process $PythonPath -ArgumentList "-m", $runtimePath -RedirectStandardOutput $logFile -NoNewWindow -WorkingDirectory $ScriptDir -PassThru
    Start-Sleep -Seconds 1
    
    $runningProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if ($runningProcess) {
        Write-Host "OK: $runtimeName started (PID: $($process.Id))" -ForegroundColor $Green
        Write-Host "  Log file: $logFile"
    } else {
        Write-Host "FAILED: $runtimeName could not start" -ForegroundColor $Red
        Write-Host "  Check log: Get-Content $logFile -Wait -Tail 50"
        return 1
    }
}

function Test-GpuAcceleration {
    Write-Host "Running GPU acceleration tests..." -ForegroundColor $Green
    Write-Host ""
    & $PythonPath tests\test_torch_acceleration.py
}

function Show-Menu {
    while ($true) {
        Write-Header
        Write-Host "Select an option:"
        Write-Host ""
        Write-Host "  1) Start infrastructure (Kafka, Redis)"
        Write-Host "  2) Stop infrastructure"
        Write-Host "  3) Start all Runtimes"
        Write-Host "  4) Stop all Runtimes"
        Write-Host "  5) Check Runtime status"
        Write-Host "  6) Start API server"
        Write-Host "  7) View Runtime logs"
        Write-Host "  8) List all Runtimes"
        Write-Host "  0) Exit"
        Write-Host ""
        
        $choice = Read-Host "Enter your choice"
        
        switch ($choice) {
            "1" { Infra-Up }
            "2" { Infra-Down }
            "3" { Start-All }
            "4" { Stop-All }
            "5" { Show-Status }
            "6" { Start-API }
            "7" { 
                List-Runtimes
                $runtimeName = Read-Host "Enter runtime name"
                Show-Logs $runtimeName
            }
            "8" { List-Runtimes }
            "0" { 
                Write-Host "Goodbye!" -ForegroundColor $Green
                return 0
            }
            default { Write-Host "Invalid option: $choice" -ForegroundColor $Red }
        }
        
        Write-Host ""
        Read-Host "Press Enter to continue..."
        Write-Host ""
    }
}

# Main program
if ($args.Count -eq 0) {
    Show-Menu
} else {
    switch ($args[0]) {
        "start" { Start-Runtime $args[1] }
        "stop" { Stop-Runtime $args[1] }
        "status" { Show-Status $args[1] }
        "logs" { Show-Logs $args[1] }
        "start-all" { Start-All }
        "stop-all" { Stop-All }
        "infra-up" { Infra-Up }
        "infra-down" { Infra-Down }
        "infra-status" { Infra-Status }
        "api" { Start-API }
        "list" { List-Runtimes }
        "gpu-start" { Start-GpuRuntime $args[1] }
        "gpu-status" { Get-GpuStatus }
        "gpu-test" { Test-GpuAcceleration }
        "menu" { Show-Menu }
        "help" { Show-Help }
        "--help" { Show-Help }
        "-h" { Show-Help }
        default {
            Write-Host "Unknown command: '$($args[0])'" -ForegroundColor $Red
            Show-Help
        }
    }
}
