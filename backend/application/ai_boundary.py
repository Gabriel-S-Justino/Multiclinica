"""Provider-neutral intent boundary. Deliberately no domain mutation executor."""

import re
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Intent(StrEnum):
    MENU = "menu"
    BOOK = "book"
    SERVICES = "services"
    HUMAN = "human"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    intent: Intent
    needs_clarification: bool
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class SafeTurn:
    """Construct only after data policy approval; never include identifiers/history."""

    text: str
    state: str
    allowed: frozenset[Intent]


class IntentInterpreter(Protocol):
    def interpret(
        self, turn: SafeTurn, *, timeout_seconds: float, max_output_tokens: int
    ) -> str: ...


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    data_policy_reference: str | None = None
    contract_reference: str | None = None
    timeout_seconds: float = 5
    max_output_tokens: int = 128

    def validate(self) -> None:
        if not 0 < self.timeout_seconds <= 10 or not 1 <= self.max_output_tokens <= 512:
            raise ValueError("invalid_ai_limits")
        if self.enabled and not all(
            (self.provider, self.model, self.data_policy_reference, self.contract_reference)
        ):
            raise ValueError("ai_policy_incomplete")


def clinical_language(text: str) -> bool:
    # Deterministic precaution; not a medical triage classifier or a diagnostic claim.
    return bool(
        re.search(
            r"\b(emerg[eê]ncia|urg[eê]ncia|sintoma|diagn[oó]stico|medicamento|rem[eé]dio|tratamento|exame|dor|sangramento|suic[ií]dio)\b|falta de ar",
            text,
            re.IGNORECASE,
        )
    )


def eligible_turn(turn: SafeTurn) -> bool:
    return (
        turn.state == "MENU"
        and 0 < len(turn.text) <= 500
        and not clinical_language(turn.text)
        and re.search(r"@|https?://|\d", turn.text) is None
    )


def interpret_safely(
    provider: IntentInterpreter | None, config: AIConfig, turn: SafeTurn, *, quota_reserved: bool
) -> IntentResult:
    fallback = IntentResult(intent=Intent.UNKNOWN, needs_clarification=True, confidence=0.0)
    config.validate()
    if not config.enabled or provider is None or not quota_reserved or not eligible_turn(turn):
        return fallback
    started = time.monotonic()
    try:
        raw = provider.interpret(
            turn, timeout_seconds=config.timeout_seconds, max_output_tokens=config.max_output_tokens
        )
        if time.monotonic() - started > config.timeout_seconds or len(raw) > 4096:
            return fallback
        result = IntentResult.model_validate_json(raw)
    except Exception:
        # Provider failures may contain sensitive text; never surface or persist it.
        return fallback
    if result.intent not in turn.allowed or result.confidence < 0.8 or result.needs_clarification:
        return fallback
    return result
