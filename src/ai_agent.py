- "uncertainties" MUST be a JSON array of strings. Use [] when there are none.
- Every observation MUST contain exactly: field, value, unit, confidence, evidence.
- "field" MUST be one of:
  road_width_ft, plot_width_ft, plot_depth_ft, front_setback_ft, rear_setback_ft,
  left_setback_ft, right_setback_ft, covered_area_sqft, building_height_ft,
  stair_width_ft, parking_spaces.
- "value" MUST be a JSON number, never text such as "5 ft".
- "unit" MUST be a short string such as "ft", "sqft", or "count".
- "confidence" MUST be a JSON number from 0.0 to 1.0.
- "evidence" MUST briefly identify the visible label/dimension supporting the value.
- If a value is ambiguous, unreadable, or not visibly stated, DO NOT guess it.
  Put the issue in "uncertainties" instead.
- Confidence describes extraction confidence only, never regulatory compliance.
""".strip()

    def messages(retry: bool, validation_feedback: str = "") -> list[dict[str, Any]]:
        retry_text = ""
        if retry:
            retry_text = (
                "\n\nIMPORTANT RETRY: Your previous response could not be validated. "
                "Return ONLY the exact JSON structure specified above. Do not add keys, "
                "markdown, commentary, null observations, or numeric values encoded as text."
            )
            if validation_feedback:
                retry_text += f" Validation problem: {validation_feedback[:300]}"
        return [{"role": "user", "content": [
            {"type": "text", "text": prompt + retry_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}]

    client = _client(api_key)
    last_error: Exception | None = None
    validation_feedback = ""

    for attempt in range(2):
        try:
            completion = client.chat.completions.create(
                model=model or vision_model(),
                messages=messages(attempt == 1, validation_feedback),
                response_format={"type": "json_object"},
                reasoning_effort="none",
                temperature=0,
                max_completion_tokens=1800,
            )
            return _parse_content(completion.choices[0].message.content, PlanAnalysis)
        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            last_error = error
            validation_feedback = str(error).replace("\n", " ")
            if attempt == 0:
                continue
            safe_feedback = validation_feedback[:450]
            raise AIServiceError(
                "Groq returned plan-extraction JSON that did not match the required format "
                f"after one retry. Validation detail: {safe_feedback}"
            ) from error
        except RateLimitError as error:
            raise AIServiceError("Groq rate limit reached. Please wait briefly and try again.") from error
        except APITimeoutError as error:
            raise AIServiceError("Groq timed out while analyzing the plan. Deterministic checking remains available.") from error
        except APIConnectionError as error:
            raise AIServiceError("Could not connect to Groq. Deterministic checking remains available.") from error
        except APIStatusError as error:
            status = getattr(error, "status_code", "unknown")
            detail = ""
            body = getattr(error, "body", None)
            if isinstance(body, dict):
                err = body.get("error", body)
                if isinstance(err, dict):
                    detail = str(err.get("message", ""))
            safe_detail = detail[:350].replace("\n", " ") if detail else "No additional error detail was returned."
            raise AIServiceError(
                f"Groq vision request returned API status {status}: {safe_detail} "
                "Deterministic checking remains available."
            ) from error
        except Exception as error:
            raise AIServiceError("Groq plan analysis failed. Deterministic checking remains available.") from error

<<<<<<< HEAD


def test_groq_connection(*, api_key: str | None = None, vision_model_id: str | None = None) -> dict[str, Any]:
    """Safely test Groq authentication and whether the configured vision model is listed.

    Never returns or logs the API key. This diagnostic is independent of plan analysis.
    """
    key = resolve_api_key(api_key)
    if not key:
        return {"secret_detected": False, "key_format_ok": False, "authenticated": False, "vision_model_available": False, "vision_model": vision_model_id or vision_model(), "message": "GROQ_API_KEY was not detected."}
    result = {
        "secret_detected": True,
        "key_format_ok": key.startswith("gsk_"),
        "authenticated": False,
        "vision_model_available": False,
        "vision_model": vision_model_id or vision_model(),
        "message": "",
    }
    if Groq is None:
        result["message"] = "The Groq Python package is not installed."
        return result
    try:
        response = _client(key, timeout_seconds=15.0).models.list()
        model_ids = {getattr(item, "id", None) for item in getattr(response, "data", [])}
        result["authenticated"] = True
        result["vision_model_available"] = result["vision_model"] in model_ids
        result["message"] = "Groq authentication succeeded."
        return result
    except RateLimitError:
        result["message"] = "Groq accepted the request path but rate-limited it. Try again shortly."
    except APITimeoutError:
        result["message"] = "Groq connection test timed out."
    except APIConnectionError:
        result["message"] = "Could not connect to Groq from this Streamlit deployment."
    except APIStatusError as error:
        status = getattr(error, "status_code", "unknown")
        result["message"] = f"Groq authentication test returned API status {status}."
    except Exception:
        result["message"] = "Groq connection test failed unexpectedly."
    return result


def prepare_image(image: Image.Image) -> tuple[bytes, str]:
    """Resize and compress a plan image before transmission."""
    prepared = image.convert("RGB")
    prepared.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
    quality = 88
    while quality >= 55:
        buffer = BytesIO()
        prepared.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= MAX_IMAGE_BYTES:
            return data, "image/jpeg"
        quality -= 10
    raise AIServiceError("The rendered plan image is too large for safe AI transmission after resizing.")


def analyze_plan_image(image: Image.Image, *, api_key: str | None = None, model: str | None = None) -> PlanAnalysis:
    image_bytes, mime = prepare_image(image)
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    prompt = """
You are an extraction assistant for an advisory building-plan pre-submission tool.
Read ONLY information visibly present in the supplied plan image. Do not infer hidden
dimensions, legal compliance, or authority requirements.

