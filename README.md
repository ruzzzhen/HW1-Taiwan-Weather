# 🌤️ HW1-Taiwan-Weather — 台灣天氣預報網頁

用 **Python + 中央氣象署(CWA)開放資料 API + SQLite + Streamlit** 做的台灣四大區域一週天氣預報網頁。
程式呼叫 CWA `F-D0047-091`(各縣市未來一週預報),把 22 縣市歸類成北、中、南、東四區,
每日彙整最低溫、最高溫、天氣與降雨機率後存進 SQLite,網頁再從資料庫讀取呈現。

## 🔗 連結

- **Streamlit App**:<https://hw1-taiwan-weather.streamlit.app/>
  — 部署在 Streamlit Community Cloud 的線上版本,打開就能直接使用網頁(選日期、看區域卡片與互動地圖),不用自己安裝或設定 API Key。
- **GitHub Repository**:<https://github.com/ruzzzhen/HW1-Taiwan-Weather>
  — 專案的完整原始碼、測試與安裝說明。

## ✨ 功能

- 日期選擇器只列出今天以後有預報的日期;開頁時若資料不是今天的會自動更新
- 四大區域卡片、六都字卡、全寬互動地圖與完整表格
- SQLite 以 `UNIQUE(city, date)` + upsert 寫入,重複抓取不會產生重複資料
- API Key 只放在 `.env`(已被 `.gitignore` 排除),錯誤訊息會自動遮蔽金鑰
- 89 個 pytest 測試,全部不呼叫真實 API

## 🚀 執行方式

```bash
cp .env.example .env               # 填入 CWA 授權碼:CWA_API_KEY=CWA-XXXX...
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py               # 開啟 http://localhost:8501
pytest                             # 執行測試
```

授權碼可在 [中央氣象署開放資料平臺](https://opendata.cwa.gov.tw/user/authkey) 免費申請。

## 📄 資料來源

- 氣象資料:[中央氣象署開放資料平臺](https://opendata.cwa.gov.tw/)
- 本專案為課堂作業用途
