"""深色儀表板的配色與樣式常數。

配色不是憑感覺挑的,而是照 dataviz 設計規範推導 + 驗證器實測:

* 溫度是「量值(magnitude)」→ 用 **sequential 單一色相** 色階,不用彩虹色。
  色相固定在 OKLCH H≈40.6°(橘),只改亮度,由深到淺代表低溫到高溫
  (深色底的 sequential 要「翻轉錨點」:越高的值越亮才看得清楚)。
* 已用 validate_palette.py --ordinal 驗證:亮度單調、相鄰 ΔL ≥ 0.06、
  最深階對卡片面 2.21:1、色相散佈 1° —— 四項全過。
* 文字一律用中性 ink,不用色階顏色上色;顏色只出現在「溫度條」這個標記上。
"""
from __future__ import annotations

# ---- 表面 ----
PLANE = "#0b1220"          # 頁面底
SURFACE = "#131d33"        # 卡片面
HAIRLINE = "rgba(255,255,255,0.10)"

# ---- 文字(全部實測 ≥ 4.5:1)----
INK = "#ffffff"            # 16.78:1
INK_SECONDARY = "#c3c2b7"  # 9.37:1
INK_MUTED = "#898781"      # 4.67:1

# ---- 溫度色階(單一橘色系,深 → 淺 = 低溫 → 高溫)----
TEMP_RAMP = [
    "#963300", "#b44109", "#cc5728", "#e46d40", "#fd8456", "#ffa888", "#ffcab6",
]

#: 色階固定對應的溫度範圍(°C)。
#: 固定而非逐日縮放,否則同一個顏色在不同日期代表不同溫度,無法互相比較。
TEMP_DOMAIN = (12.0, 38.0)


def temp_color(value: float | None) -> str:
    """把溫度對應到色階上的一階顏色。超出範圍就夾到兩端。"""
    if value is None:
        return "rgba(255,255,255,0.18)"
    lo, hi = TEMP_DOMAIN
    ratio = (float(value) - lo) / (hi - lo)
    ratio = min(max(ratio, 0.0), 1.0)
    index = round(ratio * (len(TEMP_RAMP) - 1))
    return TEMP_RAMP[index]


def temp_position(value: float | None) -> float:
    """把溫度換算成 0~100 的百分比位置,給溫度條用。"""
    if value is None:
        return 0.0
    lo, hi = TEMP_DOMAIN
    ratio = (float(value) - lo) / (hi - lo)
    return min(max(ratio, 0.0), 1.0) * 100


#: 天氣現象關鍵字 → emoji(由上往下比對,先命中先用)
WEATHER_ICONS = [
    ("雷", "⛈️"),
    ("雪", "🌨️"),
    ("雹", "🌨️"),
    ("霧", "🌫️"),
    ("陣雨", "🌦️"),
    ("短暫雨", "🌦️"),
    ("雨", "🌧️"),
    ("陰", "☁️"),
    ("多雲時晴", "🌤️"),
    ("晴時多雲", "🌤️"),
    ("多雲", "⛅"),
    ("晴", "☀️"),
]


def weather_icon(text: str | None) -> str:
    """從天氣現象文字挑一個代表 emoji。"""
    if not text:
        return "❓"
    for keyword, icon in WEATHER_ICONS:
        if keyword in text:
            return icon
    return "🌡️"
