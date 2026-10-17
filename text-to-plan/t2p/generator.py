"""Constraint-based layout generator (OR-Tools CP-SAT).

Rooms are axis-aligned rectangles on a 10 cm grid inside the buildable envelope.
A duplex stacks two floors on the same envelope; the stair is one rectangle that
occupies the same position on both floors.
Local frame: x runs along the road frontage, y runs from the front setback line
(y = 0, road side) to the rear. Hard constraints come from the city rule file;
Vastu is a soft preference (or a hard quadrant constraint when `strict`).
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

from ortools.sat.python import cp_model

from .rules import Envelope, room_standard
from .spec import PlanSpec

GRID_M = 0.1

# Compass unit vectors (east, north).
COMPASS = {"north": (0, 1), "east": (1, 0), "south": (0, -1), "west": (-1, 0)}
DIRS = {"NE": (1, 1), "SE": (1, -1), "SW": (-1, -1), "NW": (-1, 1)}


@dataclass
class RoomReq:
    name: str
    kind: str                       # key into rules["rooms"]
    adjacent_to: tuple[str, ...] = ()
    front: bool = False             # must touch the front (entrance) edge
    vastu: str | None = None        # preferred zone, e.g. "SE"
    vastu_avoid: str | None = None  # zone to keep away from
    floors: tuple[int, ...] = (0,)  # 0 = ground; the stair lists every floor it serves


@dataclass
class Room:
    name: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    floor: int = 0

    @property
    def area(self) -> float:
        return self.w * self.h


def program(spec: PlanSpec) -> list[RoomReq]:
    if spec.floors == 2:
        return _duplex_program(spec)
    rooms = [
        RoomReq("living", "habitable", front=True),
        RoomReq("kitchen", "kitchen", ("living",), vastu="SE"),
        RoomReq("bed1", "habitable", ("living",), vastu="SW"),
    ]
    for i in range(2, spec.bhk + 1):
        rooms.append(RoomReq(f"bed{i}", "habitable_secondary", ("living",)))
    if spec.bhk == 1:
        rooms.append(RoomReq("bath1", "bath", ("living",), vastu_avoid="NE"))
    else:
        rooms.append(RoomReq("bath1", "bath", ("bed1",), vastu_avoid="NE"))
        rooms.append(RoomReq("bath2", "bath", ("living",), vastu_avoid="NE"))
    if spec.pooja:
        rooms.append(RoomReq("pooja", "pooja", ("living",), vastu="NE"))
    return rooms


def _duplex_program(spec: PlanSpec) -> list[RoomReq]:
    """Ground: living, kitchen, common bath, stair (+ a guest/elders' bedroom from 3BHK).
    First: landing lobby with the master suite and remaining bedrooms."""
    up_beds = 2 if spec.bhk <= 3 else 3
    rooms = [
        RoomReq("living", "habitable", front=True),
        RoomReq("kitchen", "kitchen", ("living",), vastu="SE"),
        RoomReq("stair", "stair", ("living",), vastu_avoid="NE", floors=(0, 1)),
        RoomReq("bath2", "bath", ("living",), vastu_avoid="NE"),
    ]
    for i in range(up_beds + 1, spec.bhk + 1):
        rooms.append(RoomReq(f"bed{i}", "habitable_secondary", ("living",)))
    if spec.pooja:
        rooms.append(RoomReq("pooja", "pooja", ("living",), vastu="NE"))
    rooms += [
        RoomReq("lobby", "lobby", ("stair",), floors=(1,)),
        RoomReq("bed1", "habitable", ("lobby",), vastu="SW", floors=(1,)),
        RoomReq("bath1", "bath", ("bed1",), vastu_avoid="NE", floors=(1,)),
    ]
    for i in range(2, up_beds + 1):
        rooms.append(RoomReq(f"bed{i}", "habitable_secondary", ("lobby",), floors=(1,)))
    if up_beds >= 2:
        rooms.append(RoomReq("bath3", "bath", ("lobby",), vastu_avoid="NE", floors=(1,)))
    return rooms


def local_axes(facing: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Compass vectors of local +x and local +y, with the road at the bottom of the drawing."""
    fx, fy = COMPASS[facing]
    right = (-fy, fx)               # facing rotated 90° counter-clockwise
    rear = (-fx, -fy)
    return right, rear


def _dm(m: float) -> int:
    return int(round(m / GRID_M))


def _dm_min(m: float) -> int:
    """Grid cells for a minimum: round up so the rule still holds after snapping."""
    return math.ceil(m / GRID_M - 1e-9)


def generate(spec: PlanSpec, env: Envelope, rules: dict, n: int = 3, seed: int = 0,
             time_limit_s: float = 10.0, min_difference_m: float = 2.0) -> list[list[Room]]:
    """Return up to `n` distinct layouts. Each later layout differs from every earlier one
    by at least `min_difference_m` of summed room displacement."""
    rng = random.Random(seed)
    reqs = program(spec)
    W, D = int(env.w_m / GRID_M), int(env.d_m / GRID_M)
    right, rear = local_axes(spec.facing)
    exterior_kinds = set(rules["ventilation"]["exterior_wall_required"])
    door = _dm_min(rules["design"]["min_door_width_m"])
    max_aspect = rules["design"]["max_aspect_ratio"]
    vastu_w = {"off": 0, "light": 4, "strict": 4}[spec.vastu]

    found: list[list[Room]] = []
    for _ in range(n):
        m = cp_model.CpModel()
        v: dict[str, dict] = {}
        for r in reqs:
            std = room_standard(rules, r.kind)
            mw = _dm_min(std["min_width_m"])
            x, y = m.new_int_var(0, W, f"{r.name}_x"), m.new_int_var(0, D, f"{r.name}_y")
            w, h = m.new_int_var(mw, W, f"{r.name}_w"), m.new_int_var(mw, D, f"{r.name}_h")
            x2, y2 = m.new_int_var(0, W, f"{r.name}_x2"), m.new_int_var(0, D, f"{r.name}_y2")
            area = m.new_int_var(0, W * D, f"{r.name}_a")
            m.add_multiplication_equality(area, [w, h])
            m.add(area >= math.ceil(std["min_area_sqm"] * 100 - 1e-9))
            if cap := rules["design"]["max_area_factor"].get(r.kind):
                m.add(area <= int(cap * std["min_area_sqm"] * 100))
            if r.kind == "stair":
                along_x = m.new_bool_var(f"{r.name}_along_x")
                m.add(w >= _dm_min(std["min_length_m"])).only_enforce_if(along_x)
                m.add(h >= _dm_min(std["min_length_m"])).only_enforce_if(~along_x)
            if r.kind.startswith("habitable"):
                m.add(2 * w <= int(2 * max_aspect) * h)
                m.add(2 * h <= int(2 * max_aspect) * w)
            v[r.name] = dict(x=x, y=y, w=w, h=h, area=area,
                             xi=m.new_interval_var(x, w, x2, f"{r.name}_xi"),
                             yi=m.new_interval_var(y, h, y2, f"{r.name}_yi"))
            if r.front:
                m.add(y == 0)
            if r.kind in exterior_kinds:
                sides = [m.new_bool_var(f"{r.name}_ext{k}") for k in range(4)]
                m.add(x == 0).only_enforce_if(sides[0])
                m.add(x + w == W).only_enforce_if(sides[1])
                m.add(y == 0).only_enforce_if(sides[2])
                m.add(y + h == D).only_enforce_if(sides[3])
                m.add_bool_or(sides)

        for f in range(spec.floors):
            on_floor = [r.name for r in reqs if f in r.floors]
            m.add_no_overlap_2d([v[k]["xi"] for k in on_floor], [v[k]["yi"] for k in on_floor])

        for r in reqs:
            for other in r.adjacent_to:
                _require_shared_wall(m, v[r.name], v[other], door, f"{r.name}_{other}")

        objective = [v[r.name]["area"] for r in reqs]
        for r in reqs:
            a = v[r.name]
            # Room centre relative to envelope centre, doubled to stay integral.
            cx, cy = 2 * a["x"] + a["w"] - W, 2 * a["y"] + a["h"] - D
            east = cx * right[0] + cy * rear[0]
            north = cx * right[1] + cy * rear[1]
            if r.vastu and vastu_w:
                de, dn = DIRS[r.vastu]
                objective.append(vastu_w * (de * east + dn * north))
                if spec.vastu == "strict":
                    m.add(de * east >= 0)
                    m.add(dn * north >= 0)
            if r.vastu_avoid and vastu_w:
                de, dn = DIRS[r.vastu_avoid]
                objective.append(-vastu_w * (de * east + dn * north))
            # Small random pull per room so repeated runs explore different arrangements.
            objective.append(rng.randint(-6, 6) * a["x"] + rng.randint(-6, 6) * a["y"])

        for prev in found:
            diffs = []
            for room in {r.name: r for r in prev}.values():
                for key, val in (("x", room.x), ("y", room.y)):
                    d = m.new_int_var(0, max(W, D), f"d_{room.name}_{key}_{len(diffs)}")
                    m.add_abs_equality(d, v[room.name][key] - _dm(val))
                    diffs.append(d)
            m.add(sum(diffs) >= _dm(min_difference_m))

        m.maximize(sum(objective))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        solver.parameters.random_seed = rng.randint(0, 10_000)
        solver.parameters.num_workers = 8
        if solver.solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        found.append([
            Room(r.name, r.kind, *(solver.value(v[r.name][k]) * GRID_M for k in ("x", "y", "w", "h")), floor=f)
            for r in reqs for f in r.floors
        ])
    return found


def _require_shared_wall(m: cp_model.CpModel, a: dict, b: dict, door: int, tag: str) -> None:
    """a and b touch along one side with at least `door` of common wall."""
    opts = [m.new_bool_var(f"adj_{tag}_{k}") for k in range(4)]
    for k, (touch, lo1, hi1, lo2, hi2) in enumerate([
        (a["x"] + a["w"] == b["x"], a["y"], a["y"] + a["h"], b["y"], b["y"] + b["h"]),  # b right of a
        (b["x"] + b["w"] == a["x"], a["y"], a["y"] + a["h"], b["y"], b["y"] + b["h"]),  # b left of a
        (a["y"] + a["h"] == b["y"], a["x"], a["x"] + a["w"], b["x"], b["x"] + b["w"]),  # b behind a
        (b["y"] + b["h"] == a["y"], a["x"], a["x"] + a["w"], b["x"], b["x"] + b["w"]),  # b in front of a
    ]):
        m.add(touch).only_enforce_if(opts[k])
        m.add(hi1 - lo2 >= door).only_enforce_if(opts[k])
        m.add(hi2 - lo1 >= door).only_enforce_if(opts[k])
    m.add_bool_or(opts)


def to_dict(spec: PlanSpec, env: Envelope, rooms: list[Room]) -> dict:
    """Serialisable plan record: the unit of the synthetic dataset."""
    return {
        "spec": asdict(spec),
        "envelope": {**asdict(env), "w_m": env.w_m, "d_m": env.d_m,
                     "footprint_sqm": env.footprint_sqm, "floors_by_fsi": env.floors_by_fsi},
        "rooms": [{**asdict(r), "area_sqm": round(r.area, 2)} for r in rooms],
        "adjacency": [[r.name, o] for r in program(spec) for o in r.adjacent_to],
    }
