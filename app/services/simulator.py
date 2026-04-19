from __future__ import annotations

from typing import Any, Dict, List

from app.services import llm_reasoning as llm_reasoning_module


SCENARIO_LIBRARY = [
    {
        "name": "Stronger 5-second hook",
        "change": "Open with the highest-tension insight immediately instead of warming up slowly.",
        "trigger": "engagement gap",
    },
    {
        "name": "Better title framing",
        "change": "Rewrite the title with a clearer promise, stronger curiosity, and optionally a numeric anchor.",
        "trigger": "missing number anchor",
    },
    {
        "name": "Thumbnail-title expectation match",
        "change": "Tighten the thumbnail concept so it mirrors the title payoff instead of teasing something broader.",
        "trigger": "short title",
    },
    {
        "name": "Earlier payoff structure",
        "change": "Move the most rewarding reveal, proof point, or emotional beat earlier in the content arc.",
        "trigger": "category under-benchmark",
    },
]


SCENARIO_WEIGHTS = {
    "Stronger 5-second hook": {
        "views_weight": 0.09,
        "eng_weight": 0.09,
        "ret_weight": 0.14,
        "views_base": 9,
        "eng_base": 7,
        "ret_base": 11,
    },
    "Better title framing": {
        "views_weight": 0.14,
        "eng_weight": 0.10,
        "ret_weight": 0.07,
        "views_base": 12,
        "eng_base": 9,
        "ret_base": 6,
    },
    "Thumbnail-title expectation match": {
        "views_weight": 0.15,
        "eng_weight": 0.07,
        "ret_weight": 0.06,
        "views_base": 13,
        "eng_base": 6,
        "ret_base": 5,
    },
    "Earlier payoff structure": {
        "views_weight": 0.07,
        "eng_weight": 0.10,
        "ret_weight": 0.15,
        "views_base": 7,
        "eng_base": 8,
        "ret_base": 12,
    },
}


def _bounded_pct(value: float, low: int = 3, high: int = 35) -> int:
    return int(round(max(low, min(high, value))))


def _fallback_reasoning(
    template_name: str,
    actual_er: float,
    global_er: float,
    top_er: float,
    top_title_len: float,
    top_has_number_pct: float,
    title_len: int,
    niche: str,
) -> str:
    if template_name == "Better title framing":
        return (
            f"Top-performing 2026 titles average about {round(top_title_len, 1)} characters, "
            f"while this title is {title_len}. Numeric anchors appear in "
            f"{round(top_has_number_pct * 100, 1)}% of top performers, and your title currently lacks one."
        )
    if template_name == "Stronger 5-second hook":
        return (
            f"Measured engagement is {round(actual_er * 100, 1)}% versus {round(global_er * 100, 1)}% "
            f"global and {round(top_er * 100, 1)}% top benchmark. The topic has pull, but the opening delays "
            f"payoff for a {niche} audience."
        )
    if template_name == "Thumbnail-title expectation match":
        return (
            "Benchmark mismatch suggests click-to-payoff inconsistency. Tighter packaging improves public engagement "
            "because viewers receive what they expected faster."
        )
    return (
        "Underperformance versus category-level trending benchmarks suggests the payoff arrives too late. "
        "Moving the reward earlier improves viewer momentum when the topic is still relevant."
    )


def _fallback_recommendation(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
) -> Dict[str, str]:
    compare = benchmark_report["benchmark_comparison"]
    measured = benchmark_report["measured_metrics"]

    top = max(
        scenarios,
        key=lambda s: (
            s["simulated_metrics"]["projected_engagement_uplift_pct"],
            s["confidence"],
        ),
    )

    title_delta = compare["title_length_delta_vs_top"]
    top_title_len = compare["top_avg_title_length"]
    top_has_number_pct = compare["top_has_number_pct"]
    actual_er = measured["engagement_rate"]
    global_er = compare["global_avg_engagement_rate"]
    top_er = compare["top_avg_engagement_rate"]

    if title_delta < -8:
        title_strategy = (
            f"Measured title length is {measured['title_length']}, while top 2026 trending titles average about "
            f"{round(top_title_len, 1)}. Use slightly longer titles with clearer tension, stronger promise, and optional "
            f"numeric framing. Numeric anchors appear in {round(top_has_number_pct * 100, 1)}% of top performers."
        )
    elif title_delta > 12:
        title_strategy = (
            f"Your measured title length is above the benchmark ({measured['title_length']} vs {round(top_title_len, 1)}). "
            "Tighten the title so the payoff is visible faster."
        )
    else:
        title_strategy = (
            "Your title length is reasonably close to the benchmark, so focus on stronger curiosity and clearer value communication."
        )

    hook_strategy = (
        f"Measured engagement is {round(actual_er * 100, 1)}% versus {round(global_er * 100, 1)}% globally and "
        f"{round(top_er * 100, 1)}% for top performers. Compress setup and make the payoff visible earlier."
    )

    thumbnail_strategy = (
        "Use one dominant visual idea that exactly matches the title promise. Reduce ambiguity and clutter so the click expectation is clear."
    )

    lesson = (
        f"Best next move: {top['name'].lower()}. This recommendation combines measured public video signals with 2026 benchmark gaps and "
        "counterfactual simulation rather than claiming a guaranteed outcome."
    )

    return {
        "hook_strategy": hook_strategy,
        "title_strategy": title_strategy,
        "thumbnail_strategy": thumbnail_strategy,
        "lesson": lesson,
        "recommendation_note": "This recommendation combines measured public metrics with simulated counterfactual estimates.",
    }


