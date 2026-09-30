"""把 CWA F-D0047-091(各縣市未來一週天氣預報)的 JSON 解析成每日一列的紀錄。

設計重點:
1. **純函式、不碰網路** —— 只吃 dict、吐 list[dict],所以 pytest 可以用假 JSON 測試。
2. **原始資料是 12 小時區間**(白天 06-18、夜間 18-06),但我們要的是「每天」的最低/最高溫,
   所以要依日期 groupby 後取 min(最低溫) 與 max(最高溫)。
3. **容錯** —— 缺欄位、缺值、-99(CWA 的缺值代碼)、未知縣市都不會讓整批解析失敗。

回傳每列欄位:
    region, city, date, min_temp, max_temp, weather, pop, lat, lon
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from src.regions import city_to_region, normalize_city

logger = logging.getLogger(__name__)

UNCLASSIFIED = "未分類"

#: CWA 用來表示「無資料」的值
MISSING_VALUES = {"", "-", "-99", "-99.0", "None", None}

#: 我們要抓的天氣要素:內部欄位名 -> (ElementName 中文, ElementValue 內的 key 關鍵字)
ELEMENT_SPECS = {
    "max_temp": ("最高溫度", "MaxTemperature"),
    "min_temp": ("最低溫度", "MinTemperature"),
    "weather": ("天氣現象", "Weather"),
    "pop": ("12小時降雨機率", "ProbabilityOfPrecipitation"),
}


class ParseError(ValueError):
    """JSON 結構不是預期的 F-D0047-091 格式。"""


# --------------------------------------------------------------------------
# 低階小工具
# --------------------------------------------------------------------------
def _to_float(raw: Any) -> Optional[float]:
    """把字串溫度轉 float;缺值或轉不動就回 None。"""
    if raw in MISSING_VALUES:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return None if value <= -90 else value  # -99 類缺值代碼


def _to_int(raw: Any) -> Optional[int]:
    value = _to_float(raw)
    return None if value is None else int(value)


def _start_time(time_entry: dict) -> str:
    """區間型要素用 StartTime,瞬時型用 DataTime。"""
    return str(time_entry.get("StartTime") or time_entry.get("DataTime") or "")


def _date_of(time_entry: dict) -> Optional[str]:
    """從 '2026-09-30T06:00:00+08:00' 取出 '2026-09-30'。"""
    stamp = _start_time(time_entry)
    return stamp[:10] if len(stamp) >= 10 else None


def _hour_of(time_entry: dict) -> Optional[int]:
    """取出小時,用來分辨白天(06)或夜間(18)時段。"""
    stamp = _start_time(time_entry)
    try:
        return int(stamp[11:13])
    except (ValueError, IndexError):
        return None


def _find_element(location: dict, element_name: str) -> Optional[dict]:
    """在某縣市的 WeatherElement 中找指定名稱的要素(先精準比對,再用包含比對)。"""
    elements = location.get("WeatherElement") or []
    for element in elements:
        if str(element.get("ElementName", "")).strip() == element_name:
            return element
    for element in elements:
        if element_name in str(element.get("ElementName", "")):
            return element
    return None


def _raw_value(time_entry: dict, value_key: str) -> Any:
    """從 ElementValue[0] 取值:先找同名 key,再找含關鍵字的 key。"""
    values = time_entry.get("ElementValue") or []
    if not values or not isinstance(values[0], dict):
        return None
    first = values[0]
    if value_key in first:
        return first[value_key]
    for key, value in first.items():
        if value_key.lower() in str(key).lower():
            return value
    return None


def _times(location: dict, field: str) -> Iterable[dict]:
    """取得某內部欄位對應要素的所有時間區間。"""
    element_name, _ = ELEMENT_SPECS[field]
    element = _find_element(location, element_name)
    if element is None:
        logger.warning(
            "縣市 %s 缺少天氣要素「%s」", location.get("LocationName"), element_name
        )
        return []
    return element.get("Time") or []


# --------------------------------------------------------------------------
# 主要解析流程
# --------------------------------------------------------------------------
def _locations(payload: dict) -> list:
    """取出縣市清單,順便驗證 JSON 結構。"""
    if not isinstance(payload, dict):
        raise ParseError("payload 必須是 dict")

    records = payload.get("records")
    if not isinstance(records, dict):
        raise ParseError("JSON 缺少 records 物件")

    blocks = records.get("Locations")
    if not blocks:
        if "location" in records:
            raise ParseError(
                "這是舊版 F-C0032-001 格式(records.location),"
                "本專案使用 F-D0047-091(records.Locations)。"
            )
        raise ParseError("JSON 缺少 records.Locations")

    locations = blocks[0].get("Location") or []
    if not locations:
        raise ParseError("records.Locations[0].Location 是空的")
    return locations


def _parse_one_city(location: dict) -> list[dict]:
    """解析單一縣市,回傳該縣市每一天的一列紀錄。"""
    # 統一成官方的「臺」字寫法,避免同一縣市出現兩種名稱而讓 UNIQUE(city, date) 失效
    city = normalize_city(location.get("LocationName"))
    if not city:
        logger.warning("跳過沒有 LocationName 的縣市區塊")
        return []

    region = city_to_region(city)
    if region is None:
        logger.warning("縣市「%s」不在六大區域對應表中,歸類為「%s」", city, UNCLASSIFIED)
        region = UNCLASSIFIED

    lat = _to_float(location.get("Latitude"))
    lon = _to_float(location.get("Longitude"))

    # 以日期為 key,逐個要素把值塞進去
    daily: dict[str, dict] = {}

    def slot(date: str) -> dict:
        return daily.setdefault(
            date,
            {"max_temps": [], "min_temps": [], "pops": [], "weathers": []},
        )

    for time_entry in _times(location, "max_temp"):
        date = _date_of(time_entry)
        value = _to_float(_raw_value(time_entry, ELEMENT_SPECS["max_temp"][1]))
        if date and value is not None:
            slot(date)["max_temps"].append(value)

    for time_entry in _times(location, "min_temp"):
        date = _date_of(time_entry)
        value = _to_float(_raw_value(time_entry, ELEMENT_SPECS["min_temp"][1]))
        if date and value is not None:
            slot(date)["min_temps"].append(value)

    for time_entry in _times(location, "pop"):
        date = _date_of(time_entry)
        value = _to_int(_raw_value(time_entry, ELEMENT_SPECS["pop"][1]))
        if date and value is not None:
            slot(date)["pops"].append(value)

    for time_entry in _times(location, "weather"):
        date = _date_of(time_entry)
        text = _raw_value(time_entry, ELEMENT_SPECS["weather"][1])
        if date and text not in MISSING_VALUES:
            hour = _hour_of(time_entry)
            # 白天時段(06:00 起)優先當代表天氣
            is_daytime = hour is not None and 6 <= hour < 18
            slot(date)["weathers"].append((is_daytime, str(text).strip()))

    rows = []
    for date in sorted(daily):
        bucket = daily[date]
        if not bucket["max_temps"] and not bucket["min_temps"]:
            continue  # 這天完全沒有溫度資料,沒有顯示價值

        daytime = [text for is_day, text in bucket["weathers"] if is_day]
        any_weather = [text for _, text in bucket["weathers"]]

        rows.append(
            {
                "region": region,
                "city": city,
                "date": date,
                "min_temp": min(bucket["min_temps"]) if bucket["min_temps"] else None,
                "max_temp": max(bucket["max_temps"]) if bucket["max_temps"] else None,
                "weather": (daytime or any_weather or [None])[0],
                "pop": max(bucket["pops"]) if bucket["pops"] else None,
                "lat": lat,
                "lon": lon,
            }
        )
    return rows


def parse_forecast(payload: dict) -> list[dict]:
    """把 F-D0047-091 的 JSON 解析成每縣市每日一列的紀錄。

    Args:
        payload: `fetch_forecast()` 回傳的 JSON dict。

    Returns:
        list[dict],每列含 region/city/date/min_temp/max_temp/weather/pop/lat/lon。

    Raises:
        ParseError: JSON 結構不符預期。
    """
    rows: list[dict] = []
    for location in _locations(payload):
        rows.extend(_parse_one_city(location))

    if not rows:
        raise ParseError("解析完成但沒有任何可用資料(所有縣市都缺溫度欄位)")

    rows.sort(key=lambda r: (r["date"], r["region"], r["city"]))
    return rows
