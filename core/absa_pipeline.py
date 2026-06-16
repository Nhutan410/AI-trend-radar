"""
core/absa_pipeline.py
---------------------
Aspect-Based Sentiment Analysis (ABSA) pipeline.

Uses the OpenAI provider configured in core/llm_provider.py.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from . import llm_provider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


# ---------------------------------------------------------------------------
# ABSA Prompt
# ---------------------------------------------------------------------------
ABSA_SYSTEM_PROMPT = """Bạn là hệ thống Aspect-Based Sentiment Analysis (ABSA) chuyên nghiệp cho dữ liệu feedback khách hàng PNJ bằng tiếng Việt.

Nhiệm vụ: Phân tích feedback và trích xuất TẤT CẢ các khía cạnh được đề cập.

Cho mỗi khía cạnh, xác định:
- category: PHẢI là một trong các giá trị sau:
  * "Sản phẩm" (chất lượng, mẫu mã, vật liệu, size, lỗi sản phẩm)
  * "Dịch vụ nhân viên" (tư vấn, thái độ, kiến thức, chính sách đổi trả, bảo hành)
  * "Giá cả" (giá niêm yết, so sánh giá, khuyến mãi, trả góp)
  * "Cửa hàng" (không gian, trang trí, vệ sinh, chờ đợi, vị trí)
  * "Giao hàng/Online" (app, website, giao hàng, đóng gói, hình ảnh online)
- term: sản phẩm/dịch vụ/người cụ thể được nhắc đến
- opinion: ý kiến chính xác của khách về term đó
- sentiment: "positive" | "negative" | "neutral"

Ngoài ra trích xuất:
- trending: đoạn text CHỈ khi feedback đề cập xu hướng thị trường hoặc hành vi người tiêu dùng đang nổi lên. Để chuỗi rỗng "" nếu không có.

Quy tắc quan trọng:
1. Chỉ trả về JSON thuần túy, KHÔNG có markdown, KHÔNG có giải thích
2. Phải trích xuất TẤT CẢ các khía cạnh, không bỏ sót
3. Nếu feedback không rõ ràng về sentiment, dùng "neutral"
4. term phải cụ thể (ví dụ: "nhân viên Quỳnh" thay vì chỉ "nhân viên")"""

ABSA_USER_TEMPLATE = """Feedback: {feedback_text}

Trả về JSON theo đúng schema này:
{{
  "aspects": [
    {{"category": "...", "term": "...", "opinion": "...", "sentiment": "..."}}
  ],
  "trending": ""
}}"""


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------

def _call_absa_model(prompt_messages: list[dict]) -> str:
    """Call active LLM backend and return raw text response."""
    return llm_provider.call_llm(
        prompt_messages,
        temperature=0.1,   # low temp for consistent JSON output
        max_tokens=1024,
    )


def _parse_absa_response(raw_text: str) -> dict[str, Any]:
    """
    Parse the LLM output into a validated ABSA dict.

    Handles cases where the model wraps output in ```json ... ``` fences.
    """
    # Strip markdown fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    parsed = json.loads(text)

    # Validate schema
    if "aspects" not in parsed:
        parsed["aspects"] = []
    if "trending" not in parsed:
        parsed["trending"] = ""

    # Ensure aspects is a list
    if not isinstance(parsed["aspects"], list):
        parsed["aspects"] = []

    # Validate each aspect
    valid_categories = {
        "Sản phẩm",
        "Dịch vụ nhân viên",
        "Giá cả",
        "Cửa hàng",
        "Giao hàng/Online",
    }
    clean_aspects = []
    for asp in parsed["aspects"]:
        if not isinstance(asp, dict):
            continue
        aspect = {
            "category": asp.get("category", "Sản phẩm"),
            "term": str(asp.get("term", "")).strip(),
            "opinion": str(asp.get("opinion", "")).strip(),
            "sentiment": asp.get("sentiment", "neutral"),
        }
        # Normalise category
        if aspect["category"] not in valid_categories:
            aspect["category"] = "Sản phẩm"
        # Normalise sentiment
        if aspect["sentiment"] not in {"positive", "negative", "neutral"}:
            aspect["sentiment"] = "neutral"
        clean_aspects.append(aspect)

    return {
        "aspects": clean_aspects,
        "trending": str(parsed.get("trending", "")).strip(),
    }


def extract_absa(feedback_text: str) -> dict[str, Any]:
    """
    Extract ABSA result for a single feedback text.

    Retries up to MAX_RETRIES times on transient errors.

    Parameters
    ----------
    feedback_text : str

    Returns
    -------
    dict with keys: aspects (list), trending (str)
    Raises on persistent failure.
    """
    messages = [
        {"role": "system", "content": ABSA_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ABSA_USER_TEMPLATE.format(feedback_text=feedback_text),
        },
    ]

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _call_absa_model(messages)
            result = _parse_absa_response(raw)
            return result
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning("JSON parse lỗi (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = e
            logger.error("Lỗi không xác định (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # Return empty result instead of crashing the whole batch
    logger.error("Bỏ qua feedback sau %d lần thử. Lỗi cuối: %s", MAX_RETRIES, last_error)
    return {"aspects": [], "trending": ""}


def process_batch(
    new_rows_df,
    json_data: list[dict],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """
    Process all new feedback rows through ABSA and merge into json_data.

    Parameters
    ----------
    new_rows_df : pd.DataFrame   – new rows from detect_new_rows()
    json_data   : list[dict]     – existing JSON records (modified in-place)
    progress_callback            – optional fn(current, total, feedback_id)

    Returns
    -------
    list[dict] – updated json_data (same object, extended)
    """
    import pandas as pd  # local import to avoid circular deps at module level

    total = len(new_rows_df)
    if total == 0:
        logger.info("Không có feedback mới cần xử lý.")
        return json_data

    logger.info("Bắt đầu xử lý %d feedback mới...", total)

    for idx, row in new_rows_df.iterrows():
        feedback_id = str(row.get("Feedback ID", "")).strip()
        feedback_text = str(row.get("Nội dung feedback", "")).strip()

        if progress_callback:
            progress_callback(idx + 1, total, feedback_id)

        if not feedback_text:
            logger.warning("Bỏ qua %s: nội dung feedback trống.", feedback_id)
            continue

        # Extract ABSA
        absa_result = extract_absa(feedback_text)

        # Build full record (keep all original xlsx fields)
        record: dict[str, Any] = {
            "Feedback ID": feedback_id,
            "Ngày": str(row.get("Ngày", "")).strip(),
            "Giờ": str(row.get("Giờ", "")).strip(),
            "Nguồn": str(row.get("Nguồn", "")).strip(),
            "Kênh": str(row.get("Kênh", "")).strip(),
            "Cửa hàng": str(row.get("Cửa hàng", "")).strip(),
            "Nội dung feedback": feedback_text,
            "aspects": absa_result["aspects"],
            "trending": absa_result["trending"],
        }

        json_data.append(record)
        logger.info("✓ %s – %d aspects extracted.", feedback_id, len(absa_result["aspects"]))

    return json_data


def check_llm_available() -> tuple[bool, str]:
    """
    Check if the configured LLM backend is available.

    Returns
    -------
    (is_available: bool, message: str)
    """
    return llm_provider.check_llm_available()
