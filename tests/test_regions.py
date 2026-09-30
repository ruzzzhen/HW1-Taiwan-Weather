"""測試縣市 → 六大區域對應表。"""
from __future__ import annotations

from src.regions import (
    CITY_TO_REGION,
    OUTLYING_REGION,
    REGION_ORDER,
    REGION_TO_CITIES,
    city_to_region,
    normalize_city,
)


def test_covers_all_22_cities():
    """台灣本島加離島共 22 個縣市,全部都要有對應區域。"""
    assert len(CITY_TO_REGION) == 22


def test_six_main_regions_plus_outlying():
    assert REGION_ORDER == ["北部", "中部", "南部", "東北部", "東部", "東南部"]
    assert set(REGION_TO_CITIES) == set(REGION_ORDER) | {OUTLYING_REGION}


def test_no_city_belongs_to_two_regions():
    """把所有區域的縣市攤平後,總數應等於去重後的數量。"""
    flat = [city for cities in REGION_TO_CITIES.values() for city in cities]
    assert len(flat) == len(set(flat))


def test_normalize_handles_tai_variant():
    """民間常寫「台」,官方寫「臺」,兩者要視為同一個縣市。"""
    assert normalize_city("台北市") == "臺北市"
    assert normalize_city("  台東縣 ") == "臺東縣"
    assert normalize_city(None) == ""


def test_city_to_region_accepts_both_variants():
    assert city_to_region("臺北市") == "北部"
    assert city_to_region("台北市") == "北部"
    assert city_to_region("台中市") == "中部"
    assert city_to_region("宜蘭縣") == "東北部"
    assert city_to_region("花蓮縣") == "東部"
    assert city_to_region("臺東縣") == "東南部"
    assert city_to_region("澎湖縣") == OUTLYING_REGION


def test_unknown_city_returns_none():
    assert city_to_region("火星市") is None
    assert city_to_region("") is None
