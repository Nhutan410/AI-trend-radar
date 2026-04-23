"""
ui/sentiment_analysis.py
------------------------
Streamlit Tab 2: Phân tích Cảm xúc (Sentiment Analysis)

Shows:
- Time-series: daily sentiment ratio per category (line chart)
- Channel comparison (Online vs Offline)
- Source distribution bar chart
- Category × Store heatmap
- Drilldown: click category → see individual feedbacks
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from core.trend_engine import TrendEngineOutput

COLORS = {
    "positive": "#4CAF82",
    "negative": "#E05C6E",
    "neutral":  "#8B9CC8",
}

CATEGORY_LINE_COLORS = [
    "#D4AF37", "#7B5EA7", "#E05C6E", "#4CAF82", "#4BA3E3"
]


def render(engine_output: TrendEngineOutput, df_flat: pd.DataFrame) -> None:
    """Render the Sentiment Analysis tab."""

    st.markdown("### 📈 Phân tích Cảm xúc theo thời gian & chiều")

    # ── Time-series chart ─────────────────────────────────────────────────────
    st.markdown("#### 📉 Xu hướng Sentiment theo Danh mục (Net Score theo ngày)")

    rolling = engine_output.rolling_sentiment
    if not rolling.empty and not rolling.index.empty:
        fig_ts = go.Figure()
        for i, col in enumerate(rolling.columns):
            fig_ts.add_trace(
                go.Scatter(
                    x=rolling.index,
                    y=rolling[col].round(3),
                    name=col,
                    mode="lines",
                    line=dict(
                        color=CATEGORY_LINE_COLORS[i % len(CATEGORY_LINE_COLORS)],
                        width=2,
                    ),
                    hovertemplate=f"<b>{col}</b><br>Ngày: %{{x}}<br>Score: %{{y:.2f}}<extra></extra>",
                )
            )
        # Zero reference line
        fig_ts.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", line_width=1)

        fig_ts.update_layout(
            xaxis_title="Ngày",
            yaxis_title="Net Sentiment Score (7-day rolling)",
            yaxis=dict(range=[-1.05, 1.05]),
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
            margin=dict(t=10, b=60, l=50, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=380,
            font=dict(color="white"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("Chưa đủ dữ liệu để vẽ time-series.")

    st.markdown("---")

    # ── Channel comparison + Source distribution ────────────────────────────
    col_ch, col_src = st.columns([1, 1])

    with col_ch:
        st.markdown("#### 📡 So sánh kênh Online vs Offline")
        ch_df = engine_output.channel_sentiment
        if not ch_df.empty:
            sentiments = [c for c in ["positive", "negative", "neutral"] if c in ch_df.columns]
            labels_map = {"positive": "Tích cực", "negative": "Tiêu cực", "neutral": "Trung lập"}

            fig_ch = go.Figure()
            for sent in sentiments:
                fig_ch.add_trace(
                    go.Bar(
                        name=labels_map.get(sent, sent),
                        x=ch_df["Kênh"],
                        y=ch_df[sent],
                        marker_color=COLORS.get(sent, "#888"),
                        hovertemplate="<b>%{x}</b> – %{name}<br>%{y:,} feedback<extra></extra>",
                    )
                )
            fig_ch.update_layout(
                barmode="group",
                yaxis_title="Số feedback",
                margin=dict(t=10, b=30, l=40, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                height=300,
                font=dict(color="white"),
            )
            st.plotly_chart(fig_ch, use_container_width=True)

    with col_src:
        st.markdown("#### 📣 Phân bổ nguồn feedback")
        src_df = engine_output.source_distribution
        if not src_df.empty:
            fig_src = px.bar(
                src_df.head(10),
                x="count",
                y="Nguồn",
                orientation="h",
                color="sentiment_ratio",
                color_continuous_scale=["#E05C6E", "#8B9CC8", "#4CAF82"],
                labels={"count": "Số feedback", "sentiment_ratio": "% Tích cực"},
                text="count",
                hover_data={"sentiment_ratio": ":.1f"},
            )
            fig_src.update_traces(textposition="outside")
            fig_src.update_layout(
                margin=dict(t=10, b=30, l=10, r=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_colorbar=dict(title="% Tích cực", tickfont=dict(color="white"), title_font=dict(color="white")),
                height=300,
                font=dict(color="white"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_src, use_container_width=True)

    st.markdown("---")

    # ── Category x Store heatmap ──────────────────────────────────────────────
    st.markdown("#### 🏪 Heatmap – Sentiment trung bình theo Danh mục × Cửa hàng")

    if not df_flat.empty and "Cửa hàng" in df_flat.columns:
        pivot_store = _build_store_category_heatmap(df_flat)
        if not pivot_store.empty:
            fig_heat = go.Figure(
                go.Heatmap(
                    z=pivot_store.values,
                    x=pivot_store.columns.tolist(),
                    y=pivot_store.index.tolist(),
                    colorscale=[
                        [0.0, "#E05C6E"],
                        [0.5, "#1a1a2e"],
                        [1.0, "#4CAF82"],
                    ],
                    zmid=0,
                    zmin=-1,
                    zmax=1,
                    hovertemplate="<b>%{y}</b><br>%{x}<br>Score: %{z:.2f}<extra></extra>",
                    showscale=True,
                    colorbar=dict(
                        title="Net Score",
                        tickvals=[-1, 0, 1],
                        ticktext=["Tiêu cực", "Trung lập", "Tích cực"],
                        tickfont=dict(color="white"),
                        title_font=dict(color="white"),
                    ),
                )
            )
            fig_heat.update_layout(
                xaxis=dict(tickangle=-20, tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
                margin=dict(t=10, b=80, l=160, r=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=max(380, len(pivot_store) * 22),
                font=dict(color="white"),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown("---")

    # ── Feedback Drilldown ────────────────────────────────────────────────────
    st.markdown("#### 🔍 Tra cứu Feedback chi tiết")

    col_f1, col_f2, col_f3 = st.columns(3)

    all_categories = ["(Tất cả)"] + sorted(df_flat["category"].dropna().unique().tolist()) if not df_flat.empty else ["(Tất cả)"]
    all_sentiments = ["(Tất cả)", "positive", "negative", "neutral"]
    all_stores = ["(Tất cả)"] + sorted(df_flat["Cửa hàng"].dropna().unique().tolist()) if not df_flat.empty and "Cửa hàng" in df_flat.columns else ["(Tất cả)"]

    with col_f1:
        sel_cat = st.selectbox("Danh mục", all_categories, key="drilldown_cat")
    with col_f2:
        sel_sent = st.selectbox("Sentiment", all_sentiments, key="drilldown_sent",
                                format_func=lambda x: {"positive": "✅ Tích cực", "negative": "❌ Tiêu cực", "neutral": "⚪ Trung lập"}.get(x, x))
    with col_f3:
        sel_store = st.selectbox("Cửa hàng", all_stores, key="drilldown_store")

    filt = df_flat.copy() if not df_flat.empty else pd.DataFrame()
    if not filt.empty:
        if sel_cat != "(Tất cả)":
            filt = filt[filt["category"] == sel_cat]
        if sel_sent != "(Tất cả)":
            filt = filt[filt["sentiment"] == sel_sent]
        if sel_store != "(Tất cả)":
            filt = filt[filt["Cửa hàng"] == sel_store]

        st.caption(f"Hiển thị **{len(filt):,}** khía cạnh")

        display_cols = [c for c in ["Feedback ID", "Ngày", "Cửa hàng", "category", "term", "opinion", "sentiment"] if c in filt.columns]
        display_df = filt[display_cols].rename(columns={
            "category": "Danh mục", "term": "Đối tượng", "opinion": "Ý kiến", "sentiment": "Cảm xúc"
        })

        def _color_sent(val):
            c_map = {"positive": "color: #4CAF82", "negative": "color: #E05C6E", "neutral": "color: #8B9CC8"}
            return c_map.get(val, "")

        if "Cảm xúc" in display_df.columns:
            st.dataframe(
                display_df.style.map(_color_sent, subset=["Cảm xúc"]),
                use_container_width=True,
                height=320,
            )
        else:
            st.dataframe(display_df, use_container_width=True, height=320)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_store_category_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Build store × category net sentiment score pivot."""
    try:
        score_map = {"positive": 1, "negative": -1, "neutral": 0}
        df = df.copy()
        df["score"] = df["sentiment"].map(score_map).fillna(0)

        pivot = df.groupby(["Cửa hàng", "category"])["score"].mean().unstack(fill_value=0)

        # Show only top 20 stores by total feedback volume for readability
        store_counts = df.groupby("Cửa hàng").size().nlargest(20).index
        pivot = pivot.loc[pivot.index.intersection(store_counts)]

        return pivot.round(2)
    except Exception:
        return pd.DataFrame()
