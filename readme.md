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
- Memory efficient
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
- Memory efficient
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
- Memory efficient
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
- Higher memory usage (stores timestamps)

### Sliding Window Counter

Parameters
- Window size (seconds)
- Threshold (max requests in the last window, approximated)

Pros
- Memory efficient
- Smoother than fixed window; uses weighted counts

Cons
- Approximation (not a strict exact lookback window)

## TODOs

- Add observability: log decisions and expose counters (accepted/rejected per user)
- Add unit tests that simulate bursts, resets, and expiry boundaries
- Document design trade-offs (accuracy, memory, distributed locking, clock skew, persistence)
- Optional extensions: middleware/decorator, Redis backend, Prometheus metrics

## Interview Talking Points

- Algorithm trade-offs: fixed vs sliding, accuracy vs memory, burst behavior
- Scaling: sharding keys, Redis TTLs, atomic increments, distributed counters, clock drift
- Observability: headers, logs, metrics, load testing

## Next Steps

1. Sketch the flow of requests and state updates for your chosen limiter.
2. Implement the first algorithm incrementally, writing tests as you go.
3. Add documentation explaining how to adjust limits and swap storage backends.
4. Optional: add a CLI/script that exercises concurrency scenarios for quick demos.
