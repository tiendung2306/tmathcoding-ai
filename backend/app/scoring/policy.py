from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

GRADE_IDS = {4: "A", 5: "B", 6: "C", 7: "D", 8: "E", 13: "F"}
DEFAULT_UNCLASSIFIED_POINTS = 100


class Band(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum: int = Field(ge=50, le=100000)
    maximum: int = Field(ge=50, le=100000)
    initial: int = Field(ge=50, le=100000)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bands: dict[str, Band]
    min_attempted: int = Field(default=30, ge=5, le=100000)
    min_each_outcome: int = Field(default=5, ge=1, le=10000)
    unclassified_points: Literal[100] = DEFAULT_UNCLASSIFIED_POINTS

    @model_validator(mode="before")
    @classmethod
    def read_legacy_snapshot(cls, value):
        # Empty legacy metadata is harmless; a manual grade mapping is never accepted.
        if isinstance(value, dict) and "overrides" in value:
            if value["overrides"]:
                raise ValueError("Bậc bài chỉ được lấy từ Source API.")
            value = {key: item for key, item in value.items() if key != "overrides"}
        return value

    @model_validator(mode="after")
    def check_policy(self):
        if set(self.bands) != set("ABCDEF"):
            raise ValueError("Phải có đủ sáu bậc A–F.")
        previous = 0
        for grade in "ABCDEF":
            band = self.bands[grade]
            if not previous < band.minimum <= band.initial <= band.maximum:
                raise ValueError("Khoảng bậc phải tăng dần, không chồng lấn và chứa điểm khởi tạo.")
            if any(value % 50 for value in (band.minimum, band.maximum, band.initial)):
                raise ValueError("Điểm phải là bội số của 50.")
            previous = band.maximum
        return self


def default_policy():
    return Policy(bands={grade: Band(minimum=100 + 400 * i, maximum=450 + 400 * i,
                                    initial=300 + 400 * i) for i, grade in enumerate("ABCDEF")})


def source_grade(group_id):
    return GRADE_IDS.get(group_id)


def point_value(difficulty, band):
    return min(band.maximum, max(band.minimum, int(difficulty / 50 + 0.5) * 50))
