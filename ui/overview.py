"""
ui/overview.py
--------------
Streamlit Tab 1: Tổng quan (Overview Dashboard)

Shows:
- KPI metric cards (total feedbacks, NPS proxy, pos/neg ratio, trending signals)
- Sentiment distribution donut chart
- Category breakdown bar chart
- Feedback volume heatmap (hour x day-of-week)
- Top stores by feedback volume
- Quick LLM summary
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from core.trend_engine import TrendEngineOutput


# ---------------------------------------------------------------------------
# Colour palette (PNJ brand-inspired: gold + deep purple + dark bg)
# ---------------------------------------------------------------------------
COLORS = {
    "positive": "#4CAF82",   # emerald green
    "negative": "#E05C6E",   # rose red
    "neutral":  "#8B9CC8",   # muted blue
    "gold":     "#D4AF37",
    "purple":   "#7B5EA7",
    "bg_card":  "rgba(255,255,255,0.05)",
}

CATEGORY_COLORS = {
    "Sản phẩm":          "#7B5EA7",
    "Dịch vụ nhân viên": "#D4AF37",
    "Giá cả":            "#E05C6E",
    "Cửa hàng":          "#4CAF82",
    "Giao hàng/Online":  "#4BA3E3",
}


def render(engine_output: TrendEngineOutput, quick_summary: str | None = None) -> None:
    """Render the Overview tab."""

    stats = engine_output.summary_stats

    # ── KPI Cards ────────────────────────────────────────────────────────────
    st.markdown("### 📊 Tổng quan nhanh")
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "📝 Tổng Feedback",
            f"{stats['total_feedbacks']:,}",
            help="Tổng số feedback duy nhất trong dữ liệu",
        )
    with c2:
        nps = stats["nps_proxy"]
        st.metric(
            "🎯 NPS Proxy",
            f"{nps:+.1f}",
            delta=None,
            help="(Tích cực - Tiêu cực) / Tổng × 100. Thang điểm -100 → +100",
        )
    with c3:
        st.metric(
            "✅ Tích cực",
            f"{stats['positive_ratio']}%",
            delta=f"{stats['positive_count']:,} feedback",
        )
    with c4:
        st.metric(
            "❌ Tiêu cực",
            f"{stats['negative_ratio']}%",
            delta=f"-{stats['negative_count']:,} feedback",
            delta_color="inverse",
        )
    with c5:
        st.metric(
            "📡 Tín hiệu xu hướng",
            stats["trending_signals_count"],
            help="Số feedback chứa tín hiệu xu hướng thị trường",
        )

    st.markdown("---")

    # ── Row 1: Sentiment Donut + Category Bar ────────────────────────────────
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### 🎭 Phân bổ Sentiment tổng thể")
        fig_donut = go.Figure(
            go.Pie(
                labels=["Tích cực", "Tiêu cực", "Trung lập"],
                values=[
                    stats["positive_count"],
                    stats["negative_count"],
                    stats["neutral_count"],
                ],
                hole=0.55,
                marker=dict(
                    colors=[COLORS["positive"], COLORS["negative"], COLORS["neutral"]],
                    line=dict(color="#1a1a2e", width=2),
                ),
                textinfo="label+percent",
                textfont=dict(size=13),
                hovertemplate="<b>%{label}</b><br>Số lượng: %{value:,}<br>Tỷ lệ: %{percent}<extra></extra>",
            )
        )
        fig_donut.add_annotation(
            text=f"<b>{stats['total_feedbacks']:,}</b><br>Feedbacks",
            x=0.5, y=0.5,
            font=dict(size=14, color="white"),
            showarrow=False,
        )
        fig_donut.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            height=320,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        st.markdown("#### 🏷️ Phân bổ theo Danh mục")
        df_flat = _get_category_stats(engine_output)
        if not df_flat.empty:
            fig_cat = go.Figure()
            for sent, color in [("positive", COLORS["positive"]), ("negative", COLORS["negative"]), ("neutral", COLORS["neutral"])]:
                sent_df = df_flat[df_flat["sentiment"] == sent]
                fig_cat.add_trace(
                    go.Bar(
                        name={"positive": "Tích cực", "negative": "Tiêu cực", "neutral": "Trung lập"}[sent],
                        x=sent_df["category"],
                        y=sent_df["count"],
                        marker_color=color,
                        hovertemplate="<b>%{x}</b><br>%{y:,} aspects<extra></extra>",
                    )
                )
            fig_cat.update_layout(
                barmode="stack",
                xaxis=dict(tickangle=-20, tickfont=dict(size=10)),
                yaxis=dict(title="Số khía cạnh"),
                margin=dict(t=10, b=80, l=40, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
                height=320,
                font=dict(color="white"),
            )
            st.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("---")

    # ── Row 2: Weekly Heatmap + Top Stores ────────────────────────────────────
    col_hm, col_stores = st.columns([1, 1])

    with col_hm:
        st.markdown("#### 🗓️ Heatmap – Phân bổ feedback theo giờ & ngày")
        hm = engine_output.weekly_heatmap
        if not hm.empty:
            day_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
            cols_present = [c for c in day_labels if c in hm.columns]
            hm_data = hm[cols_present]
            fig_hm = go.Figure(
                go.Heatmap(
                    z=hm_data.values,
                    x=cols_present,
                    y=[f"{h:02d}:00" for h in hm_data.index],
                    colorscale="Viridis",
                    hovertemplate="<b>%{x} %{y}</b><br>%{z:,} feedbacks<extra></extra>",
                    showscale=True,
                )
            )
            fig_hm.update_layout(
                xaxis_title="",
                yaxis_title="Giờ trong ngày",
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=30, l=60, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                font=dict(color="white"),
            )
            st.plotly_chart(fig_hm, use_container_width=True)

    with col_stores:
        st.markdown("#### 🏪 Top 10 cửa hàng – NPS Proxy")
        store_df = engine_output.store_performance
        if not store_df.empty:
            top_stores = store_df.head(10).copy()
            top_stores["color"] = top_stores["nps_proxy"].apply(
                lambda x: COLORS["positive"] if x >= 0 else COLORS["negative"]
            )
            fig_stores = go.Figure(
                go.Bar(
                    x=top_stores["nps_proxy"],
                    y=top_stores["Cửa hàng"].str.replace("PNJ ", "", regex=False),
                    orientation="h",
                    marker=dict(color=top_stores["color"]),
                    text=top_stores["nps_proxy"].apply(lambda v: f"{v:+.0f}"),
                    textposition="auto",
                    hovertemplate="<b>%{y}</b><br>NPS: %{x:+.1f}<extra></extra>",
                )
            )
            fig_stores.update_layout(
                xaxis_title="NPS Proxy Score",
                yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
                margin=dict(t=10, b=30, l=10, r=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=320,
                font=dict(color="white"),
                shapes=[dict(type="line", x0=0, x1=0, y0=-0.5, y1=9.5,
                             line=dict(color="white", width=1, dash="dash"))],
            )
            st.plotly_chart(fig_stores, use_container_width=True)

    st.markdown("---")

    # ── Quick AI Summary ─────────────────────────────────────────────────────
    st.markdown("#### 🤖 Nhận xét nhanh từ AI")
    if quick_summary:
        st.info(quick_summary)
    else:
        st.caption("Nhấn **'Tạo Báo Cáo AI'** trong tab Khuyến nghị để xem nhận xét.")

    # ── Date range info ──────────────────────────────────────────────────────
    st.caption(
        f"📅 Dữ liệu từ **{stats['date_range_start']}** đến **{stats['date_range_end']}** · "
        f"🏪 {stats['unique_stores']} cửa hàng · "
        f"📣 {stats['unique_sources']} nguồn feedback"
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_category_stats(engine_output: TrendEngineOutput) -> pd.DataFrame:
    """Build category x sentiment count DataFrame from top_complaints + store data."""
    from core.ingestion import load_json, get_json_as_dataframe
    try:
        df = get_json_as_dataframe()
        if df.empty:
            return pd.DataFrame()
        cat_sent = (
            df[df["category"] != ""]
            .groupby(["category", "sentiment"])
            .size()
            .reset_index(name="count")
        )
        return cat_sent
    except Exception:
        return pd.DataFrame()
