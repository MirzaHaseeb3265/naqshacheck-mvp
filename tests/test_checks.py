from pathlib import Path

import pytest
import yaml

from src.checks import run_checks, summarize
from src.models import ProjectInput, Status
from src.rules import InactiveRulePackError, load_rule_pack


def project(**overrides):
    values = dict(authority="LDA", plot_class="5_marla_residential", project_title="Test",
                  location="Lahore", road_width_ft=30, plot_width_ft=25, plot_depth_ft=45,
                  front_setback_ft=5, rear_setback_ft=5, left_setback_ft=0, right_setback_ft=0,
                  covered_area_sqft=800, building_height_ft=30, stair_width_ft=3.5,
                  parking_spaces=0)
    values.update(overrides)
    return ProjectInput(**values)


def test_5_marla_reviewed_project_passes_without_mandatory_parking():
    metadata, rules = load_rule_pack("data/rules/lda_5_marla_residential.yaml")
    findings = run_checks(project(parking_spaces=0), rules)
    assert metadata["activation_allowed"] is True
    assert all(item.status == Status.PASS for item in findings)
    assert all("PARK" not in item.rule_id for item in findings)


def test_5_marla_front_violation_is_reported():
    _, rules = load_rule_pack("data/rules/lda_5_marla_residential.yaml")
    findings = run_checks(project(front_setback_ft=2), rules)
    assert summarize(findings)["violation"] == 1
    assert next(item for item in findings if item.rule_id == "LDA-RES-5-FRONT-01").status == Status.VIOLATION


def test_10_marla_side_space_passes_when_either_side_is_five_feet():
    _, rules = load_rule_pack("data/rules/lda_10_marla_residential.yaml")
    p = project(plot_class="10_marla_residential", front_setback_ft=10, rear_setback_ft=7,
                left_setback_ft=0, right_setback_ft=5, covered_area_sqft=780,
                building_height_ft=40)
    findings = run_checks(p, rules)
    side = next(item for item in findings if item.rule_id == "LDA-RES-10-SIDE-01")
    assert side.status == Status.PASS
    assert side.actual == 5


def test_10_marla_side_space_fails_when_both_sides_are_under_five_feet():
    _, rules = load_rule_pack("data/rules/lda_10_marla_residential.yaml")
    p = project(plot_class="10_marla_residential", front_setback_ft=10, rear_setback_ft=7,
                left_setback_ft=4, right_setback_ft=3, covered_area_sqft=780,
                building_height_ft=40)
    findings = run_checks(p, rules)
    side = next(item for item in findings if item.rule_id == "LDA-RES-10-SIDE-01")
    assert side.status == Status.VIOLATION
    assert side.actual == 4


def test_inactive_rule_pack_is_rejected(tmp_path: Path):
    path = tmp_path / "draft.yaml"
    path.write_text(yaml.safe_dump({
        "metadata": {"authority": "LDA", "activation_allowed": False},
        "rules": [],
    }), encoding="utf-8")
    with pytest.raises(InactiveRulePackError):
        load_rule_pack(path)
