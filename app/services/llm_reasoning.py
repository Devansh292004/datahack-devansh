from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TIMEOUT_SECONDS = 6.0


SCENARIO_SYSTEM_PROMPT = """You are Packt's reasoning engine: an elite YouTube growth strategist.

You are given:
- a specific video
- measured public performance
- benchmark comparisons against ~175k 2026 trending videos
- a specific counterfactual change

Your task:
Write 2-3 sharp sentences explaining why this specific change is the right move.

Rules:
- Be specific, not generic.
- Reference at least one real number.
- Do not mention AI, LLM, model, simulation, benchmark engine, or prompt.
- Do not invent audience traits unless directly supported by the provided data.
- Do not use filler such as "this could help", "might improve", "potentially", or "in general".
- Avoid repeating the scenario name.
- Do not just restate the input data.
- Include one real insight about audience expectation, packaging clarity, payoff timing, click decision, or retention behavior.
- Do not present exact uplift as guaranteed.
- Max 3 sentences.
"""


RECOMMENDATION_SYSTEM_PROMPT = """You are Packt's recommendation engine: an elite YouTube strategist.

You are given:
- the video
- measured public metrics
- benchmark gaps
- the highest-impact scenario

Return a JSON object with exactly these keys:
- hook_strategy
- title_strategy
- thumbnail_strategy
- lesson
- recommendation_note

Rules:
- Every field must be specific to this video.
- No generic advice.
- Reference real numbers where useful.
- Do not mention AI, LLM, prompt, or model.
- Do not invent audience traits unless directly supported by the data.
- recommendation_note must be one short sentence explaining that the recommendation combines measured public metrics with projected counterfactual analysis.
- Output valid JSON only. No markdown.
"""


def _clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _safe_json_extract(text: str) -> Dict[str, str]:
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    obj_match = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    raise ValueError("Could not parse JSON object from LLM output")


def _client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not GROQ_AVAILABLE or not api_key:
        raise RuntimeError("Groq unavailable")
    return Groq(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)


def _build_reasoning_prompt(
    scenario_name: str,
    scenario_change: str,
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
) -> str:
    measured = benchmark_report["measured_metrics"]
    compare = benchmark_report["benchmark_comparison"]
    insights = benchmark_report["insights"]

    return f"""
Scenario:
- Name: {scenario_name}
- Change: {scenario_change}

Video:
- Title: {video.get('title', 'Unknown')}
- Channel: {video.get('channel', 'Unknown')}
- Category: {video.get('category_name') or video.get('category_id')}
- Region: {video.get('country', 'GLOBAL')}
- Niche: {analysis.get('niche', 'general')}
- Audience: {analysis.get('audience', 'general audience')}

Measured public performance:
- Views: {measured['views_total']:,}
- Likes: {measured['likes']:,}
- Comments: {measured['comments']:,}
- Engagement rate: {round(measured['engagement_rate'] * 100, 2)}%
- Title length: {measured['title_length']} chars
- Has numeric anchor: {measured['has_number']}

Benchmark comparison:
- Global average engagement: {round(compare['global_avg_engagement_rate'] * 100, 2)}%
- Top-performer engagement: {round(compare['top_avg_engagement_rate'] * 100, 2)}%
- Top-performer title length: {round(compare['top_avg_title_length'], 1)} chars
- Numeric anchors in top performers: {round(compare['top_has_number_pct'] * 100, 1)}%
- Engagement gap vs top performers: {compare['engagement_gap_vs_top_pct']}%
- Title length delta vs top: {compare['title_length_delta_vs_top']} chars

Strengths:
- {" | ".join(insights.get('strengths', [])[:3])}

Weaknesses:
- {" | ".join(insights.get('weaknesses', [])[:4])}

Focus for this scenario:
- Stronger 5-second hook -> attention capture and first-click confirmation
- Better title framing -> click decision and promise clarity
- Thumbnail-title expectation match -> expectation alignment before and after click
- Earlier payoff structure -> retention curve and delayed reward

Now write the reasoning.
""".strip()


