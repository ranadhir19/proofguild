"""Model access for proofguild: free-tier providers behind one seam.

Providers:
  - groq    — OpenAI-compatible chat completions via the registered
              custom.groq connector's credential-surrogate exchange.
              The code never reads or stores a key.
  - gemini  — Google AI Studio Interactions API via the registered
              custom.google-ai-studio connector. Public material only:
              the free tier may use submitted content for product
              improvement. Everything proofguild sends is synthetic
              fixture material authored for this project.
  - fake    — deterministic offline provider for tests and demos.

Every live call is cached on disk, keyed by the full request, so a
re-run never re-spends quota. A 429 from a provider raises
RateLimited and stops that provider for the rest of the process:
free-tier caps are shared across projects on this machine, and
retrying around them is how accounts get flagged.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_STOPPED: set[str] = set()


class RateLimited(Exception):
    """A provider returned 429 (or was already stopped this run)."""


class ProviderError(Exception):
    pass


@dataclass
class Response:
    text: str
    served_model: str
    usage: dict = field(default_factory=dict)
    cached: bool = False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def _post(url: str, payload: dict, connector: str, host: str) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": _UA,
               "Accept": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers, method="POST")
    add_surrogate_to_request(req, connector, allowed_hosts=[host])
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=120) as resp:
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(f"{connector}: HTTP 429") from e
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise ProviderError(f"{connector}: HTTP {e.code} {body}") from e


def _groq_chat(model: str, system: str, user: str, max_tokens: int) -> Response:
    result = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        {"model": model,
         "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user}],
         "temperature": 0, "max_tokens": max_tokens},
        "custom.groq", "api.groq.com")
    choice = (result.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    return Response(text=text, served_model=result.get("model", model),
                    usage=result.get("usage") or {})


def _gemini_chat(model: str, system: str, user: str, max_tokens: int) -> Response:
    # The Interactions API takes a single input; max_tokens is not a
    # documented input field there, so the budget is enforced by the
    # caller's prompt discipline instead. Served model is recorded
    # from the response, never assumed from the requested alias.
    mid = model if model.startswith("models/") else "models/" + model
    result = _post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        {"model": mid, "input": f"{system}\n\n{user}"},
        "custom.google-ai-studio", "generativelanguage.googleapis.com")
    text = ""
    for step in result.get("steps") or []:
        if step.get("type") == "model_output":
            for part in step.get("content") or []:
                if part.get("type") == "text":
                    text += part.get("text", "")
    usage = result.get("usage") or {}
    return Response(text=text, served_model=result.get("model", model),
                    usage={"prompt_tokens": usage.get("total_input_tokens"),
                           "completion_tokens": usage.get("total_output_tokens")})


_PROVIDERS = {"groq": _groq_chat, "gemini": _gemini_chat}


class ModelClient:
    """One provider+model, with a disk cache and a hard 429 stop."""

    def __init__(self, provider: str, model: str, cache_dir: Path):
        if provider not in _PROVIDERS and provider != "fake":
            raise ValueError(f"unknown provider {provider!r}")
        self.provider = provider
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.live_calls = 0

    def _key(self, system: str, user: str, max_tokens: int) -> str:
        blob = json.dumps({"p": self.provider, "m": self.model,
                           "s": system, "u": user, "t": 0,
                           "mt": max_tokens}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def chat(self, system: str, user: str, max_tokens: int = 2500) -> Response:
        if self.provider == "fake":
            return fake_response(system, user)
        key = self._key(system, user, max_tokens)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return Response(text=data["text"],
                            served_model=data["served_model"],
                            usage=data.get("usage", {}), cached=True)
        if self.provider in _STOPPED:
            raise RateLimited(f"{self.provider}: stopped earlier this run")
        try:
            resp = _PROVIDERS[self.provider](self.model, system, user,
                                             max_tokens)
        except RateLimited:
            _STOPPED.add(self.provider)
            raise
        self.live_calls += 1
        path.write_text(json.dumps(
            {"text": resp.text, "served_model": resp.served_model,
             "usage": resp.usage, "provider": self.provider,
             "requested_model": self.model}, indent=1))
        return resp


def fake_response(system: str, user: str) -> Response:
    """Deterministic offline stand-in.

    Understands just enough of the task formats to exercise the
    harness end to end in tests: it echoes an ANSWER of 0, an empty
    findings list, and an empty JSON array. It is an instrument for
    plumbing tests, not a competence claim — verification records
    are only ever written from live-provider runs.
    """
    if "ANSWER:" in user or "answer" in user.lower():
        text = "ANSWER: 0"
    elif "FINDING" in user:
        text = "(no findings)"
    elif "action items" in user.lower():
        text = "[]"
    else:
        text = "FAKE RESPONSE"
    return Response(text=text, served_model="fake", usage={})
