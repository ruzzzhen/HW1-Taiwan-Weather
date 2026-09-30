"""pytest 共用 fixture。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_forecast.json"


@pytest.fixture()
def sample_payload() -> dict:
    """假的 F-D0047-091 回應(完全不呼叫真實 API)。"""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """每個測試一個乾淨的臨時資料庫,不會碰到 data/weather.db。"""
    return tmp_path / "test_weather.db"
