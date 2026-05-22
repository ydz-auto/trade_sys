import requests
import json
import time

url = "http://localhost:8001/api/v1/optimization-api/optimization/sync"
data = {
    "strategy_id": "sma_crossover",
    "symbol": "BTCUSDT",
    "optimization_start": "2026-04-01",
    "optimization_end": "2026-04-30",
    "method": "grid_search",
    "metric": "sharpe_ratio",
    "param_grid": {
        "sma_fast": [5, 10, 20],
        "sma_slow": [20, 30, 50],
    },
    "initial_capital": 10000,
    "commission": 0.0005,
    "slippage": 0.0002,
    "position_size": 0.3,
    "stop_loss": 0.02,
    "take_profit": 0.04,
}

print("Sending optimization request...")
print(f"  Strategy: {data['strategy_id']}")
print(f"  Symbol: {data['symbol']}")
print(f"  Period: {data['optimization_start']} ~ {data['optimization_end']}")
print(f"  Param grid: {data['param_grid']}")
print(f"  Combinations: {len(data['param_grid']['sma_fast']) * len(data['param_grid']['sma_slow'])}")
print()

start_time = time.time()

try:
    r = requests.post(url, json=data, timeout=120)
    elapsed = time.time() - start_time
    print(f"Status: {r.status_code}")
    print(f"Elapsed: {elapsed:.2f}s")
    result = r.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
except requests.exceptions.Timeout:
    elapsed = time.time() - start_time
    print(f"Timeout after {elapsed:.2f}s")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"Error after {elapsed:.2f}s: {e}")
