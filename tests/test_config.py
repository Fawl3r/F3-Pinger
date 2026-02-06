import unittest

from keepalive.config import ConfigLoader


class ConfigLoaderTests(unittest.TestCase):
    def test_defaults_apply_when_env_empty(self) -> None:
        loader = ConfigLoader({})
        config = loader.load()

        self.assertIn("https://www.parlaygorilla.com/", config.target_urls)
        self.assertIn("https://api.parlaygorilla.com/health", config.target_urls)
        self.assertIn(
            "https://api.parlaygorilla.com/health?deep=1", config.post_load_urls
        )
        self.assertEqual(config.interval_seconds, 600)
        self.assertEqual(config.timeout_seconds, 15)
        self.assertEqual(config.retries, 2)
        self.assertEqual(config.backoff_seconds, 3)
        self.assertEqual(config.alert_consecutive_failures, 3)
        self.assertEqual(config.alert_latency_ms, 4000)

    def test_overrides_parse_lists(self) -> None:
        loader = ConfigLoader(
            {
                "TARGET_URLS": "https://example.com, https://example.com/health",
                "POST_LOAD_URLS": "https://example.com/deep",
            }
        )
        config = loader.load()

        self.assertEqual(
            config.target_urls,
            ["https://example.com", "https://example.com/health"],
        )
        self.assertEqual(config.post_load_urls, ["https://example.com/deep"])

    def test_empty_strings_fall_back_to_defaults(self) -> None:
        loader = ConfigLoader({"TARGET_URLS": "   ", "POST_LOAD_URLS": ""})
        config = loader.load()

        self.assertIn("https://www.parlaygorilla.com/", config.target_urls)
        self.assertIn(
            "https://api.parlaygorilla.com/health?deep=1", config.post_load_urls
        )


if __name__ == "__main__":
    unittest.main()
