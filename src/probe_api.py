"""Step 2:探測並比較 CWA 候選資料集,決定正式要用哪一個。

作業要求「先印出並分析回傳的 JSON 結構,再開始解析」,這支腳本就是那個步驟的紀錄。
它會分別呼叫兩個候選資料集,把原始 JSON 存到 data/raw/(已被 .gitignore 排除),
並印出結構樹與關鍵欄位,方便判斷哪個資料集才有「多天的日期 + 最低溫 + 最高溫」。

執行方式:
    python -m src.probe_api
"""
from __future__ import annotations

import json
from typing import Any

import requests

from src.config import (
    API_BASE,
    CANDIDATE_DATASETS,
    RAW_DIR,
    ensure_dirs,
    load_api_key,
)

MAX_DEPTH = 6
SAMPLE_LIST_ITEMS = 1  # list 只展開第一個元素,避免洗版


def describe(node: Any, depth: int = 0, label: str = "root") -> None:
    """遞迴印出 JSON 結構樹:dict 印 key、list 印長度並展開第一個元素。"""
    pad = "  " * depth
    if depth > MAX_DEPTH:
        print(f"{pad}{label}: ...(超過深度上限)")
        return

    if isinstance(node, dict):
        print(f"{pad}{label}: dict({len(node)} keys) -> {list(node.keys())}")
        for key, value in node.items():
            describe(value, depth + 1, key)
    elif isinstance(node, list):
        print(f"{pad}{label}: list(len={len(node)})")
        for item in node[:SAMPLE_LIST_ITEMS]:
            describe(item, depth + 1, f"{label}[0]")
    else:
        text = str(node)
        if len(text) > 60:
            text = text[:60] + "..."
        print(f"{pad}{label}: {type(node).__name__} = {text!r}")


def fetch_raw(dataset_id: str, api_key: str) -> dict:
    """呼叫單一資料集。Key 走 params 不進 log,錯誤訊息也不含 Key。"""
    url = f"{API_BASE}/{dataset_id}"
    resp = requests.get(
        url,
        params={"Authorization": api_key, "format": "JSON"},
        timeout=30,
    )
    print(f"[{dataset_id}] HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


def summarize_weekly(payload: dict) -> None:
    """針對 F-D0047-091 這種新版格式,額外印出縣市數、天氣要素名稱與時間區間。"""
    locations_blocks = payload.get("records", {}).get("Locations")
    if not locations_blocks:
        print("  (不是新版 Locations 格式,略過此摘要)")
        return

    block = locations_blocks[0]
    cities = block.get("Location", [])
    print(f"  縣市數:{len(cities)}")
    print(f"  縣市清單:{[c.get('LocationName') for c in cities]}")

    if not cities:
        return

    first = cities[0]
    print(f"  第一個縣市:{first.get('LocationName')} "
          f"(lat={first.get('Latitude')}, lon={first.get('Longitude')})")
    print("  天氣要素(WeatherElement):")
    for element in first.get("WeatherElement", []):
        times = element.get("Time", [])
        print(f"    - {element.get('ElementName')}:{len(times)} 個時間區間")
        if times:
            t0 = times[0]
            keys = [k for k in t0.keys() if k != "ElementValue"]
            print(f"        時間欄位:{keys}")
            print(f"        範例:{json.dumps(t0, ensure_ascii=False)[:200]}")


def summarize_36h(payload: dict) -> None:
    """針對 F-C0032-001 這種舊版格式,印出縣市數與 weatherElement。"""
    cities = payload.get("records", {}).get("location")
    if not cities:
        print("  (不是舊版 location 格式,略過此摘要)")
        return

    print(f"  縣市數:{len(cities)}")
    first = cities[0]
    print(f"  第一個縣市:{first.get('locationName')}")
    for element in first.get("weatherElement", []):
        times = element.get("time", [])
        print(f"    - {element.get('elementName')}:{len(times)} 個時間區間")
        if times:
            print(f"        範例:{json.dumps(times[0], ensure_ascii=False)[:200]}")


def main() -> None:
    ensure_dirs()
    api_key = load_api_key()

    for dataset_id, title in CANDIDATE_DATASETS.items():
        print("=" * 78)
        print(f"資料集 {dataset_id}:{title}")
        print("=" * 78)
        try:
            payload = fetch_raw(dataset_id, api_key)
        except requests.RequestException as exc:
            # 只印例外類型與訊息,requests 的訊息可能含 URL,故先移除 Key
            print(f"  呼叫失敗:{type(exc).__name__}: {str(exc).replace(api_key, '***')}")
            continue

        raw_path = RAW_DIR / f"{dataset_id}.json"
        raw_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  原始 JSON 已存:{raw_path.relative_to(raw_path.parents[2])}"
              f" ({raw_path.stat().st_size / 1024:.0f} KB)")
        print(f"  success 欄位:{payload.get('success')}")

        print("\n--- 重點摘要 ---")
        summarize_weekly(payload)
        summarize_36h(payload)

        print("\n--- 結構樹(深度上限 %d)---" % MAX_DEPTH)
        describe(payload)
        print()


if __name__ == "__main__":
    main()
