from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = DATA_DIR / "state.json"
BENCHMARK_PATH = DATA_DIR / "benchmarks.json"


def _default_state() -> Dict[str, Any]:
    return {
        "next_analysis_id": 1,
        "analyses": {},
    }


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        save_state(_default_state())
    return json.loads(STATE_PATH.read_text())


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_benchmarks() -> Dict[str, Any]:
    if not BENCHMARK_PATH.exists():
        return {}
    return json.loads(BENCHMARK_PATH.read_text())


def save_benchmarks(benchmarks: Dict[str, Any]) -> None:
    BENCHMARK_PATH.write_text(json.dumps(benchmarks, indent=2))
