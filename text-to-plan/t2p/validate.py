"""Independent rule check for a finished plan.

Deliberately separate from the generator: anything that produces plans
(solver, learned model, user edit) must pass through here before display.
"""
from __future__ import annotations

from .generator import Room
from .rules import Envelope, room_standard

EPS = 1e-6


def validate(rooms: list[Room], env: Envelope, rules: dict,
             adjacency: list[tuple[str, str]] = ()) -> list[str]:
    """Return rule breaches; empty means the plan passes. `adjacency` lists room pairs
    that must share a wall long enough for a door."""
    errors = []
    exterior_kinds = set(rules["ventilation"]["exterior_wall_required"])
    for r in rooms:
        std = room_standard(rules, r.kind)
        if r.x < -EPS or r.y < -EPS or r.x + r.w > env.w_m + EPS or r.y + r.h > env.d_m + EPS:
            errors.append(f"{r.name}: outside buildable envelope (setback breach)")
        if r.area + EPS < std["min_area_sqm"]:
            errors.append(f"{r.name}: {r.area:.2f} sqm < minimum {std['min_area_sqm']} sqm")
        if min(r.w, r.h) + EPS < std["min_width_m"]:
            errors.append(f"{r.name}: width {min(r.w, r.h):.2f} m < minimum {std['min_width_m']} m")
        if "min_length_m" in std and max(r.w, r.h) + EPS < std["min_length_m"]:
            errors.append(f"{r.name}: length {max(r.w, r.h):.2f} m < minimum {std['min_length_m']} m")
        if r.kind in exterior_kinds and not _on_boundary(r, env):
            errors.append(f"{r.name}: no exterior wall for light and ventilation")
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if a.floor == b.floor and _overlap(a, b):
                errors.append(f"{a.name} overlaps {b.name}")
    door = rules["design"]["min_door_width_m"]
    for a_name, b_name in adjacency:
        if not any(a.name == a_name and b.name == b_name and a.floor == b.floor
                   and _shared_wall(a, b) + EPS >= door for a in rooms for b in rooms):
            errors.append(f"{a_name} and {b_name} do not share a {door} m wall for a door")
    floors = max(r.floor for r in rooms) + 1
    for f in range(floors):
        total = sum(r.area for r in rooms if r.floor == f)
        if total > env.footprint_sqm + EPS:
            errors.append(f"floor {f}: room area {total:.1f} sqm exceeds footprint {env.footprint_sqm:.1f} sqm")
    if floors > env.floors_by_fsi:
        errors.append(f"{floors} floors exceed the {env.floors_by_fsi} the FSI of {env.fsi:g} allows on this footprint")
    if floors > 1:
        stairs = [r for r in rooms if r.kind == "stair"]
        if sorted(r.floor for r in stairs) != list(range(floors)):
            errors.append("stair must appear exactly once on every floor")
        elif any((r.x, r.y, r.w, r.h) != (stairs[0].x, stairs[0].y, stairs[0].w, stairs[0].h) for r in stairs):
            errors.append("stair is not in the same position on every floor")
    return list(dict.fromkeys(errors))


def _on_boundary(r: Room, env: Envelope) -> bool:
    # Tolerance of one 10 cm grid cell: the envelope edge is rarely on the grid.
    tol = 0.1
    return (abs(r.x) < tol or abs(r.y) < tol
            or abs(r.x + r.w - env.w_m) < tol or abs(r.y + r.h - env.d_m) < tol)


def _overlap(a: Room, b: Room) -> bool:
    return (min(a.x + a.w, b.x + b.w) - max(a.x, b.x) > EPS
            and min(a.y + a.h, b.y + b.h) - max(a.y, b.y) > EPS)


def _shared_wall(a: Room, b: Room) -> float:
    """Length of wall a and b have in common (0 if they do not touch)."""
    tol = 1e-3
    if abs(a.x + a.w - b.x) < tol or abs(b.x + b.w - a.x) < tol:
        return min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    if abs(a.y + a.h - b.y) < tol or abs(b.y + b.h - a.y) < tol:
        return min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    return 0.0
