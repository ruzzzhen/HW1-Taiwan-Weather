"""縣市 → 六大區域對應表。

CWA 的一週預報以「縣市」為單位回傳,但作業要求顯示北部/中部/南部/東北部/東部/東南部,
因此需要這張對應表。分區依中央氣象署天氣預報的區域劃分。
"""
from __future__ import annotations

#: 六大區域的顯示順序(離島單獨一區,不列入六大區域主表)
REGION_ORDER = ["北部", "中部", "南部", "東北部", "東部", "東南部"]
OUTLYING_REGION = "外島"
ALL_REGION_ORDER = REGION_ORDER + [OUTLYING_REGION]

#: 區域 → 該區縣市
REGION_TO_CITIES = {
    "北部": ["臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部": ["臺中市", "彰化縣", "南投縣", "雲林縣"],
    "南部": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"],
    "東北部": ["宜蘭縣"],
    "東部": ["花蓮縣"],
    "東南部": ["臺東縣"],
    OUTLYING_REGION: ["澎湖縣", "金門縣", "連江縣"],
}

#: 縣市 → 區域(由上表反轉而來)
CITY_TO_REGION = {
    city: region for region, cities in REGION_TO_CITIES.items() for city in cities
}


def normalize_city(name: str) -> str:
    """正規化縣市名稱。

    CWA 官方用「臺」,民間常寫「台」;兩者都要能查到同一區域。
    """
    return (name or "").strip().replace("台", "臺")


def city_to_region(name: str) -> str | None:
    """查縣市所屬區域;查不到回傳 None(由呼叫端決定要警告或略過)。"""
    return CITY_TO_REGION.get(normalize_city(name))
