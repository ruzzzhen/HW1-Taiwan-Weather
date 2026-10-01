"""測試 app.py 裡不依賴 Streamlit runtime 的純邏輯。

日期相關的函式都允許注入「今天」,所以不用改系統時間就能測。
"""
from __future__ import annotations

from datetime import date, timedelta

from app import default_date_index, is_data_stale, upcoming_dates

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


# ---------- 預設選今天 ----------
def test_default_date_index_picks_today():
    """資料庫可能還留著昨天的預報,預設要選今天,不然開頁看到的是過期資料。"""
    assert default_date_index([YESTERDAY, TODAY, TOMORROW]) == 1


def test_default_date_index_falls_forward():
    """今天不在清單裡時,選第一個今天之後的日期。"""
    assert default_date_index([YESTERDAY, TOMORROW]) == 1


def test_default_date_index_handles_all_past_and_empty():
    assert default_date_index(["2020-01-01", "2020-01-02"]) == 0
    assert default_date_index([]) == 0


# ---------- 過濾過期日期 ----------
def test_upcoming_dates_drops_past():
    assert upcoming_dates([YESTERDAY, TODAY, TOMORROW]) == [TODAY, TOMORROW]


def test_upcoming_dates_keeps_today():
    assert TODAY in upcoming_dates([YESTERDAY, TODAY])


def test_upcoming_dates_falls_back_when_all_past():
    """全部都是過去的日期時回傳原清單,不要變成空白頁。"""
    past = ["2020-01-01", "2020-01-02"]
    assert upcoming_dates(past) == past


def test_upcoming_dates_on_empty_list():
    assert upcoming_dates([]) == []


# ---------- 是否該重抓 ----------
def test_stale_when_no_data():
    assert is_data_stale([], None, today=TODAY) is True


def test_stale_when_today_missing():
    assert is_data_stale([YESTERDAY], f"{YESTERDAY}T08:00:00", today=TODAY) is True


def test_stale_when_last_update_was_yesterday():
    """有今天的預報,但是昨天抓的 —— 氣象署一天更新好幾次,還是要重抓。"""
    assert is_data_stale([TODAY, TOMORROW], f"{YESTERDAY}T23:00:00", today=TODAY) is True


def test_stale_when_last_update_missing():
    assert is_data_stale([TODAY], None, today=TODAY) is True


def test_not_stale_when_fetched_today():
    assert is_data_stale([TODAY, TOMORROW], f"{TODAY}T06:30:00", today=TODAY) is False
