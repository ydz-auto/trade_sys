"""
Alpha Research Factory - CLI

统一命令行入口

使用方式:
    python -m research.alpha.cli --module features --action build --symbol BTCUSDT
    python -m research.alpha.cli --module ic --action analyze --symbol BTCUSDT
    python -m research.alpha.cli --module signals --action test --symbol BTCUSDT
    python -m research.alpha.cli --module validation --action pipeline --symbol BTCUSDT
    python -m research.alpha.cli --module reporting --action leaderboard --symbol BTCUSDT
"""

import sys
from pathlib import Path
from typing import Optional

import argparse

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def run_features(args):
    """运行 features 模块"""
    from research.alpha import features

    if args.action == "build":
        from research.alpha.features.matrix_adapter import get_research_feature_matrix

        feature_source = getattr(args, "feature_source", "research")
        print(f"Building feature matrix: {args.symbol} (source={feature_source})")
        fm = get_research_feature_matrix(
            symbol=args.symbol,
            exchange=args.exchange,
            days=args.days,
            timeframe=args.timeframe,
            feature_source=feature_source,
        )
        print(f"Feature matrix built: {fm.shape}")

    elif args.action == "audit":
        from research.alpha.features import run_availability_audit

        print(f"Running feature availability audit: {args.symbol}")
        audit_df = run_availability_audit(
            symbol=args.symbol,
            exchange=args.exchange,
            days=args.days,
        )
        print(f"Audit complete: {len(audit_df)} features")

    elif args.action == "quality":
        from research.alpha.features import check_feature_quality

        print(f"Checking feature quality: {args.symbol}")
        report = check_feature_quality(
            symbol=args.symbol,
            exchange=args.exchange,
            days=args.days,
        )
        print(f"Quality check complete")


def run_ic(args):
    """运行 IC 模块"""
    from research.alpha import ic

    if args.action == "analyze":
        from research.alpha.ic import calculate_rank_ic

        print(f"Running IC analysis: {args.symbol}")
        ic_result = calculate_rank_ic(
            symbol=args.symbol,
            exchange=args.exchange,
            days=args.days,
        )
        print(f"IC analysis complete")


def run_signals(args):
    """运行 signals 模块"""
    if args.action == "test":
        print(f"Testing signals: {args.symbol}")
        print("Signal test not yet implemented")


def run_validation(args):
    """运行 validation 模块"""
    if args.action == "pipeline":
        from research.alpha.validation import AlphaValidationPipeline

        print(f"Running validation pipeline: {args.symbol}")
        pipeline = AlphaValidationPipeline(
            symbol=args.symbol,
            exchange=args.exchange,
        )
        result = pipeline.run()
        print(f"Validation complete: {result}")


def run_reporting(args):
    """运行 reporting 模块"""
    if args.action == "leaderboard":
        from research.alpha.reporting import generate_leaderboard

        print(f"Generating leaderboard: {args.symbol}")
        leaderboard = generate_leaderboard(symbol=args.symbol)
        print(f"Leaderboard generated")


def main():
    parser = argparse.ArgumentParser(
        description="Alpha Research Factory - CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m research.alpha.cli --module features --action build --symbol BTCUSDT
  python -m research.alpha.cli --module features --action audit --symbol BTCUSDT
  python -m research.alpha.cli --module ic --action analyze --symbol BTCUSDT
  python -m research.alpha.cli --module validation --action pipeline --symbol BTCUSDT
  python -m research.alpha.cli --module reporting --action leaderboard --symbol BTCUSDT
        """,
    )

    parser.add_argument(
        "--module",
        type=str,
        required=True,
        choices=["features", "ic", "signals", "validation", "reporting"],
        help="Module to run",
    )
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        help="Action to perform",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        default="binance",
        help="Exchange (default: binance)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days (default: 90)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1h",
        help="Timeframe (default: 1h)",
    )
    parser.add_argument(
        "--feature-source",
        type=str,
        default="research",
        choices=["research", "engine"],
        help="Feature source to use (default: research)",
    )

    args = parser.parse_args()

    if args.module == "features":
        run_features(args)
    elif args.module == "ic":
        run_ic(args)
    elif args.module == "signals":
        run_signals(args)
    elif args.module == "validation":
        run_validation(args)
    elif args.module == "reporting":
        run_reporting(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
