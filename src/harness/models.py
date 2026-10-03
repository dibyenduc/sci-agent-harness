from datetime import datetime
from pydantic import BaseModel, Field, model_validator

ALLOWED_UNITS = {
    "viscosity": {"mPa.s", "Pa.s"},
    "cure_time": {"min", "h"},
    "hardness": {"Shore D"},
    "gloss": {"GU"},
    "adhesion": {"MPa"},
    "density": {"g/cm3"},
}

# Layer A: raw measurements
class Measurement(BaseModel):
    id: int | None = None
    tenant_id: str
    sample_id: int
    property: str
    value: float
    unit: str
    instrument: str
    measured_at: datetime

    @model_validator(mode="after")
    def check_unit(self):
        allowed = ALLOWED_UNITS.get(self.property)
        if allowed is None:
            raise ValueError(f"unknown property: {self.property}")
        if self.unit not in allowed:
            raise ValueError(f"unit {self.unit!r} invalid for {self.property}")
        return self

# Layer B: structured experiments
class FormulationItem(BaseModel):
    ingredient_id: int
    amount_wt_pct: float = Field(gt=0, le=100)

class Formulation(BaseModel):
    id: int | None = None
    tenant_id: str
    name: str
    items: list[FormulationItem]

    @model_validator(mode="after")
    def sums_to_100(self):
        total = sum(i.amount_wt_pct for i in self.items)
        if abs(total - 100.0) > 0.05:
            raise ValueError(f"wt% sums to {total:.2f}, expected 100")
        return self

# Layer C: scientific intent
class Hypothesis(BaseModel):
    id: int | None = None
    tenant_id: str
    statement: str
    target_property: str
    target_min: float | None = None
    target_max: float | None = None
    status: str = "open"   # open | supported | refuted | abandoned

