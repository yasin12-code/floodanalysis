"""Pydantic v2 request models. Invalid input is rejected with 422 by FastAPI."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SHELTER_TYPES = ("school", "hospital", "community_center", "mosque", "government_building", "camp", "other")
REPORT_TYPES = ("water_level", "road_blocked", "people_stranded")
SHELTER_STATUSES = ("open", "full", "closed")
ROAD_STATUSES = ("open", "flooded", "blocked")

# digits, spaces, plus and dashes only (Section 8.2)
PHONE_PATTERN = r"^[0-9+\-\s]+$"


class ShelterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    area: str = Field(default="nowshera", min_length=1, max_length=64)
    shelter_type: Literal[*SHELTER_TYPES]
    capacity: int = Field(ge=0, le=100000)
    contact_phone: str | None = Field(default=None, max_length=30, pattern=PHONE_PATTERN)
    address: str | None = Field(default=None, max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @field_validator("contact_phone", mode="before")
    @classmethod
    def blank_phone_is_none(cls, value):
        return None if isinstance(value, str) and value.strip() == "" else value


class FloodReportCreate(BaseModel):
    report_type: Literal[*REPORT_TYPES]
    severity: int = Field(ge=1, le=3)
    description: str | None = Field(default=None, max_length=2000)
    area: str = Field(default="nowshera", min_length=1, max_length=64)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
