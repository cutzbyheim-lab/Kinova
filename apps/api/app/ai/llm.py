"""Language-model provider abstraction with per-job cost caps.

`LLM` is the interface the rest of the app uses. `ClaudeLLM` is the only provider
today; another provider only needs to implement `complete`.
"""

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.config import get_settings

Tier = Literal["fast", "smart"]


class NotConfigured(Exception):
    """A required external service has no credentials."""


class BudgetExceeded(Exception):
    """The call would push the job past its spending cap."""


@dataclass
class Usage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class Completion:
    text: str
    usage: Usage


class UsageSink(Protocol):
    def __call__(self, purpose: str, usage: Usage | None, error: str | None) -> None: ...


def _prices(tier: Tier) -> tuple[str, float, float]:
    s = get_settings()
    if tier == "smart":
        return s.model_smart, s.price_smart_in, s.price_smart_out
    return s.model_fast, s.price_fast_in, s.price_fast_out


def estimate_cost(tier: Tier, prompt_chars: int, max_tokens: int) -> float:
    _, p_in, p_out = _prices(tier)
    est_in = prompt_chars / 3.2  # conservative chars-per-token
    return (est_in * p_in + max_tokens * p_out) / 1_000_000


class ClaudeLLM:
    def __init__(self, budget_usd: float, spent_usd: float = 0.0, sink: UsageSink | None = None) -> None:
        s = get_settings()
        if not s.anthropic_configured:
            raise NotConfigured("ANTHROPIC_API_KEY is not set")
        import anthropic  # imported lazily so the app runs without the key

        self._client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=2, timeout=180)
        self.budget = budget_usd
        self.spent = spent_usd
        self._sink = sink

    def complete(self, purpose: str, tier: Tier, system: str, prompt: str, max_tokens: int) -> Completion:
        model, p_in, p_out = _prices(tier)
        est = estimate_cost(tier, len(system) + len(prompt), max_tokens)
        if self.spent + est > self.budget:
            raise BudgetExceeded(
                f"{purpose}: estimated ${est:.3f} would exceed the job cap "
                f"(${self.spent:.3f} of ${self.budget:.2f} used)"
            )
        try:
            msg = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  # network, auth, rate-limit…
            if self._sink:
                self._sink(purpose, None, f"{type(e).__name__}: {e}")
            raise
        text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
        cost = (msg.usage.input_tokens * p_in + msg.usage.output_tokens * p_out) / 1_000_000
        usage = Usage(model, msg.usage.input_tokens, msg.usage.output_tokens, round(cost, 6))
        self.spent += cost
        if self._sink:
            self._sink(purpose, usage, None)
        return Completion(text=text, usage=usage)


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (tolerates ```json fences and prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not raw:
        raise ValueError("No JSON object in model reply")
    return json.loads(raw)
