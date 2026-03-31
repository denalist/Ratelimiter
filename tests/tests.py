import unittest


class RateLimiterUnitTests(unittest.TestCase):
    def test_token_bucket_denies_after_capacity(self) -> None:
        import src.rate_limiter as rl

        store = rl.InMemoryKV()
        limiter = rl.RateLimiter(store)

        # Freeze time.
        t = 1000.0
        limiter._now = lambda: t  # type: ignore[method-assign]

        key = ("1", "_")
        d1 = limiter.token_bucket(key, capacity=2, refill_rate_per_sec=0.0)
        d2 = limiter.token_bucket(key, capacity=2, refill_rate_per_sec=0.0)
        d3 = limiter.token_bucket(key, capacity=2, refill_rate_per_sec=0.0)

        self.assertTrue(d1.allowed)
        self.assertTrue(d2.allowed)
        self.assertFalse(d3.allowed)

    def test_token_bucket_refills_over_time(self) -> None:
        import src.rate_limiter as rl

        store = rl.InMemoryKV()
        limiter = rl.RateLimiter(store)

        t = 0.0
        limiter._now = lambda: t  # type: ignore[method-assign]

        key = ("1", "_")
        self.assertTrue(limiter.token_bucket(key, capacity=1, refill_rate_per_sec=1.0).allowed)
        self.assertFalse(limiter.token_bucket(key, capacity=1, refill_rate_per_sec=1.0).allowed)

        t = 1.0
        self.assertTrue(limiter.token_bucket(key, capacity=1, refill_rate_per_sec=1.0).allowed)

    def test_fixed_window_resets_next_window(self) -> None:
        import src.rate_limiter as rl

        store = rl.InMemoryKV()
        limiter = rl.RateLimiter(store)

        t = 1.0
        limiter._now = lambda: t  # type: ignore[method-assign]

        key = ("1", "_")
        self.assertTrue(limiter.fixed_window_counter(key, limit=2, window_seconds=10).allowed)
        self.assertTrue(limiter.fixed_window_counter(key, limit=2, window_seconds=10).allowed)
        self.assertFalse(limiter.fixed_window_counter(key, limit=2, window_seconds=10).allowed)

        t = 11.0  # next window
        self.assertTrue(limiter.fixed_window_counter(key, limit=2, window_seconds=10).allowed)

    def test_sliding_window_log_evicts_old(self) -> None:
        import src.rate_limiter as rl

        store = rl.InMemoryKV()
        limiter = rl.RateLimiter(store)

        t = 0.0
        limiter._now = lambda: t  # type: ignore[method-assign]

        key = ("1", "_")
        self.assertTrue(limiter.sliding_window_log(key, limit=2, window_seconds=10.0).allowed)
        self.assertTrue(limiter.sliding_window_log(key, limit=2, window_seconds=10.0).allowed)
        self.assertFalse(limiter.sliding_window_log(key, limit=2, window_seconds=10.0).allowed)

        t = 10.01
        self.assertTrue(limiter.sliding_window_log(key, limit=2, window_seconds=10.0).allowed)

    def test_sliding_window_counter_approx(self) -> None:
        import src.rate_limiter as rl

        store = rl.InMemoryKV()
        limiter = rl.RateLimiter(store)

        t = 0.0
        limiter._now = lambda: t  # type: ignore[method-assign]

        key = ("1", "_")
        self.assertTrue(limiter.sliding_window_counter(key, limit=2, window_seconds=10).allowed)
        self.assertTrue(limiter.sliding_window_counter(key, limit=2, window_seconds=10).allowed)
        self.assertFalse(limiter.sliding_window_counter(key, limit=2, window_seconds=10).allowed)


class RateLimiterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi is not installed; skipping API tests")

        import src.rate_limiter as rl

        if getattr(rl, "app", None) is None:
            self.skipTest("FastAPI app not available; skipping API tests")

        # Reset module-global store between tests.
        rl.store = rl.InMemoryKV()
        rl.limiter = rl.RateLimiter(rl.store)

        self.client = TestClient(rl.app)

    def test_post_event_allows_then_429(self) -> None:
        # fixed_window: limit=10 per 10 seconds (as configured in the endpoint)
        for _ in range(10):
            r = self.client.post("/event/", params={"user": 123, "action": "a", "algo": "fixed_window"})
            self.assertEqual(r.status_code, 200)
            self.assertIn("X-RateLimit-Limit", r.headers)
            self.assertIn("X-RateLimit-Remaining", r.headers)

        r = self.client.post("/event/", params={"user": 123, "action": "a", "algo": "fixed_window"})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)

    def test_post_event_isolated_by_action(self) -> None:
        # Same user, different action => different key => separate bucket/window.
        for _ in range(10):
            r = self.client.post("/event/", params={"user": 1, "action": "a", "algo": "fixed_window"})
            self.assertEqual(r.status_code, 200)

        r = self.client.post("/event/", params={"user": 1, "action": "b", "algo": "fixed_window"})
        self.assertEqual(r.status_code, 200)

    def test_post_event_unknown_algo_400(self) -> None:
        r = self.client.post("/event/", params={"user": 1, "action": "a", "algo": "nope"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
