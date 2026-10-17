import pytest

from t2p.generator import Room, generate, local_axes, program
from t2p.rules import envelope, load_rules, stair_size
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
    assert env.max_bua_sqm == pytest.approx(9.144 * 12.192)


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
    adjacency = [(r.name, o) for r in program(spec) for o in r.adjacent_to]
    assert validate(plans[0], env, RULES, adjacency) == []
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


# --- duplex / stair ---------------------------------------------------------

def test_parse_duplex():
    for prompt in ("3BHK duplex", "2bhk G+1 house", "two-storey 3bhk", "2 floor 2bhk"):
        assert parse(prompt).floors == 2, prompt
    assert parse("3BHK house").floors == 1


def test_duplex_needs_two_bedrooms():
    with pytest.raises(ValueError):
        parse("1BHK duplex")


def test_stair_size_dog_leg():
    # 3.0 m floor-to-floor at 0.19 m risers → 16 risers, 8 per flight, 7 treads of 0.25 m + 0.9 m landing.
    assert stair_size(RULES) == pytest.approx((1.8, 2.65))


def test_duplex_program_splits_floors():
    reqs = {r.name: r for r in program(parse("3bhk duplex"))}
    assert reqs["stair"].floors == (0, 1)
    assert reqs["bed1"].floors == (1,) and reqs["bed3"].floors == (0,)


def test_generated_duplex_is_valid():
    spec = parse("30x40 east facing 3BHK duplex, vastu")
    env = envelope(RULES, spec.plot_w_ft, spec.plot_d_ft, spec.zone, spec.road_width_m)
    plans = generate(spec, env, RULES, n=1, time_limit_s=5)
    assert plans
    adjacency = [(r.name, o) for r in program(spec) for o in r.adjacent_to]
    assert validate(plans[0], env, RULES, adjacency) == []
    stairs = [r for r in plans[0] if r.kind == "stair"]
    assert [s.floor for s in stairs] == [0, 1]
    assert (stairs[0].x, stairs[0].y, stairs[0].w, stairs[0].h) == (stairs[1].x, stairs[1].y, stairs[1].w, stairs[1].h)


def test_validator_catches_duplex_breaches():
    env = envelope(RULES, 30, 40, "suburbs", 9.0)
    rooms = [Room("stair", "stair", 0, 0, 1.8, 2.7, floor=0),
             Room("stair", "stair", 1.0, 0, 1.8, 2.7, floor=1),          # moved upstairs
             Room("living", "habitable", 1.8, 0, 3.0, 4.0, floor=0),
             Room("bed1", "habitable", 0, 4.0, 3.0, 3.5, floor=1)]
    errors = "\n".join(validate(rooms, env, RULES, [("living", "stair"), ("bed1", "living")]))
    assert "stair is not in the same position" in errors
    assert "bed1 and living do not share" in errors          # different floors
    assert "living overlaps" not in errors                   # same footprint, different floors is fine


def test_validator_rejects_built_up_area_beyond_fsi():
    env = envelope(RULES, 30, 40, "suburbs", 9.0)
    low_fsi = type(env)(**{**env.__dict__, "fsi": 0.1})
    rooms = [Room("living", "habitable", 0, 0, 3.0, 4.0, floor=0), Room("bed1", "habitable", 0, 0, 3.0, 4.0, floor=1)]
    assert any("built-up area" in e for e in validate(rooms, low_fsi, RULES))


# --- FSI tiers / built-up area ----------------------------------------------

def test_fsi_tiers_add_up():
    from t2p.rules import fsi_for_tier
    assert fsi_for_tier(RULES, "suburbs", 15.0, "basic") == 1.0
    assert fsi_for_tier(RULES, "suburbs", 15.0, "premium") == 1.5
    assert fsi_for_tier(RULES, "suburbs", 15.0, "premium+tdr") == 2.2
    assert fsi_for_tier(RULES, "suburbs", 6.0, "premium+tdr") == 1.5   # no TDR on roads under 9 m


def test_parse_fsi_choice():
    assert parse("3bhk duplex").fsi == "auto"
    assert parse("3bhk duplex with premium fsi").fsi == "premium"
    assert parse("3bhk duplex using TDR").fsi == "premium+tdr"
    assert parse("3bhk, basic fsi only").fsi == "basic"


def test_auto_tier_picks_cheapest_that_fits():
    from t2p.cli import choose_envelope
    assert choose_envelope(parse("40x60 3bhk duplex on 15 m road"), RULES).fsi_tier == "basic"
    small = parse("20x30 4bhk duplex on 15 m road")
    tier = choose_envelope(small, RULES).fsi_tier
    assert tier in ("premium", "premium+tdr")
    with pytest.raises(ValueError, match="needs at least"):
        choose_envelope(parse("20x30 4bhk duplex on 15 m road, basic fsi"), RULES)


def test_large_plot_duplex_is_compact_and_within_fsi():
    from t2p.cli import choose_envelope
    from t2p.generator import built_up_area
    spec = parse("40x60 north facing 3BHK duplex on 15 m road")
    env = choose_envelope(spec, RULES)
    plans = generate(spec, env, RULES, n=1, time_limit_s=5)
    assert plans
    adjacency = [(r.name, o) for r in program(spec) for o in r.adjacent_to]
    assert validate(plans[0], env, RULES, adjacency) == []
    assert built_up_area(plans[0], RULES) <= env.max_bua_sqm
    assert all(r.area <= 22.0 + 1e-6 for r in plans[0] if r.kind == "habitable")
