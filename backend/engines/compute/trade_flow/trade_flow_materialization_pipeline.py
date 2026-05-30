from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from infrastructure.storage.data_lake.raw_trade_reader import RawTradeReader
from infrastructure.storage.data_lake.trade_flow_writer import TradeFlowWriter
from engines.compute.feature.trade_flow_engine import _aggregate_single_month
from infrastructure.acceleration.cpu_executor import CPUExecutor


class TradeFlowMaterializationPipeline:

    def __init__(self) -> None:
        self._reader = RawTradeReader()
        self._writer = TradeFlowWriter()

    def run(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        force: bool = False,
    ) -> Path:
        print(f"[TradeFlowMaterialization] start: symbol={symbol}, exchange={exchange}, timeframe={timeframe}, force={force}")

        all_months = self._reader.list_available_months(exchange, symbol)
        if not all_months:
            print(f"[TradeFlowMaterialization] no available months for {exchange}/{symbol}")
            return Path()

        print(f"[TradeFlowMaterialization] available months: {len(all_months)}")

        months_to_process = self._filter_months(all_months, exchange, symbol, timeframe, start, end, force)

        if not months_to_process:
            print(f"[TradeFlowMaterialization] no months to process after filtering")
            existing = self._writer.load(exchange, symbol, timeframe)
            if not existing.empty:
                output_path = self._writer._build_path(exchange, symbol, timeframe)
                print(f"[TradeFlowMaterialization] existing data at {output_path}, {len(existing)} rows")
                return output_path
            return Path()

        print(f"[TradeFlowMaterialization] months to process: {len(months_to_process)}")

        executor = CPUExecutor(executor_type="process", max_workers=4)
        kwargs_list = [
            {"exchange": exchange, "symbol": symbol, "year": y, "month": m, "timeframe": timeframe}
            for y, m in months_to_process
        ]
        results = executor.submit_map(
            func=_aggregate_single_month,
            kwargs_list=kwargs_list,
            keys=[f"{y}-{m:02d}" for y, m in months_to_process],
        )

        all_dfs: List[pd.DataFrame] = []
        for r in results:
            if r.error is None and r.result is not None and len(r.result) > 0:
                all_dfs.append(r.result)

        if not all_dfs:
            print(f"[TradeFlowMaterialization] no data produced from aggregation")
            return Path()

        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        output_path = self._writer.save(exchange, symbol, timeframe, combined)
        print(f"[TradeFlowMaterialization] saved {len(combined)} rows to {output_path}")

        return output_path

    def _filter_months(
        self,
        all_months: List[Tuple[int, int]],
        exchange: str,
        symbol: str,
        timeframe: str,
        start: Optional[str],
        end: Optional[str],
        force: bool,
    ) -> List[Tuple[int, int]]:
        months = list(all_months)

        if start is not None:
            start_dt = pd.Timestamp(start)
            start_ym = (start_dt.year, start_dt.month)
            months = [(y, m) for y, m in months if (y, m) >= start_ym]

        if end is not None:
            end_dt = pd.Timestamp(end)
            end_ym = (end_dt.year, end_dt.month)
            months = [(y, m) for y, m in months if (y, m) <= end_ym]

        if not force:
            last_ts = self._writer.get_last_timestamp(exchange, symbol, timeframe)
            if last_ts is not None:
                cutoff_ym = (last_ts.year, last_ts.month)
                months = [(y, m) for y, m in months if (y, m) >= cutoff_ym]
                print(f"[TradeFlowMaterialization] incremental mode: last_timestamp={last_ts}, cutoff={cutoff_ym}")

        return months
