"""
core/llm_synthesis.py
---------------------
LLM-powered synthesis layer: takes structured Trend Engine output
and generates human-readable insights + actionable recommendations
via Qwen2.5:7b through Ollama.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .absa_pipeline import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
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
- NPS Proxy Score: {nps_proxy}
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
    str – Markdown-formatted synthesis report from Qwen
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
    user_prompt = SYNTHESIS_USER_TEMPLATE.format(
        total_feedbacks=stats.get("total_feedbacks", 0),
        date_start=stats.get("date_range_start", "N/A"),
        date_end=stats.get("date_range_end", "N/A"),
        positive_ratio=stats.get("positive_ratio", 0),
        negative_ratio=stats.get("negative_ratio", 0),
        neutral_ratio=stats.get("neutral_ratio", 0),
        nps_proxy=stats.get("nps_proxy", 0),
        trending_count=stats.get("trending_signals_count", 0),
        top_complaints_text=top_complaints_text,
        weak_signals_text=weak_signals_text,
        trending_texts=trending_texts,
    )

    messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM},
        {"role": "user",   "content": user_prompt},
    ]

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.95,
                "num_predict": 2048,
            },
        }
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=OLLAMA_TIMEOUT * 2,  # synthesis takes longer
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    except requests.exceptions.ConnectionError:
        return (
            "❌ **Không kết nối được Ollama.** "
            "Hãy đảm bảo Ollama đang chạy: `ollama serve`"
        )
    except Exception as e:
        logger.error("Synthesis error: %s", e)
        return f"❌ **Lỗi tạo báo cáo:** {e}"


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
        f"NPS proxy {stats['nps_proxy']}. "
        f"Danh mục nhiều khiếu nại nhất: {top_neg_cat}. "
        f"{signal_text} "
        f"Trả lời bằng tiếng Việt, súc tích."
    )

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256},
        }
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        logger.warning("Quick summary error: %s", e)
        return (
            f"📊 Tổng cộng **{stats['total_feedbacks']}** feedback được phân tích. "
            f"Sentiment: {stats['positive_ratio']}% tích cực, "
            f"{stats['negative_ratio']}% tiêu cực. "
            f"NPS Proxy: **{stats['nps_proxy']}**."
        )
