"""
ui/recommendations.py
---------------------
Streamlit Tab 4: Khuyến nghị & Hành động (AI Recommendations)

Shows:
- "Generate AI Report" button → calls LLM synthesis
- Rendered markdown report from Qwen
- Priority matrix scatter (Impact vs Effort)
- Export report as markdown file
"""

from __future__ import annotations

import datetime
import streamlit as st
import plotly.graph_objects as go

from core.trend_engine import TrendEngineOutput


def render(engine_output: TrendEngineOutput) -> None:
    """Render the Recommendations tab."""

    st.markdown("### 💡 Khuyến nghị & Hành động từ AI")

    # ── State: hold generated report ─────────────────────────────────────────
    if "ai_report" not in st.session_state:
        st.session_state.ai_report = None
    if "quick_summary" not in st.session_state:
        st.session_state.quick_summary = None

    # ── Ollama status check ───────────────────────────────────────────────────
    from core.absa_pipeline import check_ollama_available
    ollama_ok, ollama_msg = check_ollama_available()

    if ollama_ok:
        st.success(ollama_msg)
    else:
        st.error(ollama_msg)

    st.markdown("---")

    # ── Impact Summary ────────────────────────────────────────────────────────
    stats = engine_output.summary_stats
    signals = engine_output.weak_signals

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        high_signals = len([s for s in signals if s.severity == "high"])
        st.metric("🔴 Tín hiệu nghiêm trọng", high_signals)
    with col_b:
        medium_signals = len([s for s in signals if s.severity == "medium"])
        st.metric("🟡 Cần chú ý", medium_signals)
    with col_c:
        st.metric("📉 NPS Proxy hiện tại", f"{stats.get('nps_proxy', 0):+.1f}")

    st.markdown("---")

    # ── Priority Matrix ───────────────────────────────────────────────────────
    st.markdown("#### 🎯 Ma trận Ưu tiên – Tín hiệu phát hiện")

    if signals:
        IMPACT_MAP = {"high": 0.85, "medium": 0.55, "low": 0.25}
        EFFORT_MAP = {"Hệ thống": 0.8, "Thị trường": 0.6, "default": 0.4}
        COLOR_MAP  = {"high": "#E05C6E", "medium": "#D4AF37", "low": "#4CAF82"}

        fig_matrix = go.Figure()

        for sig in signals:
            impact = IMPACT_MAP.get(sig.severity, 0.3) + (sig.score * 0.1)
            effort = EFFORT_MAP.get(sig.category, 0.4)
            # Add slight jitter to avoid perfect overlap
            import random
            random.seed(hash(sig.signal_id))
            impact += random.uniform(-0.05, 0.05)
            effort += random.uniform(-0.05, 0.05)

            fig_matrix.add_trace(
                go.Scatter(
                    x=[effort],
                    y=[impact],
                    mode="markers+text",
                    name=sig.signal_id,
                    marker=dict(
                        size=max(16, sig.evidence_count * 3),
                        color=COLOR_MAP.get(sig.severity, "#888"),
                        opacity=0.85,
                        line=dict(width=1.5, color="white"),
                    ),
                    text=[sig.signal_id],
                    textposition="top center",
                    textfont=dict(size=9, color="white"),
                    hovertemplate=(
                        f"<b>{sig.title}</b><br>"
                        f"ID: {sig.signal_id}<br>"
                        f"Severity: {sig.severity}<br>"
                        f"Score: {sig.score:.2f}<br>"
                        f"Bằng chứng: {sig.evidence_count} trường hợp<br>"
                        f"Danh mục: {sig.category}"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                )
            )

        # Quadrant labels
        for qx, qy, text in [
            (0.25, 0.75, "Quick Wins<br><sub>Ưu tiên cao</sub>"),
            (0.75, 0.75, "Major Projects<br><sub>Lập kế hoạch</sub>"),
            (0.25, 0.25, "Fill-ins<br><sub>Khi có thời gian</sub>"),
            (0.75, 0.25, "Thankless Tasks<br><sub>Cân nhắc lại</sub>"),
        ]:
            fig_matrix.add_annotation(
                x=qx, y=qy, text=text,
                showarrow=False,
                font=dict(size=10, color="rgba(255,255,255,0.25)"),
                xref="x", yref="y",
            )

        fig_matrix.add_vline(x=0.5, line_dash="dash", line_color="rgba(255,255,255,0.2)")
        fig_matrix.add_hline(y=0.5, line_dash="dash", line_color="rgba(255,255,255,0.2)")

        fig_matrix.update_layout(
            xaxis=dict(title="Mức độ nỗ lực (Effort)", range=[0, 1], tickvals=[0.25, 0.75], ticktext=["Dễ", "Khó"]),
            yaxis=dict(title="Tác động (Impact)", range=[0, 1], tickvals=[0.25, 0.75], ticktext=["Thấp", "Cao"]),
            margin=dict(t=10, b=50, l=60, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,20,40,0.6)",
            height=380,
            font=dict(color="white"),
        )
        st.plotly_chart(fig_matrix, use_container_width=True)

    st.markdown("---")

    # ── AI Report Button ──────────────────────────────────────────────────────
    col_btn, col_clear = st.columns([1, 1])
    with col_btn:
        generate_btn = st.button(
            "🤖 Tạo Báo Cáo AI Đầy Đủ",
            type="primary",
            disabled=not ollama_ok,
            use_container_width=True,
            help="Gọi Qwen2.5:7b để tổng hợp insight và đề xuất hành động (~30-60s)",
        )
    with col_clear:
        if st.button("🗑️ Xoá báo cáo", use_container_width=True):
            st.session_state.ai_report = None
            st.rerun()

    if generate_btn:
        with st.spinner("⏳ Qwen đang tổng hợp báo cáo... (30-60 giây)"):
            from core.llm_synthesis import generate_synthesis
            report = generate_synthesis(engine_output)
            st.session_state.ai_report = report
            st.success("✅ Báo cáo đã được tạo!")

    # ── Render report ─────────────────────────────────────────────────────────
    if st.session_state.ai_report:
        st.markdown("---")
        st.markdown("#### 📄 Báo cáo AI – PNJ Feedback Intelligence")

        with st.container():
            st.markdown(
                f"""
                <div style="
                    border: 1px solid rgba(212,175,55,0.4);
                    border-radius: 12px;
                    padding: 24px;
                    background: rgba(255,255,255,0.03);
                    margin-top: 8px;
                ">
                """,
                unsafe_allow_html=True,
            )
            st.markdown(st.session_state.ai_report)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")

        # Export button
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        report_filename = f"PNJ_Insight_Report_{now}.md"
        report_content = f"# PNJ Feedback Intelligence Report\n*Tạo lúc: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{st.session_state.ai_report}"

        st.download_button(
            label="📥 Tải xuống Báo cáo (.md)",
            data=report_content.encode("utf-8"),
            file_name=report_filename,
            mime="text/markdown",
            use_container_width=True,
        )
