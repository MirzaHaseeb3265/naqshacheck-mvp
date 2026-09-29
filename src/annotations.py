from PIL import Image, ImageDraw

from .models import Finding, Rule, Status


def annotate_plan(image: Image.Image, findings: list[Finding]) -> Image.Image:
    """Fallback summary banner when no AI evidence coordinates are available."""
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    violations = [item for item in findings if item.status == Status.VIOLATION]
    if not violations:
        draw.rectangle((0, 0, canvas.width, 70), fill=(11, 143, 85, 225))
        draw.text((20, 22), "Passed selected preflight checks — advisory only", fill="white")
        return canvas

    banner_height = min(55 + 30 * len(violations), max(110, canvas.height // 3))
    draw.rectangle((0, 0, canvas.width, banner_height), fill=(154, 36, 36, 225))
    draw.text((20, 15), "LIKELY VIOLATIONS — ARCHITECT REVIEW REQUIRED", fill="white")
    y = 48
    for item in violations[:6]:
        line = f"• {item.title}: {item.actual} {item.unit}; required {item.required} {item.unit}"
        draw.text((25, y), line, fill="white")
        y += 28
    return canvas


def _observation_fields_for_rule(rule: Rule) -> list[str]:
    # Deterministic derived fields map back to the raw measurement(s) Gemini can locate.
    if rule.field == "coverage_percent":
        return ["covered_area_sqft"]
    if rule.field == "max_side_setback_ft":
        return ["left_setback_ft", "right_setback_ft"]
    return [rule.field]


def _box_to_pixels(box: list[int], width: int, height: int) -> tuple[int, int, int, int]:
    ymin, xmin, ymax, xmax = [max(0, min(1000, int(v))) for v in box]
    return (
        int(xmin / 1000 * width),
        int(ymin / 1000 * height),
        int(xmax / 1000 * width),
        int(ymax / 1000 * height),
    )


def annotate_compliance_overlay(
    image: Image.Image,
    analysis,
    findings: list[Finding],
    rules: list[Rule],
    confirmed_fields: set[str],
) -> Image.Image:
    """Color Gemini evidence locations using deterministic compliance findings.

    Gemini supplies only the approximate evidence box. Status/color comes solely from
    the deterministic finding. Unconfirmed detections remain blue.
    """
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    rule_by_id = {r.id: r for r in rules}

    # Map raw plan fields to deterministic findings.
    field_findings: dict[str, Finding] = {}
    for finding in findings:
        rule = rule_by_id.get(finding.rule_id)
        if not rule:
            continue
        for field in _observation_fields_for_rule(rule):
            field_findings[field] = finding

    for obs in analysis.observations:
        if not getattr(obs, "box_2d", None) or len(obs.box_2d) != 4:
            continue
        box = _box_to_pixels(obs.box_2d, canvas.width, canvas.height)
        finding = field_findings.get(obs.field)

        if obs.field not in confirmed_fields or finding is None:
            outline = (37, 99, 235, 255)  # blue: AI candidate / no deterministic mapping
            fill = (37, 99, 235, 35)
            label = f"AI CANDIDATE: {obs.field}"
        elif finding.status == Status.VIOLATION:
            outline = (220, 38, 38, 255)
            fill = (220, 38, 38, 45)
            label = f"LIKELY VIOLATION: {finding.title} | {finding.actual} {finding.unit} | required {finding.required} {finding.unit}"
        elif finding.status == Status.PASS:
            outline = (5, 150, 105, 255)
            fill = (5, 150, 105, 38)
            label = f"PASSED CHECK: {finding.title} | {finding.actual} {finding.unit}"
        else:
            outline = (245, 158, 11, 255)
            fill = (245, 158, 11, 40)
            label = f"NEEDS REVIEW: {finding.title}"

        # Make the compliance location unmistakable.
        draw.rectangle(box, outline=outline, width=max(3, canvas.width // 250), fill=fill)
        x1, y1, x2, _ = box
        text_y = max(0, y1 - 26)
        # Approximate label background width; clamp to canvas.
        text_w = min(canvas.width - x1, max(180, min(canvas.width, 8 * len(label) + 18)))
        draw.rectangle((x1, text_y, x1 + text_w, text_y + 24), fill=outline)
        draw.text((x1 + 5, text_y + 5), label, fill="white")

    return canvas