def _build_recommendation_prompt(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    top_scenario: Dict[str, Any],
) -> str:
    measured = benchmark_report["measured_metrics"]
    compare = benchmark_report["benchmark_comparison"]
    insights = benchmark_report["insights"]

    return f"""
Video:
- Title: {video.get('title', 'Unknown')}
- Channel: {video.get('channel', 'Unknown')}
- Category: {video.get('category_name') or video.get('category_id')}
- Region: {video.get('country', 'GLOBAL')}
- Niche: {analysis.get('niche', 'general')}
- Audience: {analysis.get('audience', 'general audience')}

Measured public performance:
- Views: {measured['views_total']:,}
- Likes: {measured['likes']:,}
- Comments: {measured['comments']:,}
- Engagement rate: {round(measured['engagement_rate'] * 100, 2)}%
- Title length: {measured['title_length']} chars
- Has numeric anchor: {measured['has_number']}

Benchmark comparison:
- Global average engagement: {round(compare['global_avg_engagement_rate'] * 100, 2)}%
- Top-performer engagement: {round(compare['top_avg_engagement_rate'] * 100, 2)}%
- Top-performer title length: {round(compare['top_avg_title_length'], 1)} chars
- Numeric anchors in top performers: {round(compare['top_has_number_pct'] * 100, 1)}%
- Engagement gap vs top performers: {compare['engagement_gap_vs_top_pct']}%
- Title length delta vs top: {compare['title_length_delta_vs_top']} chars

Detected strengths:
- {" | ".join(insights.get('strengths', [])[:3])}

Detected weaknesses:
- {" | ".join(insights.get('weaknesses', [])[:4])}

Top-ranked scenario:
- Name: {top_scenario.get('name')}
- Change: {top_scenario.get('change')}
- Projected engagement uplift: {top_scenario.get('simulated_metrics', {}).get('projected_engagement_uplift_pct')}%
- Projected views uplift: {top_scenario.get('simulated_metrics', {}).get('projected_views_uplift_pct')}%
- Projected retention uplift: {top_scenario.get('simulated_metrics', {}).get('projected_retention_uplift_pct')}%

Write a recommendation that sounds like a strategist reviewing this exact video, not a template.
Return the JSON object now.
""".strip()


def generate_reasoning(
    scenario_name: str,
    scenario_change: str,
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    fallback_reasoning: str,
) -> str:
    if not GROQ_AVAILABLE or not os.environ.get("GROQ_API_KEY"):
        return fallback_reasoning

    try:
        client = _client()
        prompt = _build_reasoning_prompt(
            scenario_name=scenario_name,
            scenario_change=scenario_change,
            video=video,
            analysis=analysis,
            benchmark_report=benchmark_report,
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SCENARIO_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=170,
        )

        content = response.choices[0].message.content
        if not content:
            return fallback_reasoning

        cleaned = _clean_text(content)
        if len(cleaned) < 30:
            return fallback_reasoning

        return cleaned

    except Exception:
        return fallback_reasoning


def generate_recommendation(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    benchmark_report: Dict[str, Any],
    top_scenario: Dict[str, Any],
    fallback: Dict[str, str],
) -> Dict[str, str]:
    if not GROQ_AVAILABLE or not os.environ.get("GROQ_API_KEY"):
        return fallback

    try:
        client = _client()
        prompt = _build_recommendation_prompt(
            video=video,
            analysis=analysis,
            benchmark_report=benchmark_report,
            top_scenario=top_scenario,
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=260,
        )

        content = response.choices[0].message.content
        if not content:
            return fallback

        parsed = _safe_json_extract(content)

        return {
            "hook_strategy": _clean_text(parsed.get("hook_strategy", fallback["hook_strategy"])),
            "title_strategy": _clean_text(parsed.get("title_strategy", fallback["title_strategy"])),
            "thumbnail_strategy": _clean_text(parsed.get("thumbnail_strategy", fallback["thumbnail_strategy"])),
            "lesson": _clean_text(parsed.get("lesson", fallback["lesson"])),
            "recommendation_note": _clean_text(
                parsed.get(
                    "recommendation_note",
                    "This recommendation combines measured public metrics with projected counterfactual analysis.",
                )
            ),
        }

    except Exception:
        return fallback
