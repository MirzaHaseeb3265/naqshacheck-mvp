from operator import ge, le, eq

from .models import Finding, ProjectInput, Rule, Status


OPERATORS = {">=": ge, "<=": le, "==": eq}


def _actual_value(project: ProjectInput, field: str):
    if field == "coverage_percent":
        return round(project.coverage_percent, 2)
    if field == "plot_area_sqft":
        return round(project.plot_area_sqft, 2)
    if field == "max_side_setback_ft":
        return max(project.left_setback_ft, project.right_setback_ft)
    return getattr(project, field)


def run_checks(project: ProjectInput, rules: list[Rule]) -> list[Finding]:
    findings: list[Finding] = []
    for rule in rules:
        actual = _actual_value(project, rule.field)
        passed = OPERATORS[rule.operator](actual, rule.value)
        findings.append(
            Finding(
                rule_id=rule.id,
                title=rule.title,
                status=Status.PASS if passed else Status.VIOLATION,
                actual=actual,
                required=f"{rule.operator} {rule.value}",
                unit=rule.unit,
                message="Requirement satisfied." if passed else rule.message,
                citation=rule.citation,
            )
        )
    return findings


def summarize(findings: list[Finding]) -> dict[str, int]:
    return {
        "pass": sum(item.status == Status.PASS for item in findings),
        "review": sum(item.status == Status.REVIEW for item in findings),
        "violation": sum(item.status == Status.VIOLATION for item in findings),
    }

