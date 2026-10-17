"""Command line entry points.

  python -m t2p.cli plan "30x40 east facing 2BHK in Andheri, vastu, pooja" --n 3
  python -m t2p.cli dataset --count 50
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from .generator import generate, program, to_dict
from .render import render_svg
from .rules import envelope, load_rules, unverified_rules
from .spec import FACINGS, PlanSpec, parse
from .validate import validate


def run_spec(spec: PlanSpec, n: int, out: Path, seed: int, prefix: str = "plan") -> int:
    rules = load_rules(spec.city)
    env = envelope(rules, spec.plot_w_ft, spec.plot_d_ft, spec.zone, spec.road_width_m)
    if spec.floors > env.floors_by_fsi:
        raise ValueError(f"{spec.floors} floors need FSI {spec.floors * env.footprint_sqm / env.plot_area_sqm:.2f}; "
                         f"basic FSI here is {env.fsi:g} (premium FSI / TDR not modelled yet)")
    out.mkdir(parents=True, exist_ok=True)
    plans = generate(spec, env, rules, n=n, seed=seed)
    if not plans:
        print(f"  no layout found for {prefix} (infeasible, or solver timed out): {spec.bhk}BHK on {env.footprint_sqm:.1f} sqm footprint", file=sys.stderr)
    adjacency = [(r.name, other) for r in program(spec) for other in r.adjacent_to]
    kept = 0
    for i, rooms in enumerate(plans, 1):
        errors = validate(rooms, env, rules, adjacency)
        if errors:
            print(f"  rejected {prefix}_{i}: {'; '.join(errors)}", file=sys.stderr)
            continue
        kept += 1
        record = to_dict(spec, env, rooms)
        (out / f"{prefix}_{i}.json").write_text(json.dumps(record, indent=2))
        storeys = " duplex" if spec.floors == 2 else ""
        title = f"{spec.bhk}BHK{storeys} · {spec.plot_w_ft:g}×{spec.plot_d_ft:g} ft · Mumbai ({spec.zone}) · vastu {spec.vastu} · option {i}"
        (out / f"{prefix}_{i}.svg").write_text(render_svg(spec, env, rooms, title))
    return kept


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="t2p")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="generate plans from a text prompt")
    p.add_argument("prompt")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--seed", type=int, default=0)
    d = sub.add_parser("dataset", help="sample random specs and write a synthetic dataset")
    d.add_argument("--count", type=int, default=20)
    d.add_argument("--per-spec", type=int, default=2)
    d.add_argument("--out", type=Path, default=Path("dataset"))
    d.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    rules = load_rules("mumbai")
    if unverified := unverified_rules(rules):
        print(f"WARNING: unverified rule groups: {', '.join(unverified)}", file=sys.stderr)

    if a.cmd == "plan":
        spec = parse(a.prompt)
        print(f"spec: {spec}")
        try:
            kept = run_spec(spec, a.n, a.out, a.seed)
        except ValueError as e:
            sys.exit(f"cannot plan this: {e}")
        print(f"wrote {kept} plan(s) to {a.out}/")
    else:
        rng = random.Random(a.seed)
        plots = [(30, 40), (30, 50), (40, 50), (40, 60), (25, 50)]
        total = 0
        for k in range(a.count):
            w, dp = rng.choice(plots)
            bhk = rng.choice([1, 2, 2, 3])
            spec = PlanSpec(plot_w_ft=w, plot_d_ft=dp, facing=rng.choice(FACINGS), bhk=bhk,
                            floors=rng.choice([1, 2]) if bhk >= 2 else 1,
                            zone=rng.choice(["suburbs", "island_city"]),
                            road_width_m=rng.choice([6.0, 9.0, 12.0, 15.0]),
                            vastu=rng.choice(["off", "light", "strict"]), pooja=rng.random() < 0.4)
            try:
                total += run_spec(spec, a.per_spec, a.out, a.seed + k, prefix=f"s{k:04d}")
            except ValueError as e:
                print(f"  skipped spec {k}: {e}", file=sys.stderr)
        print(f"wrote {total} plan(s) to {a.out}/")


if __name__ == "__main__":
    main()
