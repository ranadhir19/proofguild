"""The verification harness: specialist vs generalist, head-to-head.

Runs each suite under the rules frozen in PREREGISTRATION.md and
writes the competence records the registry ships. A suite that
cannot complete (rate limit, provider error) is recorded
`provisional` with the reason — never quietly dropped, never
upgraded.
"""

from __future__ import annotations

import datetime as _dt
import traceback
from pathlib import Path

from . import registry as reg
from .models import ModelClient, ProviderError, RateLimited
from .suites import SUITES

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "model_cache"

DEFAULTS = {"groq": "openai/gpt-oss-120b",
            "gemini": "gemini-3.5-flash"}


def _task_id(suite_name: str, task: dict) -> str:
    return (task.get("id") or task.get("repo") or task.get("file")
            or "task")


def run_verification(provider: str = "groq", model: str | None = None,
                     only_suite: str | None = None,
                     log=print) -> dict:
    model = model or DEFAULTS[provider]
    client = ModelClient(provider, model, CACHE_DIR)
    registry = reg.load_registry()
    by_id = {s["id"]: s for s in registry["specialists"]}
    summary = {}
    for suite_cls in SUITES:
        suite = suite_cls()
        if only_suite and suite.name != only_suite:
            continue
        sid = suite.specialist_id
        log(f"== {suite.name} ({sid}) on {provider}/{model}")
        tasks = suite.tasks()
        rows = []
        complete = True
        note = ""
        for task in tasks:
            tid = _task_id(suite.name, task)
            row = {"task": tid}
            for arm, runner in (("specialist", suite.run_specialist),
                                ("generalist", suite.run_generalist)):
                try:
                    out = runner(client, task)
                    score, details = suite.score(task, out)
                    row[f"{arm}_score"] = score
                    row[f"{arm}_details"] = details
                    row[f"{arm}_output"] = (out or "")[:1500]
                except RateLimited as e:
                    complete = False
                    note = f"provider rate-limited mid-suite: {e}"
                    row[f"{arm}_error"] = note
                    break
                except (ProviderError, Exception) as e:  # noqa: BLE001
                    complete = False
                    note = f"{arm} arm failed on {tid}: {e}"
                    row[f"{arm}_error"] = (
                        note + "\n" + traceback.format_exc()[-400:])
            rows.append(row)
            log(f"   {tid}: specialist="
                f"{row.get('specialist_score')} generalist="
                f"{row.get('generalist_score')}")
            if not complete:
                break
        scored = [r for r in rows
                  if "specialist_score" in r and "generalist_score" in r]
        n = len(scored)
        spec_mean = (sum(r["specialist_score"] for r in scored) / n
                     if n else 0.0)
        gen_mean = (sum(r["generalist_score"] for r in scored) / n
                    if n else 0.0)
        status = reg.decide_status(n, spec_mean, gen_mean, complete)
        record = {
            "specialist_id": sid,
            "suite": suite.name,
            "provider": provider,
            "requested_model": model,
            "measured_at": _dt.datetime.now(
                _dt.timezone.utc).isoformat(timespec="seconds"),
            "n_tasks_scored": n,
            "complete": complete,
            "note": note,
            "specialist_mean": round(spec_mean, 4),
            "generalist_mean": round(gen_mean, 4),
            "margin": round(spec_mean - gen_mean, 4),
            "specialist_wilson95": [round(x, 4) for x in
                                    reg.wilson(spec_mean * n, n)],
            "generalist_wilson95": [round(x, 4) for x in
                                    reg.wilson(gen_mean * n, n)],
            "status": status,
            "live_calls_made": client.live_calls,
            "tasks": rows,
        }
        path = reg.write_record(sid, record)
        by_id[sid]["competence"] = {
            "status": status,
            "suite": suite.name,
            "tasks": n,
            "specialist_score": round(spec_mean, 4),
            "generalist_score": round(gen_mean, 4),
            "margin": round(spec_mean - gen_mean, 4),
            "provider": provider,
            "model": model,
            "measured_at": record["measured_at"],
            "record": f"records/{sid}.json",
        }
        summary[sid] = status
        log(f"   -> {status} (specialist {spec_mean:.3f} vs "
            f"generalist {gen_mean:.3f}, margin "
            f"{spec_mean - gen_mean:+.3f}); record: {path}")
    reg.save_registry(registry)
    return summary
