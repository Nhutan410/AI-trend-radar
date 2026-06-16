"""
core/trend_engine.py
--------------------
Trend Detection Engine for PNJ feedback data.

Performs:
1. Time-Series Analysis     – rolling sentiment ratio, velocity, weekly patterns
2. Weak Signal Detection    – Z-score spike detection, emerging topics
3. Complaint Pattern        – top issues, recurrence rate, NPS
4. Store/Channel Analysis   – cross-store comparison, systemic issue detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes for structured output
# ---------------------------------------------------------------------------

@dataclass
class WeakSignal:
    """Represents an emerging trend or weak signal detected."""
    signal_id: str
    title: str
    description: str
    category: str
    severity: str        # "high" | "medium" | "low"
    score: float         # 0–1 severity score
    evidence_count: int
    sample_opinions: list[str] = field(default_factory=list)
    first_seen: str = ""
    trend_direction: str = "rising"  # "rising" | "stable" | "falling"


@dataclass
class TrendEngineOutput:
    """Full output from the Trend Detection Engine."""
    summary_stats: dict[str, Any]
    sentiment_timeseries: pd.DataFrame       # date x category → sentiment ratio
    rolling_sentiment: pd.DataFrame          # 7-day rolling per category
    sentiment_velocity: pd.DataFrame         # rate of change
    weak_signals: list[WeakSignal]
    top_complaints: dict[str, list[dict]]    # category → list of {opinion, count}
    store_performance: pd.DataFrame          # store x metric
    channel_sentiment: pd.DataFrame          # channel x sentiment
    source_distribution: pd.DataFrame        # source x count
    trending_texts: list[dict]               # extracted trending signals
    weekly_heatmap: pd.DataFrame             # hour x dayofweek → count


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class TrendEngine:
    """
    Orchestrates all trend detection analyses on the flat ABSA DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Flat DataFrame from ingestion.get_json_as_dataframe() with columns:
        Feedback ID, date, category, sentiment, opinion, term,
        Cửa hàng, Nguồn, Kênh, trending, Nội dung feedback
    """

    CATEGORIES = [
        "Sản phẩm",
        "Dịch vụ nhân viên",
        "Giá cả",
        "Cửa hàng",
        "Giao hàng/Online",
    ]

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self._preprocess()

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def _preprocess(self) -> None:
        df = self.df

        # Ensure date column
        if "date" not in df.columns:
            df["date"] = pd.to_datetime(df.get("Ngày", pd.NaT), format="%d/%m/%Y", errors="coerce")

        df = df.dropna(subset=["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # Sentiment numeric mapping
        df["sentiment_score"] = df["sentiment"].map(
            {"positive": 1, "neutral": 0, "negative": -1}
        ).fillna(0)

        # Binary positive/negative for ratio calc
        df["is_positive"] = (df["sentiment"] == "positive").astype(int)
        df["is_negative"] = (df["sentiment"] == "negative").astype(int)

        # Week / month for grouping
        df["week"] = df["date"].dt.to_period("W")
        df["month"] = df["date"].dt.to_period("M")
        df["hour"] = pd.to_numeric(df.get("Giờ", "00:00").str.split(":").str[0], errors="coerce").fillna(0).astype(int)
        df["dayofweek"] = df["date"].dt.dayofweek  # 0=Mon

        self.df = df

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    def _compute_summary_stats(self) -> dict[str, Any]:
        df = self.df
        # Unique feedback count (not inflated by aspect explosion)
        unique_feedbacks = df["Feedback ID"].nunique() if "Feedback ID" in df.columns else len(df)

        total_aspects = len(df[df["category"] != ""])

        positive_count = (df["sentiment"] == "positive").sum()
        negative_count = (df["sentiment"] == "negative").sum()
        neutral_count  = (df["sentiment"] == "neutral").sum()
        total_sentiments = positive_count + negative_count + neutral_count

        nps_proxy = round(
            (positive_count - negative_count) / total_sentiments * 100, 1
        ) if total_sentiments else 0

        date_min = df["date"].min()
        date_max = df["date"].max()

        # Trending feedbacks count
        trending_df = df[df.get("trending", pd.Series(dtype=str)).fillna("") != ""]
        trending_count = trending_df["Feedback ID"].nunique() if "Feedback ID" in trending_df.columns else 0

        return {
            "total_feedbacks": int(unique_feedbacks),
            "total_aspects": int(total_aspects),
            "positive_count": int(positive_count),
            "negative_count": int(negative_count),
            "neutral_count": int(neutral_count),
            "positive_ratio": round(positive_count / total_sentiments * 100, 1) if total_sentiments else 0,
            "negative_ratio": round(negative_count / total_sentiments * 100, 1) if total_sentiments else 0,
            "neutral_ratio": round(neutral_count / total_sentiments * 100, 1) if total_sentiments else 0,
            "nps_proxy": nps_proxy,
            "date_range_start": str(date_min.date()) if pd.notna(date_min) else "",
            "date_range_end": str(date_max.date()) if pd.notna(date_max) else "",
            "trending_signals_count": int(trending_count),
            "unique_stores": int(df["Cửa hàng"].nunique()) if "Cửa hàng" in df.columns else 0,
            "unique_sources": int(df["Nguồn"].nunique()) if "Nguồn" in df.columns else 0,
        }

    # ------------------------------------------------------------------
    # Time-series sentiment analysis
    # ------------------------------------------------------------------

    def _compute_sentiment_timeseries(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Returns: (daily_pivot, rolling_7d, velocity)
        """
        df = self.df

        # Daily sentiment ratio per category
        daily = (
            df.groupby(["date", "category"])
            .agg(
                pos=("is_positive", "sum"),
                neg=("is_negative", "sum"),
                total=("sentiment_score", "count"),
            )
            .reset_index()
        )
        daily["pos_ratio"] = daily["pos"] / daily["total"].clip(lower=1)
        daily["neg_ratio"] = daily["neg"] / daily["total"].clip(lower=1)
        daily["net_score"] = daily["pos_ratio"] - daily["neg_ratio"]

        # Pivot to date x category for net_score
        pivot = daily.pivot_table(
            index="date", columns="category", values="net_score", aggfunc="mean"
        )
        pivot = pivot.reindex(columns=self.CATEGORIES).ffill().fillna(0)

        # 7-day rolling average
        rolling = pivot.rolling(window=7, min_periods=1).mean()

        # Velocity = day-over-day change in rolling
        velocity = rolling.diff().fillna(0)

        return pivot, rolling, velocity

    # ------------------------------------------------------------------
    # Weak signal detection
    # ------------------------------------------------------------------

    def _detect_weak_signals(self) -> list[WeakSignal]:
        """
        Detect emerging issues using Z-score comparison:
        last 14 days vs previous 60 days baseline.
        """
        df = self.df
        signals: list[WeakSignal] = []

        if df.empty:
            return signals

        max_date = df["date"].max()
        window_end   = max_date
        window_start = max_date - pd.Timedelta(days=14)
        baseline_start = max_date - pd.Timedelta(days=74)
        baseline_end   = window_start - pd.Timedelta(days=1)

        recent_df   = df[(df["date"] >= window_start) & (df["date"] <= window_end)]
        baseline_df = df[(df["date"] >= baseline_start) & (df["date"] <= baseline_end)]

        signal_id = 0

        # ── Per-category negative spike detection ──────────────────────
        for cat in self.CATEGORIES:
            cat_recent   = recent_df[recent_df["category"] == cat]
            cat_baseline = baseline_df[baseline_df["category"] == cat]

            if len(cat_recent) < 3:
                continue

            recent_neg_rate   = cat_recent["is_negative"].mean() if len(cat_recent) > 0 else 0
            baseline_neg_rate = cat_baseline["is_negative"].mean() if len(cat_baseline) > 0 else 0

            # Z-score vs baseline
            if len(cat_baseline) >= 5:
                se = np.sqrt(
                    baseline_neg_rate * (1 - baseline_neg_rate) / max(len(cat_recent), 1)
                )
                z_score = (recent_neg_rate - baseline_neg_rate) / max(se, 1e-6)
            else:
                z_score = 0.0

            if z_score > 1.5 or (recent_neg_rate > 0.5 and len(cat_recent) >= 5):
                severity = "high" if z_score > 2.5 else "medium" if z_score > 1.5 else "low"
                score = min(1.0, max(0.0, z_score / 4.0))

                neg_opinions = cat_recent[cat_recent["is_negative"] == 1]["opinion"].dropna().tolist()
                sample = list(dict.fromkeys(neg_opinions))[:3]  # deduplicated top 3

                signal_id += 1
                signals.append(
                    WeakSignal(
                        signal_id=f"SIG-{signal_id:03d}",
                        title=f"Tăng đột biến khiếu nại: {cat}",
                        description=(
                            f"Tỷ lệ phản hồi tiêu cực trong '{cat}' tăng "
                            f"{recent_neg_rate*100:.0f}% (14 ngày gần nhất) "
                            f"so với {baseline_neg_rate*100:.0f}% (baseline 60 ngày). "
                            f"Z-score: {z_score:.2f}"
                        ),
                        category=cat,
                        severity=severity,
                        score=round(score, 3),
                        evidence_count=int(cat_recent["is_negative"].sum()),
                        sample_opinions=sample,
                        first_seen=str(cat_recent["date"].min().date()) if not cat_recent.empty else "",
                        trend_direction="rising",
                    )
                )

        # ── Emerging trending topics ────────────────────────────────────
        if "trending" in df.columns:
            trending_recent = recent_df[recent_df["trending"].fillna("").str.len() > 5]
            trending_baseline = baseline_df[baseline_df["trending"].fillna("").str.len() > 5]

            # Collect unique trending texts
            recent_trending_texts = trending_recent["trending"].dropna().unique().tolist()
            baseline_trending_ids = set(trending_baseline["Feedback ID"].tolist()) if "Feedback ID" in trending_baseline.columns else set()

            for t_text in recent_trending_texts[:5]:
                signal_id += 1
                signals.append(
                    WeakSignal(
                        signal_id=f"SIG-{signal_id:03d}",
                        title=f"Tín hiệu xu hướng mới",
                        description=t_text,
                        category="Thị trường",
                        severity="low",
                        score=0.4,
                        evidence_count=1,
                        sample_opinions=[t_text],
                        first_seen=str(max_date.date()),
                        trend_direction="rising",
                    )
                )

        # ── Cross-store recurring issues ───────────────────────────────
        if "Cửa hàng" in df.columns:
            # Issues appearing in >= 3 different stores in recent window
            neg_recent = recent_df[recent_df["is_negative"] == 1]
            store_issue = (
                neg_recent.groupby("opinion")["Cửa hàng"]
                .nunique()
                .reset_index(name="store_count")
            )
            systemic = store_issue[store_issue["store_count"] >= 3].sort_values("store_count", ascending=False)

            for _, row in systemic.head(3).iterrows():
                signal_id += 1
                signals.append(
                    WeakSignal(
                        signal_id=f"SIG-{signal_id:03d}",
                        title=f"Vấn đề hệ thống ({row['store_count']} cửa hàng)",
                        description=f"Khiếu nại xuất hiện tại {row['store_count']} cửa hàng khác nhau: \"{row['opinion']}\"",
                        category="Hệ thống",
                        severity="high" if row["store_count"] >= 5 else "medium",
                        score=min(1.0, row["store_count"] / 10),
                        evidence_count=int(row["store_count"]),
                        sample_opinions=[row["opinion"]],
                        trend_direction="stable",
                    )
                )

        # Sort by score descending
        signals.sort(key=lambda s: s.score, reverse=True)
        return signals

    # ------------------------------------------------------------------
    # Top complaints per category
    # ------------------------------------------------------------------

    def _compute_top_complaints(self) -> dict[str, list[dict]]:
        df = self.df
        result: dict[str, list[dict]] = {}

        neg_df = df[df["is_negative"] == 1]

        for cat in self.CATEGORIES:
            cat_neg = neg_df[neg_df["category"] == cat]
            if cat_neg.empty:
                result[cat] = []
                continue

            # Group by opinion similarity (simplified: exact match counts)
            top = (
                cat_neg.groupby("opinion")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(10)
            )
            result[cat] = top.to_dict("records")

        return result

    # ------------------------------------------------------------------
    # Store performance
    # ------------------------------------------------------------------

    def _compute_store_performance(self) -> pd.DataFrame:
        df = self.df
        if "Cửa hàng" not in df.columns or df.empty:
            return pd.DataFrame()

        store_stats = (
            df.groupby("Cửa hàng")
            .agg(
                total=("sentiment", "count"),
                positive=("is_positive", "sum"),
                negative=("is_negative", "sum"),
                feedback_count=("Feedback ID", "nunique"),
            )
            .reset_index()
        )
        store_stats["pos_ratio"] = (store_stats["positive"] / store_stats["total"] * 100).round(1)
        store_stats["neg_ratio"] = (store_stats["negative"] / store_stats["total"] * 100).round(1)
        store_stats["nps_proxy"] = (
            (store_stats["positive"] - store_stats["negative"])
            / store_stats["total"] * 100
        ).round(1)

        return store_stats.sort_values("nps_proxy", ascending=False)

    # ------------------------------------------------------------------
    # Channel & Source analysis
    # ------------------------------------------------------------------

    def _compute_channel_sentiment(self) -> pd.DataFrame:
        df = self.df
        if "Kênh" not in df.columns or df.empty:
            return pd.DataFrame()

        channel = (
            df.groupby(["Kênh", "sentiment"])
            .size()
            .reset_index(name="count")
        )
        pivot = channel.pivot_table(index="Kênh", columns="sentiment", values="count", fill_value=0)
        return pivot.reset_index()

    def _compute_source_distribution(self) -> pd.DataFrame:
        df = self.df
        if "Nguồn" not in df.columns or df.empty:
            return pd.DataFrame()

        src = (
            df.groupby("Nguồn")
            .agg(
                count=("Feedback ID", "nunique"),
                pos=("is_positive", "sum"),
                neg=("is_negative", "sum"),
            )
            .reset_index()
        )
        src["sentiment_ratio"] = (src["pos"] / (src["pos"] + src["neg"]).clip(lower=1) * 100).round(1)
        return src.sort_values("count", ascending=False)

    # ------------------------------------------------------------------
    # Weekly heatmap
    # ------------------------------------------------------------------

    def _compute_weekly_heatmap(self) -> pd.DataFrame:
        df = self.df

        # Unique feedbacks per hour x dayofweek
        unique_fb = df.drop_duplicates(subset=["Feedback ID"]) if "Feedback ID" in df.columns else df

        heatmap = (
            unique_fb.groupby(["hour", "dayofweek"])
            .size()
            .reset_index(name="count")
        )

        pivot = heatmap.pivot_table(index="hour", columns="dayofweek", values="count", fill_value=0)
        pivot.columns = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"][: len(pivot.columns)]
        return pivot

    # ------------------------------------------------------------------
    # Trending texts
    # ------------------------------------------------------------------

    def _collect_trending_texts(self) -> list[dict]:
        df = self.df
        if "trending" not in df.columns:
            return []

        t_df = df[df["trending"].fillna("").str.len() > 5].drop_duplicates(subset=["trending"])
        return t_df[["Feedback ID", "Ngày", "trending", "Cửa hàng"]].rename(
            columns={"trending": "signal_text"}
        ).to_dict("records")

    # ------------------------------------------------------------------
    # Public run method
    # ------------------------------------------------------------------

    def run(self) -> TrendEngineOutput:
        """Execute all analyses and return TrendEngineOutput."""
        logger.info("Trend Engine: bắt đầu phân tích %d records...", len(self.df))

        summary_stats = self._compute_summary_stats()
        pivot, rolling, velocity = self._compute_sentiment_timeseries()
        weak_signals = self._detect_weak_signals()
        top_complaints = self._compute_top_complaints()
        store_perf = self._compute_store_performance()
        channel_sent = self._compute_channel_sentiment()
        src_dist = self._compute_source_distribution()
        trending_texts = self._collect_trending_texts()
        weekly_hm = self._compute_weekly_heatmap()

        logger.info(
            "Trend Engine: hoàn thành. %d weak signals, %d trending texts.",
            len(weak_signals),
            len(trending_texts),
        )

        return TrendEngineOutput(
            summary_stats=summary_stats,
            sentiment_timeseries=pivot,
            rolling_sentiment=rolling,
            sentiment_velocity=velocity,
            weak_signals=weak_signals,
            top_complaints=top_complaints,
            store_performance=store_perf,
            channel_sentiment=channel_sent,
            source_distribution=src_dist,
            trending_texts=trending_texts,
            weekly_heatmap=weekly_hm,
        )
