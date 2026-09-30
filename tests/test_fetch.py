"""測試 API 呼叫層的錯誤處理與金鑰保護。

所有測試都用 monkeypatch 假造 requests 的回應,**完全不會連到真實 API**。
"""
from __future__ import annotations

import pytest
import requests

from src import fetch
from src.fetch import WeatherAPIError, fetch_forecast

FAKE_KEY = "CWA-FAKE-KEY-1234567890"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", raise_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"success": "true"}
        self.text = text or "fake body"
        self._raise_json = raise_json

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


@pytest.fixture()
def capture_request(monkeypatch):
    """攔截 requests.get,記下呼叫參數並回傳指定假回應。"""
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params or {}
        captured["timeout"] = timeout
        return captured["response"]

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    return captured


# ---------- 正常路徑 ----------
def test_returns_payload_on_success(capture_request):
    capture_request["response"] = FakeResponse(payload={"success": "true", "records": {}})
    result = fetch_forecast(FAKE_KEY)
    assert result == {"success": "true", "records": {}}


def test_api_key_goes_in_params_not_url(capture_request):
    """金鑰必須走 params,不能自己拼進 URL 字串(避免出現在 log 或例外訊息裡)。"""
    capture_request["response"] = FakeResponse()
    fetch_forecast(FAKE_KEY)

    assert FAKE_KEY not in capture_request["url"]
    assert capture_request["params"]["Authorization"] == FAKE_KEY
    assert capture_request["params"]["format"] == "JSON"


def test_dataset_id_appears_in_url(capture_request):
    capture_request["response"] = FakeResponse()
    fetch_forecast(FAKE_KEY, dataset_id="F-D0047-091")
    assert capture_request["url"].endswith("/F-D0047-091")


# ---------- 錯誤路徑 ----------
def test_401_gives_actionable_message(capture_request):
    capture_request["response"] = FakeResponse(status_code=401, text="Forbidden")
    with pytest.raises(WeatherAPIError) as exc:
        fetch_forecast(FAKE_KEY)
    assert "401" in str(exc.value)
    assert "授權碼" in str(exc.value)


def test_500_raises_weather_api_error(capture_request):
    capture_request["response"] = FakeResponse(status_code=500, text="boom")
    with pytest.raises(WeatherAPIError, match="500"):
        fetch_forecast(FAKE_KEY)


def test_invalid_json_raises_weather_api_error(capture_request):
    capture_request["response"] = FakeResponse(raise_json=True)
    with pytest.raises(WeatherAPIError, match="JSON"):
        fetch_forecast(FAKE_KEY)


def test_success_false_raises_weather_api_error(capture_request):
    capture_request["response"] = FakeResponse(payload={"success": "false"})
    with pytest.raises(WeatherAPIError, match="失敗"):
        fetch_forecast(FAKE_KEY)


def test_timeout_raises_weather_api_error(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    with pytest.raises(WeatherAPIError, match="逾時"):
        fetch_forecast(FAKE_KEY, timeout=5)


def test_connection_error_raises_weather_api_error(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    with pytest.raises(WeatherAPIError, match="連線"):
        fetch_forecast(FAKE_KEY)


# ---------- 金鑰不可外洩 ----------
def test_key_is_scrubbed_from_http_error_message(capture_request):
    """HTTP 錯誤時,回應內容可能含金鑰,錯誤訊息必須換成 ***。"""
    capture_request["response"] = FakeResponse(
        status_code=400, text=f"bad request for Authorization={FAKE_KEY}"
    )
    with pytest.raises(WeatherAPIError) as exc:
        fetch_forecast(FAKE_KEY)
    assert FAKE_KEY not in str(exc.value)
    assert "***" in str(exc.value)


def test_key_is_scrubbed_from_connection_error_message(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.ConnectionError(f"failed to reach ...?Authorization={FAKE_KEY}")

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    with pytest.raises(WeatherAPIError) as exc:
        fetch_forecast(FAKE_KEY)
    assert FAKE_KEY not in str(exc.value)
