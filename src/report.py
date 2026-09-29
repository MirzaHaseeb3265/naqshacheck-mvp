from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Finding, ProjectInput


def create_report(project: ProjectInput, findings: list[Finding], rule_version: str) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm,
                                 topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("NaqshaCheck Pre-Submission Report", styles["Title"]),
        Paragraph("Advisory pre-submission review — not official approval, not a substitute for a licensed architect, and not a guarantee of authority acceptance.", styles["Italic"]),
        Spacer(1, 8),
        Paragraph(f"Project: {project.project_title}", styles["Heading2"]),
        Paragraph(f"Authority: {project.authority} | Rule version: {rule_version}", styles["BodyText"]),
        Paragraph(f"Plot: {project.plot_width_ft} × {project.plot_depth_ft} ft | Road: {project.road_width_ft} ft", styles["BodyText"]),
        Spacer(1, 12),
    ]
    rows = [["Check", "Status", "Actual", "Required", "Source"]]
    for item in findings:
        status_label = "Passed selected preflight check" if item.status.value == "pass" else (
            "Likely violation" if item.status.value == "violation" else "Professional review required"
        )
        rows.append([item.title, status_label, f"{item.actual} {item.unit}",
                     f"{item.required} {item.unit}", f"{item.rule_id} · {rule_version} · {item.citation}"])
    table = Table(rows, colWidths=[41*mm, 22*mm, 28*mm, 31*mm, 52*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102A43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([table, Spacer(1, 12), Paragraph(
        "Every finding must be verified against the current authority-issued regulation and by a licensed architect before submission.",
        styles["BodyText"]
    )])
    document.build(story)
    return output.getvalue()

