from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

from dotenv import load_dotenv


class ConfigDefaults:
    @staticmethod
    def target_urls() -> List[str]:
        return [
            "https://www.parlaygorilla.com/",
            "https://api.parlaygorilla.com/health",
        ]

    @staticmethod
    def post_load_urls() -> List[str]:
        return ["https://api.parlaygorilla.com/health?deep=1"]

    @staticmethod
    def interval_seconds() -> int:
        return 600

    @staticmethod
    def timeout_seconds() -> int:
        return 15

    @staticmethod
    def retries() -> int:
        return 2

    @staticmethod
    def backoff_seconds() -> int:
        return 3

    @staticmethod
    def alert_consecutive_failures() -> int:
        return 3

    @staticmethod
    def alert_latency_ms() -> int:
        return 4000


class EnvValueParser:
    def __init__(self, environ: Mapping[str, str]):
        self._environ = environ

    def get_list(self, key: str, default: List[str]) -> List[str]:
        raw_value = self._get_raw(key)
        if raw_value is None:
            return list(default)
        items = [item.strip() for item in raw_value.split(",") if item.strip()]
        return items if items else list(default)

    def get_int(self, key: str, default: int, min_value: int = 0) -> int:
        raw_value = self._get_raw(key)
        if raw_value is None:
            return default
        try:
            parsed = int(raw_value)
        except ValueError:
            return default
        if parsed < min_value:
            return default
        return parsed

    def get_optional_str(self, key: str) -> Optional[str]:
        return self._get_raw(key)

    def _get_raw(self, key: str) -> Optional[str]:
        value = self._environ.get(key)
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None


class ConfigSanitizer:
    def mask_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        if len(token) <= 6:
            return "*" * len(token)
        return f"{token[:3]}...{token[-3:]}"


@dataclass(frozen=True)
class KeepAliveConfig:
    target_urls: List[str]
    post_load_urls: List[str]
    interval_seconds: int
    timeout_seconds: int
    retries: int
    backoff_seconds: int
    alert_consecutive_failures: int
    alert_latency_ms: int
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]

    def to_safe_dict(self) -> Dict[str, object]:
        sanitizer = ConfigSanitizer()
        return {
            "TARGET_URLS": self.target_urls,
            "POST_LOAD_URLS": self.post_load_urls,
            "INTERVAL_SECONDS": self.interval_seconds,
            "TIMEOUT_SECONDS": self.timeout_seconds,
            "RETRIES": self.retries,
            "BACKOFF_SECONDS": self.backoff_seconds,
            "ALERT_CONSECUTIVE_FAILURES": self.alert_consecutive_failures,
            "ALERT_LATENCY_MS": self.alert_latency_ms,
            "TELEGRAM_BOT_TOKEN": sanitizer.mask_token(self.telegram_bot_token),
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
        }


class ConfigLoader:
    def __init__(self, environ: Mapping[str, str]):
        self._parser = EnvValueParser(environ)

    @classmethod
    def from_env(cls, load_dotenv_enabled: bool = True) -> KeepAliveConfig:
        if load_dotenv_enabled:
            load_dotenv()
        loader = cls(os.environ)
        return loader.load()

    def load(self) -> KeepAliveConfig:
        return KeepAliveConfig(
            target_urls=self._parser.get_list(
                "TARGET_URLS", ConfigDefaults.target_urls()
            ),
            post_load_urls=self._parser.get_list(
                "POST_LOAD_URLS", ConfigDefaults.post_load_urls()
            ),
            interval_seconds=self._parser.get_int(
                "INTERVAL_SECONDS", ConfigDefaults.interval_seconds(), min_value=1
            ),
            timeout_seconds=self._parser.get_int(
                "TIMEOUT_SECONDS", ConfigDefaults.timeout_seconds(), min_value=1
            ),
            retries=self._parser.get_int(
                "RETRIES", ConfigDefaults.retries(), min_value=0
            ),
            backoff_seconds=self._parser.get_int(
                "BACKOFF_SECONDS", ConfigDefaults.backoff_seconds(), min_value=0
            ),
            alert_consecutive_failures=self._parser.get_int(
                "ALERT_CONSECUTIVE_FAILURES",
                ConfigDefaults.alert_consecutive_failures(),
                min_value=1,
            ),
            alert_latency_ms=self._parser.get_int(
                "ALERT_LATENCY_MS", ConfigDefaults.alert_latency_ms(), min_value=0
            ),
            telegram_bot_token=self._parser.get_optional_str("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=self._parser.get_optional_str("TELEGRAM_CHAT_ID"),
        )
