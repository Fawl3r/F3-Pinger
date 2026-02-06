from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from keepalive.config import ConfigLoader, KeepAliveConfig
from keepalive.pinger import PingResult, PingerManager, RetryPolicy, UserAgentProvider
from keepalive.telegram import TelegramAlertManager


class TimeProvider:
    def utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def now_epoch_seconds(self) -> float:
        return time.time()


class ResultLogManager:
    def __init__(self, time_provider: TimeProvider):
        self._time_provider = time_provider

    def log_result(self, url: str, result: PingResult) -> None:
        payload = {
            "ts": self._time_provider.utc_now_iso(),
            "url": url,
            "ok": result.ok,
            "status": result.status,
            "latency_ms": result.latency_ms,
            "error": result.error,
        }
        print(json.dumps(payload), flush=True)


class UrlSequenceBuilder:
    def __init__(self, target_urls: List[str], post_load_urls: List[str]):
        self._target_urls = list(target_urls)
        self._post_load_urls = list(post_load_urls)

    def build(self) -> List[str]:
        if not self._target_urls:
            return list(self._post_load_urls)
        primary_url = self._target_urls[0]
        remaining_urls = self._target_urls[1:]
        return [primary_url] + list(self._post_load_urls) + remaining_urls


class HealthEndpointClassifier:
    def __init__(self, health_paths: List[str] | None = None):
        self._health_paths = health_paths or ["/health", "/api/health"]

    def is_health_endpoint(self, url: str) -> bool:
        path = urlparse(url).path.rstrip("/")
        normalized = path if path else "/"
        return normalized in self._health_paths


@dataclass(frozen=True)
class PingOutcome:
    is_failure: bool
    is_warning_only: bool


class PingOutcomeEvaluator:
    def __init__(self, classifier: HealthEndpointClassifier):
        self._classifier = classifier

    def evaluate(self, url: str, result: PingResult) -> PingOutcome:
        if result.ok:
            return PingOutcome(is_failure=False, is_warning_only=False)
        if result.status == 404 and self._classifier.is_health_endpoint(url):
            return PingOutcome(is_failure=False, is_warning_only=True)
        return PingOutcome(is_failure=True, is_warning_only=False)


class FailureTracker:
    def __init__(self):
        self._counts: Dict[str, int] = {}

    def record(self, url: str, is_failure: bool) -> int:
        if is_failure:
            self._counts[url] = self._counts.get(url, 0) + 1
        else:
            self._counts[url] = 0
        return self._counts[url]


class LatencyAlertLimiter:
    def __init__(self, cooldown_seconds: int):
        self._cooldown_seconds = max(1, cooldown_seconds)
        self._last_alert_by_url: Dict[str, float] = {}

    def should_alert(self, url: str, now_epoch_seconds: float) -> bool:
        last_alert = self._last_alert_by_url.get(url)
        if last_alert is None:
            self._last_alert_by_url[url] = now_epoch_seconds
            return True
        if now_epoch_seconds - last_alert >= self._cooldown_seconds:
            self._last_alert_by_url[url] = now_epoch_seconds
            return True
        return False


class AlertPolicyManager:
    def __init__(
        self,
        failure_threshold: int,
        latency_threshold_ms: int,
        latency_limiter: LatencyAlertLimiter,
    ):
        self._failure_threshold = max(1, failure_threshold)
        self._latency_threshold_ms = max(0, latency_threshold_ms)
        self._latency_limiter = latency_limiter

    @property
    def latency_threshold_ms(self) -> int:
        return self._latency_threshold_ms

    def should_alert_failure(self, failure_count: int) -> bool:
        return failure_count == self._failure_threshold

    def should_alert_latency(
        self, url: str, latency_ms: int, now_epoch_seconds: float
    ) -> bool:
        if latency_ms < self._latency_threshold_ms:
            return False
        return self._latency_limiter.should_alert(url, now_epoch_seconds)


class AlertMessageBuilder:
    def build_failure_message(
        self, url: str, failure_count: int, result: PingResult
    ) -> str:
        status_text = f"status={result.status}" if result.status is not None else "status=none"
        error_text = f" error={result.error}" if result.error else ""
        return (
            f"Keepalive alert: {url} failed {failure_count} times in a row "
            f"({status_text}).{error_text}"
        )

    def build_latency_message(
        self, url: str, latency_ms: int, threshold_ms: int
    ) -> str:
        return (
            f"Keepalive alert: {url} latency {latency_ms}ms >= {threshold_ms}ms."
        )


class AlertDispatcher:
    def __init__(self, telegram_manager: TelegramAlertManager):
        self._telegram_manager = telegram_manager

    def dispatch(self, message: str) -> None:
        if not self._telegram_manager.is_configured():
            return
        if not self._telegram_manager.send_alert(message):
            print("Telegram alert failed to send.", file=sys.stderr)


