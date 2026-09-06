"""intervals.icu REST 客户端（只读能力，M1 范围）。

认证结论（S0-3 spike 实测）：
- HTTP Basic；用户名固定为字面量 "API_KEY"，密码 = 个人 API key；
- 本人数据 athlete 路径一律用 0。
"""
from __future__ import annotations

import time

import httpx

BASE_URL = "https://intervals.icu/api/v1"


class IntervalsError(Exception):
    """intervals.icu API 错误（4xx/5xx 且无法重试）。"""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class IntervalsAuthError(IntervalsError):
    """认证失败（401）：凭据无效或权限不足。"""


class IntervalsClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key 不能为空")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,  # 注入 MockTransport 用于契约测试
        )

    # ---- 底层请求与重试 ----
    def _request(self, method: str, path: str, params: dict | None = None) -> dict | list:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.request(
                    method, url, params=params, auth=("API_KEY", self._api_key)
                )
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise IntervalsError(0, f"网络错误: {exc}") from exc

            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise IntervalsError(resp.status_code, resp.text[:300])
            if resp.status_code == 401:
                raise IntervalsAuthError(401, "intervals.icu 认证失败，请检查 API Key")
            if resp.status_code >= 400:
                raise IntervalsError(resp.status_code, resp.text[:300])
            return resp.json()
        raise IntervalsError(0, f"请求失败: {last_exc}")

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(0.5 * (2**attempt))

    # ---- 业务只读方法 ----
    def get_athlete(self) -> dict:
        data = self._request("GET", "/athlete/0")
        assert isinstance(data, dict)
        return data

    def list_activities(self, oldest: str, newest: str) -> list[dict]:
        data = self._request(
            "GET",
            "/athlete/0/activities",
            params={"oldest": oldest, "newest": newest},
        )
        assert isinstance(data, list)
        return data
