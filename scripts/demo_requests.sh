#!/usr/bin/env bash
set -e

BASE_URL="http://127.0.0.1:8000"

curl -s -X POST "$BASE_URL/api/benchmarks/build" \
  -H "Content-Type: application/json" \
  -d '{}' | jq

echo
curl -s -X POST "$BASE_URL/api/analyses" \
  -H "Content-Type: application/json" \
  -d '{
    "niche": "productivity",
    "audience": "young professionals",
    "content_style": "educational commentary",
    "region": "US"
  }' | jq

echo
curl -s -X POST "$BASE_URL/api/analyses/an_1/publish-link" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=abc123xyz",
    "title": "Why Most People Fail at Productivity",
    "category_id": 27,
    "country": "US",
    "views_total": 18234,
    "likes": 1320,
    "comments": 214,
    "description": "A breakdown of common productivity mistakes."
  }' | jq

echo
curl -s "$BASE_URL/api/analyses/an_1/post-publish" | jq

echo
curl -s -X POST "$BASE_URL/api/analyses/an_1/counterfactual-simulate" \
  -H "Content-Type: application/json" \
  -d '{"scenarios_to_generate": 4}' | jq

echo
curl -s "$BASE_URL/api/analyses/an_1/next-recommendation" | jq
