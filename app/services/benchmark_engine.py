from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

COUNTRY_FILES = {
    "US": "archive/US_Trending.csv",
    "RU": "archive/RU_Trending.csv",
    "MX": "archive/MX_Trending.csv",
    "KR": "archive/KR_Trending.csv",
    "JP": "archive/JP_Trending.csv",
    "IN": "archive/IN_Trending.csv",
    "GB": "archive/GB_Trending.csv",
    "FR": "archive/FR_Trending.csv",
    "DE": "archive/DE_Trending.csv",
    "CA": "archive/CA_Trending.csv",
    "BR": "archive/BR_Trending.csv",
}

EMOTION_PATTERN = r"\b(shocking|insane|crazy|secret|truth|worst|best|finally|why|how|must|never|biggest|ultimate|exposed|genius|dangerous|surprising|viral|fails)\b"


def _parse_trending_date_series(s: pd.Series) -> pd.Series:
    parts = s.astype(str).str.split(".", expand=True)
    if parts.shape[1] == 3:
        year = 2000 + pd.to_numeric(parts[0], errors="coerce")
        day = pd.to_numeric(parts[1], errors="coerce")
        month = pd.to_numeric(parts[2], errors="coerce")
        return pd.to_datetime(dict(year=year, month=month, day=day), errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def _safe_div(numer: pd.Series, denom: pd.Series) -> pd.Series:
    denom_safe = denom.replace({0: np.nan})
    return (numer / denom_safe).fillna(0.0)


def _read_country_csv(country: str, path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["country"] = country
    return df


def load_dataset(csv_paths: Optional[List[str]] = None) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    if csv_paths:
        for path in csv_paths:
            p = Path(path)
            country = p.stem.split("_")[0].upper()
            frames.append(_read_country_csv(country, str(p)))
    else:
        for country, path in COUNTRY_FILES.items():
            if Path(path).exists():
                frames.append(_read_country_csv(country, path))
    if not frames:
        raise FileNotFoundError("No trending CSV files found.")
    return pd.concat(frames, ignore_index=True)


def enrich_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["title"] = df["title"].fillna("")
    df["description"] = df["description"].fillna("")
    df["likes"] = pd.to_numeric(df["likes"], errors="coerce").fillna(0)
    df["comments"] = pd.to_numeric(df["comments"], errors="coerce").fillna(0)
    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0)

    # Filter out low-view rows before computing anything else.
    # Low-view outliers distort engagement-rate benchmarks badly
    # (e.g. 20 views + 10 likes = 50% engagement, which is unrealistic).
    df = df[df["views"] >= 1000].copy()

    titles = df["title"].astype(str)
    df["trending_date_parsed"] = _parse_trending_date_series(df["trending_date"])
    df["publish_time_parsed"] = pd.to_datetime(df["publish_time"], errors="coerce", utc=True).dt.tz_convert(None)
    df["time_to_trend_hours"] = ((df["trending_date_parsed"] - df["publish_time_parsed"]).dt.total_seconds() / 3600.0).clip(lower=0)
    df["engagement_rate"] = _safe_div(df["likes"] + df["comments"], df["views"])

    df["title_length"] = titles.str.len()
    df["word_count"] = titles.str.count(r"\b\w+\b")
    df["has_number"] = titles.str.contains(r"\d", regex=True, na=False)
    df["has_question"] = titles.str.contains(r"\?", regex=True, na=False)
    df["has_exclamation"] = titles.str.contains(r"!", regex=False, na=False)
    alpha_count = titles.str.count(r"[A-Za-z]")
    upper_count = titles.str.count(r"[A-Z]")
    df["caps_ratio"] = np.where(alpha_count > 0, upper_count / alpha_count, 0.0)
    df["emotion_word_count"] = titles.str.lower().str.count(EMOTION_PATTERN)
    return df


def _summarise(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {
            "count": 0,
            "avg_views": 0,
            "avg_engagement_rate": 0,
            "avg_title_length": 0,
            "avg_word_count": 0,
            "avg_time_to_trend_hours": 0,
            "has_number_pct": 0,
            "has_question_pct": 0,
            "has_exclamation_pct": 0,
            "avg_caps_ratio": 0,
            "avg_emotion_word_count": 0,
        }
    return {
        "count": int(len(df)),
        "avg_views": round(float(df["views"].mean()), 2),
        "avg_engagement_rate": round(float(df["engagement_rate"].mean()), 4),
        "avg_title_length": round(float(df["title_length"].mean()), 2),
        "avg_word_count": round(float(df["word_count"].mean()), 2),
        "avg_time_to_trend_hours": round(float(df["time_to_trend_hours"].dropna().mean()), 2),
        "has_number_pct": round(float(df["has_number"].mean()), 4),
        "has_question_pct": round(float(df["has_question"].mean()), 4),
        "has_exclamation_pct": round(float(df["has_exclamation"].mean()), 4),
        "avg_caps_ratio": round(float(df["caps_ratio"].mean()), 4),
        "avg_emotion_word_count": round(float(df["emotion_word_count"].mean()), 2),
    }


def build_benchmarks(csv_paths: Optional[List[str]] = None, top_quantile: float = 0.9) -> Dict[str, Any]:
    raw = load_dataset(csv_paths)
    df = enrich_dataset(raw)

    threshold = float(df["engagement_rate"].quantile(top_quantile))
    top_df = df[df["engagement_rate"] >= threshold]

    benchmark = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_file_count": len(raw["country"].unique()),
        "row_count": int(len(df)),
        "global": _summarise(df),
        "title_patterns": {
            "top_quantile": top_quantile,
            "engagement_threshold": round(threshold, 4),
            "top_performers": _summarise(top_df),
        },
        "by_category": {str(int(cat)): _summarise(g) for cat, g in df.groupby("category_id")},
        "by_country": {country: _summarise(g) for country, g in df.groupby("country")},
    }
    return benchmark
