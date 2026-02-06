import unittest

from keepalive.main import (
    FailureTracker,
    HealthEndpointClassifier,
    LatencyAlertLimiter,
    PingOutcomeEvaluator,
    UrlSequenceBuilder,
)
from keepalive.pinger import PingResult


class MainStateTests(unittest.TestCase):
    def test_url_sequence_builder_orders(self) -> None:
        builder = UrlSequenceBuilder(["home", "health"], ["deep"])
        self.assertEqual(builder.build(), ["home", "deep", "health"])

    def test_failure_tracker_counts_and_resets(self) -> None:
        tracker = FailureTracker()
        self.assertEqual(tracker.record("url", True), 1)
        self.assertEqual(tracker.record("url", True), 2)
        self.assertEqual(tracker.record("url", False), 0)

    def test_latency_limiter_cooldown(self) -> None:
        limiter = LatencyAlertLimiter(cooldown_seconds=3600)
        self.assertTrue(limiter.should_alert("url", 0))
        self.assertFalse(limiter.should_alert("url", 3599))
        self.assertTrue(limiter.should_alert("url", 3600))

    def test_health_404_is_warning(self) -> None:
        evaluator = PingOutcomeEvaluator(HealthEndpointClassifier())
        result = PingResult(ok=False, status=404, latency_ms=10, error=None)
        outcome = evaluator.evaluate(
            "https://api.parlaygorilla.com/health?deep=1", result
        )
        self.assertFalse(outcome.is_failure)
        self.assertTrue(outcome.is_warning_only)


if __name__ == "__main__":
    unittest.main()
