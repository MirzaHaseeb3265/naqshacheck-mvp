"""Gemini vision assistance for NaqshaCheck.

This module is advisory only. It extracts visible measurement candidates and
approximate image locations. It never makes compliance decisions.
"""
from __future__ import annotations

from io import BytesIO
import os
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


DEFAULT_GEMINI_VISION_MODEL = "gemini-3.8-flash"
MAX_IMAGE_EDGE = 1800
MAX_IMAGE_BYTES = 8 * 1024 * 1024

AllowedField = Literal[
    "road_width_ft", "plot_width_ft", "plot_depth_ft", "front_setback_ft",
    "rear_setback_ft", "left_setback_ft", "right_setback_ft",
    "covered_area_sqft", "building_height_ft", "stair_width_ft",
    "parking_spaces",
]


class GeminiServiceError(RuntimeError):
    """Raised when optional Gemini vision cannot return a usable result."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanObservation(StrictModel):
    field: AllowedField
    value: float
    unit: Literal["ft", "sqft", "count"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1)
    box_2d: list[int] | None = Field(
        default=None,
        description="Approximate evidence box [ymin,xmin,ymax,xmax], normalized 0-1000.",
    )


class PlanAnalysis(StrictModel):
    observations: list[PlanObservation] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


PLAN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "enum": [
                            "road_width_ft", "plot_width_ft", "plot_depth_ft",
                            "front_setback_ft", "rear_setback_ft",
                            "left_setback_ft", "right_setback_ft",
                            "covered_area_sqft", "building_height_ft",
                            "stair_width_ft", "parking_spaces"
                        ]
                    },
                    "value": {"type": "number"},
                    "unit": {"type": "string", "enum": ["ft", "sqft", "count"]},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "evidence": {"type": "string"},
                    "box_2d": {
                        "type": ["array", "null"],
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4
                    }
                },
                "required": ["field", "value", "unit", "confidence", "evidence", "box_2d"]
            }
        },
        "uncertainties": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["observations", "uncertainties"]
}


def resolve_gemini_key(explicit_key: str | None = None) -> str | None:
    if explicit_key:
        return explicit_key.strip() or None
    return os.getenv("GEMINI_API_KEY") or None


def gemini_is_configured(explicit_key: str | None = None) -> bool:
    return bool(resolve_gemini_key(explicit_key)) and genai is not None


def gemini_vision_model() -> str:
    return os.getenv("GEMINI_VISION_MODEL", DEFAULT_GEMINI_VISION_MODEL)


def _prepare_image(image: Image.Image) -> tuple[bytes, str]:
    prepared = image.convert("RGB")
    if max(prepared.size) > MAX_IMAGE_EDGE:
        prepared.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)

    quality = 88
    while True:
        buf = BytesIO()
        prepared.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX_IMAGE_BYTES or quality <= 55:
            return data, "image/jpeg"
        quality -= 8


def _safe_error(error: Exception) -> str:
    # Do not include request headers, credentials, or arbitrary object reprs.
    message = str(error).replace("\n", " ").strip()
    return message[:500] if message else error.__class__.__name__


def test_gemini_connection(*, api_key: str | None = None, model: str | None = None) -> dict:
    key = resolve_gemini_key(api_key)
    result = {
        "secret_detected": bool(key),
        "sdk_available": genai is not None,
        "authenticated": False,
        "model": model or gemini_vision_model(),
        "message": "",
    }
    if not key:
        result["message"] = "GEMINI_API_KEY was not found."
        return result
    if genai is None:
        result["message"] = "google-genai is not installed."
        return result

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=result["model"],
            contents="Reply with the single word OK.",
        )
        result["authenticated"] = bool(getattr(response, "text", ""))
        result["message"] = "Gemini connection succeeded." if result["authenticated"] else "Gemini returned no text."
    except Exception as error:
        result["message"] = f"Gemini connection failed: {_safe_error(error)}"
    return result


def analyze_plan_image(
    image: Image.Image, *, api_key: str | None = None, model: str | None = None
) -> PlanAnalysis:
    key = resolve_gemini_key(api_key)
    if not key:
        raise GeminiServiceError("Gemini vision is not configured. Add GEMINI_API_KEY to Streamlit Secrets.")
    if genai is None or types is None:
        raise GeminiServiceError("google-genai is not installed. Deterministic checking remains available.")

    image_bytes, mime = _prepare_image(image)
    prompt = """
You are the vision extraction layer of NaqshaCheck, an advisory building-plan
pre-submission checker.

Read ONLY labels, dimensions and information visibly present in the supplied
architectural plan. Do not infer a dimension from drawing scale. Do not decide
whether the plan complies with any law or authority rule.

Return measurement candidates only for these fields:
road_width_ft, plot_width_ft, plot_depth_ft, front_setback_ft, rear_setback_ft,
left_setback_ft, right_setback_ft, covered_area_sqft, building_height_ft,
stair_width_ft, parking_spaces.

For each reliable observation:
- value must be numeric.
- unit must be ft, sqft, or count.
- confidence is extraction confidence from 0 to 1, not compliance confidence.
- evidence briefly quotes/describes the visible label.
- box_2d should locate the visible evidence as [ymin,xmin,ymax,xmax], normalized
  to 0-1000. If a reliable location cannot be provided, use null.

