"""Structured plan spec, and a rule-based text parser for it.

The regex parser is a Phase 0 stand-in: it defines the contract an LLM parser
must later fill (same `PlanSpec` output), and it is the fallback when no model
is configured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FACINGS = ("north", "east", "south", "west")
VASTU_LEVELS = ("off", "light", "strict")


@dataclass
class PlanSpec:
    plot_w_ft: float = 30
    plot_d_ft: float = 40
    facing: str = "east"
    bhk: int = 2
    floors: int = 1                 # 2 = duplex (G+1) with an internal stair
    zone: str = "suburbs"
    road_width_m: float = 9.0
    vastu: str = "off"
    pooja: bool = False
    city: str = "mumbai"
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.facing not in FACINGS:
            raise ValueError(f"facing must be one of {FACINGS}")
        if self.vastu not in VASTU_LEVELS:
            raise ValueError(f"vastu must be one of {VASTU_LEVELS}")
        if not 1 <= self.bhk <= 4:
            raise ValueError("bhk must be 1-4")
        if self.floors not in (1, 2):
            raise ValueError("floors must be 1 or 2")
        if self.floors == 2 and self.bhk < 2:
            raise ValueError("a duplex needs at least 2 bedrooms")


ISLAND_CITY_HINTS = ("island city", "south mumbai", "colaba", "dadar", "worli", "parel", "byculla", "girgaon", "matunga")


def parse(text: str) -> PlanSpec:
    t = text.lower()
    spec = PlanSpec()
    if m := re.search(r"(\d{2,3})\s*[x×*]\s*(\d{2,3})", t):
        spec.plot_w_ft, spec.plot_d_ft = float(m[1]), float(m[2])
    if m := re.search(r"\b(north|east|south|west)[\s-]*facing", t):
        spec.facing = m[1]
    if m := re.search(r"(\d)\s*bhk", t):
        spec.bhk = int(m[1])
    if m := re.search(r"(\d+(?:\.\d+)?)\s*m(?:etre|eter)?s?\s*(?:wide\s*)?road", t):
        spec.road_width_m = float(m[1])
    if re.search(r"duplex|g\s*\+\s*1|\b(?:two|2)[\s-]*(?:storey|story|floor)", t):
        spec.floors = 2
    if any(h in t for h in ISLAND_CITY_HINTS):
        spec.zone = "island_city"
    if "strict vastu" in t or "vastu compliant" in t:
        spec.vastu = "strict"
    elif "vastu" in t:
        spec.vastu = "light"
    spec.pooja = "pooja" in t or "puja" in t
    spec.__post_init__()
    return spec
