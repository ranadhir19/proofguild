"""Verification suites: tasks, arm runners, deterministic scorers.

Every scorer is code, not a model judge, and every ground truth is
derived independently of the arms being measured (planted-defect
manifests, the scorer's own computation over the CSV, live citation
resolution, hand-authored gold items). The generalist arm always
gets the same primary artefact and the same output format; the
specialist arm additionally executes its tool workflow.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from pathlib import Path

from . import specialists as sp
from .models import ModelClient
from .registry import GENERALIST_SYSTEM

FIXTURES = sp.FIXTURES
PAGE_CACHE = FIXTURES / "research" / "cache"


def _num(text: str):
    m = re.findall(r"-?\d[\d,]*\.?\d*", text or "")
    if not m:
        return None
    try:
        return float(m[-1].replace(",", ""))
    except ValueError:
        return None


# ------------------------------------------------------------------
# Suite: code-review
# ------------------------------------------------------------------

REVIEW_TASK = (
    "Review the Python codebase for real defects. A defect is code "
    "that contradicts a module's documented spec, fails the project's "
    "own tests, or is a well-known hazard (mutable default arguments, "
    "swallowed exceptions, SQL built from user input, unused "
    "imports). Report one finding per line, exactly in this format:\n"
    "FINDING | <file> | <one-sentence defect summary> | EVIDENCE: "
    "<failing test, check result, or the offending code>\n"
    "Report only real defects. Some files are correct; claiming a "
    "defect in correct code counts against the review."
)


class CodeReviewSuite:
    specialist_id = "code-reviewer"
    name = "code-review"

    def tasks(self):
        base = FIXTURES / "code_review"
        out = []
        for repo_dir in sorted(base.iterdir()):
            if (repo_dir / "defects.json").exists():
                out.append({"repo": repo_dir.name, "dir": repo_dir,
                            "gold": json.loads(
                                (repo_dir / "defects.json").read_text())})
        return out

    def run_specialist(self, client: ModelClient, task) -> str:
        spec = sp.specialist_by_id(self.specialist_id)
        tests = sp.run_unittests(task["dir"])
        checks = sp.static_checks(task["dir"])
        user = (f"{REVIEW_TASK}\n\nRepository: {task['repo']}\n\n"
                f"== Test-suite output (executed) ==\n{tests}\n\n"
                f"== Static checks (executed) ==\n"
                + ("\n".join(checks) if checks else "(none)")
                + f"\n\n== Source files ==\n"
                + sp.read_repo_sources(task["dir"]))
        return client.chat(spec["system_prompt"], user,
                           max_tokens=3500).text

    def run_generalist(self, client: ModelClient, task) -> str:
        user = (f"{REVIEW_TASK}\n\nRepository: {task['repo']}\n\n"
                f"== Source files ==\n"
                + sp.read_repo_sources(task["dir"]))
        return client.chat(GENERALIST_SYSTEM, user,
                           max_tokens=3500).text

    def score(self, task, output: str):
        gold = task["gold"]
        defects = gold["defects"]
        findings = []
        for line in (output or "").splitlines():
            if "FINDING" in line and "|" in line:
                findings.append(line)
        used = [False] * len(findings)
        hits = 0
        hit_ids = []
        for defect in defects:
            for i, line in enumerate(findings):
                if used[i]:
                    continue
                low = line.lower()
                if defect["file"].lower() not in low:
                    continue
                if any(k.lower() in low for k in defect["keywords"]):
                    used[i] = True
                    hits += 1
                    hit_ids.append(defect["id"])
                    break
        extra = len(findings) - hits
        score = max(0.0, hits - 0.25 * extra) / len(defects)
        return score, {"hits": hit_ids, "n_findings": len(findings),
                       "extra_findings": extra,
                       "n_defects": len(defects)}


# ------------------------------------------------------------------
# Suite: data-analysis
# ------------------------------------------------------------------

ANSWER_FORMATS = {
    "money": "ANSWER: <number>",
    "region_money": "ANSWER: <region name> <number>",
    "product_units": "ANSWER: <product name> <integer>",
    "percent": "ANSWER: <number>",
}


def _net(row) -> float:
    return (int(row["units"]) * float(row["unit_price"])
            * (1 - int(row["discount_pct"]) / 100.0))


def data_truth(csv_path: Path, qid: str):
    """The scorer's own computation — independent of both arms."""
    rows = list(csv.DictReader(csv_path.open()))
    if qid == "DQ1":
        return sum(_net(r) for r in rows
                   if "2026-04-01" <= r["date"] <= "2026-06-30")
    if qid == "DQ2":
        by: dict[str, list[float]] = {}
        for r in rows:
            by.setdefault(r["region"], []).append(_net(r))
        region, vals = max(by.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        return region, sum(vals) / len(vals)
    if qid == "DQ3":
        by: dict[str, int] = {}
        for r in rows:
            by[r["product"]] = by.get(r["product"], 0) + int(r["units"])
        return max(by.items(), key=lambda kv: kv[1])
    if qid == "DQ4":
        return 100.0 * sum(1 for r in rows
                           if int(r["discount_pct"]) >= 20) / len(rows)
    if qid == "DQ5":
        return sum(_net(r) for r in rows
                   if r["segment"] == "Enterprise"
                   and r["date"].startswith("2026-03"))
    raise KeyError(qid)


class DataAnalysisSuite:
    specialist_id = "data-analyst"
    name = "data-analysis"

    def __init__(self):
        base = FIXTURES / "data"
        self.csv_path = base / "orders.csv"
        self.spec = json.loads((base / "questions.json").read_text())

    def tasks(self):
        return self.spec["questions"]

    def _header_info(self) -> str:
        lines = self.csv_path.read_text().splitlines()
        return ("Columns: " + lines[0] + "\nFirst rows:\n"
                + "\n".join(lines[1:4])
                + f"\n({len(lines) - 1} data rows total)")

    def run_specialist(self, client: ModelClient, task) -> str:
        spec = sp.specialist_by_id(self.specialist_id)
        fmt = ANSWER_FORMATS[task["kind"]]
        user = (f"{self.spec['note']}\n\n{self._header_info()}\n\n"
                f"Question: {task['text']}\n\nWrite a Python program "
                f"using only the standard-library csv module that "
                f"reads orders.csv from the current directory and "
                f"prints exactly one line in this format: {fmt}\n"
                f"Output only the program, no explanation.")
        code_resp = client.chat(spec["system_prompt"], user,
                                max_tokens=2000)
        code = _extract_code(code_resp.text)
        answer_line, repairs = self._execute(client, spec, code, task)
        return answer_line or ""

    def _execute(self, client, spec, code, task):
        for attempt in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                workdir = Path(tmp)
                shutil.copy(self.csv_path, workdir / "orders.csv")
                ok, out, err = sp.execute_python(code, workdir)
            line = _answer_line(out)
            if ok and line is not None:
                return line, attempt
            if attempt == 0:
                repair = client.chat(
                    spec["system_prompt"],
                    f"Your program failed or printed no ANSWER line.\n"
                    f"Program:\n```python\n{code}\n```\nError/output:\n"
                    f"{err or out}\nRewrite the complete corrected "
                    f"program. Output only the program.",
                    max_tokens=2000)
                code = _extract_code(repair.text)
        return None, 1

    def run_generalist(self, client: ModelClient, task) -> str:
        fmt = ANSWER_FORMATS[task["kind"]]
        user = (f"{self.spec['note']}\n\nFull dataset (orders.csv):\n"
                f"{self.csv_path.read_text()}\n\nQuestion: "
                f"{task['text']}\n\nReply with exactly one line in "
                f"this format: {fmt}")
        return client.chat(GENERALIST_SYSTEM, user,
                           max_tokens=2000).text

    def score(self, task, output: str):
        line = _answer_line(output) or output or ""
        truth = data_truth(self.csv_path, task["id"])
        got = _num(line)
        ok = False
        if task["kind"] == "money":
            ok = got is not None and abs(got - truth) <= task["tol_rel"] * truth
        elif task["kind"] == "percent":
            ok = got is not None and abs(got - truth) <= task["tol_abs"]
        elif task["kind"] == "region_money":
            region, value = truth
            ok = (region.lower() in line.lower() and got is not None
                  and abs(got - value) <= task["tol_rel"] * value)
        elif task["kind"] == "product_units":
            product, units = truth
            ok = (product.lower() in line.lower() and got is not None
                  and int(got) == units)
        return (1.0 if ok else 0.0), {"truth": str(truth),
                                      "answer_line": line[:200]}


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text or "", re.S)
    return (m.group(1) if m else (text or "")).strip()


