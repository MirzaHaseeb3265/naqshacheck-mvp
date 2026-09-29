"""Optional Groq AI assistance for NaqshaCheck.

AI output is advisory only. This module never runs compliance decisions and never
activates rule drafts. All returned data is validated with Pydantic before use.
"""
from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any, Callable, TypeVar

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:
    from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq, RateLimitError
except ImportError:  # Keeps deterministic features importable without the optional client.
    Groq = None  # type: ignore[assignment]
    APIConnectionError = APIStatusError = APITimeoutError = RateLimitError = Exception  # type: ignore[misc,assignment]


DEFAULT_TEXT_MODEL = "openai/gpt-oss-20b"
DEFAULT_VISION_MODEL = "qwen/qwen3.8-27b"
MAX_IMAGE_EDGE = 1800
MAX_IMAGE_BYTES = 4 * 1024 * 1024


class AIUnavailableError(RuntimeError):
    """Raised when optional AI functionality is not configured."""


class AIServiceError(RuntimeError):
    """Raised when Groq cannot return a usable advisory response."""


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanObservation(StrictAIModel):
    field: str
    value: float | int | str
    unit: str
    confidence: float = Field(ge=0, le=1)
    evidence: str


class PlanAnalysis(StrictAIModel):
    observations: list[PlanObservation]
    uncertainties: list[str]


class CandidateRule(StrictAIModel):
    title: str
    field: str
    operator: str
    value: float
    unit: str
    citation: str
    applicability: str
    exceptions: str
    status: str


class RuleDraftResponse(StrictAIModel):
    rules: list[CandidateRule]
    uncertainties: list[str]


class ExplanationItem(StrictAIModel):
    rule_id: str
    priority: str
    explanation: str
    correction_guidance: str


class ResultExplanation(StrictAIModel):
    items: list[ExplanationItem] = Field(default_factory=list)
    disclaimer: str


T = TypeVar("T", bound=BaseModel)


def resolve_api_key(explicit_key: str | None = None) -> str | None:
    """Resolve a key without ever requiring Streamlit to be installed/configured."""
    if explicit_key:
        return explicit_key.strip() or None
    return os.getenv("GROQ_API_KEY") or None


def ai_is_configured(explicit_key: str | None = None) -> bool:
    return bool(resolve_api_key(explicit_key)) and Groq is not None
