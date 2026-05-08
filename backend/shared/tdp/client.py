"""
TDP 服务器和客户端实现
"""

import time
import uuid
import json
import hashlib
import hmac
from typing import Dict, Optional, Any, Callable
from abc import ABC, abstractmethod


class TDPVersionError(Exception):
    pass


class TDPValidationError(Exception):
    pass


class TDPHandlerNotFoundError(Exception):
    pass


class TDPSecurityError(Exception):
    pass


class TDPSigner:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def sign(self, message: Dict[str, Any]) -> str:
        payload = json.dumps(message, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def verify(self, message: Dict[str, Any], signature: str) -> bool:
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)


class TDPEncryption:
    def __init__(self, encryption_key: bytes):
        try:
            from cryptography.fernet import Fernet
            self.cipher = Fernet(encryption_key)
        except ImportError:
            self.cipher = None

    def encrypt(self, message: Dict[str, Any]) -> bytes:
        if self.cipher is None:
            raise ImportError("cryptography library not installed")
        return self.cipher.encrypt(json.dumps(message).encode())

    def decrypt(self, encrypted: bytes) -> Dict[str, Any]:
        if self.cipher is None:
            raise ImportError("cryptography library not installed")
        return json.loads(self.cipher.decrypt(encrypted).decode())


class TDPMessageBuilder:
    VERSION = "1.0"

    @classmethod
    def create_message(
        cls,
        msg_type: str,
        payload: Dict[str, Any],
        source: str,
        destination: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "timestamp": int(time.time()),
            "type": msg_type,
            "meta": {
                "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
                "source": source,
                "destination": destination,
                "time_generated": int(time.time()),
                "status": "OK",
            },
            "data": payload,
        }

    @classmethod
    def create_market_data_request(
        cls,
        symbols: list,
        timeframe: str,
        source: str,
    ) -> Dict[str, Any]:
        return cls.create_message(
            "market_data_request",
            {"symbols": symbols, "timeframe": timeframe},
            source,
        )

    @classmethod
    def create_market_data_response(
        cls,
        market_data: Dict[str, Any],
        request_id: str,
        source: str,
    ) -> Dict[str, Any]:
        return cls.create_message(
            "market_data_response",
            {"market": market_data},
            source,
            request_id=request_id,
        )

    @classmethod
    def create_factor_request(
        cls,
        symbols: list,
        source: str,
    ) -> Dict[str, Any]:
        return cls.create_message(
            "factor_request",
            {"symbols": symbols},
            source,
        )

    @classmethod
    def create_signal_response(
        cls,
        signals: Dict[str, Any],
        request_id: str,
        source: str,
    ) -> Dict[str, Any]:
        return cls.create_message(
            "signal_response",
            {"signals": signals},
            source,
            request_id=request_id,
        )

    @classmethod
    def create_error_response(
        cls,
        error: str,
        request_id: str,
        source: str,
    ) -> Dict[str, Any]:
        message = cls.create_message(
            "error",
            {"error": error},
            source,
            request_id=request_id,
        )
        message["meta"]["status"] = "ERROR"
        message["meta"]["error"] = error
        return message


class TDPClient:
    def __init__(
        self,
        server_url: str,
        secret_key: Optional[str] = None,
        encryption_key: Optional[bytes] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.signer = TDPSigner(secret_key) if secret_key else None
        self.encryption = TDPEncryption(encryption_key) if encryption_key else None
        self._session = None

    @property
    def session(self):
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=30)
        return self._session

    def close(self):
        if self._session:
            self._session.close()
            self._session = None

    def _prepare_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        message["version"] = TDPMessageBuilder.VERSION

        if self.signer:
            signature = self.signer.sign(message)
            message["signature"] = signature

        return message

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        prepared = self._prepare_message(message)

        if self.encryption:
            encrypted = self.encryption.encrypt(prepared)
            response = self.session.post(
                f"{self.server_url}/tdp/message",
                content=encrypted,
                headers={"Content-Type": "application/octet-stream"},
            )
        else:
            response = self.session.post(
                f"{self.server_url}/tdp/message",
                json=prepared,
            )

        response.raise_for_status()
        return response.json()

    def request_market_data(self, symbols: list, timeframe: str) -> Dict[str, Any]:
        message = TDPMessageBuilder.create_market_data_request(
            symbols, timeframe, "tdp_client"
        )
        return self.send_message(message)

    def request_signals(self, symbols: list) -> Dict[str, Any]:
        message = TDPMessageBuilder.create_factor_request(symbols, "tdp_client")
        return self.send_message(message)

    def request_state(self, state_type: str) -> Dict[str, Any]:
        message = TDPMessageBuilder.create_message(
            "state_request",
            {"state_type": state_type},
            "tdp_client",
        )
        return self.send_message(message)


class TDPServer:
    def __init__(
        self,
        secret_key: Optional[str] = None,
        encryption_key: Optional[bytes] = None,
    ):
        self.handlers: Dict[str, Callable] = {}
        self.signer = TDPSigner(secret_key) if secret_key else None
        self.encryption = TDPEncryption(encryption_key) if encryption_key else None

    def register_handler(self, msg_type: str, handler: Callable):
        self.handlers[msg_type] = handler

    def validate_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(message, dict):
            raise TDPValidationError("Message must be a dictionary")

        if "version" not in message:
            raise TDPValidationError("Missing version field")

        if message["version"] != TDPMessageBuilder.VERSION:
            raise TDPVersionError(
                f"Version mismatch: expected {TDPMessageBuilder.VERSION}"
            )

        if "type" not in message:
            raise TDPValidationError("Missing type field")

        if self.signer and "signature" in message:
            signature = message.pop("signature")
            if not self.signer.verify(message, signature):
                raise TDPSecurityError("Signature verification failed")

        return message

    def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        validated = self.validate_message(message)

        msg_type = validated.get("type")
        handler = self.handlers.get(msg_type)

        if not handler:
            raise TDPHandlerNotFoundError(f"No handler for type: {msg_type}")

        try:
            result = handler(validated)
            return result
        except Exception as e:
            return TDPMessageBuilder.create_error_response(
                str(e),
                validated.get("meta", {}).get("request_id", "unknown"),
                "tdp_server",
            )

    def process_encrypted_message(self, encrypted: bytes) -> bytes:
        if not self.encryption:
            raise TDPSecurityError("Encryption not configured")

        message = self.encryption.decrypt(encrypted)
        result = self.process_message(message)

        encrypted_result = self.encryption.encrypt(result)
        return encrypted_result


class TDPPubSub:
    def __init__(self):
        self._subscribers: Dict[str, list] = {}

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable):
        if topic in self._subscribers:
            self._subscribers[topic].remove(callback)

    def publish(self, topic: str, message: Dict[str, Any]):
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    callback(message)
                except Exception:
                    pass


_tdp_pubsub = TDPPubSub()


def get_tdp_pubsub() -> TDPPubSub:
    return _tdp_pubsub