def _answer_line(text: str):
    for line in (text or "").splitlines():
        if "ANSWER:" in line:
            return line.strip()
    return None


# ------------------------------------------------------------------
# Suite: research-citations
# ------------------------------------------------------------------

class ResearchSuite:
    specialist_id = "researcher"
    name = "research-citations"

    def __init__(self):
        base = FIXTURES / "research"
        self.spec = json.loads((base / "questions.json").read_text())

    def tasks(self):
        return self.spec["questions"]

    def run_specialist(self, client: ModelClient, task) -> str:
        spec = sp.specialist_by_id(self.specialist_id)
        first = client.chat(
            spec["system_prompt"],
            f"Question: {task['question']}\nTopic: {task['topic']}\n"
            f"Reply with exactly one line: FETCH: <url> — the "
            f"English Wikipedia article URL for this topic.",
            max_tokens=1200)
        m = re.search(r"FETCH:\s*(\S+)", first.text or "")
        url = m.group(1) if m else ""
        status, text = (sp.fetch_url_text(url, PAGE_CACHE)
                        if url else (0, ""))
        second = client.chat(
            spec["system_prompt"],
            f"Question: {task['question']}\n\nFetched page "
            f"({url}, HTTP {status}) text:\n{text[:9000]}\n\nAnswer "
            f"from the fetched text only, in exactly this format:\n"
            f"ANSWER: <value>\nSOURCES: {url}",
            max_tokens=1200)
        return second.text

    def run_generalist(self, client: ModelClient, task) -> str:
        user = (f"Question: {task['question']}\n\nAnswer from your "
                f"knowledge in exactly this format:\nANSWER: <value>\n"
                f"SOURCES: <one or more URLs you believe support the "
                f"answer, comma-separated>")
        return client.chat(GENERALIST_SYSTEM, user,
                           max_tokens=1200).text

    def score(self, task, output: str):
        gold = task["gold_value"]
        line = _answer_line(output) or ""
        fact = 1.0 if re.search(rf"\b{re.escape(gold)}\b", line) else 0.0
        urls = re.findall(r"https?://[^\s,\)\]]+", output or "")
        per_url = []
        any_resolves = False
        any_supports = False
        for url in dict.fromkeys(urls):
            status, text = sp.fetch_url_text(url, PAGE_CACHE)
            resolves = status == 200
            supports = resolves and bool(
                re.search(rf"\b{re.escape(gold)}\b", text))
            any_resolves |= resolves
            any_supports |= supports
            per_url.append({"url": url, "status": status,
                            "supports": supports})
        cq = 1.0 if any_supports else (0.4 if any_resolves else 0.0)
        return 0.5 * fact + 0.5 * cq, {"fact": fact,
                                       "citation_quality": cq,
                                       "citations": per_url}


