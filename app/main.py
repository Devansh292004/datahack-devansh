from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import re
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    BuildBenchmarksRequest,
    CreateAnalysisRequest,
    PublishLinkRequest,
    SimulateRequest,
)
from app.services.analyzer import compare_to_benchmarks
from app.services.benchmark_engine import build_benchmarks
from app.services.simulator import generate_counterfactuals, next_recommendation
from app.services.storage import load_benchmarks, load_state, save_benchmarks, save_state
from app.services.youtube_fetcher import fetch_video_metadata, YouTubeFetchError


app = FastAPI(title="Packt Counterfactual Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_video_id(url: str) -> str:
    patterns = [
        r"v=([A-Za-z0-9_-]{6,})",
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"/shorts/([A-Za-z0-9_-]{6,})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return "unknown_video"


def _get_analysis_or_404(analysis_id: str) -> Dict[str, Any]:
    state = load_state()
    analysis = state["analyses"].get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _verdict_for_score(score: int) -> str:
    if score >= 70:
        return "High potential — close to trending performance"
    if score >= 40:
        return "Moderate — strong idea, packaging limits reach"
    return "Low — major gaps vs trending benchmarks"


def _age_caveat(publish_time: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Returns a caveat block if the video is older than 30 days. Engagement rate
    naturally decays over time as view counts accumulate, so comparing a long-lived
    video's lifetime stats against 2026 trending-snapshot benchmarks is not fair.
    """
    if not publish_time:
        return None
    try:
        pub_dt = datetime.fromisoformat(publish_time.replace("Z", ""))
    except ValueError:
        return None

    age_days = (datetime.utcnow() - pub_dt).days
    if age_days < 30:
        return {"video_age_days": age_days, "applies": False}

    return {
        "video_age_days": age_days,
        "applies": True,
        "note": (
            f"This video is {age_days} days old. Engagement rate here reflects lifetime "
            "stats against 2026 trending-snapshot benchmarks, so older videos will "
            "naturally show a gap even if they performed well at launch. Packt is "
            "most accurate on videos under ~30 days old."
        ),
    }


def _build_post_publish_report(analysis: Dict[str, Any], benchmarks: Dict[str, Any]) -> Dict[str, Any]:
    report = compare_to_benchmarks(analysis["video"], benchmarks)
    score = report["derived_scores"]["virality_score"]

    # Upgrade insights with LLM. Falls back to the raw templated bullets on failure.
    from app.services.llm_reasoning import generate_insights
    llm_insights = generate_insights(analysis["video"], analysis, report)

    insights_block = {
        "strengths": llm_insights["strengths"],
        "weaknesses": llm_insights["weaknesses"],
        "themes": report["insights"]["themes"],
    }
    if llm_insights.get("verdict_paragraph"):
        insights_block["verdict_paragraph"] = llm_insights["verdict_paragraph"]

    result = {
        "status": "analyzing_feedback",
        "verdict": _verdict_for_score(score),
        "video": {
            "youtube_video_id": analysis["video"]["youtube_video_id"],
            "title": analysis["video"]["title"],
            "country": analysis["video"].get("country", "GLOBAL"),
            "category_id": analysis["video"]["category_id"],
        },
        "measured_metrics": report["measured_metrics"],
        "derived_scores": report["derived_scores"],
        "benchmark_comparison": report["benchmark_comparison"],
        "insights": insights_block,
    }

    caveat = _age_caveat(analysis["video"].get("publish_time"))
    if caveat:
        result["comparison_caveat"] = caveat

    return result

@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "Packt Counterfactual Engine is running."}


@app.post("/api/benchmarks/build")
def api_build_benchmarks(req: BuildBenchmarksRequest) -> Dict[str, Any]:
    benchmarks = build_benchmarks(req.csv_paths, req.top_quantile)
    save_benchmarks(benchmarks)
    return {
        "status": "ok",
        "row_count": benchmarks["row_count"],
        "source_file_count": benchmarks["source_file_count"],
        "generated_at": benchmarks["generated_at"],
    }


@app.get("/api/benchmarks")
def api_get_benchmarks() -> Dict[str, Any]:
    benchmarks = load_benchmarks()
    if not benchmarks:
        raise HTTPException(status_code=404, detail="Benchmarks not built yet")
    return benchmarks


@app.post("/api/analyses")
def create_analysis(req: CreateAnalysisRequest) -> Dict[str, Any]:
    state = load_state()
    analysis_id = f"an_{state['next_analysis_id']}"
    state["next_analysis_id"] += 1
    state["analyses"][analysis_id] = {
        "analysis_id": analysis_id,
        "status": "draft",
        "workspace_id": req.workspace_id,
        "creator_channel_id": req.creator_channel_id,
        "input_mode": req.input_mode,
        "niche": req.niche,
        "audience": req.audience,
        "content_style": req.content_style,
        "target_platform": req.target_platform,
        "language": req.language,
        "region": req.region,
        "notes": req.notes,
        "video": None,
        "post_publish_report": None,
        "counterfactuals": [],
        "next_recommendation": None,
    }
    save_state(state)
    return state["analyses"][analysis_id]


@app.post("/api/analyses/{analysis_id}/publish-link")
def publish_link(analysis_id: str, req: PublishLinkRequest) -> Dict[str, Any]:
    state = load_state()
    analysis = state["analyses"].get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    fetched: Dict[str, Any] = {}
    fetch_error: Optional[str] = None
    try:
        fetched = fetch_video_metadata(req.youtube_url)
    except YouTubeFetchError as e:
        fetch_error = str(e)

    def pick(manual, key, default=None):
        if manual is not None:
            return manual
        return fetched.get(key, default)

    analysis["video"] = {
        "youtube_url": req.youtube_url,
        "youtube_video_id": pick(req.youtube_video_id, "youtube_video_id", _extract_video_id(req.youtube_url)),
        "title": pick(req.title, "title", "Untitled video"),
        "category_id": pick(req.category_id, "category_id", 24),
        "country": req.country or analysis.get("region") or "GLOBAL",
        "views_total": pick(req.views_total, "views_total", 0),
        "likes": pick(req.likes, "likes", 0),
        "comments": pick(req.comments, "comments", 0),
        "publish_time": pick(req.publish_time, "publish_time"),
        "trending_date": req.trending_date,
        "description": pick(req.description, "description", ""),
        "channel": fetched.get("channel"),
        "channel_id": fetched.get("channel_id"),
        "duration_seconds": fetched.get("duration_seconds"),
        "thumbnail_url": fetched.get("thumbnail_url"),
        "category_name": fetched.get("category_name"),
        "tags": fetched.get("tags", []),
        "metric_source": "yt_dlp_public_metadata" if not fetch_error else "manual_input_fetch_failed",
    }
    analysis["status"] = "tracking_started"
    save_state(state)

    response: Dict[str, Any] = {
        "analysis_id": analysis_id,
        "youtube_video_id": analysis["video"]["youtube_video_id"],
        "status": analysis["status"],
        "fetch_status": "success" if not fetch_error else "failed",
    }
    if not fetch_error:
        response["fetched"] = {
            "title": analysis["video"]["title"],
            "channel": analysis["video"]["channel"],
            "views_total": analysis["video"]["views_total"],
            "likes": analysis["video"]["likes"],
            "comments": analysis["video"]["comments"],
            "category_id": analysis["video"]["category_id"],
            "category_name": analysis["video"]["category_name"],
            "publish_time": analysis["video"]["publish_time"],
            "duration_seconds": analysis["video"]["duration_seconds"],
        }
    else:
        response["fetch_error"] = fetch_error
        response["note"] = "Fetch failed. Provide views_total, likes, comments, title, category_id manually."

    return response


@app.get("/api/analyses/{analysis_id}/post-publish")
def post_publish(analysis_id: str) -> Dict[str, Any]:
    benchmarks = load_benchmarks()
    if not benchmarks:
        raise HTTPException(status_code=400, detail="Build benchmarks first")

    state = load_state()
    analysis = state["analyses"].get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not analysis.get("video"):
        raise HTTPException(status_code=400, detail="Attach a published video first")

    analysis["post_publish_report"] = _build_post_publish_report(analysis, benchmarks)
    analysis["status"] = "analyzing_feedback"
    save_state(state)

    return analysis["post_publish_report"]


@app.post("/api/analyses/{analysis_id}/counterfactual-simulate")
def simulate(analysis_id: str, req: SimulateRequest) -> Dict[str, Any]:
    state = load_state()
    analysis = state["analyses"].get(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not analysis.get("video"):
        raise HTTPException(status_code=400, detail="Attach a published video first")

    report = analysis.get("post_publish_report")
    if not report:
        benchmarks = load_benchmarks()
        if not benchmarks:
            raise HTTPException(status_code=400, detail="Build benchmarks first")
        report = _build_post_publish_report(analysis, benchmarks)
        analysis["post_publish_report"] = report

    scenarios = generate_counterfactuals(
        video=analysis["video"],
        analysis=analysis,
        benchmark_report=report,
        limit=req.scenarios_to_generate,
    )

    recommendation = next_recommendation(
        video=analysis["video"],
        analysis=analysis,
        benchmark_report=report,
        scenarios=scenarios,
    )

    analysis["counterfactuals"] = scenarios
    analysis["next_recommendation"] = recommendation
    analysis["status"] = "simulation_ready"
    save_state(state)

    response = {
        "status": analysis["status"],
        "simulation_note": (
            "These are counterfactual projections derived from benchmark gaps across "
            "~175k trending videos. They estimate how much a newly published video of "
            "similar content could improve if the suggested change were applied. They "
            "are not guaranteed outcomes."
        ),
        "counterfactuals": scenarios,
    }
    if report.get("comparison_caveat", {}).get("applies"):
        response["comparison_caveat"] = report["comparison_caveat"]

    return response


@app.get("/api/analyses/{analysis_id}/counterfactuals")
def get_counterfactuals(analysis_id: str) -> Dict[str, Any]:
    analysis = _get_analysis_or_404(analysis_id)
    return {
        "analysis_id": analysis_id,
        "status": analysis.get("status"),
        "counterfactuals": analysis.get("counterfactuals", []),
    }


@app.get("/api/analyses/{analysis_id}/next-recommendation")
def get_recommendation(analysis_id: str) -> Dict[str, Any]:
    analysis = _get_analysis_or_404(analysis_id)
    if not analysis.get("next_recommendation"):
        raise HTTPException(status_code=400, detail="Run simulation first")
    return analysis["next_recommendation"]