def _maybe_llm_recommendation(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    fallback: Dict[str, str],
) -> Dict[str, str]:
    generate_recommendation = getattr(llm_reasoning_module, "generate_recommendation", None)
    if not callable(generate_recommendation):
        return fallback

    top = max(
        scenarios,
        key=lambda s: (
            s["simulated_metrics"]["projected_engagement_uplift_pct"],
            s["confidence"],
        ),
    )

    try:
        result = generate_recommendation(
            video=video,
            analysis=analysis,
            benchmark_report=benchmark_report,
            top_scenario=top,
            fallback=fallback,
        )
        if isinstance(result, dict):
            return {
                "hook_strategy": result.get("hook_strategy", fallback["hook_strategy"]),
                "title_strategy": result.get("title_strategy", fallback["title_strategy"]),
                "thumbnail_strategy": result.get("thumbnail_strategy", fallback["thumbnail_strategy"]),
                "lesson": result.get("lesson", fallback["lesson"]),
                "recommendation_note": result.get(
                    "recommendation_note",
                    "This recommendation combines measured public metrics with projected counterfactual analysis.",
                ),
            }
    except Exception:
        pass

    return fallback


def generate_counterfactuals(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    limit: int = 4,
) -> List[Dict[str, Any]]:
    measured = benchmark_report["measured_metrics"]
    derived = benchmark_report["derived_scores"]
    compare = benchmark_report["benchmark_comparison"]
    themes = {t["label"] for t in benchmark_report["insights"]["themes"]}

    actual_er = measured["engagement_rate"]
    global_er = compare["global_avg_engagement_rate"]
    top_er = compare["top_avg_engagement_rate"]
    virality = derived["virality_score"]
    top_title_len = compare["top_avg_title_length"]
    top_has_number_pct = compare["top_has_number_pct"]
    title_len = measured["title_length"]
    niche = analysis.get("niche") or "your niche"

    er_gap_abs = abs(compare["engagement_gap_vs_top_pct"])

    scenarios: List[Dict[str, Any]] = []
    for i, template in enumerate(SCENARIO_LIBRARY[:limit], start=1):
        trigger_bonus = 6 if template["trigger"] in themes else 2
        score_factor = max(0, (70 - virality) / 8)
        w = SCENARIO_WEIGHTS[template["name"]]

        views_up = _bounded_pct(
            w["views_base"] + er_gap_abs * w["views_weight"] + trigger_bonus + score_factor
        )
        eng_up = _bounded_pct(
            w["eng_base"] + er_gap_abs * w["eng_weight"] + trigger_bonus + score_factor / 2
        )
        ret_up = _bounded_pct(
            w["ret_base"] + er_gap_abs * w["ret_weight"] + trigger_bonus + score_factor
        )

        confidence = round(
            min(0.9, max(0.58, 0.66 + trigger_bonus / 100 - er_gap_abs / 700)),
            2,
        )

        fallback = _fallback_reasoning(
            template["name"],
            actual_er,
            global_er,
            top_er,
            top_title_len,
            top_has_number_pct,
            title_len,
            niche,
        )

        reasoning = llm_reasoning_module.generate_reasoning(
            scenario_name=template["name"],
            scenario_change=template["change"],
            video=video,
            analysis=analysis,
            benchmark_report=benchmark_report,
            fallback_reasoning=fallback,
        )

        scenarios.append(
            {
                "scenario_id": f"cf_{i}",
                "name": template["name"],
                "change": template["change"],
                "simulated_metrics": {
                    "projected_views_uplift_pct": views_up,
                    "projected_engagement_uplift_pct": eng_up,
                    "projected_retention_uplift_pct": ret_up,
                    "metric_source": "counterfactual_simulation",
                    "interpretation": "Projected uplift if these changes were applied before publishing a similar video.",
                },
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )

    scenarios = sorted(
        scenarios,
        key=lambda s: (
            s["simulated_metrics"]["projected_engagement_uplift_pct"],
            s["confidence"],
        ),
        reverse=True,
    )

    for i, scenario in enumerate(scenarios, start=1):
        scenario["impact_rank"] = i

    return scenarios


def next_recommendation(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
) -> Dict[str, str]:
    fallback = _fallback_recommendation(
        video=video,
        analysis=analysis,
        benchmark_report=benchmark_report,
        scenarios=scenarios,
    )
    return _maybe_llm_recommendation(
        video=video,
        analysis=analysis,
        benchmark_report=benchmark_report,
        scenarios=scenarios,
        fallback=fallback,
    )