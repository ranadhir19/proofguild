# proofguild

**Verified specialists, not named ones.**

Most "specialist agent" libraries are libraries of prompts: a role
name, a system prompt, a list of tools — and no evidence that the
specialist actually outperforms a good generalist at the thing it
claims to specialise in. proofguild is a small specialist library
built on the opposite rule:

> **No specialist is listed as verified until it has beaten a strong
> generalist baseline, head-to-head on the same model, on tasks in
> its specialty, scored by deterministic checks — and the receipts
> are shipped in the registry.**

A specialist that fails the measurement is flagged `unverified`.
One that could not be fully measured is `provisional`. The router
only ever prefers `verified` specialists, and says so out loud when
it falls back to the generalist.

## The specialists (v1)

| Specialist | Real work it does | How it is scored |
|---|---|---|
| `code-reviewer` | Runs the repo's test suite and static checks, then reviews against module specs | Planted-defect checklist (file + evidence keyword), false-positive penalty |
| `data-analyst` | Writes and **executes** Python against the real CSV | Ground truth recomputed independently from the CSV |
| `researcher` | Fetches a real source first, answers only from it | Fact correctness + cited URL must resolve live and support the answer |
| `action-extractor` | Extracts committed action items, then re-reads the transcript to drop uncommitted ones | Item-level F1 vs gold (owner match + task overlap) |

## The verification contract

Rules are frozen in [`PREREGISTRATION.md`](PREREGISTRATION.md) before
any run: same provider, same model, temperature 0 for both arms; the
generalist gets the same artefact and output format, no tools.
**Verified** = ≥4 tasks scored for both arms **and** margin ≥ 0.15
**and** specialist mean ≥ 0.60. Wilson 95% intervals are reported
with every record — at n=4–5 they are wide, and the records say so.

## Current state (honest)

As of 2026-11-10, **no specialist is verified yet** — and the
registry says exactly that:

- `code-reviewer`: **provisional**. On Groq (`openai/gpt-oss-120b`),
  the first task scored specialist **0.9375** vs generalist **0.75**
  before the free-tier daily quota returned HTTP 429 mid-suite; the
  partial record is preserved in `records/code-reviewer.groq-partial.json`.
  A Gemini attempt was rate-limited on its first task. Per the
  preregistration, a 429 is a hard stop, not a retry prompt.
- `data-analyst`, `researcher`, `action-extractor`: **unmeasured**
  (suites built and scorer-tested offline; live runs wait for quota).

Run the suites yourself when quota is available:

```bash
PYTHONPATH=src python3 -m proofguild verify --provider groq --suite all
PYTHONPATH=src python3 -m proofguild list
PYTHONPATH=src python3 -m proofguild route "Please review this pull request for defects"
PYTHONPATH=src python3 -m proofguild demo
python3 validate.py
```

## Layout

- `src/proofguild/` — registry, specialists, suites + scorers,
  verification runner, router, CLI, model providers (Groq / Gemini
  free tiers via local connectors, plus an offline fake provider;
  every live call is cached on disk).
- `fixtures/` — the real artefacts: 4 small repos with 14 planted
  defects and failing tests, a 240-row orders CSV, 4 meeting
  transcripts with gold action items, stable-fact research questions.
- `registry/registry.json` — the shipped registry, competence
  records included.
- `records/` — per-specialist measurement records (the receipts).
- `tests/` — offline tests for the decision rule, router, scorers,
  tools and registry integrity.

MIT licensed.
