from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class BuildBenchmarksRequest(BaseModel):
    csv_paths: Optional[List[str]] = None
    top_quantile: float = Field(default=0.9, ge=0.5, le=0.99)


class ManualVideoMetrics(BaseModel):
    title: str
    category_id: int
    country: str = "GLOBAL"
    views_total: int = Field(ge=0)
    likes: int = Field(ge=0)
    comments: int = Field(ge=0)
    publish_time: Optional[str] = None
    trending_date: Optional[str] = None
    description: Optional[str] = ""


class CreateAnalysisRequest(BaseModel):
    workspace_id: Optional[str] = None
    creator_channel_id: Optional[str] = None
    input_mode: Optional[str] = "youtube_link"
    niche: Optional[str] = None
    audience: Optional[str] = None
    content_style: Optional[str] = None
    target_platform: Optional[str] = "youtube"
    language: Optional[str] = "en"
    region: Optional[str] = "GLOBAL"
    notes: Optional[str] = None


class PublishLinkRequest(BaseModel):
    youtube_url: str
    youtube_video_id: Optional[str] = None
    title: Optional[str] = None
    category_id: Optional[int] = None
    country: Optional[str] = None
    views_total: Optional[int] = Field(default=None, ge=0)
    likes: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    publish_time: Optional[str] = None
    trending_date: Optional[str] = None
    description: Optional[str] = None


class SimulateRequest(BaseModel):
    scenarios_to_generate: int = Field(default=4, ge=1, le=6)


class ThemeCount(BaseModel):
    label: str
    count: int


class MeasuredMetricsResponse(BaseModel):
    views_total: int
    likes: int
    comments: int
    engagement_rate: float
    title_length: int
    word_count: int
    has_number: bool
    has_question: bool
    has_exclamation: bool
    metric_source: str


class DerivedScoresResponse(BaseModel):
    virality_score: int


class BenchmarkComparisonResponse(BaseModel):
    engagement_gap_vs_global_pct: float
    engagement_gap_vs_top_pct: float
    title_length_delta_vs_top: float
    word_count_delta_vs_top: float
    global_avg_engagement_rate: float
    top_avg_engagement_rate: float
    top_avg_title_length: float
    top_has_number_pct: float
    country_benchmark_available: bool
    category_benchmark_available: bool


class SimulatedMetricsResponse(BaseModel):
    projected_views_uplift_pct: int
    projected_engagement_uplift_pct: int
    projected_retention_uplift_pct: int
    metric_source: str
    interpretation: str


class CounterfactualScenario(BaseModel):
    scenario_id: str
    name: str
    change: str
    simulated_metrics: SimulatedMetricsResponse
    confidence: float
    reasoning: str
    impact_rank: Optional[int] = None


class RecommendationResponse(BaseModel):
    hook_strategy: str
    title_strategy: str
    thumbnail_strategy: str
    lesson: str
    recommendation_note: Optional[str] = None