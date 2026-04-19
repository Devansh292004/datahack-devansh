from __future__ import annotations

import re
from typing import Any, Dict, List


def title_features(title: str) -> Dict[str, Any]:
    t = title or ""
    alpha_chars = [c for c in t if c.isalpha()]
    caps_ratio = (sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)) if alpha_chars else 0.0
    return {
        "title_length": len(t),
        "word_count": len(re.findall(r"\b\w+\b", t)),
        "has_number": bool(re.search(r"\d", t)),
        "has_question": "?" in t,
        "has_exclamation": "!" in t,
        "caps_ratio": round(caps_ratio, 4),
    }


def engagement_rate(views_total: int, likes: int, comments: int) -> float:
    if views_total <= 0:
        return 0.0
    return (likes + comments) / views_total


def virality_score(video: Dict[str, Any], benchmarks: Dict[str, Any]) -> int:
    top = benchmarks["title_patterns"]["top_performers"]
    vf = title_features(video["title"])
    er = engagement_rate(video["views_total"], video["likes"], video["comments"])

    er_score = min(100, (er / max(top["avg_engagement_rate"], 0.0001)) * 100)

    title_len_target = top["avg_title_length"]
    title_delta = abs(vf["title_length"] - title_len_target)
    title_score = max(0, 100 - min(100, title_delta * 2))

    pattern_score = 0
    pattern_score += 35 if vf["has_number"] == (top["has_number_pct"] >= 0.3) else 15
    pattern_score += 25 if vf["has_question"] == (top["has_question_pct"] >= 0.15) else 10
    pattern_score += 20 if vf["has_exclamation"] == (top["has_exclamation_pct"] >= 0.15) else 10
    pattern_score += max(0, 20 - abs(vf["caps_ratio"] - top["avg_caps_ratio"]) * 100)
    pattern_score = min(100, pattern_score)

    category = benchmarks["by_category"].get(str(video["category_id"]))
    if category:
        cat_score = min(100, (er / max(category["avg_engagement_rate"], 0.0001)) * 100)
    else:
        cat_score = 50

    score = 0.4 * er_score + 0.25 * title_score + 0.2 * pattern_score + 0.15 * cat_score
    return int(round(max(1, min(100, score))))


