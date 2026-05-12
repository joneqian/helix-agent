"""Tests for :class:`control_plane.middleware.RateLimitMiddleware`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse

from control_plane.middleware import RateLimitMiddleware
from control_plane.ratelimit import InProcessTokenBucketLimiter, RateLimitDecision, RateLimiter


@dataclass
class _StubLimiter:
    """Records the (dimension, key) the middleware computed."""

    decision: RateLimitDecision
    calls: list[tuple[str, str]]

    async def acquire(self, *, dimension: str, key: str) -> RateLimitDecision:
        self.calls.append((dimension, key))
        return self.decision


def _build_probe_app(limiter: RateLimiter, *, enabled: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter, enabled=enabled)

    @app.get("/probe")
    async def probe() -> JSONResponse:
        return JSONResponse({"ok": True})

    return app


@pytest.mark.asyncio
async def test_allowed_request_passes_through() -> None:
    stub = _StubLimiter(
        decision=RateLimitDecision(allowed=True, retry_after_s=0.0, remaining=5.0),
        calls=[],
    )
    app = _build_probe_app(stub)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")
    assert response.status_code == 200
    assert stub.calls and stub.calls[0][0] == "ip"


@pytest.mark.asyncio
async def test_api_key_used_when_header_present() -> None:
    stub = _StubLimiter(
        decision=RateLimitDecision(allowed=True, retry_after_s=0.0, remaining=5.0),
        calls=[],
    )
    app = _build_probe_app(stub)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/probe", headers={"X-API-Key": "secret-token"})
    assert stub.calls[0][0] == "apikey"
    # Raw key must NOT appear in the recorded bucket key.
    assert stub.calls[0][1] != "secret-token"
    assert len(stub.calls[0][1]) == 16


@pytest.mark.asyncio
async def test_denied_returns_429_with_envelope() -> None:
    stub = _StubLimiter(
        decision=RateLimitDecision(allowed=False, retry_after_s=2.5, remaining=0.0),
        calls=[],
    )
    app = _build_probe_app(stub)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"  # ceil(2.5)
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert body["error"]["retry_after_s"] == 3


@pytest.mark.asyncio
async def test_disabled_short_circuit_skips_limiter() -> None:
    stub = _StubLimiter(
        decision=RateLimitDecision(allowed=False, retry_after_s=10.0, remaining=0.0),
        calls=[],
    )
    app = _build_probe_app(stub, enabled=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/probe")
    assert response.status_code == 200
    assert stub.calls == []


@pytest.mark.asyncio
async def test_concurrent_burst_returns_some_429s() -> None:
    """N concurrent requests > burst → exactly `burst` allowed, rest 429."""
    limiter = InProcessTokenBucketLimiter(capacity=3, refill_per_sec=0.001)
    app = _build_probe_app(limiter)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(*(client.get("/probe") for _ in range(8)))
    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 3
    assert status_codes.count(429) == 5
