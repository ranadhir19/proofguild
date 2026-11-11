"""Specialist definitions and the real tools their workflows run.

A proofguild specialist is a configuration, not a costume: a domain
system prompt, a workflow whose steps execute real tools (a test
runner, a static checker, a code executor, a web fetcher), and an
output contract. The generalist baseline gets none of these — same
model, same artefact, strong generic prompt. The verification
harness measures whether the configuration earns its claim.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

SPECIALISTS = [
    {
        "id": "code-reviewer",
        "name": "Code Reviewer",
        "specialty": "code-review",
        "task_types": ["code-review", "pr-review"],
        "description": "Reviews a small Python codebase for real "
                       "defects, grounded in executed evidence: it "
                       "runs the test suite and static checks first, "
                       "then reviews against the module specs.",
        "tools": ["run_unittests", "static_checks", "read_files"],
        "workflow": ["run the repo's test suite and capture failures",
                     "run static checks (compile, unused imports, "
                     "mutable defaults, bare excepts)",
                     "read every source file against its spec",
                     "report only findings it can tie to evidence"],
        "system_prompt": (
            "You are a meticulous code reviewer. You never guess: "
            "every finding you report must be tied to evidence — a "
            "failing test, a static-check result, or the exact code "
            "contradicting the module's documented spec. You read "
            "docstrings and specs as requirements. You do not report "
            "style nits, and you do not invent defects in code that "
            "is correct. Precision matters as much as recall: a "
            "finding against clean code is a failure of the review."),
    },
    {
        "id": "data-analyst",
        "name": "Data Analyst",
        "specialty": "data-analysis",
        "task_types": ["data-analysis", "csv-analysis"],
        "description": "Answers quantitative questions about a CSV "
                       "by writing and actually executing analysis "
                       "code against the file — never by estimating "
                       "from a sample.",
        "tools": ["execute_python", "read_csv"],
        "workflow": ["inspect the CSV header and shape",
                     "write a stdlib Python program that computes "
                     "the answer from the full file",
                     "execute it; on error, repair once from the "
                     "traceback",
                     "report the executed result"],
        "system_prompt": (
            "You are a data analyst who computes, never estimates. "
            "For every quantitative question you write a short "
            "Python program using only the standard-library csv "
            "module, run it against the full dataset, and report "
            "what it printed. You read the question's definitions "
            "literally (date ranges inclusive, discounts applied as "
            "defined) and you double-check column meanings before "
            "aggregating."),
    },
    {
        "id": "researcher",
        "name": "Researcher",
        "specialty": "research",
        "task_types": ["research", "fact-finding"],
        "description": "Answers factual questions by fetching a "
                       "real source first and citing resolvable URLs "
                       "whose text supports the answer — not from "
                       "memory.",
        "tools": ["fetch_url"],
        "workflow": ["choose the authoritative reference page for "
                     "the topic and fetch it",
                     "answer only from the fetched text",
                     "cite the fetched URL"],
        "system_prompt": (
            "You are a researcher who works from sources, not "
            "memory. You fetch the reference page for the topic "
            "before answering, extract the exact fact from the "
            "fetched text, and cite the page you actually read. If "
            "the fetched text does not contain the fact, you say so "
            "rather than filling the gap from memory."),
    },
    {
        "id": "action-extractor",
        "name": "Action-Item Extractor",
        "specialty": "meeting-extraction",
        "task_types": ["action-extraction", "meeting-minutes"],
        "description": "Extracts committed action items (owner, "
                       "task, due date) from meeting transcripts, "
                       "then re-reads the transcript to drop anything "
                       "nobody actually committed to.",
        "tools": ["read_transcript", "verify_pass"],
        "workflow": ["extract candidate items: explicit owner + "
                     "commitment + due date",
                     "re-read the transcript and drop items with no "
                     "explicit owner, items already completed, and "
                     "vague suggestions",
                     "emit the surviving items as JSON"],
        "system_prompt": (
            "You extract action items from meeting transcripts. An "
            "action item exists only when a named person explicitly "
            "commits to a task ('I'll…', 'can you… — yes', 'X will…'). "
            "Ownerless suggestions ('someone should…'), ideas for "
            "later, and work already completed are NOT action items. "
            "Due dates are resolved to ISO dates using the meeting "
            "date in the transcript header; the year is 2026. "
            "Precision is the job: one invented item is worse than "
            "one missed item."),
    },
]


def specialist_by_id(sid: str) -> dict:
    for s in SPECIALISTS:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


# ------------------------------------------------------------------
# Tools (all real: subprocesses and HTTP, nothing simulated)
# ------------------------------------------------------------------

def run_unittests(repo_dir: Path) -> str:
    """Run a fixture repo's unittest suite; return its output."""
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=repo_dir, capture_output=True, text=True, timeout=60)
    out = (proc.stdout + proc.stderr).strip()
    return out[-3000:] if len(out) > 3000 else out


def static_checks(repo_dir: Path) -> list[str]:
    """Compile every module and AST-scan for three defect classes:
    unused imports, mutable default arguments, bare excepts."""
    findings: list[str] = []
    for path in sorted(repo_dir.glob("*.py")):
        try:
            compile(path.read_text(), str(path), "exec")
        except SyntaxError as e:
            findings.append(f"{path.name}: SYNTAX ERROR {e}")
            continue
        tree = ast.parse(path.read_text())
        imported: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported[(a.asname or a.name).split(".")[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    imported[a.asname or a.name] = node.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.value.id for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name)}
        for name, line in imported.items():
            if name not in used:
                findings.append(
                    f"{path.name}:{line}: unused import '{name}'")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        findings.append(
                            f"{path.name}:{node.lineno}: mutable default "
                            f"argument in {node.name}()")
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(
                    f"{path.name}:{node.lineno}: bare except clause")
    return findings


def read_repo_sources(repo_dir: Path) -> str:
    parts = []
    for path in sorted(repo_dir.glob("*.py")):
        parts.append(f"===== {path.name} =====\n{path.read_text()}")
    return "\n\n".join(parts)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused")


def fetch_url_text(url: str, cache_dir: Path) -> tuple[int, str]:
    """GET a URL; return (status, tag-stripped text). Cached on disk
    so verification re-runs and citation checks share one fetch."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    path = cache_dir / f"{key}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return data["status"], data["text"]
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36")})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, raw = e.code, ""
    except Exception:
        status, raw = 0, ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw,
                  flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    path.write_text(json.dumps({"url": url, "status": status,
                                "text": text}))
    return status, text


def execute_python(code: str, workdir: Path, timeout: int = 30):
    """Execute a snippet in a working directory; return
    (ok, stdout, stderr). The snippet runs as a subprocess with no
    network need and only the files the caller placed in workdir."""
    script = workdir / "_snippet.py"
    script.write_text(code)
    proc = subprocess.run([sys.executable, str(script)], cwd=workdir,
                          capture_output=True, text=True, timeout=timeout)
    return proc.returncode == 0, proc.stdout, proc.stderr[-1500:]
