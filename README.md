# Packt Counterfactual Engine

Backend for a post-publish video intelligence tool. Given a YouTube URL, it:

1. Fetches real public metrics
2. Compares them against 174k 2026 trending videos across 11 countries
3. Generates 4 LLM-reasoned counterfactual scenarios (what-if creative changes)
4. Produces a next-upload recommendation

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:
GROQ_API_KEY=YOUR API KEY

Place the 2026 YouTube Trending Kaggle dataset CSVs in `archive/` (not committed — download from Kaggle).

## Run

```bash
python -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for the Swagger UI.

## Build benchmarks (first run)

```bash
curl -X POST http://127.0.0.1:8000/api/benchmarks/build -H "Content-Type: application/json" -d '{}'
```

## Endpoints

- `POST /api/benchmarks/build` — process dataset into benchmark JSON
- `POST /api/analyses` — create analysis context
- `POST /api/analyses/{id}/publish-link` — attach YouTube URL, fetch real metadata
- `GET /api/analyses/{id}/post-publish` — benchmark-backed diagnosis with LLM insights
- `POST /api/analyses/{id}/counterfactual-simulate` — LLM-reasoned scenarios
- `GET /api/analyses/{id}/next-recommendation` — LLM next-upload strategy
