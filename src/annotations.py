from __future__ import annotations

from typing import Iterable, Any

from PIL import Image, ImageDraw, ImageFont

from .models import Finding, Status


# Deterministic rule fields do not always have the same name as Gemini's visible
# measurement fields. These aliases let us reuse Gemini only for location while
# Python findings determine the compliance colour/status.
FINDING_TO_OBSERVATION_FIELDS = {
    "front_setback_ft": ("front_setback_ft",),
    "rear_setback_ft": ("rear_setback_ft",),
    "left_setback_ft": ("left_setback_ft",),
    "right_setback_ft": ("right_setback_ft",),
    "covered_area_sqft": ("covered_area_sqft",),
    "coverage_percent": ("covered_area_sqft",),
    "building_height_ft": ("building_height_ft",),
    "stair_width_ft": ("stair_width_ft",),
    "parking_spaces": ("parking_spaces",),
    "road_width_ft": ("road_width_ft",),
    "plot_width_ft": ("plot_width_ft",),
    "plot_depth_ft": ("plot_depth_ft",),
    # For the 10-Marla rule, 5 ft is required on at least one side. The finding
    # is based on max(left, right), so either visible side measurement may be
    # used as evidence; the deterministic engine still decides pass/fail.
    "max_side_setback_ft": ("left_setback_ft", "right_setback_ft"),
}

STATUS_STYLE = {
    Status.PASS: ((7, 148, 85), "PASSED"),
    Status.REVIEW: ((245, 158, 11), "NEEDS REVIEW"),
    Status.VIOLATION: ((220, 38, 38), "LIKELY VIOLATION"),
}
BLUE = (30, 100, 220)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _observation_box(obs: Any, width: int, height: int):
    box = getattr(obs, "box_2d", None)
    if not box or len(box) != 4:
        return None
    ymin, xmin, ymax, xmax = [max(0, min(1000, int(v))) for v in box]
    if ymax <= ymin or xmax <= xmin:
        return None
    return (
        int(xmin / 1000 * width), int(ymin / 1000 * height),
        int(xmax / 1000 * width), int(ymax / 1000 * height),
    )


def _draw_tag(draw: ImageDraw.ImageDraw, box, text: str, color, image_size):
    x1, y1, x2, y2 = box
    width, height = image_size
    line_width = max(3, width // 300)
    draw.rectangle(box, outline=color, width=line_width)

    font = _font(max(12, min(22, width // 55)), bold=True)
    pad = max(4, width // 350)
    # Keep labels short enough to remain useful on phone-sized previews.
    text = text[:90]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = min(max(0, x1), max(0, width - tw - 2 * pad))
    ty = y1 - th - 2 * pad
    if ty < 0:
        ty = min(height - th - 2 * pad, y2 + 2)
    draw.rectangle((tx, ty, tx + tw + 2 * pad, ty + th + 2 * pad), fill=(*color, 225))
    draw.text((tx + pad, ty + pad), text, fill="white", font=font)


def annotate_plan(
    image: Image.Image,
    findings: list[Finding],
    *,
    rules: Iterable[Any] | None = None,
    analysis: Any | None = None,
    confirmed_fields: Iterable[str] | None = None,
) -> Image.Image:
    """Create an advisory compliance overlay.

    Gemini observations supply only approximate evidence locations. Colours and
    labels come exclusively from deterministic findings. Unconfirmed AI boxes
    remain blue and are never presented as compliance results.
    """
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    width, height = canvas.size

    violations = [item for item in findings if item.status == Status.VIOLATION]
    banner_color = (154, 36, 36) if violations else (7, 148, 85)
    banner_text = (
        "LIKELY VIOLATIONS — ARCHITECT REVIEW REQUIRED"
        if violations else
        "PASSED SELECTED PREFLIGHT CHECKS — ADVISORY ONLY"
    )
    banner_h = max(44, min(72, height // 10))
    draw.rectangle((0, 0, width, banner_h), fill=(*banner_color, 225))
    draw.text((14, max(8, banner_h // 4)), banner_text, fill="white", font=_font(max(13, width // 48), True))

    if analysis is None:
        # Backward-compatible summary if no Gemini location data exists.
        y = banner_h + 10
        font = _font(max(12, width // 60))
        for item in violations[:6]:
            draw.text((18, y), f"• {item.title}: {item.actual} {item.unit}; required {item.required} {item.unit}", fill=(154, 36, 36), font=font)
            y += max(20, width // 35)
        return canvas

    observations = list(getattr(analysis, "observations", []) or [])
    confirmed = set(confirmed_fields or [])
    rules_by_id = {getattr(rule, "id", None): rule for rule in (rules or [])}

    # Build field -> deterministic finding. Rule.field is the authoritative link.
    finding_by_obs_field: dict[str, Finding] = {}
    for finding in findings:
        rule = rules_by_id.get(finding.rule_id)
        if rule is None:
            continue
        for obs_field in FINDING_TO_OBSERVATION_FIELDS.get(getattr(rule, "field", ""), (getattr(rule, "field", ""),)):
            if obs_field:
                finding_by_obs_field[obs_field] = finding

    for obs in observations:
        box = _observation_box(obs, width, height)
        if box is None:
            continue
        field = getattr(obs, "field", "")
        finding = finding_by_obs_field.get(field)

        # A compliance colour is allowed only when the user explicitly confirmed
        # that AI field. Everything else stays an AI candidate in blue.
        if finding is None or field not in confirmed:
            _draw_tag(draw, box, f"AI candidate: {field}", BLUE, (width, height))
            continue

        color, status_text = STATUS_STYLE[finding.status]
        actual = finding.actual
        unit = finding.unit
        label = f"{status_text}: {finding.title} | {actual} {unit} | required {finding.required} {unit}"
        _draw_tag(draw, box, label, color, (width, height))

    return canvas
