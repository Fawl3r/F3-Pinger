from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass(frozen=True)
class PingResult:
    ok: bool
    status: Optional[int]
    latency_ms: int
    error: Optional[str]


class UserAgentProvider:
    def get_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )


class RetryPolicy:
    def __init__(self, retries: int, backoff_seconds: int):
        self._max_attempts = max(1, retries + 1)
        self._backoff_seconds = max(0, backoff_seconds)

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    @property
    def backoff_seconds(self) -> int:
        return self._backoff_seconds

    def should_retry(self, attempt: int, result: PingResult) -> bool:
        if attempt >= self._max_attempts:
            return False
        if result.error is not None:
            return True
        return result.status is not None and result.status >= 500


class BackoffSleeper:
    def sleep(self, seconds: int) -> None:
        time.sleep(seconds)


class PingerManager:
    def __init__(
        self,
        timeout_seconds: int,
        retry_policy: RetryPolicy,
        user_agent_provider: UserAgentProvider,
        session: Optional[requests.Session] = None,
        sleeper: Optional[BackoffSleeper] = None,
    ):
        self._timeout_seconds = max(1, timeout_seconds)
        self._retry_policy = retry_policy
        self._user_agent_provider = user_agent_provider
        self._session = session or requests.Session()
        self._sleeper = sleeper or BackoffSleeper()

    def ping_url(self, url: str) -> PingResult:
        headers = {"User-Agent": self._user_agent_provider.get_user_agent()}
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            result = self._attempt_request(url, headers)
            if self._retry_policy.should_retry(attempt, result):
                self._sleeper.sleep(self._retry_policy.backoff_seconds)
                continue
            return result
        return PingResult(ok=False, status=None, latency_ms=0, error="Unknown error")

    def _attempt_request(self, url: str, headers: dict) -> PingResult:
        start_time = time.monotonic()
        try:
            response = self._session.get(
                url, headers=headers, timeout=self._timeout_seconds
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)
            status_code = response.status_code
            ok = response.ok
            response.close()
            return PingResult(ok=ok, status=status_code, latency_ms=latency_ms, error=None)
        except requests.exceptions.RequestException as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return PingResult(ok=False, status=None, latency_ms=latency_ms, error=str(exc))
