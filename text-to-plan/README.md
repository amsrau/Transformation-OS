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
| `12 m road` | road width, which sets the front setback |
| Island City place names (Dadar, Worli, Colaba…) | `island_city` FSI zone; otherwise `suburbs` |
| `vastu` / `strict vastu` | Vastu preference strength (`light` / `strict`); `off` by default |
| `pooja` | adds a pooja room |

The regex parser defines the `PlanSpec` contract. An LLM parser can replace it
later, as long as it produces the same `PlanSpec` fields.

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
2. Add staircases and multi-floor (duplex) plans. The FSI floor count is calculated but not yet laid out.
3. Doors and windows are drawn only as shared walls of at least 0.9 m. Window placement for the ventilation ratio isn't modelled yet.
4. Corridors and dining rooms. Today every bedroom opens off the living room.
5. DXF export via ezdxf, so plans open in CAD software.
6. LLM prompt parser, behind the same `PlanSpec` contract.
