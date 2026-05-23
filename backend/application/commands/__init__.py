"""Application Commands - 写操作 facade"""
from .trading import submit_order, cancel_order
from .mode import switch_mode, get_trading_mode
from .backtest import start_backtest, stop_backtest
from .data_commands import (
    collect_exchange_data,
    collect_etf_data,
    collect_news_data,
    collect_macro_data,
    collect_social_media_data,
    collect_trader_data,
    check_black_swan,
    publish_exchange_prices,
)
