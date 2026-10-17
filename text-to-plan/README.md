# text-to-plan — Phase 0 (Mumbai)

A prompt like *"30x40 east facing 2BHK in Andheri, vastu, pooja"* goes in.
Out come several floor plans, each checked against Mumbai's building rules
(DCPR 2034) and written out as SVG drawings plus JSON records.
It uses only free data and open-source tools.

```
text prompt ─▶ spec.parse ─▶ PlanSpec
                               │
rules/mumbai_dcpr2034.yaml ─▶ rules.envelope  (setbacks, FSI → buildable footprint, floors)
                               │
                       generator.generate     (OR-Tools CP-SAT: rooms as rectangles, hard rules + Vastu preferences)
                               │
                       validate.validate      (independent re-check; nothing ships without passing)
                               │
                 render.render_svg + to_dict  (SVG drawing + JSON record = one synthetic dataset row)
```

## ⚠️ The engine runs on assumed rule values

The engine runs on assumed rule values. Every number and its source is listed in
**[ASSUMPTIONS.md](ASSUMPTIONS.md)**. Verifying them against DCPR 2034 is an
operational dependency to close before launch.

Until then:
- each rule group in `rules/mumbai_dcpr2034.yaml` carries `verified: false`
- the CLI prints a warning
- every drawing is stamped "ASSUMED RULES"

## Run

```bash
cd text-to-plan
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python -m t2p.cli plan "30x40 east facing 2BHK in Andheri, vastu, pooja" --n 3   # → out/plan_*.svg|json
python -m t2p.cli dataset --count 50                                             # → dataset/ (synthetic)
pytest -q
```

Example output is in `examples/`. Each plan takes up to about 10 s to solve.

## What the prompt parser understands

| Prompt fragment | Spec field |
|---|---|
| `30x40`, `40×60` | plot width × depth in ft (width = road frontage) |
| `east facing` | which side the road is on |
| `2BHK` | 1–4 bedrooms; sets the room list (`generator.program`) |
| `duplex`, `G+1`, `two-storey` | 2 floors with an internal stair (needs 2BHK or more) |
| `12 m road` | road width, which sets the front setback |
| Island City place names (Dadar, Worli, Colaba…) | `island_city` FSI zone; otherwise `suburbs` |
| `vastu` / `strict vastu` | Vastu preference strength (`light` / `strict`); `off` by default |
| `pooja` | adds a pooja room |
| `premium fsi` / `TDR` / `basic fsi` | FSI tier; `auto` by default (the cheapest tier the plan fits in) |

The regex parser defines the `PlanSpec` contract. An LLM parser can replace it
later, as long as it produces the same `PlanSpec` fields.

## How duplexes are laid out

| | Ground floor | First floor |
|---|---|---|
| Always | living, kitchen, common bath, stair, pooja room (if requested) | landing lobby, master bedroom (`bed1`) with attached bath |
| 2BHK | — | `bed2`, plus a common bath off the lobby |
| 3BHK | `bed3` (guest or elders' room) | `bed2`, plus a common bath off the lobby |
| 4BHK | `bed4` | `bed2`, `bed3`, plus a common bath off the lobby |

**The stair** is a single rectangle that sits in the same position on both
floors. On the ground floor it opens off the living room; upstairs it opens
onto the lobby. Its size comes from the stair rules:

- 3.0 m from one floor to the next, with steps at most 0.19 m high, gives 16 steps, split into two flights of 8.
- A dog-legged stair runs those two flights side by side. Each flight is 0.9 m wide and has 7 steps 0.25 m deep, with a 0.9 m landing between them.
- So the stair needs at least **1.8 × 2.65 m**.
- Vastu, when on, keeps the stair out of the north-east.

## How the FSI limit is applied

FSI caps the **built-up area**: total room area × 1.10 for walls, with the stair
counted once. The solver keeps every plan under the cap. That means an upper
floor can be smaller than the ground floor, and whatever isn't built there is
open terrace.

There are three tiers, each adding to the one before:

- **basic**
- **premium:** extra FSI bought from MCGM
- **premium+tdr:** also adds TDR bought on the market

With `auto` (the default), the tool uses the cheapest tier that the minimum room
sizes fit in. If even the top tier doesn't fit, it refuses the request and says
how much area the plan needs against how much is allowed.

The JSON record and the drawing footer show the tier used, the allowed built-up
area and the plan's built-up area.

## Layout quality on large plots

- **Maximum room sizes:** living room and master bedroom 22 m², other bedrooms 14 m².
- **Compact floors:** rooms must fill at least 85% of the rectangle around each floor's rooms.
- **Light and air:** a room only needs to face the open edge of its own floor's built mass, not the edge of the whole buildable area.
- **Stacking:** the upper floor stays over the ground floor.

So a large plot gets a compact house with open space around it, not huge rooms.

**The validator also checks:**
- overlaps on each floor separately
- the stair's width and length
- that the stair is in the same position on every floor
- that built-up area is within FSI
- that every required pair of rooms shares a wall of at least 0.9 m for a door

## How Vastu is applied

- **off:** ignored.
- **light:** preferences the solver tries to meet:
  - kitchen towards the south-east
  - master bedroom towards the south-west
  - pooja room towards the north-east
  - baths kept away from the north-east
- **strict:** those zones become hard constraints. On small plots this can make
  a request impossible to solve, and the CLI says so instead of producing a plan
  that breaks the rules.

## Known gaps, in order of value

1. Close the assumptions in [ASSUMPTIONS.md](ASSUMPTIONS.md). This is an operational dependency, not code.
2. Balconies and FSI exclusions (Reg. 31), plus a marked-up terrace on the upper floor.
3. Doors and windows are drawn only as shared walls of at least 0.9 m. Window placement for the ventilation ratio isn't modelled yet.
4. Corridors and dining rooms. Today every room opens off the living room or the lobby.
5. Other stair types (straight, L-shaped) and stair-specific Vastu rules.
6. DXF export via ezdxf, so plans open in CAD software.
7. LLM prompt parser, behind the same `PlanSpec` contract.