class IntervalSleeper:
    def __init__(self, interval_seconds: int):
        self._interval_seconds = max(1, interval_seconds)

    def sleep(self) -> None:
        time.sleep(self._interval_seconds)


class KeepAliveCoordinator:
    def __init__(
        self,
        url_sequence_builder: UrlSequenceBuilder,
        pinger: PingerManager,
        log_manager: ResultLogManager,
        outcome_evaluator: PingOutcomeEvaluator,
        failure_tracker: FailureTracker,
        alert_policy: AlertPolicyManager,
        alert_dispatcher: AlertDispatcher,
        message_builder: AlertMessageBuilder,
        time_provider: TimeProvider,
        interval_sleeper: IntervalSleeper,
    ):
        self._url_sequence_builder = url_sequence_builder
        self._pinger = pinger
        self._log_manager = log_manager
        self._outcome_evaluator = outcome_evaluator
        self._failure_tracker = failure_tracker
        self._alert_policy = alert_policy
        self._alert_dispatcher = alert_dispatcher
        self._message_builder = message_builder
        self._time_provider = time_provider
        self._interval_sleeper = interval_sleeper

    def run_once(self) -> bool:
        cycle_success = True
        for url in self._url_sequence_builder.build():
            result = self._pinger.ping_url(url)
            self._log_manager.log_result(url, result)
            outcome = self._outcome_evaluator.evaluate(url, result)
            if outcome.is_failure:
                cycle_success = False
            failure_count = self._failure_tracker.record(url, outcome.is_failure)
            self._handle_failure_alert(url, result, outcome, failure_count)
            self._handle_latency_alert(url, result)
        return cycle_success

    def run_forever(self) -> None:
        while True:
            self.run_once()
            self._interval_sleeper.sleep()

    def _handle_failure_alert(
        self, url: str, result: PingResult, outcome: PingOutcome, failure_count: int
    ) -> None:
        if not outcome.is_failure:
            return
        if self._alert_policy.should_alert_failure(failure_count):
            message = self._message_builder.build_failure_message(
                url, failure_count, result
            )
            self._alert_dispatcher.dispatch(message)

    def _handle_latency_alert(self, url: str, result: PingResult) -> None:
        now_epoch = self._time_provider.now_epoch_seconds()
        if not self._alert_policy.should_alert_latency(
            url, result.latency_ms, now_epoch
        ):
            return
        message = self._message_builder.build_latency_message(
            url, result.latency_ms, self._alert_policy.latency_threshold_ms
        )
        self._alert_dispatcher.dispatch(message)


class ConfigPrinter:
    def print_config(self, config: KeepAliveConfig) -> None:
        print(json.dumps(config.to_safe_dict(), indent=2))


class ArgumentParserBuilder:
    def build(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="ParlayGorilla Keep-Alive Pinger")
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one ping cycle then exit.",
        )
        parser.add_argument(
            "--print-config",
            action="store_true",
            help="Print resolved config and exit.",
        )
        return parser


class CoordinatorFactory:
    def build(self, config: KeepAliveConfig) -> KeepAliveCoordinator:
        time_provider = TimeProvider()
        retry_policy = RetryPolicy(config.retries, config.backoff_seconds)
        pinger = PingerManager(
            timeout_seconds=config.timeout_seconds,
            retry_policy=retry_policy,
            user_agent_provider=UserAgentProvider(),
        )
        return KeepAliveCoordinator(
            url_sequence_builder=UrlSequenceBuilder(
                config.target_urls, config.post_load_urls
            ),
            pinger=pinger,
            log_manager=ResultLogManager(time_provider),
            outcome_evaluator=PingOutcomeEvaluator(HealthEndpointClassifier()),
            failure_tracker=FailureTracker(),
            alert_policy=AlertPolicyManager(
                config.alert_consecutive_failures,
                config.alert_latency_ms,
                LatencyAlertLimiter(cooldown_seconds=3600),
            ),
            alert_dispatcher=AlertDispatcher(
                TelegramAlertManager(
                    config.telegram_bot_token, config.telegram_chat_id
                )
            ),
            message_builder=AlertMessageBuilder(),
            time_provider=time_provider,
            interval_sleeper=IntervalSleeper(config.interval_seconds),
        )


def main() -> int:
    args = ArgumentParserBuilder().build().parse_args()
    config = ConfigLoader.from_env()
    if args.print_config:
        ConfigPrinter().print_config(config)
        return 0
    coordinator = CoordinatorFactory().build(config)
    if args.once:
        return 0 if coordinator.run_once() else 1
    try:
        coordinator.run_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
