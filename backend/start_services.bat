@echo off
REM 服务启动脚本 (Windows)
REM 使用方法:
REM   start_services.bat - 显示菜单
REM   start_services.bat --monitor - 仅启动监控面板

chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

:MENU
cls
echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                    交易系统 - 服务启动器                       ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.
echo 请选择要执行的操作:
echo.
echo   1. 运行系统验证
echo   2. 运行完整模拟
echo   3. 启动监控面板
echo   4. 查看快速开始指南
echo   5. 查看架构文档
echo   0. 退出
echo.

set /p "choice=请输入选项: "

if "%choice%"=="1" goto VERIFY
if "%choice%"=="2" goto SIMULATE
if "%choice%"=="3" goto MONITOR
if "%choice%"=="4" goto QUICKSTART
if "%choice%"=="5" goto ARCHITECTURE
if "%choice%"=="0" goto EXIT
goto MENU

:VERIFY
echo.
echo 正在运行系统验证...
echo.
python -m scripts.verify_all
pause
goto MENU

:SIMULATE
echo.
echo 正在运行完整模拟...
echo.
python -m scripts.simulate_pipeline
pause
goto MENU

:MONITOR
echo.
echo 正在启动监控面板...
echo 请在浏览器中打开: http://localhost:8000
echo 按 Ctrl+C 停止服务器
echo.
python -m services.monitoring.monitoring_panel
pause
goto MENU

:QUICKSTART
echo.
if exist "QUICKSTART.md" (
    type "QUICKSTART.md"
) else (
    echo 错误: QUICKSTART.md 文件不存在
)
echo.
pause
goto MENU

:ARCHITECTURE
echo.
if exist "docs\ARCHITECTURE_COMPLETION.md" (
    type "docs\ARCHITECTURE_COMPLETION.md"
) else (
    echo 错误: 架构文档不存在
)
echo.
pause
goto MENU

:EXIT
echo.
echo 再见！
exit /b 0
