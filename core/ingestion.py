"""
core/ingestion.py
-----------------
Handles loading PNJ_Feedback.xlsx and PNJ_ABSA_Result.json,
detecting new feedback rows not yet processed, and saving
results back to JSON atomically.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file's parent-parent = project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = PROJECT_ROOT / "PNJ_Feedback.xlsx"
JSON_PATH = PROJECT_ROOT / "PNJ_ABSA_Result.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_xlsx() -> pd.DataFrame:
    """
    Load PNJ_Feedback.xlsx and return a clean DataFrame.

    Columns expected:
        Feedback ID | Ngày | Giờ | Nguồn | Kênh | Cửa hàng | Nội dung feedback

    Returns
    -------
    pd.DataFrame  – one row per feedback, dtypes normalised.
    """
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {XLSX_PATH}")

    df = pd.read_excel(XLSX_PATH, dtype=str, engine="openpyxl")

    # Normalise column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]

    required = {"Feedback ID", "Nội dung feedback"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"xlsx thiếu các cột: {missing}")

    # Drop completely empty rows
    df = df.dropna(subset=["Feedback ID", "Nội dung feedback"]).reset_index(drop=True)

    # Normalise Feedback ID
    df["Feedback ID"] = df["Feedback ID"].str.strip()

    return df


def load_json() -> list[dict[str, Any]]:
    """
    Load PNJ_ABSA_Result.json.

    Returns an empty list if the file does not exist yet.
    """
    if not JSON_PATH.exists():
        logger.warning("JSON file không tồn tại, sẽ tạo mới: %s", JSON_PATH)
        return []

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON phải là một array ở top-level.")

    return data


def detect_new_rows(df_xlsx: pd.DataFrame, json_data: list[dict]) -> pd.DataFrame:
    """
    Return rows in df_xlsx whose Feedback ID is NOT yet in json_data.

    Parameters
    ----------
    df_xlsx : pd.DataFrame   – full xlsx data
    json_data : list[dict]   – existing ABSA results

    Returns
    -------
    pd.DataFrame – subset of df_xlsx containing only new, unprocessed rows.
    """
    existing_ids: set[str] = {
        str(record.get("Feedback ID", "")).strip()
        for record in json_data
        if record.get("Feedback ID")
    }

    mask = ~df_xlsx["Feedback ID"].isin(existing_ids)
    new_df = df_xlsx[mask].copy().reset_index(drop=True)

    logger.info(
        "Phát hiện %d / %d feedback mới chưa xử lý.",
        len(new_df),
        len(df_xlsx),
    )
    return new_df


def save_json(data: list[dict[str, Any]]) -> None:
    """
    Write `data` to JSON_PATH atomically using a temp file + rename.

    This prevents data corruption if the process is killed mid-write.
    """
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=JSON_PATH.parent, prefix=".tmp_absa_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, JSON_PATH)  # atomic on POSIX
        logger.info("JSON đã lưu thành công: %s", JSON_PATH)
    except Exception:
        # Clean up temp file if something went wrong
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_json_as_dataframe() -> pd.DataFrame:
    """
    Convenience: load JSON and explode aspects into a flat DataFrame.

    Each row = one (feedback, aspect) pair.
    """
    data = load_json()
    if not data:
        return pd.DataFrame()

    rows = []
    for record in data:
        base = {
            "Feedback ID": record.get("Feedback ID", ""),
            "Ngày": record.get("Ngày", ""),
            "Giờ": record.get("Giờ", ""),
            "Nguồn": record.get("Nguồn", ""),
            "Kênh": record.get("Kênh", ""),
            "Cửa hàng": record.get("Cửa hàng", ""),
            "Nội dung feedback": record.get("Nội dung feedback", ""),
            "trending": record.get("trending", ""),
        }
        aspects = record.get("aspects", [])
        if aspects:
            for asp in aspects:
                row = base.copy()
                row["category"] = asp.get("category", "")
                row["term"] = asp.get("term", "")
                row["opinion"] = asp.get("opinion", "")
                row["sentiment"] = asp.get("sentiment", "")
                rows.append(row)
        else:
            # Record with no aspects – keep it so we don't lose metadata
            row = base.copy()
            row["category"] = ""
            row["term"] = ""
            row["opinion"] = ""
            row["sentiment"] = ""
            rows.append(row)

    df = pd.DataFrame(rows)

    # Parse date safely
    if "Ngày" in df.columns and not df["Ngày"].empty:
        df["date"] = pd.to_datetime(df["Ngày"], format="%d/%m/%Y", errors="coerce")

    return df
