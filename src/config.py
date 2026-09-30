"""專案共用設定:路徑、資料集代碼、API Key 讀取。

安全原則:本模組是唯一接觸 API Key 的地方,任何錯誤訊息都不會印出 Key 內容。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------- 路徑 ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "weather.db"
ENV_PATH = PROJECT_ROOT / ".env"

# ---------- CWA Open Data API ----------
API_BASE = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"

#: 正式使用的資料集:臺灣各縣市未來一週天氣預報
DATASET_ID = "F-D0047-091"

#: Step 2 探測用的候選資料集
CANDIDATE_DATASETS = {
    "F-C0032-001": "一般天氣預報-今明 36 小時天氣預報",
    "F-D0047-091": "鄉鎮天氣預報-臺灣各縣市未來一週天氣預報",
}

ENV_KEY_NAME = "CWA_API_KEY"


class MissingAPIKeyError(RuntimeError):
    """找不到 CWA_API_KEY 時拋出。訊息只說明如何設定,不含任何 Key 內容。"""


def load_api_key() -> str:
    """從 .env(或環境變數)讀取 CWA API 授權碼。

    Returns:
        授權碼字串。

    Raises:
        MissingAPIKeyError: .env 不存在、或 CWA_API_KEY 未設定/仍是範例值。
    """
    load_dotenv(ENV_PATH)
    key = (os.getenv(ENV_KEY_NAME) or "").strip()

    if not key:
        raise MissingAPIKeyError(
            f"找不到 {ENV_KEY_NAME}。請在專案根目錄建立 .env 檔,內容為:\n"
            f"    {ENV_KEY_NAME}=你的授權碼\n"
            "授權碼可在 https://opendata.cwa.gov.tw/user/authkey 免費申請。\n"
            "(可直接複製 .env.example 改名為 .env)"
        )

    if key == "your_key_here":
        raise MissingAPIKeyError(
            f".env 裡的 {ENV_KEY_NAME} 還是範例值 your_key_here,請換成你自己的授權碼。"
        )

    return key


def ensure_dirs() -> None:
    """確保 data/ 與 data/raw/ 存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
