"""Profile setup payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.base import MemberRole


class RoleOption(BaseModel):
    id: MemberRole
    title: str
    description: str


class OnboardingOptions(BaseModel):
    """Everything the two steps offer, so the client invents nothing."""

    roles: list[RoleOption]
    markets: list[str]
    team_sizes: list[str]
    asset_classes: list[str]


class OnboardingState(BaseModel):
    """Where the member is, and what they have entered so far."""

    step: int
    total_steps: int
    completed: bool
    role: MemberRole | None = None
    company: str | None = None
    primary_market: str | None = None
    team_size: str | None = None
    asset_classes: list[str] = []
    short_description: str | None = None
    completed_at: datetime | None = None
    options: OnboardingOptions


class RoleChoice(BaseModel):
    role: MemberRole


class ProfileSetup(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    primary_market: str = Field(min_length=1, max_length=160)
    team_size: str = Field(min_length=1, max_length=40)
    asset_classes: list[str] = Field(default_factory=list, max_length=12)
    short_description: str | None = Field(default=None, max_length=2000)

    @field_validator("asset_classes")
    @classmethod
    def _clean(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and de-duplicate, keeping the order chosen."""
        seen: set[str] = set()
        cleaned = []
        for item in value:
            label = item.strip()
            if label and label.lower() not in seen:
                seen.add(label.lower())
                cleaned.append(label)
        return cleaned
