"""
简单的交易系统监控面板
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    print("请安装依赖：pip install fastapi uvicorn")
    exit(1)

from infrastructure.logging import get_logger
logger = get_logger("monitoring_panel")

app = FastAPI(title="交易系统监控面板")

# 存储模拟数据
state = {
    "signals": [],
    "decisions": [],
    "orders": [],
    "price_history": [],
    "system_status": {
        "data_service": "offline",
        "event_service": "offline",
        "fusion_service": "offline",
        "strategy_service": "offline",
        "risk_service": "offline",
        "execution_service": "offline",
    },
    "current_price": 50000.0,
}

# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>交易系统监控面板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
        header {{ margin-bottom: 32px; }}
        h1 {{ font-size: 32px; font-weight: 700; background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ color: #94a3b8; margin-top: 8px; font-size: 14px; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; margin-bottom: 32px; }}
        .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
        .stat-label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-value {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
        .stat-value.up {{ color: #10b981; }}
        .stat-value.down {{ color: #ef4444; }}
        
        .price-display {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 32px; }}
        .price-label {{ color: #94a3b8; font-size: 14px; margin-bottom: 8px; }}
        .price-value {{ font-size: 48px; font-weight: 700; }}
        
        .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .status-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
        .status-name {{ font-weight: 600; margin-bottom: 8px; }}
        .status-indicator {{ display: flex; align-items: center; gap: 8px; }}
        .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #64748b; }}
        .dot.online {{ background: #10b981; }}
        .dot.offline {{ background: #ef4444; }}
        
        .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
        .section-title {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #334155; }}
        
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th {{ text-align: left; padding: 12px; color: #94a3b8; font-weight: 600; font-size: 12px; text-transform: uppercase; }}
        .table td {{ padding: 12px; border-top: 1px solid #334155; }}
        
        .long {{ color: #10b981; }}
        .short {{ color: #ef4444; }}
        
        .actions {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }}
        .btn-primary {{ background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; }}
        .btn-secondary {{ background: #334155; color: #e2e8f0; border: 1px solid #475569; }}
        
        .refresh-time {{ color: #64748b; font-size: 12px; margin-top: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 交易系统监控面板</h1>
            <p class="subtitle">实时监控交易系统的运行状态</p>
        </header>
        
        <div class="actions">
            <button class="btn btn-primary" onclick="location.reload()">🔄 刷新页面</button>
            <button class="btn btn-secondary" onclick="simulateStep()">🎲 模拟下一步</button>
        </div>
        
        <div class="price-display">
            <div class="price-label">BTCUSDT 价格</div>
            <div class="price-value">${price:,.2f}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">总信号数</div>
                <div class="stat-value">{signals_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">决策数</div>
                <div class="stat-value">{decisions_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">订单数</div>
                <div class="stat-value">{orders_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">总成交额</div>
                <div class="stat-value up">${total_value:,.2f}</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">⚡ 服务状态</div>
            <div class="status-grid">
                {status_cards}
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">📊 最近订单</div>
            <table class="table">
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>动作</th>
                        <th>数量</th>
                        <th>价格</th>
                        <th>价值</th>
                    </tr>
                </thead>
                <tbody>
                    {orders_rows}
                </tbody>
            </table>
        </div>
        
        <div class="refresh-time">最后更新: {last_update}</div>
    </div>
    
    <script>
        async function simulateStep() {{
            await fetch('/api/simulate-step');
            location.reload();
        }}
    </script>
</body>
</html>
"""


def format_status_cards() -> str:
    """格式化服务状态卡片"""
    cards_html = []
    for service, status in state["system_status"].items():
        display_name = service.replace("_", " ").title()
        is_online = status == "online"
        status_class = "online" if is_online else "offline"
        
        cards_html.append(f"""
            <div class="status-card">
                <div class="status-name">{display_name}</div>
                <div class="status-indicator">
                    <span class="dot {status_class}"></span>
                    <span>{status.upper()}</span>
                </div>
            </div>
        """)
    return "\n".join(cards_html)


def format_orders_rows() -> str:
    """格式化订单表格"""
    if not state["orders"]:
        return '<tr><td colspan="5" style="text-align: center; color: #64748b;">暂无订单</td></tr>'
    
    rows = []
    for order in reversed(state["orders"][-10:]):  # 最近 10 个
        action_class = "long" if order["action"] == "LONG" else "short"
        rows.append(f"""
            <tr>
                <td>{order["timestamp"].split("T")[1][:8]}</td>
                <td class="{action_class}">{order["action"]}</td>
                <td>{order["quantity"]:.4f}</td>
                <td>${order["price"]:.2f}</td>
                <td>${order["value"]:.2f}</td>
            </tr>
        """)
    return "\n".join(rows)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """获取监控面板"""
    total_value = sum(o["value"] for o in state["orders"])
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = HTML_TEMPLATE.format(
        price=state["current_price"],
        signals_count=len(state["signals"]),
        decisions_count=len(state["decisions"]),
        orders_count=len(state["orders"]),
        total_value=total_value,
        status_cards=format_status_cards(),
        orders_rows=format_orders_rows(),
        last_update=last_update,
    )
    return html


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    total_value = sum(o["value"] for o in state["orders"])
    return {
        "current_price": state["current_price"],
        "signals_count": len(state["signals"]),
        "decisions_count": len(state["decisions"]),
        "orders_count": len(state["orders"]),
        "total_value": total_value,
        "services": state["system_status"],
    }


@app.post("/api/simulate-step")
async def simulate_step():
    """模拟一个步骤"""
    from scripts.simulate_pipeline import PipelineSimulator
    
    # 创建临时模拟器
    simulator = PipelineSimulator()
    
    # 运行一个步骤
    simulator.execution_engine.current_price = state["current_price"]
    simulator.execution_engine.orders = state["orders"]
    
    # 产生信号并运行流程
    import random
    signal = simulator.generate_signal(random.random() > 0.3)
    state["signals"].append(signal)
    
    decision = simulator.run_strategy(signal)
    state["decisions"].append(decision)
    
    checked = simulator.check_risk(decision)
    if checked.approved:
        simulator.execute_decision(checked)
        state["orders"] = simulator.execution_engine.orders
    
    # 更新价格
    price_change = (random.random() - 0.5) * 200
    state["current_price"] += price_change
    
    return {"success": True}


@app.post("/api/set-service-status")
async def set_service_status(service: str, status: str):
    """设置服务状态"""
    valid_statuses = ["online", "offline"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="无效的状态")
    
    if service not in state["system_status"]:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    state["system_status"][service] = status
    return {"service": service, "status": status}


if __name__ == "__main__":
    import uvicorn
    print("=" * 70)
    print("交易系统监控面板")
    print("=" * 70)
    print("\n请在浏览器中访问: http://localhost:8000")
    print("\n按 Ctrl+C 停止服务器\n")
    
    # 设置一些服务为在线
    state["system_status"] = {
        "data_service": "online",
        "event_service": "online",
        "fusion_service": "online",
        "strategy_service": "online",
        "risk_service": "online",
        "execution_service": "online",
    }
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
