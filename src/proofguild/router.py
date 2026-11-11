"""Routing by measured competence.

The router classifies a job to a task type, then prefers the
verified specialist with the highest measured margin for that type.
If no specialist is verified for the type, it returns the generalist
and says so — the honest outcome a prompt library never gives you,
because it has no measurements to route by.
"""

from __future__ import annotations

from .registry import load_registry

# Ordered: first matching type wins. Keywords are deliberately
# plain; misclassification risk is stated in the README.
RULES: list[tuple[str, list[str]]] = [
    ("code-review", ["review", "pull request", " pr ", "codebase",
                     "lint", "defect"]),
    ("data-analysis", ["csv", "dataset", "revenue", "sales data",
                       "analyse", "analyze", "spreadsheet",
                       "orders"]),
    ("research", ["research", "find out", "look up", "cite",
                  "citation", "sources", "fact"]),
    ("action-extraction", ["action items", "transcript", "minutes",
                           "meeting notes", "meeting"]),
]


def classify(job: str) -> str | None:
    text = f" {job.lower()} "
    for task_type, keywords in RULES:
        if any(k in text for k in keywords):
            return task_type
    return None


def route(job: str, registry: dict | None = None) -> dict:
    registry = registry or load_registry()
    task_type = classify(job)
    if task_type is None:
        return {"decision": "generalist", "specialist_id": None,
                "task_type": None,
                "reason": "No task type matched this job, so no "
                          "specialist can claim it. Routed to the "
                          "generalist (labelled, not disguised)."}
    candidates = [s for s in registry["specialists"]
                  if task_type in s.get("task_types", [])
                  or s.get("specialty") == task_type]
    verified = [s for s in candidates
                if s.get("competence", {}).get("status") == "verified"]
    if verified:
        best = max(verified,
                   key=lambda s: s["competence"].get("margin", 0))
        c = best["competence"]
        return {"decision": "specialist", "specialist_id": best["id"],
                "task_type": task_type,
                "reason": f"{best['name']} is verified for "
                          f"{task_type}: measured margin "
                          f"{c['margin']:+.3f} over the generalist "
                          f"on {c['tasks']} tasks ({c['suite']}, "
                          f"{c['measured_at'][:10]})."}
    seen = ", ".join(
        f"{s['id']}={s.get('competence', {}).get('status', 'unmeasured')}"
        for s in candidates) or "none registered"
    return {"decision": "generalist", "specialist_id": None,
            "task_type": task_type,
            "reason": f"No verified specialist for {task_type} "
                      f"(candidates: {seen}). Routed to the "
                      f"generalist, labelled as such — an unverified "
                      f"specialist is not silently substituted."}
