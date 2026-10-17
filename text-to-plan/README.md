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

## ⚠️ The rules are unverified

Every rule group in `rules/mumbai_dcpr2034.yaml` has a `source` and a
`verified: false` flag:

- The FSI and setback figures came from secondary references.
- The room minimums are interim figures from NBC 2016 and the Model Building Bye-laws.

Check each group against the notified DCPR 2034 text and its amendments on the
MCGM portal, then set `verified: true`. Until then the CLI prints a warning,
and every drawing is stamped "rules UNVERIFIED".

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

**The FSI limit is checked before solving.** With only basic FSI, a suburban
plot often can't take two full floors. For example, 40×60 ft on a 15 m road
needs FSI 1.01 against an allowed 1.0. The tool refuses these with that
explanation. Allowing more needs premium FSI and TDR, which aren't modelled yet.

**The validator also checks:**
- overlaps on each floor separately
- the stair's width and length
- that the stair is in the same position on every floor
- the FSI floor count
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

1. Verify the DCPR 2034 numbers. Then add premium FSI and TDR, which depend on road width (Table 12 of the regulations).
2. Upper floors smaller than the ground floor, plus balconies and terraces. Today both floors fill the same footprint, which is why FSI often rules out a duplex.
3. Doors and windows are drawn only as shared walls of at least 0.9 m. Window placement for the ventilation ratio isn't modelled yet.
4. Corridors and dining rooms. Today every room opens off the living room or the lobby.
5. Other stair types (straight, L-shaped) and stair-specific Vastu rules.
6. DXF export via ezdxf, so plans open in CAD software.
7. LLM prompt parser, behind the same `PlanSpec` contract.