Return ONLY one valid JSON object, with no markdown, prose, or code fences, using
EXACTLY this top-level structure:

{
  "observations": [
    {
      "field": "front_setback_ft",
      "value": 5.0,
      "unit": "ft",
      "confidence": 0.91,
      "evidence": "Visible 5'-0\" dimension label near the front boundary"
    }
  ],
  "uncertainties": [
    "Rear boundary dimension is not clearly readable"
  ]
}

JSON CONTRACT:
- "observations" MUST be a JSON array. Use [] when nothing reliable is visible.
- "uncertainties" MUST be a JSON array of strings. Use [] when there are none.
- Every observation MUST contain exactly: field, value, unit, confidence, evidence.
- "field" MUST be one of:
  road_width_ft, plot_width_ft, plot_depth_ft, front_setback_ft, rear_setback_ft,
  left_setback_ft, right_setback_ft, covered_area_sqft, building_height_ft,
  stair_width_ft, parking_spaces.
- "value" MUST be a JSON number, never text such as "5 ft".
- "unit" MUST be a short string such as "ft", "sqft", or "count".
- "confidence" MUST be a JSON number from 0.0 to 1.0.
- "evidence" MUST briefly identify the visible label/dimension supporting the value.
- If a value is ambiguous, unreadable, or not visibly stated, DO NOT guess it.
  Put the issue in "uncertainties" instead.
