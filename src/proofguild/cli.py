"""proofguild command line: list / verify / route / demo."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .registry import load_registry
from .router import route


def _cmd_list(_args) -> int:
    reg = load_registry()
    for s in reg["specialists"]:
        c = s.get("competence", {})
        status = c.get("status", "unmeasured")
        extra = ""
        if status in ("verified", "unverified", "provisional"):
            extra = (f" — specialist {c.get('specialist_score')} vs "
                     f"generalist {c.get('generalist_score')} "
                     f"(margin {c.get('margin'):+}) on "
                     f"{c.get('tasks')} tasks [{c.get('suite')}]")
        flag = {"verified": "VERIFIED  ", "unverified": "UNVERIFIED",
                "provisional": "PROVISIONAL",
                "unmeasured": "UNMEASURED"}[status]
        print(f"[{flag}] {s['id']:<18} {s['specialty']:<18}{extra}")
    return 0


def _cmd_verify(args) -> int:
    from .verify import run_verification
    summary = run_verification(provider=args.provider,
                               model=args.model, only_suite=args.suite)
    print(json.dumps(summary, indent=1))
    return 0


def _cmd_route(args) -> int:
    result = route(" ".join(args.job))
    print(f"decision: {result['decision']}"
          + (f" -> {result['specialist_id']}"
             if result["specialist_id"] else ""))
    print(f"reason:   {result['reason']}")
    return 0


def _cmd_demo(_args) -> int:
    """Offline smoke: registry integrity + router behaviour."""
    reg = load_registry()
    jobs = [
        "Please review this pull request for defects",
        "Analyse the revenue in this sales CSV by region",
        "Research when the Eiffel Tower was completed and cite sources",
        "Pull the action items out of the meeting transcript",
        "Write a haiku about autumn rain",
    ]
    for job in jobs:
        r = route(job, reg)
        print(f"job: {job}\n  -> {r['decision']}"
              + (f" ({r['specialist_id']})" if r["specialist_id"]
                 else "") + f"\n  {r['reason']}")
    print(f"proofguild {__version__} demo OK "
          f"({len(reg['specialists'])} specialists registered)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="proofguild",
        description="A specialist agent library whose specialists "
                    "ship their measured competence records.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list specialists with their "
                                "competence status")
    p_verify = sub.add_parser("verify", help="run the verification "
                                             "harness (live, cached)")
    p_verify.add_argument("--provider", default="groq",
                          choices=["groq", "gemini"])
    p_verify.add_argument("--model", default=None)
    p_verify.add_argument("--suite", default=None)
    p_route = sub.add_parser("route", help="route a job by measured "
                                           "competence")
    p_route.add_argument("job", nargs="+")
    sub.add_parser("demo", help="offline smoke demo")
    args = parser.parse_args(argv)
    return {"list": _cmd_list, "verify": _cmd_verify,
            "route": _cmd_route, "demo": _cmd_demo}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
