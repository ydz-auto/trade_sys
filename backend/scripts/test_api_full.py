import requests
import json
import time

BASE_URL = "http://localhost:8001/api/v1"

def test_feature_generation():
    print("=" * 60)
    print("Step 1: Generate features for BTCUSDT (2023-04)")
    print("=" * 60)

    url = f"{BASE_URL}/features/generate"
    data = {
        "symbol": "BTCUSDT",
        "years": [2023],
        "intervals": ["1h"],
        "force_regenerate": True,
    }

    print(f"POST {url}")
    print(f"  Data: {json.dumps(data, indent=2)}")
    print()

    start_time = time.time()
    try:
        r = requests.post(url, json=data, timeout=300)
        elapsed = time.time() - start_time
        print(f"Status: {r.status_code}")
        print(f"Elapsed: {elapsed:.2f}s")
        result = r.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result.get("success", False)
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"Timeout after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Error after {elapsed:.2f}s: {e}")
        return False


def test_optimization():
    print()
    print("=" * 60)
    print("Step 2: Run optimization (2023-04, 1 month)")
    print("=" * 60)

    url = f"{BASE_URL}/optimization-api/optimization/sync"
    data = {
        "strategy_id": "sma_crossover",
        "symbol": "BTCUSDT",
        "optimization_start": "2023-04-01",
        "optimization_end": "2023-04-30",
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

    combos = len(data["param_grid"]["sma_fast"]) * len(data["param_grid"]["sma_slow"])
    print(f"POST {url}")
    print(f"  Strategy: {data['strategy_id']}")
    print(f"  Symbol: {data['symbol']}")
    print(f"  Period: {data['optimization_start']} ~ {data['optimization_end']}")
    print(f"  Param combinations: {combos}")
    print()

    start_time = time.time()
    try:
        r = requests.post(url, json=data, timeout=120)
        elapsed = time.time() - start_time
        print(f"Status: {r.status_code}")
        print(f"Elapsed: {elapsed:.2f}s")
        result = r.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"Timeout after {elapsed:.2f}s")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Error after {elapsed:.2f}s: {e}")
        return None


def test_backtest():
    print()
    print("=" * 60)
    print("Step 3: Run backtest (2023-04, 1 month)")
    print("=" * 60)

    url = f"{BASE_URL}/backtest-api/backtest"
    data = {
        "config": {
            "symbol": "BTCUSDT",
            "start_date": "2023-04-01",
            "end_date": "2023-04-30",
            "initial_capital": 10000,
            "strategy": "sma_crossover",
        }
    }

    print(f"POST {url}")
    print(f"  Data: {json.dumps(data, indent=2)}")
    print()

    start_time = time.time()
    try:
        r = requests.post(url, json=data, timeout=120)
        elapsed = time.time() - start_time
        print(f"Status: {r.status_code}")
        print(f"Elapsed: {elapsed:.2f}s")
        result = r.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"Timeout after {elapsed:.2f}s")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Error after {elapsed:.2f}s: {e}")
        return None


if __name__ == "__main__":
    test_feature_generation()
    test_optimization()
    test_backtest()
