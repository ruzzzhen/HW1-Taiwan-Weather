"""資料更新流程:抓取 → 解析 → 寫入 SQLite。

Streamlit 的「重新抓取最新資料」按鈕與命令列都呼叫同一個 refresh_data(),
避免兩邊邏輯不一致。

執行方式:
    python -m src.pipeline
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from src import db
from src.config import DATASET_ID, DB_PATH, MissingAPIKeyError, load_api_key
from src.fetch import WeatherAPIError, fetch_forecast, save_raw
from src.parse import ParseError, parse_forecast

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def refresh_data(
    db_path: PathLike = DB_PATH,
    dataset_id: str = DATASET_ID,
    keep_raw: bool = False,
    api_key: Optional[str] = None,
) -> dict:
    """抓一次最新預報並寫入資料庫。

    Args:
        db_path: SQLite 檔案路徑。
        dataset_id: CWA 資料集代碼。
        keep_raw: 是否把原始 JSON 存到 data/raw/(除錯用)。
        api_key: 測試時可直接注入;正式執行時留空,由 .env 讀取。

    Returns:
        dict:rows(寫入列數)、cities(縣市數)、dates(日期清單)、dataset。

    Raises:
        MissingAPIKeyError: .env 未設定 CWA_API_KEY。
        WeatherAPIError: 呼叫 API 失敗。
        ParseError: 回傳的 JSON 結構不符預期。
    """
    key = api_key or load_api_key()

    logger.info("開始抓取資料集 %s", dataset_id)  # 只記 dataset,不記授權碼
    payload = fetch_forecast(key, dataset_id=dataset_id)

    if keep_raw:
        path = save_raw(payload, dataset_id)
        logger.info("原始 JSON 已存:%s", path)

    rows = parse_forecast(payload)
    written = db.upsert_forecasts(rows, db_path)

    result = {
        "dataset": dataset_id,
        "rows": written,
        "cities": len({row["city"] for row in rows}),
        "dates": sorted({row["date"] for row in rows}),
    }
    logger.info(
        "寫入完成:%d 列 / %d 縣市 / %d 天", result["rows"], result["cities"], len(result["dates"])
    )
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = refresh_data(keep_raw=True)
    except MissingAPIKeyError as exc:
        print(f"\n[設定錯誤] {exc}\n")
        return 2
    except WeatherAPIError as exc:
        print(f"\n[API 錯誤] {exc}\n")
        return 3
    except ParseError as exc:
        print(f"\n[解析錯誤] {exc}\n")
        return 4

    print("\n=== 更新成功 ===")
    print(f"資料集    : {result['dataset']}")
    print(f"寫入列數  : {result['rows']}")
    print(f"縣市數    : {result['cities']}")
    print(f"日期範圍  : {result['dates'][0]} ~ {result['dates'][-1]}"
          f"(共 {len(result['dates'])} 天)")
    print(f"資料庫    : {DB_PATH}")
    print(f"總列數    : {db.count_rows()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
