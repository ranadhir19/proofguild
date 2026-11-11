"""The specialist registry and competence records.

The registry is the library's public face: one entry per specialist
with its role, tools, workflow and — the part prompt libraries omit —
its competence record. A record is written only by the verification
harness from a live, same-provider, same-model head-to-head against
the generalist baseline, under the rules frozen in
PREREGISTRATION.md. Statuses: verified / unverified / provisional /
unmeasured. The router may only prefer `verified`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "registry" / "registry.json"
RECORDS_DIR = ROOT / "records"

GENERALIST_SYSTEM = (
    "You are an expert assistant with deep experience across software "
    "engineering, data analysis, research and operations. Work "
    "carefully, check your reasoning, and follow the requested output "
    "format exactly."
)


def wilson(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval, fractional successes allowed."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    from .specialists import SPECIALISTS
    return {"specialists": [
        {**{k: v for k, v in s.items() if k != "system_prompt"},
         "competence": {"status": "unmeasured"}}
        for s in SPECIALISTS]}


def save_registry(reg: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=1))


def write_record(specialist_id: str, record: dict) -> Path:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECORDS_DIR / f"{specialist_id}.json"
    path.write_text(json.dumps(record, indent=1))
    return path


def decide_status(n_tasks: int, specialist_mean: float,
                  generalist_mean: float,
                  complete: bool) -> str:
    """The frozen decision rule from PREREGISTRATION.md."""
    if not complete or n_tasks < 4:
        return "provisional"
    margin = specialist_mean - generalist_mean
    if margin >= 0.15 and specialist_mean >= 0.60:
        return "verified"
    return "unverified"
