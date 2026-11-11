"""Offline tests: decision rule, router, scorers, tools, integrity.

No network, no live model calls. Scorers are exercised with
hand-written arm outputs; the research scorer's fetcher is
monkeypatched to canned pages.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from proofguild import registry as reg  # noqa: E402
from proofguild import specialists as sp  # noqa: E402
from proofguild.router import classify, route  # noqa: E402
from proofguild.suites import (CodeReviewSuite, DataAnalysisSuite,  # noqa: E402
                               ExtractionSuite, ResearchSuite,
                               data_truth)


# ---------------- registry / decision rule ----------------

def test_wilson_bounds():
    lo, hi = reg.wilson(4, 4)
    assert 0.0 <= lo < 1.0 and hi <= 1.0
    lo0, hi0 = reg.wilson(0, 0)
    assert (lo0, hi0) == (0.0, 0.0)


def test_decision_rule_frozen():
    # verified: full suite, margin >= 0.15, specialist >= 0.60
    assert reg.decide_status(4, 0.90, 0.70, True) == "verified"
    assert reg.decide_status(5, 0.75, 0.60, True) == "verified"
    # margin too small
    assert reg.decide_status(4, 0.90, 0.80, True) == "unverified"
    # specialist below floor despite margin
    assert reg.decide_status(4, 0.59, 0.30, True) == "unverified"
    # tie
    assert reg.decide_status(4, 0.80, 0.80, True) == "unverified"
    # incomplete / too few tasks
    assert reg.decide_status(3, 1.00, 0.00, True) == "provisional"
    assert reg.decide_status(4, 1.00, 0.00, False) == "provisional"


def _fake_registry():
    return {"specialists": [
        {"id": "code-reviewer", "name": "Code Reviewer",
         "specialty": "code-review", "task_types": ["code-review"],
         "competence": {"status": "verified", "margin": 0.30,
                        "tasks": 4, "suite": "code-review",
                        "measured_at": "2026-11-10T00:00:00+00:00"}},
        {"id": "data-analyst", "name": "Data Analyst",
         "specialty": "data-analysis",
         "task_types": ["data-analysis"],
         "competence": {"status": "unverified", "margin": 0.05,
                        "tasks": 5, "suite": "data-analysis",
                        "measured_at": "2026-11-10T00:00:00+00:00"}},
    ]}


def test_router_prefers_verified():
    r = route("please review this codebase", _fake_registry())
    assert r["decision"] == "specialist"
    assert r["specialist_id"] == "code-reviewer"


def test_router_refuses_unverified():
    r = route("analyse this csv of sales data", _fake_registry())
    assert r["decision"] == "generalist"
    assert r["specialist_id"] is None
    assert "No verified specialist" in r["reason"]


def test_router_unknown_job():
    r = route("write a haiku about rain", _fake_registry())
    assert r["decision"] == "generalist"
    assert r["task_type"] is None


def test_classify():
    assert classify("pull the action items from the transcript") \
        == "action-extraction"
    assert classify("research this and cite your sources") == "research"


# ---------------- tools on fixtures ----------------

def test_static_checks_find_planted():
    base = sp.FIXTURES / "code_review"
    joined = {}
    for repo in base.iterdir():
        if (repo / "defects.json").exists():
            joined[repo.name] = " ".join(sp.static_checks(repo))
    assert "mutable default" in joined["invoice"]
    assert "unused import 'os'" in joined["textkit"]
    assert "bare except" in joined["sched"]
    assert "unused import 'json'" in joined["cart"]


def test_fixture_tests_fail_as_planted():
    base = sp.FIXTURES / "code_review"
    for repo in base.iterdir():
        if (repo / "defects.json").exists():
            out = sp.run_unittests(repo)
            assert "FAILED" in out, repo.name


# ---------------- scorers ----------------

def test_code_review_scorer():
    suite = CodeReviewSuite()
    task = [t for t in suite.tasks() if t["repo"] == "invoice"][0]
    perfect = (
        "FINDING | billing.py | Tax computed before discount; "
        "discount must come before tax | EVIDENCE: failing test\n"
        "FINDING | billing.py | Mutable default basket argument | "
        "EVIDENCE: static check\n"
        "FINDING | discounts.py | Banker's rounding instead of "
        "half-up | EVIDENCE: failing test")
    score, details = suite.score(task, perfect)
    assert score == 1.0 and details["hits"] == ["INV-1", "INV-2",
                                                "INV-3"]
    score0, _ = suite.score(task, "Looks fine to me.")
    assert score0 == 0.0
    fp, _ = suite.score(task, perfect +
                        "\nFINDING | tables.py | Rates are wrong | x")
    assert fp < 1.0  # false positive on the clean file costs 0.25/3


def test_data_scorer_against_truth():
    suite = DataAnalysisSuite()
    for q in suite.tasks():
        truth = data_truth(suite.csv_path, q["id"])
        if q["kind"] == "money":
            out = f"ANSWER: {truth}"
        elif q["kind"] == "percent":
            out = f"ANSWER: {truth}"
        elif q["kind"] == "region_money":
            out = f"ANSWER: {truth[0]} {truth[1]}"
        else:
            out = f"ANSWER: {truth[0]} {truth[1]}"
        score, _ = suite.score(q, out)
        assert score == 1.0, q["id"]
        score0, _ = suite.score(q, "ANSWER: 1")
        assert score0 == 0.0, q["id"]


def test_extraction_scorer():
    suite = ExtractionSuite()
    task = [t for t in suite.tasks()
            if t["file"] == "retro_2026-11-12.txt"][0]
    perfect = json.dumps([
        {"owner": "Felix Wagner", "task": "Split the staging and "
         "demo databases", "due": "2026-11-19"},
        {"owner": "Omar Haddad", "task": "Remove the stale feature "
         "flags", "due": "2026-11-17"},
        {"owner": "Grace Liu", "task": "Write up the interview "
         "synthesis", "due": "2026-11-20"},
        {"owner": "Nina Petrova", "task": "Revise the incident "
         "response template", "due": "2026-11-16"}])
    score, details = suite.score(task, perfect)
    assert score == 1.0 and details["tp"] == 4
    invented = json.dumps([
        {"owner": "Felix Wagner", "task": "Automate the staging "
         "snapshot", "due": None}])
    score2, details2 = suite.score(task, invented)
    assert score2 < 0.3 and details2["tp"] == 0


def test_research_scorer(monkeypatch):
    suite = ResearchSuite()
    task = suite.tasks()[0]  # Python, gold 1991

    def fake_fetch(url, cache_dir):
        if "Python" in url:
            return 200, "Python first appeared in 1991 as a hobby."
        return 404, ""

    monkeypatch.setattr(sp, "fetch_url_text", fake_fetch)
    good = "ANSWER: 1991\nSOURCES: https://en.wikipedia.org/wiki/Python"
    score, d = suite.score(task, good)
    assert score == 1.0 and d["citation_quality"] == 1.0
    dead = "ANSWER: 1991\nSOURCES: https://example.invalid/made-up"
    score2, d2 = suite.score(task, dead)
    assert score2 == 0.5 and d2["citation_quality"] == 0.0
    wrong = "ANSWER: 1989\nSOURCES: https://en.wikipedia.org/wiki/Python"
    score3, _ = suite.score(task, wrong)
    assert score3 == 0.5  # citation supports a value, fact is wrong


# ---------------- registry integrity ----------------

def test_registry_matches_code():
    registry = reg.load_registry()
    ids = {s["id"] for s in registry["specialists"]}
    assert ids == {s["id"] for s in sp.SPECIALISTS}
    for s in registry["specialists"]:
        status = s["competence"]["status"]
        assert status in ("verified", "unverified", "provisional",
                          "unmeasured")
        if status != "unmeasured":
            rec = reg.RECORDS_DIR / f"{s['id']}.json"
            assert rec.exists(), s["id"]
            data = json.loads(rec.read_text())
            assert data["status"] == status
