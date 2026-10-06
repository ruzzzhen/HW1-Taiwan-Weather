"""測試 SQLite 寫入與查詢。

每個測試都用 tmp_path 建立獨立的臨時資料庫,不會影響 data/weather.db。
"""
from __future__ import annotations

import sqlite3

import pytest

from src import db
from src.parse import parse_forecast


def make_row(city="臺北市", date="2026-09-30", **overrides) -> dict:
    row = {
        "region": "北部",
        "city": city,
        "date": date,
        "min_temp": 24.0,
        "max_temp": 31.0,
        "weather": "晴時多雲",
        "pop": 40,
        "lat": 25.0478,
        "lon": 121.5319,
    }
    row.update(overrides)
    return row


# ---------- 建表 ----------
def test_table_does_not_exist_before_init(db_path):
    assert db.table_exists(db_path) is False


def test_init_db_creates_table(db_path):
    db.init_db(db_path)
    assert db.table_exists(db_path) is True


def test_init_db_is_idempotent(db_path):
    db.init_db(db_path)
    db.init_db(db_path)  # 再跑一次不該拋錯
    assert db.count_rows(db_path) == 0


# ---------- 寫入 ----------
def test_upsert_inserts_rows(db_path):
    assert db.upsert_forecasts([make_row()], db_path) == 1
    assert db.count_rows(db_path) == 1


def test_upsert_empty_list_returns_zero(db_path):
    assert db.upsert_forecasts([], db_path) == 0


def test_upsert_twice_does_not_duplicate(db_path):
    """同一批資料寫兩次,列數不能變多(UNIQUE(city, date) 生效)。"""
    rows = [make_row(), make_row(city="臺中市", region="中部")]
    db.upsert_forecasts(rows, db_path)
    db.upsert_forecasts(rows, db_path)
    assert db.count_rows(db_path) == 2


def test_upsert_updates_changed_values(db_path):
    """第二次寫入的值不同時,應該更新既有那一列。"""
    db.upsert_forecasts([make_row(max_temp=31.0)], db_path)
    db.upsert_forecasts([make_row(max_temp=35.5, weather="午後雷陣雨")], db_path)

    rows = db.get_by_date("2026-09-30", db_path)
    assert len(rows) == 1
    assert rows[0]["max_temp"] == 35.5
    assert rows[0]["weather"] == "午後雷陣雨"


def test_upsert_keeps_same_row_id(db_path):
    """這是選 ON CONFLICT DO UPDATE 而非 INSERT OR REPLACE 的原因:id 不會跳號。"""
    db.upsert_forecasts([make_row()], db_path)
    first_id = db.get_by_date("2026-09-30", db_path)[0]["id"]

    db.upsert_forecasts([make_row(max_temp=99.0)], db_path)
    assert db.get_by_date("2026-09-30", db_path)[0]["id"] == first_id


def test_same_city_different_dates_are_separate_rows(db_path):
    db.upsert_forecasts(
        [make_row(date="2026-09-30"), make_row(date="2026-10-01")], db_path
    )
    assert db.count_rows(db_path) == 2


def test_unique_constraint_is_enforced_at_sql_level(db_path):
    """直接繞過 upsert 硬塞重複資料,資料庫本身就該擋下來。"""
    db.upsert_forecasts([make_row()], db_path)
    with pytest.raises(sqlite3.IntegrityError):
        with db.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO forecast (region, city, date, updated_at) "
                "VALUES ('北部', '臺北市', '2026-09-30', 'now')"
            )


def test_none_values_are_stored_as_null(db_path):
    db.upsert_forecasts([make_row(min_temp=None, pop=None)], db_path)
    row = db.get_by_date("2026-09-30", db_path)[0]
    assert row["min_temp"] is None
    assert row["pop"] is None


# ---------- 查詢 ----------
def test_get_dates_returns_sorted_unique_dates(db_path):
    db.upsert_forecasts(
        [
            make_row(date="2026-10-02"),
            make_row(date="2026-09-30"),
            make_row(city="臺中市", date="2026-09-30"),
        ],
        db_path,
    )
    assert db.get_dates(db_path) == ["2026-09-30", "2026-10-02"]


def test_get_dates_on_empty_db(db_path):
    db.init_db(db_path)
    assert db.get_dates(db_path) == []


def test_get_by_date_filters_correctly(db_path):
    db.upsert_forecasts(
        [make_row(date="2026-09-30"), make_row(date="2026-10-01")], db_path
    )
    rows = db.get_by_date("2026-10-01", db_path)
    assert [r["date"] for r in rows] == ["2026-10-01"]


def test_get_by_date_unknown_date_returns_empty(db_path):
    db.upsert_forecasts([make_row()], db_path)
    assert db.get_by_date("1999-01-01", db_path) == []


def test_get_last_updated(db_path):
    db.init_db(db_path)
    assert db.get_last_updated(db_path) is None
    db.upsert_forecasts([make_row()], db_path)
    assert db.get_last_updated(db_path) is not None


def test_reads_on_missing_database_return_empty(db_path):
    """雲端首次部署時還沒有資料庫,查詢不該拋 no such table。"""
    assert db.get_last_updated(db_path) is None
    assert db.get_dates(db_path) == []
    assert db.get_all(db_path) == []
    assert db.count_rows(db_path) == 0


# ---------- 與解析器串接 ----------
def test_parsed_fixture_can_be_written_and_read_back(sample_payload, db_path):
    """解析 → 寫入 → 讀回,欄位要能對得上(不呼叫任何 API)。"""
    rows = parse_forecast(sample_payload)
    written = db.upsert_forecasts(rows, db_path)

    assert written == len(rows)
    assert db.count_rows(db_path) == len(rows)
    assert db.get_dates(db_path) == ["2026-09-30", "2026-10-01"]

    taipei = [
        r for r in db.get_by_date("2026-09-30", db_path) if r["city"] == "臺北市"
    ][0]
    assert taipei["region"] == "北部"
    assert taipei["min_temp"] == 24.0
    assert taipei["max_temp"] == 31.0
    assert taipei["weather"] == "晴時多雲"
    assert taipei["pop"] == 40
