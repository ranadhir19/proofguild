# Preregistration — proofguild verification rules

Frozen 2026-11-10, before any verification run. These rules do not move
after results are seen. If a rule turns out to be unworkable, the
deviation is recorded here with a date and a reason, and the affected
specialist is marked `provisional`, never silently re-ruled.

## The claim under test

A specialist in this library is a configuration: a domain system
prompt, a tool workflow, and an output contract, all running on the
**same underlying model** as the generalist baseline. The claim a
specialist makes is narrow and falsifiable:

> On tasks in my specialty, my configuration scores higher than a
> strong generalist prompt on the same model given the same primary
> artefact.

If the measurement does not support the claim, the specialist is
flagged `unverified` in the registry and the router will not prefer
it. There is no third outcome in which an unmeasured or beaten
specialist is presented as verified.

## Arms

- **Specialist arm**: the specialist's system prompt + its tool
  workflow executed for real (tests actually run, code actually
  executed, pages actually fetched, transcript actually re-read)
  + its output contract.
- **Generalist arm**: a strong generic system prompt ("You are an
  expert assistant…"), the same model, the same temperature (0),
  the same primary artefact in context, the same output format
  requested in the task statement. No tools, no domain workflow.
- Both arms in a suite use **one provider and one requested model**.
  If a provider rate-limits mid-suite (HTTP 429), that provider is
  stopped for the rest of the run; the suite may restart on the
  other provider with both arms re-run there, or be left
  `provisional`. Arms are never mixed across providers in one
  comparison.

## Suites (v1)

| Suite | Tasks | Scorer (deterministic) |
|---|---|---|
| code-review | 4 fixture repos with planted defects | defect checklist: credit per defect when a finding names the right file and carries an evidence keyword; −0.25 per unmatched extra finding; clean files are false-positive bait |
| data-analysis | 5 questions on one 240-row CSV | ground truth computed from the CSV by the scorer's own independent code path; numeric match within tolerance (counts exact, money ≤1.5% relative, percentages ≤0.5 absolute) |
| research-citations | 4 factual questions | 0.5 × fact correctness (gold value present in answer) + 0.5 × citation quality (1.0 if ≥1 cited URL resolves live with HTTP 200 **and** its text contains the gold value; 0.4 if ≥1 resolves but none supports; 0 otherwise) |
| action-extraction | 4 meeting transcripts | item-level F1 against gold action items; an item matches when the owner matches (normalised) and task-token overlap ≥ 0.4; due-date agreement reported per matched item |

## Decision rule

For each specialist, over its suite:

- **verified** — at least 4 tasks scored for both arms, specialist
  mean score − generalist mean score ≥ **0.15**, and specialist mean
  ≥ **0.60**.
- **unverified** — both arms fully scored but the rule above is not
  met (including ties and negative margins).
- **provisional** — fewer than 4 tasks scored for either arm, or a
  provider inconsistency inside the suite. Provisional specialists
  are labelled as such and are **not** router-eligible.

Wilson 95% intervals (task-level, score treated as fractional
successes) are reported for both arms in every record. At n = 4–5
the intervals are wide; that is stated in the record rather than
hidden, and the margin rule above — not interval overlap — is the
decision rule, chosen in advance.

## Router rule

The router may only *prefer* a specialist whose status is
`verified`, choosing the highest measured margin among verified
specialists claiming the job's task type. If none is verified for
the type, the router returns the generalist and says so in plain
language. It never presents an unverified or provisional specialist
as a verified pick.

## Model-call discipline

Free tiers only. Every live call is cached on disk keyed by
(provider, requested model, system prompt, user prompt, temperature,
max_tokens); a cache hit never re-spends quota. A 429 from a
provider is a hard stop for that provider for the rest of the run.
Served-model identifiers are recorded from provider responses,
because aliases lie.
