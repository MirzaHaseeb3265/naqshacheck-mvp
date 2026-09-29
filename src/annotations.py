from PIL import Image, ImageDraw, ImageFont

from .models import Finding, Status


def annotate_plan(image: Image.Image, findings: list[Finding]) -> Image.Image:
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