def compare_to_benchmarks(video: Dict[str, Any], benchmarks: Dict[str, Any]) -> Dict[str, Any]:
    vf = title_features(video["title"])
    er = engagement_rate(video["views_total"], video["likes"], video["comments"])

    global_b = benchmarks["global"]
    top_b = benchmarks["title_patterns"]["top_performers"]
    category_b = benchmarks["by_category"].get(str(video["category_id"]))
    country_key = video.get("country", "GLOBAL")
    country_b = benchmarks["by_country"].get(country_key)

    strengths: List[str] = []
    weaknesses: List[str] = []
    themes: List[Dict[str, Any]] = []

    if er >= global_b["avg_engagement_rate"]:
        strengths.append(
            f"Measured engagement is above the global 2026 trending average ({round(er * 100, 1)}% vs {round(global_b['avg_engagement_rate'] * 100, 1)}%)."
        )
        themes.append({"label": "healthy engagement", "count": 1})
    else:
        weaknesses.append(
            f"Measured engagement is below the global 2026 trending average ({round(er * 100, 1)}% vs {round(global_b['avg_engagement_rate'] * 100, 1)}%)."
        )
        themes.append({"label": "engagement gap", "count": 1})

    if er < top_b["avg_engagement_rate"]:
        weaknesses.append(
            f"This video is below top-performing engagement benchmarks ({round(er * 100, 1)}% vs {round(top_b['avg_engagement_rate'] * 100, 1)}%)."
        )

    if vf["title_length"] < top_b["avg_title_length"] - 10:
        weaknesses.append(
            f"Title is shorter than the top-performer benchmark ({vf['title_length']} vs {round(top_b['avg_title_length'], 1)} characters)."
        )
        themes.append({"label": "short title", "count": 1})
    elif vf["title_length"] > top_b["avg_title_length"] + 15:
        weaknesses.append(
            f"Title is longer than the top-performer benchmark ({vf['title_length']} vs {round(top_b['avg_title_length'], 1)} characters)."
        )
        themes.append({"label": "long title", "count": 1})
    else:
        strengths.append(
            f"Title length is close to the high-performing benchmark ({vf['title_length']} vs {round(top_b['avg_title_length'], 1)})."
        )

    if not vf["has_number"] and top_b["has_number_pct"] >= 0.3:
        weaknesses.append(
            f"Your title lacks a numeric anchor, while {round(top_b['has_number_pct'] * 100, 1)}% of top-performing 2026 titles use one."
        )
        themes.append({"label": "missing number anchor", "count": 1})
    elif vf["has_number"]:
        strengths.append(
            f"Your title uses a numeric anchor, which matches a pattern seen in {round(top_b['has_number_pct'] * 100, 1)}% of top performers."
        )

    if category_b and er < category_b["avg_engagement_rate"]:
        weaknesses.append(
            f"Within category {video['category_id']}, measured engagement is below the category benchmark ({round(er * 100, 1)}% vs {round(category_b['avg_engagement_rate'] * 100, 1)}%)."
        )
        themes.append({"label": "category under-benchmark", "count": 1})
    elif category_b:
        strengths.append(
            f"Within category {video['category_id']}, measured engagement is above the category benchmark ({round(er * 100, 1)}% vs {round(category_b['avg_engagement_rate'] * 100, 1)}%)."
        )

    if country_b:
        if er < country_b["avg_engagement_rate"]:
            weaknesses.append(
                f"In {country_key}, measured engagement is below the country benchmark ({round(er * 100, 1)}% vs {round(country_b['avg_engagement_rate'] * 100, 1)}%)."
            )
            themes.append({"label": "country under-benchmark", "count": 1})
        else:
            strengths.append(
                f"In {country_key}, measured engagement is above the country benchmark ({round(er * 100, 1)}% vs {round(country_b['avg_engagement_rate'] * 100, 1)}%)."
            )

        strengths.append(
            f"{country_key} has a regional benchmark of {round(country_b['avg_engagement_rate'] * 100, 1)}% versus the global {round(global_b['avg_engagement_rate'] * 100, 1)}%, so packaging quality matters more in this market."
        )

    if not strengths:
        strengths.append(
            "The topic still shows some baseline audience pull, so packaging improvements may unlock better performance."
        )

    return {
        "measured_metrics": {
            "views_total": video["views_total"],
            "likes": video["likes"],
            "comments": video["comments"],
            "engagement_rate": round(er, 4),
            "title_length": vf["title_length"],
            "word_count": vf["word_count"],
            "has_number": vf["has_number"],
            "has_question": vf["has_question"],
            "has_exclamation": vf["has_exclamation"],
            "metric_source": "youtube_link_public_stats_or_manual_input",
        },
        "derived_scores": {
            "virality_score": virality_score(video, benchmarks)
        },
        "benchmark_comparison": {
            "engagement_gap_vs_global_pct": round(((er - global_b["avg_engagement_rate"]) / max(global_b["avg_engagement_rate"], 0.0001)) * 100, 1),
            "engagement_gap_vs_top_pct": round(((er - top_b["avg_engagement_rate"]) / max(top_b["avg_engagement_rate"], 0.0001)) * 100, 1),
            "title_length_delta_vs_top": round(vf["title_length"] - top_b["avg_title_length"], 1),
            "word_count_delta_vs_top": round(vf["word_count"] - top_b["avg_word_count"], 1),
            "global_avg_engagement_rate": round(global_b["avg_engagement_rate"], 4),
            "top_avg_engagement_rate": round(top_b["avg_engagement_rate"], 4),
            "top_avg_title_length": round(top_b["avg_title_length"], 2),
            "top_has_number_pct": round(top_b["has_number_pct"], 4),
            "country_benchmark_available": bool(country_b),
            "category_benchmark_available": bool(category_b),
        },
        "insights": {
            "strengths": strengths[:6],
            "weaknesses": weaknesses[:6],
            "themes": themes[:6],
        },
    }