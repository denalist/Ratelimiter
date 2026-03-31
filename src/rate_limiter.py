import time
from src.store import InMemoryKV
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Optional, Tuple, TypeVar


@dataclass(frozen=True)
class RateLimitDecision: 
    allowed: bool 
    remaining: float 
    limit: float 
    retry_after_sec: float


class RateLimiter: 
    def __init__(self, store: InMemoryKV) -> None:
        self._store = store

    @staticmethod
    def _now() -> float: 
        return time.monotonic()


    # 1. token bucket 
    def token_bucket(self, key: Tuple[str, str], capacity, refill_rate_per_sec) -> RateLimitDecision: 
        # has predefined capacity and tokens are refilled periodically
        # no background thread to refill, refill when request arrives 
        now = self._now()

        def do_update(state: Dict[str, any]) -> Tuple[Dict[str, Any], RateLimitDecision]:
            tokens = float(state.get("tokens", capacity))
            last_ts = float(state.get("ts", now))
            elapsed_time = max(0.0, now - last_ts) 
            tokens = min(float(capacity), tokens + refill_rate_per_sec * elapsed_time)

            if tokens >= 1: 
                allowed = True
                tokens -= 1
                retry_after_sec = 0.0
            else: 
                allowed = False 
                retry_after_sec = 2.0 

            decision = RateLimitDecision(
                allowed=allowed, remaining=max(0.0, tokens), limit=float(capacity), retry_after_sec=retry_after_sec
            )
            
            return {"tokens": tokens, "ts": now}, decision
        
        return self._store.update(key, do_update)
        

    from collections import deque
    # 2. leaking bucket 
    def leaking_bucket(self, key, capacity, request, outflow_rate) -> RateLimitDecision: 
        # similar to token bucket except requests are processe at a fixed rate and stored in a queue (FIFO)
        # when arrive, check if the queue is full. If not full, push to queue, else drop it. 
        # requests are pulled from the queue and processed at regular intervals 
        now = self._now()

        def do_update(state: Dict[str, any]) -> Tuple[Dict[str, Any], RateLimitDecision]:
        
            queue = state.get("req_queue", deque())
            last_ts = float(state.get("ts", now))
            elapsed = max(0.0, now - last_ts)
            drain_n = float(elapsed * outflow_rate)

            # simulate requests being pulled/consumed
            queue.popleft(drain_n)

            if len(queue) + 1 <= capacity: 
                queue.append(request)
                allowed = True
                retry_after_sec = 0.0 
            else: 
                allowed = False
                retry_after_sec = capacity/outflow_rate if outflow_rate > 0 else float("inf")

            remaining = max(0, capacity - len(queue))
            decision = RateLimitDecision(allowed=allowed, remaining=remaining, limit=float(capacity), retry_after_sec=retry_after_sec)

            return {"req_queue", queue, "ts", now},  decision

        return self._store.update(do_update)

    # 3.  fixed window counter
    def fixed_window_counter(self, key, limit, window_seconds) -> RateLimitDecision:
        # fixed size window and assign a counter for each window 
       
        now = self._now()
        window_id = int(now//window_seconds) if window_seconds > 0 else 0
       
        def do_update(state: Dict[str, any]) -> Tuple[Dict[str, Any], RateLimitDecision]:
            saved_window = float(state.get("window", window_id))
            count = float(state.get("ts", now) )

            # reset the window 
            if saved_window != window_id: 
                count = 0 
                saved_window = window_id

            if count + 1 < limit:
                count += 1 
                allowed = True
            else: 
                allowed = False
                if window_seconds > 0: 
                    retry_after_sec = (window_id + 1) * window_seconds       
                else: 
                    retry_after_sec = float("inf")

            remaining = max(0, limit - count)
            decision = RateLimitDecision(allowed=allowed, remaining=float(remaining), limit=float(limit), retry_after_sec=retry_after_sec)

            return {"window": saved_window, "count": count}, decision
        
        # write count and window_start back 
        return self._store.update(key, do_update)


# from sortedcontainers import SortedSet

# # sliding window log 
# def sliding_window_log(threshold, window_seconds): 
#     # fix the bursts at the boudry issue raised by the fixed_window_counter
#     # add request to a log, if exceeds the size, reject, else accept and append it to log. 
#     # remove previous logs that are outdated. 

#     # get the sorted log based on the user 
#     log = SortedSet()
#     prev_window = 0 # get this too 

#     curr_window_start = prev_window + window_seconds

#     # remove outdated timestamps 
#     i = 0 
#     while log[i] < curr_window_start:
#         log.discard(log[i]) # ? BUG
#         i += 1 

#     log.append(time.now()) # record both accept and reject requests 
#     if len(log) < threshold: 
#         return accept_message

#     return reject_message


# # sliding window counter 
# def sliding_window_count(threshold, window_seconds): 
#     # in a rolling window of prev minute% + curr minute%, calculate the total time-weighted reuqests
#     # check if it exceeds the threshold 

#     # get the number of requests of previous minute 
#     num_prev_req = 0 
#     num_curr_req = 0 + 1 # get the request of curr min then add curr request 

#     # ttl= (1- elaspsed% of curr minute) * num_prev_req + num_curr_req TODO
#     elasped_curr_min = time.now() # get the curr min % BUG 

#     ttl = (1-elasped_curr_min) * num_prev_req + num_curr_req
#     # write num_curr_req back 

#     if ttl <= threshold: 
#         return accept_message
#     return reject_message



# ----------------------- API ----------------------- #
from fastapi import FastAPI, HTTPException, Response
app = FastAPI()

store = InMemoryKV()
limiter = RateLimiter(store)

def _apply_headers(response: Response, decision) -> None: 
    response.headers["X-RateLimit-Limit"] = str(int(decision.limit))
    response.headers["X-RateLimit-Remaining"] = str(int(max(0.0, decision.remaining)))
    response.headers["Retry-After"] = str(int(max(0.0, decision.retry_after_seconds)))

def _make_key(user: int, action: Optional[str]) -> Tuple[str, str]: 
    return (str(user), action or "_")

@app.post("/event/")
def create_event(user: int, action: str | None, 
                algo: str = "token_bucket", *, 
                response):

    key = _make_key(user=user, action=action)

    # Defaults are intentionally small so you can hit the limit quickly while testing.
    if algo == "token_bucket":
        decision = limiter.token_bucket(key, capacity=10, refill_rate_per_sec_per_sec=1.0)
    elif algo == "leaky_bucket":
        decision = limiter.leaky_bucket(key, capacity=10, leak_rate_per_sec=1.0)
    elif algo == "fixed_window":
        decision = limiter.fixed_window_counter(key, limit=10, window_seconds=10)
    elif algo == "sliding_log":
        decision = limiter.sliding_window_log(key, limit=10, window_seconds=10.0)
    elif algo == "sliding_counter":
        decision = limiter.sliding_window_counter(key, limit=10, window_seconds=10)
    else:
        raise HTTPException(status_code=400, detail="Unknown algo")

    _apply_headers(response=response, decision=decision)

    if not decision.allowed: 
        raise HTTPException(status=429, detail="Too many requests ...")

    return{
        "message": f"Event created by user {user}", 
        "algo": algo, 
        "action": action, 
        "allowed": decision.allowed, 
        "remaining": decision.remaining, 
        "retry_after_sec": decision.retry_after_sec
    }



