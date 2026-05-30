import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from research.alpha.feature_availability_audit import run_availability_audit, print_ready_features
    
    print("Starting audit...")
    audit_df = run_availability_audit(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        days=30,
        exclude_sources=["oi", "liquidation", "orderbook"],
    )
    
    print_ready_features(audit_df)
    
    output_path = BACKEND_ROOT / "reports" / "alpha" / "no_oi" / "feature_audit_BTCUSDT_1h_30d.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()