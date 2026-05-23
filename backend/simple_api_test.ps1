# API 流程测试 - 简化版

Write-Host "========================================"
Write-Host "   API 流程测试"
Write-Host "========================================"

$BaseUrl = "http://localhost:8001/api/v1"

# 测试 1: 健康检查
Write-Host "`n[Step 1] 健康检查"
Write-Host "----------------------------------------"
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET
    Write-Host "API 状态: $($health.status)"
    Write-Host "Mock 模式: $($health.mock_mode)"
    Write-Host "时间: $($health.timestamp)"
    Write-Host "✅ API 服务正常"
} catch {
    Write-Host "❌ API 连接失败: $_"
    exit 1
}

# 测试 2: 特征生成
Write-Host "`n[Step 2] 生成特征"
Write-Host "----------------------------------------"
$body = @{
    symbol = "BTCUSDT"
    years = @(2023)
    intervals = @("1h")
    force_regenerate = $true
} | ConvertTo-Json

try {
    $start = Get-Date
    $resp = Invoke-RestMethod -Uri "$BaseUrl/features/generate" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 300
    $elapsed = ((Get-Date) - $start).TotalSeconds
    
    Write-Host "耗时: $($elapsed.ToString('F2'))s"
    Write-Host "成功: $($resp.success)"
    Write-Host "记录数: $($resp.total_records)"
    Write-Host "✅ 特征生成完成"
} catch {
    Write-Host "❌ 特征生成失败: $_"
}

# 测试 3: 策略优化
Write-Host "`n[Step 3] 策略优化"
Write-Host "----------------------------------------"
$optBody = @{
    strategy_id = "sma_cross"
    symbol = "BTCUSDT"
    optimization_start = "2023-04-01"
    optimization_end = "2023-04-30"
    method = "grid_search"
    metric = "sharpe_ratio"
    param_grid = @{
        fast = @(5, 10)
        slow = @(20, 30)
    }
    initial_capital = 10000
    commission = 0.0005
    slippage = 0.0002
    position_size = 0.3
    stop_loss = 0.02
    take_profit = 0.04
    use_multiprocess = $true
    max_concurrent = 2
} | ConvertTo-Json

try {
    $start = Get-Date
    $resp = Invoke-RestMethod -Uri "$BaseUrl/optimization-api/optimization" -Method POST -Body $optBody -ContentType "application/json" -TimeoutSec 180
    $elapsed = ((Get-Date) - $start).TotalSeconds
    
    Write-Host "耗时: $($elapsed.ToString('F2'))s"
    Write-Host "优化ID: $($resp.optimization_id)"
    Write-Host "策略: $($resp.strategy_id)"
    Write-Host "状态: $($resp.status)"
    Write-Host "✅ 优化任务已创建"
} catch {
    Write-Host "❌ 优化失败: $_"
}

# 测试 4: 回测
Write-Host "`n[Step 4] 回测"
Write-Host "----------------------------------------"
$btBody = @{
    config = @{
        symbol = "BTCUSDT"
        start_date = "2023-04-01"
        end_date = "2023-04-30"
        initial_capital = 10000
        strategy = "sma_cross"
        params = @{
            fast = 10
            slow = 50
        }
    }
} | ConvertTo-Json

try {
    $start = Get-Date
    $resp = Invoke-RestMethod -Uri "$BaseUrl/backtest-api/backtest" -Method POST -Body $btBody -ContentType "application/json" -TimeoutSec 120
    $elapsed = ((Get-Date) - $start).TotalSeconds
    
    Write-Host "耗时: $($elapsed.ToString('F2'))s"
    Write-Host "回测ID: $($resp.id)"
    Write-Host "状态: $($resp.status)"
    Write-Host "✅ 回测任务已创建"
} catch {
    Write-Host "❌ 回测失败: $_"
}

Write-Host "`n========================================"
Write-Host "   测试完成"
Write-Host "========================================"
