"""測試溫度色階與天氣 emoji 對應。

重點:色階是「固定刻度」,同一個溫度在任何日期都要得到同一個顏色,
否則不同日期的顏色無法互相比較。
"""
from __future__ import annotations

from src.theme import (
    TEMP_DOMAIN,
    TEMP_RAMP,
    temp_color,
    temp_position,
    weather_icon,
)


# ---------- 色階 ----------
def test_ramp_is_single_hue_ordered():
    """色階有 7 階,淺色底由淺到深代表低溫到高溫。"""
    assert len(TEMP_RAMP) == 7
    assert TEMP_RAMP[0] == "#ff8e64"   # 最淺 = 低溫
    assert TEMP_RAMP[-1] == "#6f2300"  # 最深 = 高溫


def test_low_temp_gets_light_end():
    lo, _ = TEMP_DOMAIN
    assert temp_color(lo) == TEMP_RAMP[0]


def test_high_temp_gets_dark_end():
    _, hi = TEMP_DOMAIN
    assert temp_color(hi) == TEMP_RAMP[-1]


def test_color_is_stable_for_same_temperature():
    """同一個溫度永遠對到同一個顏色(固定刻度,不隨當日資料縮放)。"""
    assert temp_color(28) == temp_color(28.0)


def test_color_is_monotonic_along_ramp():
    """溫度越高,取到的色階索引不會往回走。"""
    indices = [TEMP_RAMP.index(temp_color(t)) for t in range(12, 39, 2)]
    assert indices == sorted(indices)


def test_out_of_range_is_clamped():
    lo, hi = TEMP_DOMAIN
    assert temp_color(lo - 50) == TEMP_RAMP[0]
    assert temp_color(hi + 50) == TEMP_RAMP[-1]


def test_missing_temperature_gets_neutral_color():
    assert temp_color(None).startswith("rgba")


# ---------- 溫度條位置 ----------
def test_position_spans_zero_to_hundred():
    lo, hi = TEMP_DOMAIN
    assert temp_position(lo) == 0.0
    assert temp_position(hi) == 100.0
    assert temp_position((lo + hi) / 2) == 50.0


def test_position_is_clamped():
    lo, hi = TEMP_DOMAIN
    assert temp_position(lo - 10) == 0.0
    assert temp_position(hi + 10) == 100.0
    assert temp_position(None) == 0.0


# ---------- 天氣 emoji ----------
def test_weather_icon_matches_keyword():
    assert weather_icon("晴時多雲") == "🌤️"
    assert weather_icon("多雲") == "⛅"
    assert weather_icon("陰天") == "☁️"
    assert weather_icon("多雲短暫雨") == "🌦️"
    assert weather_icon("午後雷陣雨") == "⛈️"


def test_thunder_beats_rain():
    """關鍵字有優先順序:雷陣雨要給雷,不能只看到「雨」。"""
    assert weather_icon("雷陣雨") == "⛈️"


def test_missing_weather_returns_placeholder():
    assert weather_icon(None) == "❓"
    assert weather_icon("") == "❓"


def test_unknown_weather_has_fallback():
    assert weather_icon("外星天氣") == "🌡️"
