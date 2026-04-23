"""
ui/trend_detection.py
---------------------
Streamlit Tab 3: Xu hướng & Tín hiệu (Trend Detection)

Shows:
- Weak Signal Alert cards (color-coded by severity)
- Sentiment velocity chart (rate of change per category)
- Top complaints per category with frequency bars
- Cross-store systemic issues
- Extracted trending texts from feedback
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from core.trend_engine import TrendEngineOutput, WeakSignal

SEVERITY_CONFIG = {
    "high":   {"emoji": "🔴", "color": "#E05C6E", "label": "NGHIÊM TRỌNG",  "bg": "rgba(224,92,110,0.15)"},
    "medium": {"emoji": "🟡", "color": "#D4AF37", "label": "TRUNG BÌNH",    "bg": "rgba(212,175,55,0.15)"},
    "low":    {"emoji": "🟢", "color": "#4CAF82", "label": "THEO DÕI",      "bg": "rgba(76,175,130,0.15)"},
}

CATEGORY_COLORS = {
    "Sản phẩm":          "#7B5EA7",
    "Dịch vụ nhân viên": "#D4AF37",
    "Giá cả":            "#E05C6E",
    "Cửa hàng":          "#4CAF82",
    "Giao hàng/Online":  "#4BA3E3",
}


def render(engine_output: TrendEngineOutput) -> None:
    """Render the Trend Detection & Signals tab."""

    # ── Weak Signal Alerts ────────────────────────────────────────────────────
    st.markdown("### 📡 Tín hiệu Yếu & Cảnh báo Sớm")

    signals = engine_output.weak_signals
    if not signals:
        st.success("✅ Không phát hiện tín hiệu bất thường trong giai đoạn gần đây.")
    else:
        # Group by severity
        high    = [s for s in signals if s.severity == "high"]
        medium  = [s for s in signals if s.severity == "medium"]
        low     = [s for s in signals if s.severity == "low"]

        for group_name, group_signals in [("🔴 Nghiêm trọng", high), ("🟡 Cần chú ý", medium), ("🟢 Theo dõi", low)]:
            if not group_signals:
                continue
            st.markdown(f"**{group_name}** ({len(group_signals)} tín hiệu)")
            for sig in group_signals:
                _render_signal_card(sig)
            st.markdown("")

    st.markdown("---")

    # ── Sentiment Velocity ────────────────────────────────────────────────────
    st.markdown("### 📊 Tốc độ thay đổi Sentiment (Velocity)")
    st.caption("Giá trị dương = sentiment đang cải thiện · Giá trị âm = đang xấu đi")

    velocity = engine_output.sentiment_velocity
    if not velocity.empty and not velocity.index.empty:
        fig_vel = go.Figure()
        line_colors = ["#D4AF37", "#7B5EA7", "#E05C6E", "#4CAF82", "#4BA3E3"]
        for i, col in enumerate(velocity.columns):
            fig_vel.add_trace(
                go.Scatter(
                    x=velocity.index,
                    y=velocity[col].round(4),
                    name=col,
                    mode="lines",
                    line=dict(color=line_colors[i % len(line_colors)], width=1.5),
                    fill="tozeroy",
                    fillcolor=f"rgba{tuple(list(_hex_to_rgb(line_colors[i % len(line_colors)])) + [0.08])}",
                    hovertemplate=f"<b>{col}</b><br>%{{x}}<br>Velocity: %{{y:.4f}}<extra></extra>",
                )
            )
        fig_vel.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.4)", line_width=1)
        fig_vel.update_layout(
            xaxis_title="Ngày",
            yaxis_title="Velocity (Δ Net Score)",
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
            margin=dict(t=10, b=60, l=60, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=340,
            font=dict(color="white"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_vel, use_container_width=True)

    st.markdown("---")

    # ── Top Complaints per Category ───────────────────────────────────────────
    st.markdown("### 🔎 Top Khiếu nại theo Danh mục")

    complaints = engine_output.top_complaints
    tab_keys = [cat for cat, items in complaints.items() if items]

    if tab_keys:
        cat_tabs = st.tabs(tab_keys)
        for tab, cat in zip(cat_tabs, tab_keys):
            with tab:
                items = complaints[cat]
                df_c = pd.DataFrame(items).head(10)
                if not df_c.empty:
                    fig_c = go.Figure(
                        go.Bar(
                            x=df_c["count"],
                            y=df_c["opinion"],
                            orientation="h",
                            marker=dict(
                                color=df_c["count"],
                                colorscale=[[0, "#8B9CC8"], [1, "#E05C6E"]],
                                showscale=False,
                            ),
                            text=df_c["count"],
                            textposition="outside",
                            hovertemplate="<b>%{y}</b><br>%{x} lần xuất hiện<extra></extra>",
                        )
                    )
                    fig_c.update_layout(
                        xaxis_title="Số lần xuất hiện",
                        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
                        margin=dict(t=10, b=30, l=10, r=60),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=max(280, len(df_c) * 32),
                        font=dict(color="white"),
                    )
                    st.plotly_chart(fig_c, use_container_width=True)

    st.markdown("---")

    # ── Trending Texts ────────────────────────────────────────────────────────
    st.markdown("### 🌊 Tín hiệu xu hướng thị trường từ feedback")
    trending_texts = engine_output.trending_texts

    if not trending_texts:
        st.info("Không có tín hiệu xu hướng được trích xuất.")
    else:
        st.caption(f"Phát hiện **{len(trending_texts)}** tín hiệu xu hướng từ khách hàng")
        for item in trending_texts:
            with st.container():
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.markdown(f"💬 *{item.get('signal_text', '')}*")
                with cols[1]:
                    st.caption(f"📅 {item.get('Ngày', '')}")
                with cols[2]:
                    store = str(item.get("Cửa hàng", "")).replace("PNJ ", "")
                    st.caption(f"🏪 {store}")
                st.divider()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_signal_card(sig: WeakSignal) -> None:
    """Render a single signal as a styled card."""
    cfg = SEVERITY_CONFIG.get(sig.severity, SEVERITY_CONFIG["low"])
    emoji = cfg["emoji"]
    label = cfg["label"]

    with st.container():
        st.markdown(
            f"""
            <div style="
                border-left: 4px solid {cfg['color']};
                background: {cfg['bg']};
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 8px;
            ">
                <div style="font-weight:600; font-size:15px;">{emoji} {sig.title}
                    <span style="float:right; font-size:11px; color:{cfg['color']}; font-weight:bold;">
                        {label} · Score: {sig.score:.2f}
                    </span>
                </div>
                <div style="font-size:13px; margin-top:4px; color: rgba(255,255,255,0.85);">
                    {sig.description}
                </div>
                {"<div style='font-size:12px; margin-top:6px; color: rgba(255,255,255,0.6);'>Bằng chứng: " + " | ".join(f'"{o}"' for o in sig.sample_opinions[:2]) + "</div>" if sig.sample_opinions else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to (R, G, B)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
