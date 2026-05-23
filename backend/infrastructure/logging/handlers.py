"""
日志处理器
支持文件、控制台、Elasticsearch等多种输出
"""

import os
import gzip
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler as LoggingRotatingFileHandler
from logging import LogRecord
import logging

from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS


class BaseHandler(logging.Handler):
    def __init__(self, level: int = logging.INFO):
        super().__init__(level)

    def emit(self, record: LogRecord):
        raise NotImplementedError


class FileHandler(logging.FileHandler):
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        encoding: Optional[str] = "utf-8",
        retention_days: int = 30,
    ):
        self.retention_days = retention_days
        self._ensure_log_dir(filename)
        super().__init__(filename, mode, encoding)

    def _ensure_log_dir(self, filename: str):
        log_dir = os.path.dirname(filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


class RotatingFileHandler(LoggingRotatingFileHandler):
    def __init__(
        self,
        filename: str,
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 10,
        encoding: Optional[str] = "utf-8",
        retention_days: int = 30,
    ):
        self.retention_days = retention_days
        self._ensure_log_dir(filename)
        super().__init__(
            filename,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
        )

    def _ensure_log_dir(self, filename: str):
        log_dir = os.path.dirname(filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


class ConsoleHandler(logging.StreamHandler):
    def __init__(self, level: int = logging.INFO):
        super().__init__()
        self.setLevel(level)


class ElasticsearchHandler(logging.Handler):
    def __init__(
        self,
        es_host: str = "localhost",
        es_port: int = 9200,
        index_prefix: str = "tradeagent-logs",
        level: int = logging.INFO,
    ):
        super().__init__(level)
        self.es_host = es_host
        self.es_port = es_port
        self.index_prefix = index_prefix
        self._es_client = None

    @property
    def es_client(self):
        if self._es_client is None:
            try:
                from elasticsearch import Elasticsearch

                self._es_client = Elasticsearch([f"http://{self.es_host}:{self.es_port}"])
            except ImportError:
                return None
        return self._es_client

    def emit(self, record: LogRecord):
        if not self.es_client:
            return

        try:
            from datetime import datetime

            doc = {
                "@timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            if hasattr(record, "request_id"):
                doc["request_id"] = record.request_id
            if hasattr(record, "user_id"):
                doc["user_id"] = record.user_id

            if record.exc_info:
                doc["exception"] = self.formatException(record.exc_info)

            index_name = f"{self.index_prefix}-{datetime.utcnow().strftime('%Y.%m.%d')}"
            self.es_client.index(index=index_name, document=doc)
        except Exception:
            self.handleError(record)


class KafkaHandler(logging.Handler):
    def __init__(
        self,
        bootstrap_servers: str = None,
        topic: str = "tradeagent-logs",
        level: int = logging.INFO,
    ):
        super().__init__(level)
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.topic = topic
        self._producer = None

    @property
    def producer(self):
        if self._producer is None:
            try:
                from aiokafka import AIOKafkaProducer

                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers
                )
            except ImportError:
                return None
        return self._producer

    def emit(self, record: LogRecord):
        if not self.producer:
            return

        try:
            import json
            from datetime import datetime

            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            if hasattr(record, "request_id"):
                log_data["request_id"] = record.request_id
            if hasattr(record, "user_id"):
                log_data["user_id"] = record.user_id

            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            import asyncio

            asyncio.create_task(
                self.producer.send_and_wait(self.topic, json.dumps(log_data).encode())
            )
        except Exception:
            self.handleError(record)


class CompositeHandler(logging.Handler):
    def __init__(self, handlers: list, level: int = logging.INFO):
        super().__init__(level)
        self.handlers = handlers

    def emit(self, record: LogRecord):
        for handler in self.handlers:
            try:
                handler.emit(record)
            except Exception:
                pass

    def close(self):
        for handler in self.handlers:
            handler.close()
        super().close()