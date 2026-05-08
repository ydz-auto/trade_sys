"""
TDP 消息校验器
"""

from typing import Dict, Any, List, Optional, Tuple


class TDPValidator:
    VALID_TYPES = {"market", "etf_flow", "macro", "news", "social", "error"}
    VALID_STATUS = {"OK", "ERROR"}

    @classmethod
    def validate(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not isinstance(message, dict):
            return False, "Message must be a dictionary"

        meta = message.get("meta")
        if not meta:
            return False, "Missing 'meta' field"

        is_valid, error = cls._validate_meta(meta)
        if not is_valid:
            return is_valid, error

        msg_type = meta.get("type")
        if msg_type == "error":
            return True, None

        if msg_type == "market":
            return cls._validate_market(message)
        elif msg_type == "etf_flow":
            return cls._validate_etf_flow(message)
        elif msg_type == "macro":
            return cls._validate_macro(message)
        elif msg_type == "news":
            return cls._validate_news(message)
        elif msg_type == "social":
            return cls._validate_social(message)

        return True, None

    @classmethod
    def _validate_meta(cls, meta: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if "version" not in meta:
            return False, "Missing 'version' in meta"

        if "type" not in meta:
            return False, "Missing 'type' in meta"

        msg_type = meta.get("type")
        if msg_type not in cls.VALID_TYPES:
            return False, f"Invalid type: {msg_type}"

        if "status" not in meta:
            return False, "Missing 'status' in meta"

        status = meta.get("status")
        if status not in cls.VALID_STATUS:
            return False, f"Invalid status: {status}"

        return True, None

    @classmethod
    def _validate_market(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        market = message.get("market")
        if not market:
            return False, "Missing 'market' field"

        crypto = market.get("crypto")
        if not crypto:
            return False, "Missing 'crypto' data"

        for symbol, data in crypto.items():
            if "price" not in data:
                return False, f"Missing 'price' for {symbol}"
            if not isinstance(data["price"], (int, float)):
                return False, f"Invalid price type for {symbol}"

        return True, None

    @classmethod
    def _validate_etf_flow(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        market = message.get("market")
        if not market:
            return False, "Missing 'market' field"

        etf = market.get("etf")
        if not etf:
            return False, "Missing 'etf' data"

        for symbol, data in etf.items():
            if "inflow" not in data or "outflow" not in data:
                return False, f"Missing inflow/outflow for {symbol}"

        return True, None

    @classmethod
    def _validate_macro(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        market = message.get("market")
        if not market:
            return False, "Missing 'market' field"

        commodities = market.get("commodities", {})
        if not commodities:
            return False, "Missing 'commodities' data"

        return True, None

    @classmethod
    def _validate_news(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        events = message.get("events", [])
        if not events:
            return False, "Missing 'events' data"

        for event in events:
            if "title" not in event or "content" not in event:
                return False, "Missing title or content in news event"

        return True, None

    @classmethod
    def _validate_social(cls, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        events = message.get("events", [])
        if not events:
            return False, "Missing 'events' data"

        for event in events:
            if "author" not in event or "content" not in event:
                return False, "Missing author or content in social event"

        return True, None

    @classmethod
    def check_required_fields(cls, message: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, Optional[str]]:
        for field in required_fields:
            if field not in message:
                return False, f"Missing required field: {field}"
        return True, None
