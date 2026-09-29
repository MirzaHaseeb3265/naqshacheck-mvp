from src.checks import run_checks, summarize
from src.models import ProjectInput, Status
from src.rules import load_rule_pack


def project(**overrides):
    values = dict(authority="LDA", plot_class="5_marla_residential", project_title="Test",
                  location="Lahore", road_width_ft=30, plot_width_ft=25, plot_depth_ft=45,
                  front_setback_ft=5, rear_setback_ft=5, left_setback_ft=0, right_setback_ft=0,
                  covered_area_sqft=800, building_height_ft=30, stair_width_ft=3.5,
                  parking_spaces=1)
    values.update(overrides)
    return ProjectInput(**values)


def test_compliant_demo_project_passes():
    _, rules = load_rule_pack("data/rules/lda_5_marla_residential.yaml")
    findings = run_checks(project(), rules)
    assert all(item.status == Status.PASS for item in findings)


def test_violation_is_reported():
    _, rules = load_rule_pack("data/rules/lda_5_marla_residential.yaml")
    findings = run_checks(project(front_setback_ft=2), rules)
    assert summarize(findings)["violation"] == 1
    assert next(item for item in findings if item.rule_id == "DEMO-FRONT-01").status == Status.VIOLATION

