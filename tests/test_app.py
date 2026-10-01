"""測試 app.py 裡不依賴 Streamlit runtime 的純邏輯。"""
from __future__ import annotations

from datetime import date

from app import default_date_index


def test_default_date_index_picks_today():
    """資料庫可能還留著昨天的預報,預設要選今天,不然開頁看到的是過期資料。"""
    today = date.today().isoformat()
    assert default_date_index(["2020-01-01", today, "2099-12-31"]) == 1


def test_default_date_index_falls_forward():
    """今天不在清單裡時,選第一個今天之後的日期。"""
    assert default_date_index(["2020-01-01", "2099-12-30", "2099-12-31"]) == 1


def test_default_date_index_handles_all_past_and_empty():
    assert default_date_index(["2020-01-01", "2020-01-02"]) == 0
    assert default_date_index([]) == 0
