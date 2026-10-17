import pytest

from t2p.generator import Room, generate, local_axes, program
from t2p.rules import envelope, load_rules
from t2p.spec import parse
from t2p.validate import validate

RULES = load_rules("mumbai")


def test_parse_prompt():
    s = parse("40x60 north-facing 3BHK in Dadar on 12 m road, strict vastu with pooja room")
    assert (s.plot_w_ft, s.plot_d_ft, s.facing, s.bhk) == (40, 60, "north", 3)
    assert (s.zone, s.road_width_m, s.vastu, s.pooja) == ("island_city", 12.0, "strict", True)


def test_parse_defaults():
    s = parse("small house")
    assert (s.plot_w_ft, s.plot_d_ft, s.bhk, s.vastu, s.zone) == (30, 40, 2, "off", "suburbs")


def test_envelope_30x40_suburbs():
    env = envelope(RULES, 30, 40, "suburbs", 9.0)
    assert env.w_m == pytest.approx(9.144 - 3.0)
    assert env.d_m == pytest.approx(12.192 - 4.5)
    assert env.fsi == 1.0
    assert env.floors_by_fsi == 2


def test_wider_road_increases_front_setback():
    assert envelope(RULES, 30, 40, "suburbs", 15.0).front_m > envelope(RULES, 30, 40, "suburbs", 9.0).front_m


def test_large_plot_rejected():
    with pytest.raises(ValueError):
        envelope(RULES, 100, 100, "suburbs", 9.0)


@pytest.mark.parametrize("facing,right", [("north", (-1, 0)), ("east", (0, 1)), ("south", (1, 0)), ("west", (0, -1))])
def test_local_axes(facing, right):
    r, rear = local_axes(facing)
    assert r == right
    assert r[0] * rear[1] - r[1] * rear[0] == 1  # rear is 90° counter-clockwise of right


def test_program_sizes():
    assert [r.name for r in program(parse("1bhk"))] == ["living", "kitchen", "bed1", "bath1"]
    assert len(program(parse("3bhk with pooja"))) == 8


def test_generated_plan_is_valid():
    spec = parse("30x40 east facing 2BHK, vastu, pooja")
    env = envelope(RULES, spec.plot_w_ft, spec.plot_d_ft, spec.zone, spec.road_width_m)
    plans = generate(spec, env, RULES, n=1, time_limit_s=3)
    assert plans
    assert validate(plans[0], env, RULES) == []
    assert {r.name for r in plans[0]} == {r.name for r in program(spec)}


def test_validator_catches_breaches():
    env = envelope(RULES, 30, 40, "suburbs", 9.0)
    rooms = [Room("living", "habitable", 0, 0, 3.0, 4.0),
             Room("bed1", "habitable", 2.0, 0, 3.0, 2.0),           # overlaps, under min area
             Room("kitchen", "kitchen", 2.0, 5.0, 1.5, 3.0)]          # interior, past rear setback
    errors = "\n".join(validate(rooms, env, RULES))
    assert "overlaps" in errors
    assert "bed1: 6.00 sqm" in errors
    assert "outside buildable envelope" in errors
