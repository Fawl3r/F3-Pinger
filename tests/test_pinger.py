import unittest
from unittest.mock import Mock

import requests

from keepalive.pinger import PingerManager, RetryPolicy, UserAgentProvider


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400

    def close(self) -> None:
        return None


class NoOpSleeper:
    def __init__(self):
        self.calls = []

    def sleep(self, seconds: int) -> None:
        self.calls.append(seconds)


class PingerManagerTests(unittest.TestCase):
    def test_retries_on_5xx_then_succeeds(self) -> None:
        session = Mock()
        session.get.side_effect = [FakeResponse(500), FakeResponse(200)]

        retry_policy = RetryPolicy(retries=1, backoff_seconds=1)
        sleeper = NoOpSleeper()
        pinger = PingerManager(
            timeout_seconds=1,
            retry_policy=retry_policy,
            user_agent_provider=UserAgentProvider(),
            session=session,
            sleeper=sleeper,
        )

        result = pinger.ping_url("https://example.com")

        self.assertTrue(result.ok)
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(sleeper.calls, [1])

    def test_network_error_returns_failure(self) -> None:
        session = Mock()
        session.get.side_effect = requests.exceptions.Timeout("boom")

        retry_policy = RetryPolicy(retries=0, backoff_seconds=1)
        pinger = PingerManager(
            timeout_seconds=1,
            retry_policy=retry_policy,
            user_agent_provider=UserAgentProvider(),
            session=session,
            sleeper=NoOpSleeper(),
        )

        result = pinger.ping_url("https://example.com")

        self.assertFalse(result.ok)
        self.assertIsNone(result.status)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
