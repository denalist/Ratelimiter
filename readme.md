# System Design - Rate Limiter

This repository is a hands-on playground for implementing common rate limiting algorithms and related infrastructure. The existing `rate_limiter.py` file sketches a FastAPI service entry point and placeholders for algorithms such as token bucket, fixed window, and sliding windows (log and counter method). This is a starting canvas explaining trade-offs and scaling considerations.

Main code:
- `src/rate_limiter.py`
- `src/store.py`

## Rate Limiting Solutions

Below are 5 common rate limiting approaches, with a quick cheat sheet of parameters and trade-offs.

### Token Bucket

![Token Bucket](<rate limiter designs/token_bucket.svg>)

Parameters
- Bucket size (capacity): max number of tokens in the bucket
- Refill rate: tokens added per second

Pros
- Easy to implement
- Memory efficient - O(1): `tokens` and `ts`
- Handles bursts well (up to available tokens)

Cons
- Not precise for smoothing traffic over short intervals
- Can still allow bursty behavior depending on tuning
- Tuning can be tricky with only two knobs

### Leaky Bucket

![Leaky Bucket](<rate limiter designs/leaky_bucket.svg>)

Parameters
- Bucket size (capacity): queue size
- Outflow rate: how many requests are processed per second

Pros
- Memory efficient - O(queue): `queue` and `ts`, Note: this can be reduced to O(1)
- Good when you want a steady output rate

Cons
- Bad for spikes if the queue fills (old requests may wait a long time)
- Tuning can be tricky with only two knobs

### Fixed Window Counter

![Fixed Window Counter](<rate limiter designs/fixed_window_1.svg>)
![Fixed Window Counter Boundary Burst](<rate limiter designs/fixed_window_2.svg>)

Parameters
- Window size (seconds)
- Threshold (max requests per window)

Pros
- Very easy to implement
- Memory efficient - O(1): `window_id` and `count`
- Natural reset behavior each window

Cons
- Boundary burst problem: can allow ~2x traffic around window edges

### Sliding Window Log

![Sliding Window Log](<rate limiter designs/slide_window_log.svg>)

Parameters
- Window size (seconds)
- Threshold (max requests in the last window)

Pros
- Fixes the boundary burst problem
- Smooth, accurate last-N-seconds view
- Fine-grained control

Cons
- Higher memory usage (stores timestamps) - O(queue)

### Sliding Window Counter

Parameters
- Window size (seconds)
- Threshold (max requests in the last window, approximated)

Pros
- Memory efficient - O(1): `window_id`, `prev` and `curr` - Can be linked list ?
- Smoother than fixed window; uses weighted counts

Cons
- Approximation (not a strict exact lookback window)

## TODOs

- Add observability: log decisions and expose counters (accepted/rejected per user)
    - shoudld we expose the counters ? any security risk here ? whats the trade offs ?
        - Safely expose per-user-request headers such as `X-RateLimi-Limit`,`X-RateLimi-Remaining` and `X-RateLimi-Retry-After` only to authenticated users.  

- Add unit tests that simulate bursts, resets, and expiry boundaries
    - whats expiry boundaries ?
        - For fixed window: the boundary at t = k * window_size where a user can burst at the end of one window and the start of the next.
        - For sliding windows: the boundary at now - window_seconds (exact cutoff); ensure you evict timestamps/counters correctly.
        - For TTL-based KV stores: state might disappear mid-stream; your algorithm must handle missing state as “new key”.


- Document design trade-offs (accuracy, memory, distributed locking, clock skew, persistence)
    - sliding window log could be memory inefficient, as it appends new requests into the log. each time during rate limit decsion, we need to clear expired reqests. 
        - If need scale, token bucket and sliding window counter are good candidates. 
        - If need exactness, sliding window log but costs more memory. 
    - In distributed setups, you avoid locks by using atomic KV operations (Redis INCR, Lua scripts) so the check+update happens atomically
    - whats clock skew: 
        - Window calculations based on wall-clock can allow extra requests or incorrectly reject.
        - Use server-side time from the store when possible, or monotonic locally; in Redis, rely on Redis time inside Lua if you need consistency.
    - presistence: Redis cache is a suitable options here as we need to store the Key and Value pairs based on the user and action. we can hash on "userid_action" as the key to avoid celebrity problem. We can add TTL to each key to expire any KV pair that is not regularly accessed. 
- Optional extensions: middleware/decorator, Redis backend, Prometheus metrics

## Interview Talking Points

- Algorithm trade-offs: fixed vs sliding, accuracy vs memory, burst behavior
- Scaling: sharding keys, Redis TTLs, atomic increments, distributed counters, clock drift
    - atomic increments: Atomic increment means the KV store guarantees increments aren’t lost under concurrency (e.g., Redis INCR). For more complex logic (sliding windows / token bucket), use a Redis `Lua` script to do read-modify-write atomically.

- Observability: headers, logs, metrics, load testing

## Next Steps

1. Sketch the flow of requests and state updates for your chosen limiter.
2. Implement the first algorithm incrementally, writing tests as you go.
3. Add documentation explaining how to adjust limits and swap storage backends.
4. Optional: add a CLI/script that exercises concurrency scenarios for quick demos.
