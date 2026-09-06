"""intervals.icu 客户端契约测试（T2，使用 MockTransport，不发真实网络请求）。

样例字段来自 S0-3 spike 抓取的真实活动结构（值已替换为合成数据）。
"""
from __future__ import annotations

import base64

import httpx
import pytest

from app.integrations.intervals.client import (
    IntervalsAuthError,
    IntervalsClient,
    IntervalsError,
)

API_KEY = "test-api-key-1234"
EXPECTED_AUTH = "Basic " + base64.b64encode(b"API_KEY:test-api-key-1234").decode()


def _resp(json_body, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=json_body, request=httpx.Request("GET", "http://x"))


def test_auth_header_and_athlete_path():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return _resp({"id": "i0", "name": "Tester"})

    client = IntervalsClient(API_KEY, transport=httpx.MockTransport(handler))
    out = client.get_athlete()
    assert out["id"] == "i0"
    assert seen["auth"] == EXPECTED_AUTH
    assert "/athlete/0" in seen["url"]


def test_activities_endpoint_params():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _resp([])

    client = IntervalsClient(API_KEY, transport=httpx.MockTransport(handler))
    assert client.list_activities("2026-06-08", "2026-09-05") == []
    assert "oldest=2026-06-08" in seen["url"]
    assert "newest=2026-09-05" in seen["url"]


def test_retry_on_429_then_success():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return _resp({"error": "rate"}, status=429)
        return _resp({"id": "i0"})

    client = IntervalsClient(API_KEY, transport=httpx.MockTransport(handler))
    assert client.get_athlete()["id"] == "i0"
    assert len(calls) == 2


def test_401_raises_auth_error_without_retry():
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return _resp({"error": "auth"}, status=401)

    client = IntervalsClient(API_KEY, transport=httpx.MockTransport(handler))
    with pytest.raises(IntervalsAuthError):
        client.get_athlete()
    assert len(calls) == 1


def test_other_4xx_raises_intervals_error():
    client = IntervalsClient(
        API_KEY, transport=httpx.MockTransport(lambda r: _resp({}, status=404))
    )
    with pytest.raises(IntervalsError) as exc_info:
        client.get_athlete()
    assert exc_info.value.status == 404


def test_empty_api_key_rejected():
    with pytest.raises(ValueError):
        IntervalsClient("")
