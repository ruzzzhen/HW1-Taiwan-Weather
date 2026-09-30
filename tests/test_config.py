"""測試 API Key 讀取邏輯(不需要真實金鑰)。"""
from __future__ import annotations

import pytest

from src import config
from src.config import ENV_KEY_NAME, MissingAPIKeyError, load_api_key


@pytest.fixture()
def isolated_env(monkeypatch, tmp_path):
    """把 .env 路徑指到不存在的檔案,並清掉環境變數,避免讀到開發者本機的真實金鑰。"""
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "missing.env")
    monkeypatch.delenv(ENV_KEY_NAME, raising=False)


def test_missing_key_raises_with_instructions(isolated_env):
    with pytest.raises(MissingAPIKeyError) as exc:
        load_api_key()
    message = str(exc.value)
    assert ".env" in message
    assert "opendata.cwa.gov.tw" in message


def test_placeholder_key_is_rejected(isolated_env, monkeypatch):
    """.env 直接從 .env.example 複製、忘了換金鑰時要提醒。"""
    monkeypatch.setenv(ENV_KEY_NAME, "your_key_here")
    with pytest.raises(MissingAPIKeyError, match="your_key_here"):
        load_api_key()


def test_blank_key_is_rejected(isolated_env, monkeypatch):
    monkeypatch.setenv(ENV_KEY_NAME, "   ")
    with pytest.raises(MissingAPIKeyError):
        load_api_key()


def test_valid_key_is_returned_and_stripped(isolated_env, monkeypatch):
    monkeypatch.setenv(ENV_KEY_NAME, "  CWA-SOME-KEY  ")
    assert load_api_key() == "CWA-SOME-KEY"


def test_error_message_never_contains_the_key(isolated_env, monkeypatch):
    """錯誤訊息只能講怎麼設定,不能回顯任何金鑰內容。"""
    monkeypatch.setenv(ENV_KEY_NAME, "your_key_here")
    with pytest.raises(MissingAPIKeyError) as exc:
        load_api_key()
    assert "CWA-" not in str(exc.value)
