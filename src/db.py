"""SQLite 存取層:建表、upsert 寫入、查詢。

為什麼用 upsert 而不是 INSERT OR REPLACE?
    INSERT OR REPLACE 會先 DELETE 再 INSERT,主鍵 id 會跳號、其他欄位會被清成預設值;
    ON CONFLICT ... DO UPDATE 只更新指定欄位,語意更精準,也保留原本的 id。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence, Union

from src.config import DB_PATH

PathLike = Union[str, Path]

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    region     TEXT    NOT NULL,          -- 六大區域(北部/中部/南部/東北部/東部/東南部/外島)
    city       TEXT    NOT NULL,          -- 縣市名稱(已正規化為「臺」)
    date       TEXT    NOT NULL,          -- YYYY-MM-DD
    min_temp   REAL,                      -- 當日最低溫(°C)
    max_temp   REAL,                      -- 當日最高溫(°C)
    weather    TEXT,                      -- 天氣現象(白天時段優先)
    pop        INTEGER,                   -- 降雨機率(%,當日最大值)
    lat        REAL,                      -- 緯度(給地圖用)
    lon        REAL,                      -- 經度
    updated_at TEXT    NOT NULL,          -- 本列最後寫入時間
    UNIQUE (city, date)                   -- 同一縣市同一天只會有一列 -> upsert 的依據
);

CREATE INDEX IF NOT EXISTS idx_forecast_date   ON forecast (date);
CREATE INDEX IF NOT EXISTS idx_forecast_region ON forecast (region);
"""

UPSERT_SQL = """
INSERT INTO forecast
    (region, city, date, min_temp, max_temp, weather, pop, lat, lon, updated_at)
VALUES
    (:region, :city, :date, :min_temp, :max_temp, :weather, :pop, :lat, :lon, :updated_at)
ON CONFLICT (city, date) DO UPDATE SET
    region     = excluded.region,
    min_temp   = excluded.min_temp,
    max_temp   = excluded.max_temp,
    weather    = excluded.weather,
    pop        = excluded.pop,
    lat        = excluded.lat,
    lon        = excluded.lon,
    updated_at = excluded.updated_at;
"""

ROW_FIELDS = (
    "region", "city", "date", "min_temp", "max_temp", "weather", "pop", "lat", "lon",
)


@contextmanager
def connect(db_path: PathLike = DB_PATH) -> Iterator[sqlite3.Connection]:
    """開啟連線(自動 commit / rollback / close),並讓查詢結果可用欄位名取值。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: PathLike = DB_PATH) -> None:
    """建立資料表與索引(可重複執行)。"""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_forecasts(rows: Iterable[dict], db_path: PathLike = DB_PATH) -> int:
    """寫入或更新預報資料,回傳處理的列數。

    重複執行同一批資料不會產生重複列(靠 UNIQUE(city, date) + ON CONFLICT DO UPDATE)。
    """
    stamp = datetime.now().isoformat(timespec="seconds")
    payload = []
    for row in rows:
        record = {field: row.get(field) for field in ROW_FIELDS}
        record["updated_at"] = stamp
        payload.append(record)

    if not payload:
        return 0

    init_db(db_path)
    with connect(db_path) as conn:
        conn.executemany(UPSERT_SQL, payload)
    return len(payload)


def _fetch(sql: str, params: Sequence = (), db_path: PathLike = DB_PATH) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def get_dates(db_path: PathLike = DB_PATH) -> list[str]:
    """回傳資料庫中實際有資料的日期(升冪)。"""
    rows = _fetch("SELECT DISTINCT date FROM forecast ORDER BY date", (), db_path)
    return [row["date"] for row in rows]


def get_by_date(date: str, db_path: PathLike = DB_PATH) -> list[dict]:
    """回傳某一天所有縣市的預報。"""
    return _fetch(
        "SELECT * FROM forecast WHERE date = ? ORDER BY region, city", (date,), db_path
    )


def get_all(db_path: PathLike = DB_PATH) -> list[dict]:
    """回傳全部預報資料。"""
    return _fetch("SELECT * FROM forecast ORDER BY date, region, city", (), db_path)


def count_rows(db_path: PathLike = DB_PATH) -> int:
    with connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM forecast").fetchone()[0])


def get_last_updated(db_path: PathLike = DB_PATH) -> Optional[str]:
    """回傳最後一次寫入時間;資料庫空的就回 None。"""
    with connect(db_path) as conn:
        value = conn.execute("SELECT MAX(updated_at) FROM forecast").fetchone()[0]
    return value


def table_exists(db_path: PathLike = DB_PATH) -> bool:
    """資料表是否已建立(Streamlit 首次啟動、DB 還不存在時要用)。"""
    if not Path(db_path).exists():
        return False
    with connect(db_path) as conn:
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='forecast'"
        ).fetchone()
    return found is not None
