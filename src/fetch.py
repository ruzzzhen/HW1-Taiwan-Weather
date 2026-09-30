"""呼叫 CWA Open Data API 取得天氣預報原始 JSON。

安全原則:
- 授權碼一律透過 requests 的 params 傳遞,不自行拼進 URL 字串。
- 任何錯誤訊息 / log 都會先把授權碼置換成 ***,確保不會外洩。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import requests

from src.config import API_BASE, DATASET_ID, RAW_DIR, ensure_dirs

DEFAULT_TIMEOUT = 30


class WeatherAPIError(RuntimeError):
    """呼叫 CWA API 失敗(連線錯誤、HTTP 錯誤、回傳格式非預期)。"""


def _scrub(text: str, secret: str) -> str:
    """把字串中的授權碼換成 ***。"""
    return text.replace(secret, "***") if secret else text


def fetch_forecast(
    api_key: str,
    dataset_id: str = DATASET_ID,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """抓取指定資料集的預報 JSON。

    Args:
        api_key: CWA 授權碼。
        dataset_id: 資料集代碼,預設 F-D0047-091(各縣市未來一週天氣預報)。
        timeout: 連線逾時秒數。

    Returns:
        解析後的 JSON dict。

    Raises:
        WeatherAPIError: 連線失敗、HTTP 非 2xx、回傳非 JSON,或 success 欄位不為 true。
    """
    url = f"{API_BASE}/{dataset_id}"
    try:
        resp = requests.get(
            url,
            params={"Authorization": api_key, "format": "JSON"},
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise WeatherAPIError(
            f"連線 CWA API 逾時({timeout} 秒),請稍後再試。"
        ) from exc
    except requests.RequestException as exc:
        raise WeatherAPIError(
            f"連線 CWA API 失敗:{_scrub(str(exc), api_key)}"
        ) from exc

    if resp.status_code == 401:
        raise WeatherAPIError(
            "CWA API 回傳 401:授權碼不正確或已失效。"
            "請到 https://opendata.cwa.gov.tw/user/authkey 確認你的授權碼,"
            "再更新 .env 裡的 CWA_API_KEY。"
        )
    if not resp.ok:
        raise WeatherAPIError(
            f"CWA API 回傳 HTTP {resp.status_code}:"
            f"{_scrub(resp.text[:200], api_key)}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise WeatherAPIError(
            f"CWA API 回傳的不是合法 JSON(前 200 字):"
            f"{_scrub(resp.text[:200], api_key)}"
        ) from exc

    # CWA 用字串 "true" 而非布林值
    success = str(payload.get("success", "")).lower()
    if success not in ("true", "1"):
        raise WeatherAPIError(
            f"CWA API 回報失敗(success={payload.get('success')!r}),資料集 {dataset_id}。"
        )

    return payload


def save_raw(payload: dict, dataset_id: str = DATASET_ID) -> Path:
    """把原始 JSON 存到 data/raw/(除錯用,此目錄已被 .gitignore 排除)。"""
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RAW_DIR / f"{dataset_id}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
