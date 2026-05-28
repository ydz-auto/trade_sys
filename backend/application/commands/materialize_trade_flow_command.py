import sys
import argparse
from pathlib import Path
from typing import List

_BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

def main():
    parser = argparse.ArgumentParser(description="Trade Flow Materialization")
    parser.add_argument("--exchange", type=str, default="binance")
    parser.add_argument("--symbols", type=str, default="BTCUSDT")
    parser.add_argument("--timeframe", type=str, default="1h")
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    symbols: List[str] = [s.strip() for s in args.symbols.split(",")]
    timeframes: List[str] = [t.strip() for t in args.timeframe.split(",")]

    from runtime.pipeline.trade_flow_materialization_pipeline import TradeFlowMaterializationPipeline
    pipeline = TradeFlowMaterializationPipeline()

    for symbol in symbols:
        for tf in timeframes:
            print(f"[{symbol} | {tf}] Materializing...")
            path = pipeline.run(
                symbol=symbol,
                exchange=args.exchange,
                timeframe=tf,
                start=args.start,
                end=args.end,
                force=args.force,
            )
            if path:
                print(f"  Saved to {path}")
            else:
                print(f"  No data")

if __name__ == "__main__":
    main()
