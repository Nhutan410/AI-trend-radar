"""
core/llm_synthesis.py
---------------------
LLM-powered synthesis layer: takes structured Trend Engine output
and generates human-readable insights + actionable recommendations.

Uses the OpenAI provider configured in core/llm_provider.py.
"""

from __future__ import annotations

import logging

from . import llm_provider
from .trend_engine import TrendEngineOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthesis prompt
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM = """Bạn là chuyên gia phân tích trải nghiệm khách hàng (CX Analyst) cho PNJ - thương hiệu trang sức hàng đầu Việt Nam.

Nhiệm vụ: Tổng hợp dữ liệu phân tích feedback và đưa ra insight chiến lược.

Yêu cầu output:
- Viết bằng tiếng Việt, rõ ràng, chuyên nghiệp
- Có cấu trúc rõ ràng với headings
- Cụ thể, dựa trên số liệu thực tế
- Đề xuất hành động SMART (Specific, Measurable, Achievable, Relevant, Time-bound)"""

SYNTHESIS_USER_TEMPLATE = """Dữ liệu phân tích từ {total_feedbacks} feedback khách hàng PNJ (từ {date_start} đến {date_end}):

## Tổng quan sentiment
- Tích cực: {positive_ratio}% | Tiêu cực: {negative_ratio}% | Trung lập: {neutral_ratio}%
- NPS Score: {nps_proxy}
- Tín hiệu xu hướng phát hiện: {trending_count}

## Vấn đề hàng đầu theo danh mục
{top_complaints_text}

## Tín hiệu yếu (Weak Signals) phát hiện gần đây
{weak_signals_text}

## Xu hướng thị trường từ feedback
{trending_texts}

Dựa trên dữ liệu trên, hãy tạo báo cáo với 4 phần:

### 1. 🔍 PHÂN TÍCH VẤN ĐỀ CỐT LÕI
Tóm tắt 4-5 vấn đề quan trọng nhất mà khách hàng đang gặp phải. Mỗi vấn đề cần: mô tả rõ ràng + bằng chứng số liệu + mức độ nghiêm trọng.

### 2. 📡 XU HƯỚNG CẦN THEO DÕI
Xác định 3-4 tín hiệu xu hướng (kể cả tín hiệu yếu) đang nổi lên. Đánh giá tác động tiềm năng đến PNJ.

### 3. 💡 KHUYẾN NGHỊ HÀNH ĐỘNG ƯU TIÊN
Đề xuất 5-6 hành động cụ thể, sắp xếp theo mức độ ưu tiên (Impact vs Effort). Mỗi hành động gồm: mục tiêu → hành động cụ thể → KPI đo lường → thời gian triển khai.

### 4. ⚠️ RỦI RO NẾU KHÔNG HÀNH ĐỘNG
Dự báo hệ quả cụ thể nếu các vấn đề trên không được giải quyết trong 30 ngày tới."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_synthesis(engine_output: TrendEngineOutput) -> str:
    """
    Generate a full synthesis report from TrendEngineOutput.

    Parameters
    ----------
    engine_output : TrendEngineOutput

    Returns
    -------
    str – Markdown-formatted synthesis report
    """
    stats = engine_output.summary_stats

    # ── Format top complaints ─────────────────────────────────────────
    complaints_lines = []
    for cat, complaints in engine_output.top_complaints.items():
        if not complaints:
            continue
        complaints_lines.append(f"\n**{cat}:**")
        for c in complaints[:3]:
            complaints_lines.append(f"  - \"{c.get('opinion', '')}\" ({c.get('count', 1)} lần)")
    top_complaints_text = "\n".join(complaints_lines) or "Không có dữ liệu"

    # ── Format weak signals ───────────────────────────────────────────
    signal_lines = []
    for sig in engine_output.weak_signals[:6]:
        severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sig.severity, "⚪")
        signal_lines.append(
            f"{severity_emoji} [{sig.severity.upper()}] {sig.title}: {sig.description} "
            f"(bằng chứng: {sig.evidence_count} trường hợp)"
        )
    weak_signals_text = "\n".join(signal_lines) or "Không phát hiện tín hiệu bất thường"

    # ── Format trending texts ─────────────────────────────────────────
    trend_lines = []
    for t in engine_output.trending_texts[:5]:
        trend_lines.append(f"- {t.get('signal_text', '')}")
    trending_texts = "\n".join(trend_lines) or "Không có tín hiệu xu hướng"

    # ── Build prompt ──────────────────────────────────────────────────
    # Escape curly braces in user data to prevent str.format() misinterpretation
    def _esc(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    user_prompt = SYNTHESIS_USER_TEMPLATE.format(
        total_feedbacks=stats.get("total_feedbacks", 0),
        date_start=stats.get("date_range_start", "N/A"),
        date_end=stats.get("date_range_end", "N/A"),
        positive_ratio=stats.get("positive_ratio", 0),
        negative_ratio=stats.get("negative_ratio", 0),
        neutral_ratio=stats.get("neutral_ratio", 0),
        nps_proxy=stats.get("nps_proxy", 0),
        trending_count=stats.get("trending_signals_count", 0),
        top_complaints_text=_esc(top_complaints_text),
        weak_signals_text=_esc(weak_signals_text),
        trending_texts=_esc(trending_texts),
    )

    messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user",   "content": user_prompt},
    ]

    try:
        return llm_provider.call_llm(
            messages,
            temperature=0.3,
            max_tokens=2048,
            timeout=llm_provider.LLM_TIMEOUT * 2,  # synthesis takes longer
        )
    except Exception as e:
        logger.error("Synthesis error: %s", e)
        return f"❌ **Lỗi tạo báo cáo:** {e}"


def generate_weak_signal_reasons(signals: list) -> dict:
    """
    Generate a short LLM explanation for each weak signal.

    Returns
    -------
    dict[signal_id, str] – one-sentence reason per signal
    """
    if not signals:
        return {}

    lines = []
    for sig in signals:
        lines.append(
            f"- {sig.signal_id} | [{sig.severity.upper()}] {sig.title}: {sig.description} "
            f"(danh mục: {sig.category}, bằng chứng: {sig.evidence_count} trường hợp)"
        )
    signals_text = "\n".join(lines)

    prompt = (
        "Bạn là chuyên gia CX của PNJ. Dưới đây là các tín hiệu yếu phát hiện từ feedback khách hàng:\n\n"
        f"{signals_text}\n\n"
        "Với mỗi tín hiệu, hãy viết 1–2 câu giải thích ngắn gọn TẠI SAO đây là vấn đề đáng chú ý "
        "và tác động tiềm năng đến PNJ. Trả lời theo định dạng:\n"
        "<signal_id>: <giải thích>\n"
        "Ví dụ:\nSIG-001: Khách hàng liên tục phản ánh...\nSIG-002: Xu hướng này cho thấy..."
    )

    try:
        raw = llm_provider.call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=512,
            timeout=90,
        )
        result: dict = {}
        for line in raw.splitlines():
            line = line.strip()
            if ":" in line:
                sid, _, reason = line.partition(":")
                sid = sid.strip()
                if sid.startswith("SIG-"):
                    result[sid] = reason.strip()
        return result
    except Exception as e:
        logger.warning("generate_weak_signal_reasons error: %s", e)
        return {}


def generate_trend_signal_reasons(trending_texts: list[dict]) -> list[dict]:
    """
    Enrich each trending text dict with an LLM-generated reason.

    Parameters
    ----------
    trending_texts : list of dicts with 'signal_text', 'Ngày', 'Cửa hàng', etc.

    Returns
    -------
    Same list with 'llm_reason' key added to each dict.
    """
    if not trending_texts:
        return trending_texts

    lines = [f"{i + 1}. {t.get('signal_text', '')}" for i, t in enumerate(trending_texts)]
    texts = "\n".join(lines)

    prompt = (
        "Bạn là chuyên gia CX của PNJ. Dưới đây là các tín hiệu xu hướng từ feedback khách hàng:\n\n"
        f"{texts}\n\n"
        "Với mỗi tín hiệu, hãy viết 1-2 câu giải thích ngắn gọn tại sao đây là xu hướng đáng chú ý "
        "và tác động tiềm năng đến PNJ. Trả lời theo định dạng:\n"
        "1: <giải thích>\n"
        "2: <giải thích>\n"
        "..."
    )

    try:
        raw = llm_provider.call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=512,
            timeout=90,
        )
        reasons: dict[int, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if line and ":" in line:
                num, _, reason = line.partition(":")
                num = num.strip()
                if num.isdigit():
                    reasons[int(num) - 1] = reason.strip()

        result = []
        for i, t in enumerate(trending_texts):
            enriched = t.copy()
            enriched["llm_reason"] = reasons.get(i, "")
            result.append(enriched)
        return result
    except Exception as e:
        logger.warning("generate_trend_signal_reasons error: %s", e)
        return trending_texts


def generate_quick_summary(engine_output: TrendEngineOutput) -> str:
    """
    Generate a quick 3-sentence summary of the current state.
    Faster than full synthesis, used in the Overview tab.
    """
    stats = engine_output.summary_stats

    quick_signals = [s for s in engine_output.weak_signals if s.severity == "high"]
    signal_text = (
        f"Phát hiện {len(quick_signals)} tín hiệu nghiêm trọng cần chú ý."
        if quick_signals
        else "Không có tín hiệu khẩn cấp."
    )

    top_neg_cat = ""
    max_neg = 0
    for cat, complaints in engine_output.top_complaints.items():
        total = sum(c.get("count", 1) for c in complaints)
        if total > max_neg:
            max_neg = total
            top_neg_cat = cat

    prompt = (
        f"Tóm tắt ngắn gọn (3 câu) tình hình feedback PNJ: "
        f"{stats['total_feedbacks']} feedback, "
        f"tích cực {stats['positive_ratio']}%, tiêu cực {stats['negative_ratio']}%, "
        f"NPS {stats['nps_proxy']}. "
        f"Danh mục nhiều khiếu nại nhất: {top_neg_cat}. "
        f"{signal_text} "
        f"Trả lời bằng tiếng Việt, súc tích."
    )

    try:
        return llm_provider.call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=256,
            timeout=60,
        )
    except Exception as e:
        logger.warning("Quick summary error: %s", e)
        return (
            f"📊 Tổng cộng **{stats['total_feedbacks']}** feedback được phân tích. "
            f"Sentiment: {stats['positive_ratio']}% tích cực, "
            f"{stats['negative_ratio']}% tiêu cực. "
            f"NPS: **{stats['nps_proxy']}**."
        )