INSIGHTS_SYSTEM_PROMPT = """You are Packt's diagnosis engine: an elite YouTube strategist reviewing one specific video.

You are given:
- a video's public performance
- its benchmark comparisons against ~175k 2026 trending videos
- raw detected strengths and weaknesses as starting material

Your task:
Rewrite the strengths and weaknesses as if a strategist were pointing them out in a review.
Each bullet should be specific, tight, and reference a real number or specific trait.

Rules:
- Output valid JSON only, no markdown.
- Keys: "strengths" (array of 2-3 strings), "weaknesses" (array of 3-4 strings), "verdict_paragraph" (one string, 2-3 sentences).
- Each bullet: one sentence, under 25 words.
- Reference real numbers where possible.
- Do not invent facts that aren't in the data.
- Do not say "likely" or "potentially" more than once across the whole output.
- Do not mention AI, LLM, model, prompt, or benchmark engine.
- verdict_paragraph is a qualitative read — the one thing a creator should take away.
"""


def _build_insights_prompt(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_report: Dict[str, Any],
) -> str:
    measured = raw_report["measured_metrics"]
    compare = raw_report["benchmark_comparison"]
    raw_insights = raw_report["insights"]

    return f"""
Video:
- Title: {video.get('title', 'Unknown')}
- Channel: {video.get('channel', 'Unknown')}
- Category: {video.get('category_name') or video.get('category_id')}
- Region: {video.get('country', 'GLOBAL')}
- Niche: {analysis.get('niche', 'general')}
- Audience: {analysis.get('audience', 'general audience')}

Measured public performance:
- Views: {measured['views_total']:,}
- Likes: {measured['likes']:,}
- Comments: {measured['comments']:,}
- Engagement rate: {round(measured['engagement_rate'] * 100, 2)}%
- Title length: {measured['title_length']} chars
- Has numeric anchor: {measured['has_number']}
- Virality score (0-100): {raw_report['derived_scores']['virality_score']}

Benchmark comparison:
- Global avg engagement: {round(compare['global_avg_engagement_rate'] * 100, 2)}%
- Top-performer engagement: {round(compare['top_avg_engagement_rate'] * 100, 2)}%
- Top-performer title length: {round(compare['top_avg_title_length'], 1)} chars
- Numeric anchors in top performers: {round(compare['top_has_number_pct'] * 100, 1)}%
- Engagement gap vs top: {compare['engagement_gap_vs_top_pct']}%
- Title length delta vs top: {compare['title_length_delta_vs_top']} chars

Raw detected strengths:
{chr(10).join('- ' + s for s in raw_insights.get('strengths', []))}

Raw detected weaknesses:
{chr(10).join('- ' + w for w in raw_insights.get('weaknesses', []))}

Return the JSON object now.
""".strip()


def generate_insights(
    video: Dict[str, Any],
    analysis: Dict[str, Any],
    raw_report: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns {"strengths": [...], "weaknesses": [...], "verdict_paragraph": "..."}.
    Falls back to the raw templated insights on any failure.
    """
    fallback = {
        "strengths": raw_report["insights"].get("strengths", [])[:3],
        "weaknesses": raw_report["insights"].get("weaknesses", [])[:4],
        "verdict_paragraph": None,
    }

    if not GROQ_AVAILABLE or not os.environ.get("GROQ_API_KEY"):
        return fallback

    try:
        client = _client()
        prompt = _build_insights_prompt(video, analysis, raw_report)

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": INSIGHTS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=380,
        )

        content = response.choices[0].message.content
        if not content:
            return fallback

        parsed = _safe_json_extract(content)
        strengths = parsed.get("strengths") or fallback["strengths"]
        weaknesses = parsed.get("weaknesses") or fallback["weaknesses"]
        verdict_paragraph = parsed.get("verdict_paragraph")

        if not isinstance(strengths, list) or not isinstance(weaknesses, list):
            return fallback

        return {
            "strengths": [_clean_text(s) for s in strengths if isinstance(s, str)][:3],
            "weaknesses": [_clean_text(w) for w in weaknesses if isinstance(w, str)][:4],
            "verdict_paragraph": _clean_text(verdict_paragraph) if isinstance(verdict_paragraph, str) else None,
        }

    except Exception:
        return fallback