"""
app.py
------
PNJ AI Trend Radar V2 – Main Streamlit Application

Entry point: streamlit run app.py

Architecture:
    1. Sidebar   – filters + data update trigger
    2. Tab 1     – Tổng quan (Overview)
    3. Tab 2     – Phân tích Cảm xúc (Sentiment Analysis)
    4. Tab 3     – Xu hướng & Tín hiệu (Trend Detection)
    5. Tab 4     – Khuyến nghị & Hành động (Recommendations)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Ensure project root is on sys.path ───────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import ingestion, absa_pipeline, trend_engine
from ui import overview, sentiment_analysis, trend_detection, recommendations

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PNJ AI Trend Radar",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "PNJ AI Trend Radar V2 – Powered by Qwen2.5:7b & Streamlit",
    },
)

# ---------------------------------------------------------------------------
# Global CSS – dark gold theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Base ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0d0d1a 0%, #12122a 50%, #0d1320 100%);
        color: #e8e8f0;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12122a 0%, #0d1320 100%);
        border-right: 1px solid rgba(212, 175, 55, 0.2);
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(212,175,55,0.2);
        border-radius: 12px;
        padding: 12px 16px;
        transition: border-color 0.2s;
    }
    [data-testid="stMetric"]:hover {
        border-color: rgba(212,175,55,0.5);
    }
    [data-testid="stMetricLabel"] { color: rgba(255,255,255,0.65) !important; font-size: 13px !important; }
    [data-testid="stMetricValue"] { color: #D4AF37 !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"] svg { display: none; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: rgba(255,255,255,0.6);
        font-size: 14px;
        font-weight: 500;
        padding: 8px 16px;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #D4AF37, #b8962e) !important;
        color: #0d0d1a !important;
        font-weight: 700 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #D4AF37, #b8962e);
        color: #0d0d1a;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #e8c84a, #D4AF37);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(212,175,55,0.35);
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.06);
        color: #e8e8f0;
        border: 1px solid rgba(255,255,255,0.15);
    }

    /* ── Dataframe ── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ── Dividers ── */
    hr { border-color: rgba(212,175,55,0.15) !important; }

    /* ── Selectbox ── */
    [data-baseweb="select"] > div {
        background: rgba(255,255,255,0.06) !important;
        border-color: rgba(212,175,55,0.3) !important;
        border-radius: 8px !important;
    }

    /* ── Info / Success / Error boxes ── */
    .stAlert {
        border-radius: 8px;
    }

    /* ── Progress bar ── */
    [data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #D4AF37, #7B5EA7) !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(212,175,55,0.3); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(212,175,55,0.6); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def _init_session() -> None:
    defaults = {
        "df_flat":       None,   # flat ABSA DataFrame
        "engine_output": None,   # TrendEngineOutput
        "quick_summary": None,   # quick LLM summary string
        "ai_report":     None,   # full AI report string
        "last_loaded":   None,   # timestamp of last data load
        "processing":    False,  # flag: currently running ABSA
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Data loading & caching helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def _load_and_analyse(force_reload: bool = False) -> tuple[pd.DataFrame, trend_engine.TrendEngineOutput]:
    """Load JSON → flat DataFrame → run Trend Engine. Cached for 5 min."""
    df = ingestion.get_json_as_dataframe()
    if df.empty:
        return df, None  # type: ignore

    # Apply any active sidebar filters (passed via session state keys)
    df_filtered = _apply_filters(df)

    engine = trend_engine.TrendEngine(df_filtered)
    output = engine.run()
    return df_filtered, output


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply sidebar filter selections to the flat DataFrame."""
    f = df.copy()

    date_range = st.session_state.get("filter_date_range")
    if date_range and "date" in f.columns and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        f = f[(f["date"] >= start) & (f["date"] <= end)]

    stores = st.session_state.get("filter_stores")
    if stores and "Cửa hàng" in f.columns:
        f = f[f["Cửa hàng"].isin(stores)]

    channels = st.session_state.get("filter_channels")
    if channels and "Kênh" in f.columns:
        f = f[f["Kênh"].isin(channels)]

    sources = st.session_state.get("filter_sources")
    if sources and "Nguồn" in f.columns:
        f = f[f["Nguồn"].isin(sources)]

    return f


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    with st.sidebar:
        # Logo / Header
        st.markdown(
            """
            <div style="text-align:center; padding: 16px 0 8px 0;">
                <div style="font-size: 36px;">💎</div>
                <div style="font-size: 20px; font-weight: 700; color: #D4AF37;">
                    PNJ AI Trend Radar
                </div>
                <div style="font-size: 12px; color: rgba(255,255,255,0.5);">
                    Powered by Qwen2.5:7b
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Data Update Section ──────────────────────────────────────────────
        st.markdown("### 🔄 Cập nhật dữ liệu")

        # Check Ollama status
        ollama_ok, ollama_msg = absa_pipeline.check_ollama_available()
        if ollama_ok:
            st.success(ollama_msg, icon="✅")
        else:
            st.warning(ollama_msg, icon="⚠️")

        # Check new rows
        try:
            df_xlsx = ingestion.load_xlsx()
            json_data = ingestion.load_json()
            new_rows = ingestion.detect_new_rows(df_xlsx, json_data)
            n_new = len(new_rows)
        except FileNotFoundError as e:
            st.error(f"Lỗi file: {e}")
            n_new = 0
            new_rows = pd.DataFrame()
            json_data = []
            df_xlsx = pd.DataFrame()

        if n_new > 0:
            st.info(f"📋 Phát hiện **{n_new}** feedback mới trong xlsx")
        else:
            st.success("✅ Dữ liệu đã đồng bộ (không có feedback mới)")

        update_btn = st.button(
            f"⚡ Xử lý {n_new} feedback mới" if n_new > 0 else "✓ Không có gì mới",
            disabled=(n_new == 0 or not ollama_ok or st.session_state.processing),
            use_container_width=True,
        )

        if update_btn and n_new > 0 and ollama_ok:
            _run_absa_pipeline(new_rows, json_data)

        st.markdown("---")

        # ── Filters ─────────────────────────────────────────────────────────
        st.markdown("### 🔍 Bộ lọc")

        try:
            raw_df = ingestion.get_json_as_dataframe()
        except Exception:
            raw_df = pd.DataFrame()

        if not raw_df.empty:
            # Date range
            if "date" in raw_df.columns:
                min_date = raw_df["date"].min().date()
                max_date = raw_df["date"].max().date()
                date_sel = st.date_input(
                    "📅 Khoảng thời gian",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="filter_date_range",
                )

            # Store filter
            if "Cửa hàng" in raw_df.columns:
                all_stores = sorted(raw_df["Cửa hàng"].dropna().unique().tolist())
                st.multiselect(
                    "🏪 Cửa hàng",
                    options=all_stores,
                    default=[],
                    placeholder="Tất cả cửa hàng",
                    key="filter_stores",
                )

            # Channel filter
            if "Kênh" in raw_df.columns:
                all_channels = sorted(raw_df["Kênh"].dropna().unique().tolist())
                st.multiselect(
                    "📡 Kênh",
                    options=all_channels,
                    default=[],
                    placeholder="Tất cả kênh",
                    key="filter_channels",
                )

            # Source filter
            if "Nguồn" in raw_df.columns:
                all_sources = sorted(raw_df["Nguồn"].dropna().unique().tolist())
                st.multiselect(
                    "📣 Nguồn",
                    options=all_sources,
                    default=[],
                    placeholder="Tất cả nguồn",
                    key="filter_sources",
                )

            st.button(
                "🔄 Áp dụng bộ lọc",
                on_click=_clear_cache,
                use_container_width=True,
                key="apply_filters_btn",
            )
        else:
            st.caption("Chưa có dữ liệu để lọc.")

        st.markdown("---")

        # ── Stats ────────────────────────────────────────────────────────────
        if st.session_state.engine_output:
            stats = st.session_state.engine_output.summary_stats
            st.markdown("### 📈 Tóm tắt nhanh")
            st.caption(f"📝 {stats['total_feedbacks']:,} feedbacks")
            st.caption(f"✅ {stats['positive_ratio']}% tích cực")
            st.caption(f"❌ {stats['negative_ratio']}% tiêu cực")
            st.caption(f"🎯 NPS Proxy: {stats['nps_proxy']:+.1f}")


def _clear_cache():
    """Clear cached data so filters are reapplied."""
    _load_and_analyse.clear()
    st.session_state.engine_output = None
    st.session_state.df_flat = None


def _run_absa_pipeline(new_rows: pd.DataFrame, json_data: list) -> None:
    """Run ABSA on new rows with live progress display."""
    st.session_state.processing = True

    progress_bar = st.progress(0, text="Đang khởi động...")
    status_text  = st.empty()
    total = len(new_rows)

    def on_progress(current: int, total: int, feedback_id: str) -> None:
        pct = current / total
        progress_bar.progress(pct, text=f"Đang xử lý {current}/{total}: {feedback_id}")
        status_text.caption(f"⏳ {feedback_id} – phân tích ABSA...")

    try:
        updated = absa_pipeline.process_batch(new_rows, json_data, on_progress)
        ingestion.save_json(updated)
        _clear_cache()
        progress_bar.progress(1.0, text="✅ Hoàn thành!")
        status_text.success(f"Đã xử lý và lưu {total} feedback mới.")
        logger.info("ABSA pipeline hoàn thành: %d records mới.", total)
    except Exception as e:
        status_text.error(f"❌ Lỗi pipeline: {e}")
        logger.exception("ABSA pipeline error")
    finally:
        st.session_state.processing = False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    _init_session()
    render_sidebar()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; padding: 8px 0 16px 0;">
            <h1 style="
                font-size: 2.2rem;
                font-weight: 800;
                background: linear-gradient(135deg, #D4AF37, #7B5EA7, #4CAF82);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 4px;
            ">💎 PNJ AI Trend Radar V2</h1>
            <p style="color: rgba(255,255,255,0.55); font-size: 14px; margin: 0;">
                Phân tích Feedback Khách hàng · ABSA · Trend Detection · AI Insights
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("⏳ Đang tải và phân tích dữ liệu..."):
        try:
            df_flat, engine_out = _load_and_analyse()
            st.session_state.df_flat = df_flat
            st.session_state.engine_output = engine_out
        except Exception as e:
            st.error(f"❌ Lỗi tải dữ liệu: {e}")
            logger.exception("Data loading error")
            return

    if df_flat is None or df_flat.empty or engine_out is None:
        st.warning(
            "⚠️ Chưa có dữ liệu ABSA. "
            "Nhấn **'⚡ Xử lý feedback mới'** trong sidebar để bắt đầu phân tích."
        )
        return

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏠 Tổng quan",
        "📊 Phân tích Cảm xúc",
        "📡 Xu hướng & Tín hiệu",
        "💡 Khuyến nghị",
    ])

    with tab1:
        overview.render(engine_out, st.session_state.get("quick_summary"))

    with tab2:
        sentiment_analysis.render(engine_out, df_flat)

    with tab3:
        trend_detection.render(engine_out)

    with tab4:
        recommendations.render(engine_out)


if __name__ == "__main__":
    main()



# source .venv/bin/activate
# streamlit run app.py