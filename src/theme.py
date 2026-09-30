"""清爽淡藍風格的配色與樣式常數。

配色不是憑感覺挑的,而是照 dataviz 設計規範推導 + 驗證器實測:

* 溫度是「量值(magnitude)」→ 用 **sequential 單一色相** 色階,不用彩虹色。
  色相固定在 OKLCH H≈40.6°(橘),只改亮度;淺色底用正常錨點,
  由淺到深代表低溫到高溫。
* 已用 validate_palette.py --ordinal --mode light 驗證:亮度單調、
  相鄰 ΔL ≥ 0.06、最淺階對白卡片 2.26:1、色相散佈 0° —— 四項全過。
* 文字一律用中性 ink,不用色階顏色上色;顏色只出現在「溫度條」這個標記上。
* 三個文字色對白卡片與淡藍底都 ≥ 4.5:1(小字的 WCAG 門檻)。
"""
from __future__ import annotations

# ---- 表面 ----
PLANE = "#eef4fb"          # 頁面底(淡藍)
PLANE_TOP = "#e3eefb"      # 頁首漸層起點
SURFACE = "#ffffff"        # 卡片面
HAIRLINE = "rgba(11,11,11,0.10)"
SHADOW = "0 1px 2px rgba(11,11,11,0.04), 0 6px 18px rgba(31,74,135,0.07)"

# ---- 文字(實測:白卡片 / 淡藍底)----
INK = "#0b0b0b"            # 19.68:1 / 17.78:1
INK_SECONDARY = "#52514e"  #  7.94:1 /  7.17:1
INK_MUTED = "#6f6e6a"      #  5.10:1 /  4.61:1

# ---- 溫度色階(單一橘色系,淺 → 深 = 低溫 → 高溫)----
TEMP_RAMP = [
    "#ff8e64", "#ed7548", "#d66133", "#c04c1b", "#a83a00", "#8b2e00", "#6f2300",
]

#: 色階固定對應的溫度範圍(°C)。
#: 固定而非逐日縮放,否則同一個顏色在不同日期代表不同溫度,無法互相比較。
TEMP_DOMAIN = (12.0, 38.0)


def temp_color(value: float | None) -> str:
    """把溫度對應到色階上的一階顏色。超出範圍就夾到兩端。"""
    if value is None:
        return "rgba(11,11,11,0.12)"
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
