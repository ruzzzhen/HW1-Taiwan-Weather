"""測試 JSON 解析邏輯。

重點:全部使用 tests/fixtures/sample_forecast.json 這份假資料,不呼叫真實 API。
"""
from __future__ import annotations

import copy

import pytest

from src.parse import ParseError, parse_forecast


def find(rows, city, date):
    """從解析結果中找出某縣市某天的那一列。"""
    hits = [r for r in rows if r["city"] == city and r["date"] == date]
    assert len(hits) == 1, f"{city} {date} 應該只有一列,實際 {len(hits)} 列"
    return hits[0]


# ---------- 基本欄位 ----------
def test_returns_expected_row_count(sample_payload):
    """3 個縣市:臺北 2 天 + 臺東 2 天 + 火星市 1 天 = 5 列。"""
    assert len(parse_forecast(sample_payload)) == 5


def test_row_has_all_required_fields(sample_payload):
    row = parse_forecast(sample_payload)[0]
    assert set(row) == {
        "region", "city", "date", "min_temp", "max_temp", "weather", "pop", "lat", "lon",
    }


def test_region_is_mapped_from_city(sample_payload):
    rows = parse_forecast(sample_payload)
    assert find(rows, "臺北市", "2026-09-30")["region"] == "北部"
    assert find(rows, "臺東縣", "2026-09-30")["region"] == "東部"


def test_city_name_normalized_to_tai(sample_payload):
    """假資料裡寫「台東縣」,解析後要統一成「臺東縣」,否則 UNIQUE(city, date) 會失效。"""
    cities = {r["city"] for r in parse_forecast(sample_payload)}
    assert "臺東縣" in cities
    assert "台東縣" not in cities


def test_coordinates_parsed_as_float(sample_payload):
    row = find(parse_forecast(sample_payload), "臺北市", "2026-09-30")
    assert row["lat"] == pytest.approx(25.0478)
    assert row["lon"] == pytest.approx(121.5319)


# ---------- 12 小時區間 → 每日彙整(本專案最關鍵的邏輯)----------
def test_daily_min_is_min_across_intervals(sample_payload):
    """臺北市 9/30 白天最低 26、夜間最低 24 -> 當日最低溫應為 24。"""
    row = find(parse_forecast(sample_payload), "臺北市", "2026-09-30")
    assert row["min_temp"] == 24.0


def test_daily_max_is_max_across_intervals(sample_payload):
    """臺北市 9/30 白天最高 31、夜間最高 27 -> 當日最高溫應為 31。"""
    row = find(parse_forecast(sample_payload), "臺北市", "2026-09-30")
    assert row["max_temp"] == 31.0


def test_pop_is_max_across_intervals(sample_payload):
    """降雨機率取當日最大值(白天 10%、夜間 40% -> 40%)。"""
    row = find(parse_forecast(sample_payload), "臺北市", "2026-09-30")
    assert row["pop"] == 40


def test_weather_prefers_daytime_interval(sample_payload):
    """白天「晴時多雲」與夜間「多雲」並存時,代表天氣取白天那個。"""
    row = find(parse_forecast(sample_payload), "臺北市", "2026-09-30")
    assert row["weather"] == "晴時多雲"


def test_weather_falls_back_to_night_when_no_daytime(sample_payload):
    """臺東縣 9/30 只有夜間的天氣現象,就用夜間的值而不是留空。"""
    row = find(parse_forecast(sample_payload), "臺東縣", "2026-09-30")
    assert row["weather"] == "短暫陣雨"


def test_multiple_dates_are_split(sample_payload):
    rows = parse_forecast(sample_payload)
    assert {r["date"] for r in rows} == {"2026-09-30", "2026-10-01"}


def test_rows_sorted_by_date(sample_payload):
    dates = [r["date"] for r in parse_forecast(sample_payload)]
    assert dates == sorted(dates)


# ---------- 容錯 ----------
def test_missing_value_code_becomes_none(sample_payload):
    """CWA 用 -99 表示缺值,不能被當成攝氏 -99 度。"""
    row = find(parse_forecast(sample_payload), "臺東縣", "2026-10-01")
    assert row["min_temp"] is None
    assert row["max_temp"] == 32.0


def test_dash_value_becomes_none(sample_payload):
    """CWA 對較遠日期的降雨機率會回傳 '-',要轉成 None。"""
    payload = copy.deepcopy(sample_payload)
    location = payload["records"]["Locations"][0]["Location"][0]
    for element in location["WeatherElement"]:
        if element["ElementName"] == "12小時降雨機率":
            for time_entry in element["Time"]:
                time_entry["ElementValue"][0]["ProbabilityOfPrecipitation"] = "-"
    row = find(parse_forecast(payload), "臺北市", "2026-09-30")
    assert row["pop"] is None


def test_missing_element_does_not_crash(sample_payload):
    """臺東縣刻意沒有「12小時降雨機率」要素,應該回 None 而不是拋錯。"""
    row = find(parse_forecast(sample_payload), "臺東縣", "2026-09-30")
    assert row["pop"] is None
    assert row["min_temp"] == 23.0


def test_unknown_city_is_classified_not_dropped(sample_payload):
    """未知縣市歸「未分類」,不要整批解析失敗、也不要靜靜消失。"""
    row = find(parse_forecast(sample_payload), "火星市", "2026-09-30")
    assert row["region"] == "未分類"


def test_day_without_temperature_is_skipped(sample_payload):
    """某天只有濕度沒有溫度時,那天沒有顯示價值,應被略過。"""
    payload = copy.deepcopy(sample_payload)
    location = payload["records"]["Locations"][0]["Location"][0]
    location["WeatherElement"] = [
        element
        for element in location["WeatherElement"]
        if element["ElementName"] not in ("最高溫度", "最低溫度")
    ]
    rows = parse_forecast(payload)
    assert not [r for r in rows if r["city"] == "臺北市"]


# ---------- 結構錯誤 ----------
def test_legacy_format_raises_helpful_error():
    """舊版 F-C0032-001 用 records.location,要給看得懂的錯誤訊息。"""
    legacy = {"success": "true", "records": {"location": [{"locationName": "臺北市"}]}}
    with pytest.raises(ParseError, match="F-C0032-001"):
        parse_forecast(legacy)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"records": {}},
        {"records": {"Locations": []}},
        {"records": {"Locations": [{"Location": []}]}},
    ],
)
def test_broken_structure_raises_parse_error(payload):
    with pytest.raises(ParseError):
        parse_forecast(payload)


def test_non_dict_payload_raises_parse_error():
    with pytest.raises(ParseError):
        parse_forecast(["not", "a", "dict"])
