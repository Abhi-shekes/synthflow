"""Coarse, in-process request throttling for unauthenticated endpoints.

Login, signup and refresh are exactly the endpoints an attacker can hit
without already holding a credential, so they need a limiter in front of
them before any application logic — including a database query — runs.
This is a per-process sliding window keyed by the connecting IP: cheap,
dependency-free, and enough to blunt a single-source flood.

It is deliberately not the whole defense. It resets on every restart and
does not share state across replicas, so if SynthFlow is ever run with more
than one API process behind a load balancer, an attacker distributed across
enough source IPs — or just routed to a different replica each request —
isn't meaningfully slowed by this alone. What actually stops credential
stuffing against one account is the per-account lockout in
`app.models.user` (`failed_login_attempts`/`locked_until`), which lives in
Postgres and is correct regardless of how many replicas are running. This
module is the fast, cheap layer in front of that; a shared store (Redis, or
the database) is the upgrade path if this app ever runs multi-replica
behind a public load balancer.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Try again in a minute.",
                )
            hits.append(now)

    def reset(self) -> None:
        """Test-only: the test suite reuses one client "IP" across many
        tests in the same process, which would otherwise exhaust a limiter
        sized for real traffic after a handful of tests. Production code
        never calls this."""
        with self._lock:
            self._hits.clear()


# Generous for a real user typing a password wrong once or twice; slow for
# an attacker trying many.
login_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60)
signup_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
refresh_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=60)


def _client_ip(request: Request) -> str:
    # request.client.host is the actual TCP peer as uvicorn sees it — not a
    # client-supplied header, which a caller could set to any value and
    # thereby pick their own rate-limit bucket. A deployment that terminates
    # TLS at a reverse proxy should run uvicorn with --proxy-headers and a
    # trusted proxy list so this still resolves to the real client; that is
    # a deployment-time decision, not something to trust unconditionally
    # here by default.
    return request.client.host if request.client else "unknown"


def limit_login(request: Request) -> None:
    login_limiter.check(_client_ip(request))


def limit_signup(request: Request) -> None:
    signup_limiter.check(_client_ip(request))


def limit_refresh(request: Request) -> None:
    refresh_limiter.check(_client_ip(request))
