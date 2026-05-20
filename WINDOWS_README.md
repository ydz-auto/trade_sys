# Windows PowerShell Scripts Documentation

## Overview

These Windows PowerShell scripts replace the original zsh shell scripts for Windows compatibility.

## Files

- `start.ps1` - Main project startup script (unified entry point)
- `backend/dev.ps1` - Backend development service manager
- `WINDOWS_README.md` - This documentation file

## Requirements

- Windows PowerShell 5.1 or later
- Docker Desktop for Windows (running and functional)
- Python 3.8+
- Node.js (for frontend development)

## Quick Start

```powershell
# Navigate to project directory
cd E:\00_crypto\00_code

# If you get execution policy errors, run this first (current session only):
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Show help
.\start.ps1 --help

# Start mixed mode (recommended for development)
.\start.ps1 --mixed
```

## Commands

### Main Startup Script (start.ps1)

| Command | Description |
|---------|-------------|
| `-d, --dev` | Start backend dev mode |
| `-m, --mixed` | Start mixed mode (Docker infrastructure + Python runtime) |
| `-b, --backend` | Start backend Docker services |
| `-f, --frontend` | Start frontend dev server |
| `-a, --all` | Start all services |
| `-g, --governor` | Start Runtime Governor only |
| `-s, --stop` | Stop all services |
| `-t, --status` | Check service status |
| `-l, --logs` | View backend logs |
| `-h, --help` | Show help message |

### Backend Dev Script (backend/dev.ps1)

| Command | Description |
|---------|-------------|
| `start <runtime>` | Start a specific runtime |
| `stop <runtime>` | Stop a specific runtime |
| `status [runtime]` | Check runtime status |
| `logs <runtime>` | View runtime logs |
| `start-all` | Start all runtimes |
| `stop-all` | Stop all runtimes |
| `infra-up` | Start infrastructure (Kafka, Redis) |
| `infra-down` | Stop infrastructure |
| `infra-status` | Check infrastructure status |
| `api` | Start API server |
| `list` | List all runtimes |
| `menu` | Show interactive menu |
| `help` | Show help |

### Available Runtimes

- `ingestion` - Data Ingestion Runtime
- `signal` - Signal Generation Runtime
- `execution` - Order Execution Runtime
- `projection` - CQRS Projection Runtime
- `correlation` - Correlation Analysis Runtime
- `narrative` - AI Narrative Runtime
- `monitoring` - Monitoring Runtime
- `scheduler` - Scheduler Runtime
- `governor` - Runtime Governor

## Typical Development Workflow

```powershell
# 1. Navigate to project directory
cd E:\00_crypto\00_code

# 2. Start mixed mode (infrastructure + runtimes + frontend)
.\start.ps1 --mixed

# 3. Check status
.\start.ps1 --status

# 4. View logs (if needed)
cd backend
.\dev.ps1 logs ingestion

# 5. When finished, stop everything
cd ..
.\start.ps1 --stop
```

## Services

After starting, you can access:

- Frontend: http://localhost:3000
- API Server: http://localhost:8001
- API Docs: http://localhost:8001/docs
- Kafka UI: http://localhost:8080
- Kafka: localhost:9092
- Redis: localhost:6379

## Troubleshooting

### Execution Policy Errors

If you see "cannot be loaded because running scripts is disabled on this system":

```powershell
# Temporary fix (current session only)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Permanent fix (run as Administrator)
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Docker Not Running

Make sure Docker Desktop is started and running:

```powershell
# Check Docker status
docker info
```

### Port Conflicts

If ports are already in use:

```powershell
# Find what's using a port
netstat -ano | findstr "3000"
netstat -ano | findstr "8001"

# Stop the process using the port
taskkill /F /PID <ProcessID>
```

### Log Files

All logs are stored in `backend/logs/`:
- `api_server.log` - API Server logs
- `frontend.log` - Frontend logs
- `governor.log` - Runtime Governor logs
- `<runtime>.log` - Individual runtime logs

## Differences from Original Shell Scripts

1. Uses Windows PowerShell syntax instead of zsh
2. Uses Windows path separators (`\` instead of `/`)
3. Uses PowerShell process management instead of Unix tools
4. Uses ANSI colors via PowerShell `ForegroundColor`
5. Uses `Start-Process` for background processes
6. Uses `Get-Content -Wait -Tail` for log tailing
7. All output in English for better compatibility

## Notes

- These scripts should be run in PowerShell, not Command Prompt (CMD)
- Make sure Docker Desktop is running before starting services
- First run of frontend will install dependencies automatically
- If you need Chinese language support, you can modify the scripts
