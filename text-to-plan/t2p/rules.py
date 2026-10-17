"""Load a city's rule file and derive the buildable envelope for a plot."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

FT = 0.3048
RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


@dataclass(frozen=True)
class Envelope:
    plot_w_m: float          # along the road
    plot_d_m: float          # away from the road
    front_m: float
    side_m: float
    rear_m: float
    fsi: float

    @property
    def w_m(self) -> float:
        return self.plot_w_m - 2 * self.side_m

    @property
    def d_m(self) -> float:
        return self.plot_d_m - self.front_m - self.rear_m

    @property
    def plot_area_sqm(self) -> float:
        return self.plot_w_m * self.plot_d_m

    @property
    def footprint_sqm(self) -> float:
        return self.w_m * self.d_m

    @property
    def max_bua_sqm(self) -> float:
        return self.plot_area_sqm * self.fsi

    @property
    def floors_by_fsi(self) -> int:
        return int(self.max_bua_sqm // self.footprint_sqm) if self.footprint_sqm > 0 else 0


def load_rules(city: str) -> dict:
    with open(RULES_DIR / f"{city}_dcpr2034.yaml") as f:
        return yaml.safe_load(f)


def unverified_rules(rules: dict) -> list[str]:
    return [k for k, v in rules.items() if isinstance(v, dict) and v.get("verified") is False]


def envelope(rules: dict, plot_w_ft: float, plot_d_ft: float, zone: str, road_width_m: float) -> Envelope:
    plot_w, plot_d = plot_w_ft * FT, plot_d_ft * FT
    sb = rules["setbacks"]
    limit = sb["applies_to"]["max_plot_area_sqm"]
    if plot_w * plot_d > limit:
        raise ValueError(f"plot {plot_w * plot_d:.0f} sqm exceeds the small-plot case ({limit} sqm) modelled so far")
    front = next(r["front_m"] for r in sb["front_by_road_width"] if road_width_m <= r["road_width_max_m"])
    env = Envelope(plot_w, plot_d, front, sb["side_m"], sb["rear_m"], rules["fsi"]["basic"][zone])
    if env.w_m <= 0 or env.d_m <= 0:
        raise ValueError("setbacks leave no buildable area on this plot")
    return env


def stair_size(rules: dict) -> tuple[float, float]:
    """(short side, long side) in metres of a dog-legged stair for one storey."""
    st = rules["stairs"]
    risers = math.ceil(st["floor_to_floor_m"] / st["max_riser_m"] - 1e-9)
    treads_per_flight = math.ceil(risers / 2) - 1
    width = st["min_flight_width_m"]
    return 2 * width, treads_per_flight * st["min_tread_m"] + width


def room_standard(rules: dict, kind: str) -> dict:
    """Minimum area / width for a room kind; the stair's are derived from the stair rules."""
    if kind == "stair":
        short, long = stair_size(rules)
        return {"min_area_sqm": round(short * long, 2), "min_width_m": short, "min_length_m": long}
    return rules["rooms"][kind]