- Confidence describes extraction confidence only, never regulatory compliance.
""".strip()

    def messages(retry: bool, validation_feedback: str = "") -> list[dict[str, Any]]:
        retry_text = ""
        if retry:
            retry_text = (
                "\n\nIMPORTANT RETRY: Your previous response could not be validated. "
                "Return ONLY the exact JSON structure specified above. Do not add keys, "
                "markdown, commentary, null observations, or numeric values encoded as text."
            )
            if validation_feedback:
                retry_text += f" Validation problem: {validation_feedback[:300]}"
        return [{"role": "user", "content": [
            {"type": "text", "text": prompt + retry_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}]

    client = _client(api_key)
    last_error: Exception | None = None
    validation_feedback = ""

    for attempt in range(2):
        try:
            completion = client.chat.completions.create(
                model=model or vision_model(),
                messages=messages(attempt == 1, validation_feedback),
                response_format={"type": "json_object"},
                reasoning_effort="none",
                temperature=0,
                max_completion_tokens=1800,
            )
            return _parse_content(completion.choices[0].message.content, PlanAnalysis)
        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            last_error = error
            validation_feedback = str(error).replace("\n", " ")
            if attempt == 0:
                continue
            safe_feedback = validation_feedback[:450]
            raise AIServiceError(
                "Groq returned plan-extraction JSON that did not match the required format "
                f"after one retry. Validation detail: {safe_feedback}"
            ) from error
        except RateLimitError as error:
            raise AIServiceError("Groq rate limit reached. Please wait briefly and try again.") from error
        except APITimeoutError as error:
            raise AIServiceError("Groq timed out while analyzing the plan. Deterministic checking remains available.") from error
        except APIConnectionError as error:
            raise AIServiceError("Could not connect to Groq. Deterministic checking remains available.") from error
        except APIStatusError as error:
            status = getattr(error, "status_code", "unknown")
            detail = ""
            body = getattr(error, "body", None)
            if isinstance(body, dict):
                err = body.get("error", body)
                if isinstance(err, dict):
                    detail = str(err.get("message", ""))
            safe_detail = detail[:350].replace("\n", " ") if detail else "No additional error detail was returned."
            raise AIServiceError(
                f"Groq vision request returned API status {status}: {safe_detail} "
                "Deterministic checking remains available."
            ) from error
        except Exception as error:
            raise AIServiceError("Groq plan analysis failed. Deterministic checking remains available.") from error

=======
>>>>>>> b7646d04a936deadf00e1791055cc8533f2d348e
    raise AIServiceError("Groq plan analysis failed.") from last_error


def extract_candidate_rules(
    text_chunk: str, *, authority: str, source_label: str, api_key: str | None = None, model: str | None = None
) -> RuleDraftResponse:
    prompt = (
        f"Extract candidate numerical requirements from this {authority} regulation excerpt. "
        "Do not invent requirements. Every candidate must have an exact citation using the supplied source/page labels. "
        "Return only explicit numerical requirements with operator, value, unit, applicability, and exceptions. "
        "Every rule is an AI-DRAFT requiring licensed-architect review and must never be treated as active law.\n\n"
        f"SOURCE: {source_label}\n\n{text_chunk}"
    )

    def messages(retry: bool) -> list[dict[str, Any]]:
        suffix = "\nPrevious output was malformed; return only schema-valid data." if retry else ""
        return [{"role": "user", "content": prompt + suffix}]

    result = _call_structured(
        client=_client(api_key), model=model or text_model(), messages_factory=messages,
        schema=RuleDraftResponse, schema_name="rule_drafts", max_tokens=3000, reasoning_effort="low",
    )
    for rule in result.rules:
        rule.status = "AI-DRAFT"
    return result


def explain_findings(
    payload: dict[str, Any], *, api_key: str | None = None, model: str | None = None
) -> ResultExplanation:
    prompt = (
        "Explain the supplied deterministic preflight findings concisely and in priority order. "
        "Use only the supplied confirmed measurements, findings, rule IDs, citations, and calculated differences. "
        "Do not add rules, measurements, legal conclusions, or recalculate/override any finding. "
        "Use advisory wording such as likely violation, passed selected preflight check, needs information, or "
        "professional review required.\n\nDATA:\n" + json.dumps(payload, ensure_ascii=False)
    )

    def messages(retry: bool) -> list[dict[str, Any]]:
        suffix = "\nPrevious output was malformed; return only schema-valid data." if retry else ""
        return [{"role": "user", "content": prompt + suffix}]

    return _call_structured(
        client=_client(api_key), model=model or text_model(), messages_factory=messages,
        schema=ResultExplanation, schema_name="result_explanation", max_tokens=1800, reasoning_effort="low",
    )
