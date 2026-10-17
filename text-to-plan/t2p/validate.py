"""Independent rule check for a finished plan.

Deliberately separate from the generator: anything that produces plans
(solver, learned model, user edit) must pass through here before display.
"""
from __future__ import annotations

from .generator import Room
from .rules import Envelope

EPS = 1e-6


def validate(rooms: list[Room], env: Envelope, rules: dict) -> list[str]:
    errors = []
    exterior_kinds = set(rules["ventilation"]["exterior_wall_required"])
    for r in rooms:
        std = rules["rooms"][r.kind]
        if r.x < -EPS or r.y < -EPS or r.x + r.w > env.w_m + EPS or r.y + r.h > env.d_m + EPS:
            errors.append(f"{r.name}: outside buildable envelope (setback breach)")
        if r.area + EPS < std["min_area_sqm"]:
            errors.append(f"{r.name}: {r.area:.2f} sqm < minimum {std['min_area_sqm']} sqm")
        if min(r.w, r.h) + EPS < std["min_width_m"]:
            errors.append(f"{r.name}: width {min(r.w, r.h):.2f} m < minimum {std['min_width_m']} m")
        if r.kind in exterior_kinds and not _on_boundary(r, env):
            errors.append(f"{r.name}: no exterior wall for light and ventilation")
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if _overlap(a, b):
                errors.append(f"{a.name} overlaps {b.name}")
    total = sum(r.area for r in rooms)
    if total > env.footprint_sqm + EPS:
        errors.append(f"room area {total:.1f} sqm exceeds footprint {env.footprint_sqm:.1f} sqm")
    return errors


def _on_boundary(r: Room, env: Envelope) -> bool:
    # Tolerance of one 10 cm grid cell: the envelope edge is rarely on the grid.
    tol = 0.1
    return (abs(r.x) < tol or abs(r.y) < tol
            or abs(r.x + r.w - env.w_m) < tol or abs(r.y + r.h - env.d_m) < tol)


def _overlap(a: Room, b: Room) -> bool:
    return (min(a.x + a.w, b.x + b.w) - max(a.x, b.x) > EPS
            and min(a.y + a.h, b.y + b.h) - max(a.y, b.y) > EPS)
