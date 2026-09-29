from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Status(str, Enum):
    PASS = "pass"
    REVIEW = "review"
    VIOLATION = "violation"


class ProjectInput(BaseModel):
    authority: str = "LDA"
    plot_class: str = "5_marla_residential"
    project_title: str = "Untitled project"
    location: str = "Lahore"
    road_width_ft: float = Field(gt=0)
    plot_width_ft: float = Field(gt=0)
    plot_depth_ft: float = Field(gt=0)
    front_setback_ft: float = Field(ge=0)
    rear_setback_ft: float = Field(ge=0)
    left_setback_ft: float = Field(ge=0)
    right_setback_ft: float = Field(ge=0)
    covered_area_sqft: float = Field(gt=0)
    building_height_ft: float = Field(gt=0)
    stair_width_ft: float = Field(gt=0)
    parking_spaces: int = Field(ge=0)

    @property
    def plot_area_sqft(self) -> float:
        return self.plot_width_ft * self.plot_depth_ft

    @property
    def coverage_percent(self) -> float:
        return self.covered_area_sqft / self.plot_area_sqft * 100


class Rule(BaseModel):
    id: str
    title: str
    field: str
    operator: str
    value: float
    unit: str
    citation: str
    severity: str = "major"
    message: str


class Finding(BaseModel):
    rule_id: str
    title: str
    status: Status
    actual: Any
    required: Any
    unit: str
    message: str
    citation: str
    confidence: float = 1.0