# ------------------------------------------------------------------
# Suite: action-extraction
# ------------------------------------------------------------------

_STOP = {"the", "a", "an", "to", "of", "for", "and", "by", "on",
         "in", "up", "out", "with", "our", "team"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in _STOP}


def _parse_items(output: str):
    m = re.search(r"\[.*\]", output or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and d.get("owner")]


class ExtractionSuite:
    specialist_id = "action-extractor"
    name = "action-extraction"

    def __init__(self):
        base = FIXTURES / "meetings"
        self.gold = json.loads((base / "gold.json").read_text())
        self.base = base

    def tasks(self):
        return [{"file": name, "gold_items": items}
                for name, items in self.gold["transcripts"].items()]

    _CONTRACT = (
        "Return ONLY a JSON array of objects with keys \"owner\" "
        "(full name exactly as in the transcript), \"task\" (short "
        "imperative summary) and \"due\" (ISO date YYYY-MM-DD, or "
        "null if no date was given).")

    def run_specialist(self, client: ModelClient, task) -> str:
        spec = sp.specialist_by_id(self.specialist_id)
        transcript = (self.base / task["file"]).read_text()
        draft = client.chat(
            spec["system_prompt"],
            f"Transcript:\n{transcript}\n\nExtract the committed "
            f"action items. {self._CONTRACT}",
            max_tokens=2000)
        final = client.chat(
            spec["system_prompt"],
            f"Transcript:\n{transcript}\n\nDraft extraction:\n"
            f"{draft.text}\n\nRe-read the transcript. Drop every "
            f"item whose owner did not explicitly commit, every item "
            f"already completed, and every ownerless suggestion. "
            f"Fix owners, tasks and due dates. {self._CONTRACT}",
            max_tokens=2000)
        return final.text

    def run_generalist(self, client: ModelClient, task) -> str:
        transcript = (self.base / task["file"]).read_text()
        user = (f"Transcript:\n{transcript}\n\nExtract the action "
                f"items. {self._CONTRACT}")
        return client.chat(GENERALIST_SYSTEM, user,
                           max_tokens=2000).text

    def score(self, task, output: str):
        preds = _parse_items(output)
        golds = task["gold_items"]
        matched_pred: set[int] = set()
        tp = 0
        due_agree = 0
        for gold in golds:
            gold_tokens: set[str] = set()
            for kw in gold["task_keywords"]:
                gold_tokens |= _tokens(kw)
            best, best_overlap = None, 0.0
            for i, pred in enumerate(preds):
                if i in matched_pred:
                    continue
                if (pred.get("owner", "").strip().lower()
                        != gold["owner"].lower()):
                    continue
                overlap = (len(_tokens(pred.get("task", ""))
                               & gold_tokens)
                           / max(1, len(gold_tokens)))
                if overlap > best_overlap:
                    best, best_overlap = i, overlap
            if best is not None and best_overlap >= 0.4:
                matched_pred.add(best)
                tp += 1
                if preds[best].get("due") == gold["due"]:
                    due_agree += 1
        precision = tp / len(preds) if preds else 0.0
        recall = tp / len(golds) if golds else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if precision + recall else 0.0)
        return f1, {"tp": tp, "n_pred": len(preds),
                    "n_gold": len(golds), "precision": precision,
                    "recall": recall,
                    "due_agreement_on_matched": (
                        due_agree / tp if tp else None)}


SUITES = [CodeReviewSuite, DataAnalysisSuite, ResearchSuite,
          ExtractionSuite]
