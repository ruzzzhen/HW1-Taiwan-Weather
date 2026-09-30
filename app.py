"""Taiwan Weather Forecast —— Streamlit 清爽淡藍卡片介面。

資料流:CWA Open Data API → src/parse.py 解析 → SQLite → 本頁讀取顯示。
本頁只負責「顯示」與「觸發更新」,抓取與解析邏輯都在 src/ 底下,方便單獨測試。

視覺設計依據見 src/theme.py:溫度是量值,所以用「單一橘色系 sequential 色階」,
不用彩虹色;淺色底由淺到深代表低溫到高溫,文字一律用中性 ink。
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
from src.theme import (
    HAIRLINE,
    PLANE_TOP,
    SHADOW,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    PLANE,
    SURFACE,
    TEMP_DOMAIN,
    TEMP_RAMP,
    temp_color,
    temp_position,
    weather_icon,
)

st.set_page_config(
    page_title="Taiwan Weather Forecast",
    page_icon="🌤️",
    layout="wide",
)

WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# --------------------------------------------------------------------------
# 樣式
# --------------------------------------------------------------------------
CSS = f"""
<style>
.stApp {{
    background:
        radial-gradient(1200px 520px at 10% -10%, #dbeafe 0%, rgba(219,234,254,0) 60%),
        radial-gradient(900px 460px at 95% 0%, #e0f2fe 0%, rgba(224,242,254,0) 55%),
        linear-gradient(180deg, {PLANE_TOP} 0%, {PLANE} 38%, #f7fafd 100%);
}}
/* Streamlit 固定在最上方的工具列(Deploy 按鈕、⋮ 選單、側邊欄收放鈕)是浮在內容之上的,
   預設 padding-top 要留夠空間才不會蓋住標題。順便把 Deploy 按鈕藏起來(本專案不需要)。*/
[data-testid="stAppHeader"] {{ background: transparent; box-shadow: none; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
[data-testid="stMainBlockContainer"], .block-container {{
    padding-top: 4.75rem; padding-bottom: 3rem; max-width: 1320px;
}}

/* ---- 頁首 ---- */
.wx-title {{
    font-size: 2rem; font-weight: 700; color: {INK};
    letter-spacing: -0.01em; margin: 0 0 .25rem 0;
}}
.wx-subtitle {{ color: {INK_MUTED}; font-size: .85rem; margin: 0; }}

/* ---- 頁首統計小標 ---- */
.wx-stats {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: 1rem 0 .25rem 0; }}
.wx-chip {{
    background: {SURFACE}; border: 1px solid {HAIRLINE}; border-radius: 999px;
    padding: .38rem .85rem; font-size: .82rem; color: {INK_SECONDARY};
    display: inline-flex; align-items: center; gap: .45rem; box-shadow: {SHADOW};
}}
.wx-chip b {{ color: {INK}; font-weight: 650; font-size: .95rem; }}
.wx-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}

/* ---- 區域卡片 ---- */
.wx-card {{
    background: {SURFACE}; border: 1px solid {HAIRLINE}; border-radius: 18px;
    padding: 1.15rem 1.2rem 1.1rem 1.2rem; height: 100%; box-shadow: {SHADOW};
}}
.wx-card-top {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: .6rem;
}}
.wx-region {{
    color: {INK_MUTED}; font-size: .8rem; font-weight: 600; letter-spacing: .09em;
}}
.wx-icon {{ font-size: 1.6rem; line-height: 1; }}
.wx-temp {{
    color: {INK}; font-size: 2.05rem; font-weight: 700; line-height: 1.1;
    letter-spacing: -0.02em;
}}
.wx-temp .wx-lo {{ color: {INK_SECONDARY}; font-weight: 550; font-size: 1.4rem; }}
.wx-temp .wx-sep {{ color: {INK_MUTED}; font-weight: 400; font-size: 1.15rem; margin: 0 .18rem; }}
.wx-bar {{
    position: relative; height: 7px; border-radius: 4px;
    background: rgba(11,11,11,0.07); margin: .75rem 0 .65rem 0; overflow: hidden;
}}
.wx-bar-fill {{ position: absolute; top: 0; height: 100%; border-radius: 4px; }}
.wx-meta {{
    display: flex; align-items: center; justify-content: space-between;
    font-size: .8rem; color: {INK_SECONDARY}; gap: .5rem;
}}
.wx-pop {{ color: {INK_MUTED}; white-space: nowrap; }}
.wx-scale-note {{ color: {INK_MUTED}; font-size: .74rem; margin: .55rem 0 .2rem 0; }}

/* ---- 區塊標題 ---- */
.wx-section {{
    color: {INK_SECONDARY}; font-size: .9rem; font-weight: 600;
    letter-spacing: .04em; margin: 1.6rem 0 .6rem 0;
}}
</style>
"""


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
def load_last_updated():
    return db.get_last_updated()


def clear_caches() -> None:
    load_dates.clear()
    load_day.clear()
    load_last_updated.clear()


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------
def format_date_label(date: str) -> str:
    """把 2026-09-30 顯示成 2026-09-30(週三)。"""
    try:
        stamp = pd.Timestamp(date)
        return f"{date}({WEEKDAYS[stamp.weekday()]})"
    except (ValueError, TypeError):
        return date


def fmt_temp(value) -> str:
    return "—" if pd.isna(value) else f"{float(value):.0f}°"


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
    weather = (
        day.dropna(subset=["weather"])
        .groupby("region")["weather"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    grouped["天氣現象"] = weather
    grouped["包含縣市"] = day.groupby("region")["city"].agg(
        lambda s: "、".join(sorted(s))
    )
    return grouped


# --------------------------------------------------------------------------
# 版面元件
# --------------------------------------------------------------------------
def render_header(dates: list) -> str:
    """頁首:標題 + 日期選擇器。回傳選中的日期。"""
    left, right = st.columns([2.6, 1])
    with left:
        st.markdown('<p class="wx-title">🌤️ Taiwan Weather Forecast</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="wx-subtitle">台灣四大區域一週天氣預報 · 資料來源:中央氣象署開放資料平臺</p>',
            unsafe_allow_html=True,
        )
    with right:
        selected = st.selectbox(
            "選擇日期",
            options=dates,
            format_func=format_date_label,
            help="只列出資料庫中實際有預報資料的日期",
        )
    return selected


def render_stats(day: pd.DataFrame) -> None:
    """頁首下方一排小標:全台最高溫 / 最低溫 / 平均高溫 / 最高降雨機率。"""
    chips = []

    hot = day.dropna(subset=["max_temp"])
    if not hot.empty:
        row = hot.loc[hot["max_temp"].idxmax()]
        chips.append(
            f'<span class="wx-chip"><span class="wx-dot" style="background:'
            f'{temp_color(row["max_temp"])}"></span>全台最高 <b>{row["max_temp"]:.0f}°C</b>'
            f' {row["city"]}</span>'
        )

    cold = day.dropna(subset=["min_temp"])
    if not cold.empty:
        row = cold.loc[cold["min_temp"].idxmin()]
        chips.append(
            f'<span class="wx-chip"><span class="wx-dot" style="background:'
            f'{temp_color(row["min_temp"])}"></span>全台最低 <b>{row["min_temp"]:.0f}°C</b>'
            f' {row["city"]}</span>'
        )

    if not hot.empty:
        chips.append(f'<span class="wx-chip">平均高溫 <b>{hot["max_temp"].mean():.1f}°C</b></span>')

    pops = day.dropna(subset=["pop"])
    if not pops.empty:
        row = pops.loc[pops["pop"].idxmax()]
        chips.append(
            f'<span class="wx-chip">最高降雨機率 <b>{row["pop"]:.0f}%</b> {row["city"]}</span>'
        )
    else:
        chips.append('<span class="wx-chip">降雨機率 <b>—</b> 氣象署尚未發布</span>')

    st.markdown(f'<div class="wx-stats">{"".join(chips)}</div>', unsafe_allow_html=True)


def card_html(region: str, row) -> str:
    """產生單一區域卡片的 HTML(壓成一行,避免 Streamlit 把它拆成段落)。"""
    if row is None:
        return (
            f'<div class="wx-card"><div class="wx-card-top">'
            f'<span class="wx-region">{region}</span><span class="wx-icon">❓</span></div>'
            f'<div class="wx-temp">—</div><div class="wx-bar"></div>'
            f'<div class="wx-meta"><span>這一天沒有資料</span></div></div>'
        )

    lo, hi = row["最低溫"], row["最高溫"]
    icon = weather_icon(row.get("天氣現象"))
    weather = row.get("天氣現象") or "—"
    pop = row.get("降雨機率")
    pop_text = "降雨 —" if pd.isna(pop) else f"降雨 {pop:.0f}%"

    # 溫度條:在固定的 12–38°C 刻度上,標出這一區的低溫到高溫區間
    if pd.isna(lo) or pd.isna(hi):
        bar = ""
    else:
        start, end = temp_position(lo), temp_position(hi)
        width = max(end - start, 2.5)
        bar = (
            f'<span class="wx-bar-fill" style="left:{start:.1f}%;width:{width:.1f}%;'
            f'background:linear-gradient(90deg,{temp_color(lo)},{temp_color(hi)})"></span>'
        )

    return (
        f'<div class="wx-card">'
        f'<div class="wx-card-top"><span class="wx-region">{region}</span>'
        f'<span class="wx-icon">{icon}</span></div>'
        f'<div class="wx-temp"><span class="wx-lo">{fmt_temp(lo)}</span>'
        f'<span class="wx-sep">/</span>{fmt_temp(hi)}</div>'
        f'<div class="wx-bar">{bar}</div>'
        f'<div class="wx-meta"><span>{weather}</span>'
        f'<span class="wx-pop">{pop_text}</span></div>'
        f'</div>'
    )


def render_region_cards(table: pd.DataFrame) -> None:
    """四大區域卡片,一排四張。"""
    cols = st.columns(len(REGION_ORDER), gap="medium")
    for col, region in zip(cols, REGION_ORDER):
        row = table.loc[region] if region in table.index else None
        with col:
            st.markdown(card_html(region, row), unsafe_allow_html=True)

    lo, hi = TEMP_DOMAIN
    st.markdown(
        f'<p class="wx-scale-note">溫度條對應固定刻度 {lo:.0f}–{hi:.0f}°C(不隨日期縮放,'
        f'所以不同日期的顏色可以直接互相比較);左端為該區最低溫、右端為最高溫。</p>',
        unsafe_allow_html=True,
    )


def render_map(day: pd.DataFrame) -> None:
    st.markdown('<p class="wx-section">各縣市氣溫分布</p>', unsafe_allow_html=True)

    geo = day.dropna(subset=["lat", "lon", "max_temp"]).copy()
    if geo.empty:
        st.info("這一天沒有可繪製地圖的座標或溫度資料。")
        return

    geo["降雨機率"] = geo["pop"].apply(lambda v: "—" if pd.isna(v) else f"{v:.0f}%")
    geo["天氣"] = geo["weather"].fillna("—")

    try:
        import plotly.express as px

        fig = px.scatter_map(
            geo,
            lat="lat",
            lon="lon",
            color="max_temp",
            hover_name="city",
            hover_data={
                "region": True,
                "min_temp": ":.0f",
                "max_temp": ":.0f",
                "天氣": True,
                "降雨機率": True,
                "lat": False,
                "lon": False,
            },
            color_continuous_scale=TEMP_RAMP,
            range_color=TEMP_DOMAIN,
            labels={
                "max_temp": "最高溫 (°C)",
                "min_temp": "最低溫 (°C)",
                "region": "區域",
            },
            zoom=6.15,
            center={"lat": 23.75, "lon": 120.95},
            height=540,
            map_style="carto-voyager",
        )
        fig.update_traces(marker={"size": 16, "opacity": 1.0})

        # scattermap 的 marker 不支援 line(外框),所以在彩色點底下疊一層
        # 稍大的白點當作「底環」,彩色點放到有顏色的底圖上才不會糊掉。
        import plotly.graph_objects as go

        halo = go.Scattermap(
            lat=geo["lat"],
            lon=geo["lon"],
            mode="markers",
            marker={"size": 23, "color": "rgba(255,255,255,0.95)"},
            hoverinfo="skip",
            showlegend=False,
        )
        fig.add_trace(halo)
        fig.data = (fig.data[1], fig.data[0])  # 把白色底環排到彩色點下面
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=INK_SECONDARY, size=12),
            coloraxis_colorbar=dict(
                title=dict(text="最高溫<br>(°C)", font=dict(color=INK_MUTED, size=11)),
                tickfont=dict(color=INK_MUTED, size=11),
                outlinewidth=0,
                thickness=12,
                len=0.75,
                bgcolor="rgba(255,255,255,0.88)",
                x=0.99,
            ),
            hoverlabel=dict(bgcolor=SURFACE, font=dict(color=INK), bordercolor="rgba(11,11,11,0.15)"),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("圓點顏色代表當日最高溫(色階與上方溫度條相同),滑鼠移上去可看該縣市詳細預報。")
    except Exception as exc:  # 地圖畫不出來時退回 st.map,不讓整頁掛掉
        st.warning(f"互動地圖載入失敗({exc}),改用簡易地圖顯示位置。")
        st.map(geo.rename(columns={"lat": "latitude", "lon": "longitude"}))


def render_tables(day: pd.DataFrame, table: pd.DataFrame) -> None:
    """完整表格放在展開區:既是明細,也是色彩之外的第二種讀法。"""
    st.markdown('<p class="wx-section">完整資料</p>', unsafe_allow_html=True)

    display_cols = ["最低溫", "最高溫", "天氣現象", "降雨機率", "包含縣市"]
    column_config = {
        "最低溫": st.column_config.NumberColumn("最低溫 (°C)", format="%.0f"),
        "最高溫": st.column_config.NumberColumn("最高溫 (°C)", format="%.0f"),
        "降雨機率": st.column_config.NumberColumn("降雨機率 (%)", format="%d"),
    }

    main_rows = [r for r in REGION_ORDER if r in table.index]
    with st.expander("📋 四大區域彙整表", expanded=False):
        if main_rows:
            main = table.loc[main_rows, display_cols].copy()
            main.index.name = "區域"
            st.dataframe(main, width="stretch", column_config=column_config)
        else:
            st.warning("這一天沒有四大區域的資料。")

    with st.expander("🔍 各縣市明細(22 縣市)", expanded=False):
        detail = day[["region", "city", "min_temp", "max_temp", "weather", "pop"]].copy()
        detail.columns = ["區域", "縣市", "最低溫 (°C)", "最高溫 (°C)", "天氣現象", "降雨機率 (%)"]
        detail = detail.sort_values(["區域", "縣市"]).reset_index(drop=True)
        st.dataframe(detail, width="stretch", hide_index=True)

    other_rows = [r for r in table.index if r not in REGION_ORDER]
    if other_rows:
        with st.expander(f"🏝️ 其他地區({'、'.join(other_rows)})", expanded=False):
            st.dataframe(
                table.loc[other_rows, display_cols],
                width="stretch",
                column_config=column_config,
            )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<p class="wx-section" style="margin-top:0">資料操作</p>', unsafe_allow_html=True)
        if st.button("🔄 重新抓取最新資料", width="stretch", type="primary"):
            do_refresh()

        last = load_last_updated()
        st.caption(f"資料最後更新:{last.replace('T', ' ') if last else '尚無資料'}")

        st.divider()
        st.markdown('<p class="wx-section" style="margin-top:0">資料來源</p>', unsafe_allow_html=True)
        st.markdown(
            f"""
            - 中央氣象署開放資料平臺
            - 資料集:`{DATASET_ID}`
              (臺灣各縣市未來一週天氣預報)
            - 授權碼由 `.env` 讀取,不寫入程式碼
            """
        )

        st.divider()
        with st.expander("🎨 溫度色階說明"):
            swatches = "".join(
                f'<span style="flex:1;height:14px;background:{c}"></span>' for c in TEMP_RAMP
            )
            lo, hi = TEMP_DOMAIN
            st.markdown(
                f'<div style="display:flex;border-radius:4px;overflow:hidden;margin-bottom:.4rem">'
                f'{swatches}</div>'
                f'<p style="color:{INK_MUTED};font-size:.75rem;margin:0">'
                f'{lo:.0f}°C(淺)→ {hi:.0f}°C(深)。溫度是量值,所以用單一色相的漸層,'
                f'不用彩虹色;淺色底下越高的溫度越深,對比才夠。</p>',
                unsafe_allow_html=True,
            )

        with st.expander("🗺️ 縣市 → 區域對應表"):
            for region in REGION_ORDER + [OUTLYING_REGION]:
                st.markdown(f"**{region}**:{'、'.join(REGION_TO_CITIES[region])}")


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    render_sidebar()

    if not db.table_exists():
        st.markdown('<p class="wx-title">🌤️ Taiwan Weather Forecast</p>', unsafe_allow_html=True)
        st.info(
            "📦 資料庫還沒建立。請點左側的「🔄 重新抓取最新資料」抓取第一份資料。\n\n"
            "也可以在終端機執行 `python -m src.pipeline`。"
        )
        return

    dates = load_dates()
    if not dates:
        st.markdown('<p class="wx-title">🌤️ Taiwan Weather Forecast</p>', unsafe_allow_html=True)
        st.warning("⚠️ 資料庫是空的。請點左側的「🔄 重新抓取最新資料」。")
        return

    selected = render_header(dates)

    day = load_day(selected)
    if day.empty:
        st.warning(f"⚠️ {selected} 沒有任何預報資料,請改選其他日期或重新抓取。")
        return

    table = aggregate_regions(day)

    render_stats(day)
    st.markdown('<p class="wx-section">四大區域</p>', unsafe_allow_html=True)
    render_region_cards(table)
    render_map(day)
    render_tables(day, table)


if __name__ == "__main__":
    main()
