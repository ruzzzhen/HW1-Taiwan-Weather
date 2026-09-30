"""Taiwan Weather Forecast —— Streamlit 主程式。

資料流:CWA Open Data API → src/parse.py 解析 → SQLite → 本頁讀取顯示。
本頁只負責「顯示」與「觸發更新」,抓取與解析邏輯都在 src/ 底下,方便單獨測試。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import db
from src.config import DATASET_ID, MissingAPIKeyError
from src.fetch import WeatherAPIError
from src.parse import ParseError
from src.pipeline import refresh_data
from src.regions import OUTLYING_REGION, REGION_ORDER, REGION_TO_CITIES

st.set_page_config(
    page_title="Taiwan Weather Forecast",
    page_icon="🌤️",
    layout="wide",
)

WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# --------------------------------------------------------------------------
# 資料讀取(加快取,按下更新按鈕時會清掉)
# --------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def load_dates() -> list:
    return db.get_dates()


@st.cache_data(ttl=600, show_spinner=False)
def load_day(date: str) -> pd.DataFrame:
    return pd.DataFrame(db.get_by_date(date))


@st.cache_data(ttl=600, show_spinner=False)
def load_last_updated() -> str | None:
    return db.get_last_updated()


def clear_caches() -> None:
    load_dates.clear()
    load_day.clear()
    load_last_updated.clear()


# --------------------------------------------------------------------------
# 版面元件
# --------------------------------------------------------------------------
def format_date_label(date: str) -> str:
    """把 2026-09-30 顯示成 2026-09-30(週三)。"""
    try:
        stamp = pd.Timestamp(date)
        return f"{date}({WEEKDAYS[stamp.weekday()]})"
    except (ValueError, TypeError):
        return date


def do_refresh() -> None:
    """執行「重新抓取最新資料」,把各種失敗轉成看得懂的畫面訊息。"""
    with st.spinner("正在向中央氣象署抓取最新預報…"):
        try:
            result = refresh_data()
        except MissingAPIKeyError as exc:
            st.error("🔑 API Key 未設定")
            st.code(str(exc), language="text")
            return
        except WeatherAPIError as exc:
            st.error(f"🌐 無法取得氣象資料:{exc}")
            st.info("請確認網路連線與授權碼後,再按一次「重新抓取最新資料」。")
            return
        except ParseError as exc:
            st.error(f"🧩 資料格式解析失敗:{exc}")
            st.info("CWA 可能調整了資料格式,需要更新 src/parse.py。")
            return

    clear_caches()
    st.success(
        f"✅ 更新完成:{result['rows']} 列 / {result['cities']} 個縣市 / "
        f"{len(result['dates'])} 天({result['dates'][0]} ~ {result['dates'][-1]})"
    )


def aggregate_regions(day: pd.DataFrame) -> pd.DataFrame:
    """把縣市層級資料彙整成區域層級:最低溫取區內最小、最高溫取區內最大。"""
    grouped = day.groupby("region", dropna=False).agg(
        最低溫=("min_temp", "min"),
        最高溫=("max_temp", "max"),
        降雨機率=("pop", "max"),
        縣市數=("city", "count"),
    )
    # 天氣現象取區內出現次數最多的那個
    weather = (
        day.dropna(subset=["weather"])
        .groupby("region")["weather"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    grouped["天氣現象"] = weather
    cities = day.groupby("region")["city"].agg(lambda s: "、".join(sorted(s)))
    grouped["包含縣市"] = cities
    return grouped


def render_region_table(day: pd.DataFrame) -> None:
    table = aggregate_regions(day)

    main_rows = [r for r in REGION_ORDER if r in table.index]
    other_rows = [r for r in table.index if r not in REGION_ORDER]

    display_cols = ["最低溫", "最高溫", "天氣現象", "降雨機率", "包含縣市"]

    st.subheader("六大區域氣溫")
    if not main_rows:
        st.warning("這一天沒有六大區域的資料。")
    else:
        main = table.loc[main_rows, display_cols].copy()
        main.index.name = "區域"
        st.dataframe(
            main,
            width="stretch",
            column_config={
                "最低溫": st.column_config.NumberColumn("最低溫 (°C)", format="%.0f"),
                "最高溫": st.column_config.NumberColumn("最高溫 (°C)", format="%.0f"),
                "降雨機率": st.column_config.NumberColumn("降雨機率 (%)", format="%d"),
            },
        )

    if other_rows:
        label = "、".join(other_rows)
        with st.expander(f"🏝️ 其他地區({label})", expanded=False):
            st.dataframe(
                table.loc[other_rows, display_cols],
                width="stretch",
            )


def render_city_detail(day: pd.DataFrame) -> None:
    with st.expander("🔍 展開各縣市明細", expanded=False):
        detail = day[["region", "city", "min_temp", "max_temp", "weather", "pop"]].copy()
        detail.columns = ["區域", "縣市", "最低溫 (°C)", "最高溫 (°C)", "天氣現象", "降雨機率 (%)"]
        detail = detail.sort_values(["區域", "縣市"]).reset_index(drop=True)
        st.dataframe(detail, width="stretch", hide_index=True)


def render_metrics(day: pd.DataFrame) -> None:
    valid_max = day.dropna(subset=["max_temp"])
    valid_min = day.dropna(subset=["min_temp"])

    col1, col2, col3, col4 = st.columns(4)

    if not valid_max.empty:
        hottest = valid_max.loc[valid_max["max_temp"].idxmax()]
        col1.metric("全台最高溫", f"{hottest['max_temp']:.0f} °C", hottest["city"])
    else:
        col1.metric("全台最高溫", "—")

    if not valid_min.empty:
        coldest = valid_min.loc[valid_min["min_temp"].idxmin()]
        col2.metric("全台最低溫", f"{coldest['min_temp']:.0f} °C", coldest["city"])
    else:
        col2.metric("全台最低溫", "—")

    if not valid_max.empty:
        col3.metric("平均高溫", f"{valid_max['max_temp'].mean():.1f} °C")
    else:
        col3.metric("平均高溫", "—")

    pops = day.dropna(subset=["pop"])
    if not pops.empty:
        rainy = pops.loc[pops["pop"].idxmax()]
        col4.metric("最高降雨機率", f"{rainy['pop']:.0f} %", rainy["city"])
    else:
        col4.metric("最高降雨機率", "—")


def render_map(day: pd.DataFrame) -> None:
    st.subheader("氣溫分布地圖")

    geo = day.dropna(subset=["lat", "lon", "max_temp"]).copy()
    if geo.empty:
        st.info("這一天沒有可繪製地圖的座標或溫度資料。")
        return

    geo["標籤"] = geo.apply(
        lambda r: f"{r['city']} {r['min_temp']:.0f}–{r['max_temp']:.0f}°C", axis=1
    )

    try:
        import plotly.express as px

        fig = px.scatter_map(
            geo,
            lat="lat",
            lon="lon",
            color="max_temp",
            size=[14] * len(geo),
            size_max=18,
            hover_name="city",
            hover_data={
                "region": True,
                "min_temp": ":.0f",
                "max_temp": ":.0f",
                "weather": True,
                "pop": True,
                "lat": False,
                "lon": False,
            },
            color_continuous_scale="RdYlBu_r",
            labels={
                "max_temp": "最高溫 (°C)",
                "min_temp": "最低溫 (°C)",
                "region": "區域",
                "weather": "天氣",
                "pop": "降雨機率 (%)",
            },
            zoom=6.1,
            center={"lat": 23.7, "lon": 121.0},
            height=620,
            map_style="open-street-map",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("圓點顏色代表當日最高溫,滑過可看該縣市詳細預報。")
    except Exception as exc:  # 地圖畫不出來時退回 st.map,不讓整頁掛掉
        st.warning(f"互動地圖載入失敗({exc}),改用簡易地圖顯示位置。")
        st.map(geo.rename(columns={"lat": "latitude", "lon": "longitude"}))


def render_sidebar() -> None:
    with st.sidebar:
        st.header("資料操作")
        if st.button("🔄 重新抓取最新資料", width="stretch", type="primary"):
            do_refresh()

        last = load_last_updated()
        st.caption(f"資料最後更新:{last.replace('T', ' ') if last else '尚無資料'}")

        st.divider()
        st.subheader("資料來源")
        st.markdown(
            f"""
            - 中央氣象署開放資料平臺
            - 資料集:`{DATASET_ID}`
              (臺灣各縣市未來一週天氣預報)
            - 授權碼由 `.env` 讀取,不寫入程式碼
            """
        )

        st.divider()
        with st.expander("縣市 → 區域對應表"):
            for region in REGION_ORDER + [OUTLYING_REGION]:
                st.markdown(f"**{region}**:{'、'.join(REGION_TO_CITIES[region])}")


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main() -> None:
    st.title("🌤️ Taiwan Weather Forecast")
    st.caption("台灣六大區域一週天氣預報 · 資料來源:中央氣象署開放資料平臺")

    render_sidebar()

    if not db.table_exists():
        st.info(
            "📦 資料庫還沒建立。請點左側的「🔄 重新抓取最新資料」抓取第一份資料。\n\n"
            "也可以在終端機執行 `python -m src.pipeline`。"
        )
        return

    dates = load_dates()
    if not dates:
        st.warning(
            "⚠️ 資料庫是空的。請點左側的「🔄 重新抓取最新資料」。"
        )
        return

    selected = st.selectbox(
        "選擇日期",
        options=dates,
        format_func=format_date_label,
        help="只列出資料庫中實際有預報資料的日期",
    )

    day = load_day(selected)
    if day.empty:
        st.warning(f"⚠️ {selected} 沒有任何預報資料,請改選其他日期或重新抓取。")
        return

    st.markdown(f"### {format_date_label(selected)} 全台概況")
    render_metrics(day)
    st.divider()

    left, right = st.columns([1.15, 1])
    with left:
        render_region_table(day)
        render_city_detail(day)
    with right:
        render_map(day)


if __name__ == "__main__":
    main()