If a relevant label is unreadable, ambiguous or absent, do not guess. Add a
short statement to uncertainties instead.
""".strip()

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model or gemini_vision_model(),
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=PLAN_RESPONSE_SCHEMA,
                temperature=0,
            ),
        )
        raw = getattr(response, "text", None)
        if not raw:
            raise GeminiServiceError("Gemini returned an empty plan-analysis response.")
        return PlanAnalysis.model_validate_json(raw)
    except ValidationError as error:
        detail = str(error).replace("\n", " ")[:500]
        raise GeminiServiceError(
            f"Gemini returned plan data that failed validation: {detail}. "
            "Deterministic checking remains available."
        ) from error
    except GeminiServiceError:
        raise
    except Exception as error:
        raise GeminiServiceError(
            f"Gemini plan analysis failed: {_safe_error(error)}. "
            "Deterministic checking remains available."
        ) from error



class FindingExplanation(StrictModel):
    rule_id: str
    priority: Literal["high", "medium", "low"]
    explanation: str
    correction_guidance: str


class FindingsExplanation(StrictModel):
    summary: str
    items: list[FindingExplanation] = Field(default_factory=list)
    disclaimer: str


EXPLANATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "explanation": {"type": "string"},
                    "correction_guidance": {"type": "string"}
                },
                "required": ["rule_id", "priority", "explanation", "correction_guidance"]
            }
        },
        "disclaimer": {"type": "string"}
    },
    "required": ["summary", "items", "disclaimer"]
}


def explain_findings(
    confirmed_project: dict,
    findings: list[dict],
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> FindingsExplanation:
    """Explain deterministic findings without recalculating or overriding them."""
    key = resolve_gemini_key(api_key)
    if not key:
        raise GeminiServiceError("Gemini is not configured. Add GEMINI_API_KEY to Streamlit Secrets.")
    if genai is None or types is None:
        raise GeminiServiceError("google-genai is not installed. Deterministic checking remains available.")

    # Only deterministic/human-confirmed data is sent. No plan image is required here.
    import json
    payload = {
        "confirmed_project_measurements": confirmed_project,
        "deterministic_findings": findings,
    }
    prompt = """
You explain results produced by NaqshaCheck's deterministic building-plan preflight engine.

STRICT BOUNDARIES:
- Do NOT decide, recalculate, reverse, upgrade, or downgrade any compliance status.
- Do NOT invent rules, measurements, citations, exceptions, legal conclusions, or authority requirements.
- Use ONLY the supplied human-confirmed measurements and deterministic findings.
- Preserve rule IDs and citations exactly as supplied.
- "Passed selected preflight check" means only that the selected deterministic check passed.
- Use "Likely violation" for a supplied violation status.
- Use "Needs information" or "Professional review required" only when supplied by the deterministic result.
- Never say legally approved, government approved, fully compliant, or guaranteed acceptance.
- correction_guidance must explain what the supplied finding indicates should be reviewed/corrected; do not redesign the building.
- Keep explanations concise and practical.
- The disclaimer must state that NaqshaCheck is an advisory pre-submission review and does not issue official approval, replace a licensed architect, or guarantee authority acceptance.

Return only the requested structured JSON.
DATA:
""" + json.dumps(payload, ensure_ascii=False, default=str)

    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model or gemini_vision_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=EXPLANATION_RESPONSE_SCHEMA,
            ),
        )
        raw = getattr(response, "text", None)
        if not raw:
            raise GeminiServiceError("Gemini returned an empty findings explanation.")
        return FindingsExplanation.model_validate_json(raw)
    except ValidationError as error:
        detail = str(error).replace("\n", " ")[:500]
        raise GeminiServiceError(
            f"Gemini returned an explanation that failed validation: {detail}. "
            "Deterministic findings remain unchanged."
        ) from error
    except GeminiServiceError:
        raise
    except Exception as error:
        raise GeminiServiceError(
            f"Gemini explanation failed: {_safe_error(error)}. "
            "Deterministic findings remain unchanged."
        ) from error

def draw_candidate_overlay(image: Image.Image, analysis: PlanAnalysis) -> Image.Image:
    """Draw blue evidence boxes for AI candidates; no compliance colors are assigned here."""
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    width, height = overlay.size
    for obs in analysis.observations:
        if not obs.box_2d or len(obs.box_2d) != 4:
            continue
        ymin, xmin, ymax, xmax = [max(0, min(1000, int(v))) for v in obs.box_2d]
        if ymax <= ymin or xmax <= xmin:
            continue
        x1, y1 = int(xmin / 1000 * width), int(ymin / 1000 * height)
        x2, y2 = int(xmax / 1000 * width), int(ymax / 1000 * height)
        draw.rectangle((x1, y1, x2, y2), outline=(30, 100, 220), width=max(2, width // 500))
        label = f"{obs.field}: {obs.value:g} {obs.unit}"
        text_y = max(0, y1 - 18)
        draw.rectangle((x1, text_y, min(width, x1 + max(140, len(label) * 7)), y1), fill=(255, 255, 255))
        draw.text((x1 + 3, text_y + 2), label, fill=(30, 100, 220))
    return overlay
