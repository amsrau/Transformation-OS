# Assumptions register: Mumbai (DCPR 2034)

The engine runs on the values below. None of them has been checked against the
notified DCPR 2034 text. That makes **verifying them an operational dependency:
it must be closed before any plan is shown to a buyer as compliant.** Until then:

- every rule group in `rules/mumbai_dcpr2034.yaml` carries `verified: false`
- the CLI prints a warning on every run
- every drawing is stamped "ASSUMED RULES"

## How to close an item

1. A licensed architect or a DCPR consultant checks the value against the current
   DCPR 2034 text and its amendments on the MCGM portal.
2. Correct the value in the YAML file if needed. Code changes are only needed for
   items marked †, where the rule's *shape* may differ, not just its number.
3. Set `verified: true` on that rule group and record who signed it off and when in the table below.
4. Run `pytest`, then regenerate `examples/`.

## Regulatory assumptions (must verify)

| ID | Assumption | Value used | Verify against | If wrong |
|---|---|---|---|---|
| A1 | Basic (zonal) FSI for residential use | Suburbs 1.0 · Island City 1.33 | Reg. 30, Table 12 | Every plan's built-up area limit shifts |
| A2 | Premium FSI, purchasable from MCGM | +0.5 on every road width, both zones | Reg. 30, Table 12 | `auto` picks the wrong tier; premium cost advice is wrong |
| A3 | TDR allowed, by road width | Suburbs: <9 m 0 · 9–12 m 0.5 · 12–18 m 0.7 · 18–27 m 0.9 · ≥27 m 1.0. Island City: <9 m 0 · ≥9 m 0.5 | Reg. 30, Table 12; Reg. 32 | Same as A2 |
| A4 † | Built-up area counted against FSI | Room area × 1.10 for walls; stair counted once; **no exclusions** | Reg. 31 (exclusions: stair, lift, balcony and fungible FSI rules) | Plans are conservative if exclusions apply, and over the limit if the wall factor is low |
| A5 | Front setback, by road width | ≤12 m road: 3.0 m · ≤18 m: 4.5 m · wider: 6.0 m | Reg. 41 | Buildable area is wrong on every plot |
| A6 † | Side and rear setbacks | 1.5 m each, flat, for low-rise buildings (≤15 m tall) on plots ≤500 m² | Reg. 41 (may depend on height or plot width) | Buildable width is wrong; narrow plots may be over- or under-built |
| A7 | Minimum room sizes | Habitable 9.5 m² / 2.4 m wide · second bedroom 7.5 / 2.1 · kitchen 4.5 / 1.5 · bath 1.8 / 1.2 · WC 1.1 / 1.0 | Reg. 37 (current values come from NBC 2016 and the Model Building Bye-laws) | Rooms fail checks, or space is wasted |
| A8 † | Light and ventilation | Habitable rooms and kitchens need an outside wall; window size (≥1/6 of floor area) not yet checked | Reg. 37 | Some rooms may lack a legal window |
| A9 | Internal stair | Flights 0.9 m wide · steps ≤0.19 m high and ≥0.25 m deep · 3.0 m between floors · dog-legged (U-turn) | Reg. 37 / NBC Part 4 | Stair space is wrong on every duplex |
| A10 | Ground coverage | Not applied; setbacks assumed to govern | DCPR 2034 | Could allow too large a footprint on some plots |
| A11 | Island City vs suburbs | Decided from a short list of place names in the prompt | MCGM ward boundaries | A plot gets the wrong FSI zone |

† The rule may need a code change, not just a new number.

## Product/design assumptions (our choices, not regulations)

These set how plans look, not whether they comply. Review them with architects in the Phase 1 feedback round.

| ID | Choice | Value | Where |
|---|---|---|---|
| D1 | Maximum room size | Living / master bedroom 22 m² · other bedrooms 14 m² · service rooms 2–2.5× their minimum | `design.max_area_*` |
| D2 | Room proportions | At most 2:1 for bedrooms, living room and kitchen | `design.max_aspect_ratio` |
| D3 | Compactness | Rooms fill ≥85% of the rectangle around each floor's rooms | `design.min_fill_ratio` |
| D4 | Door width | Rooms that need a door share at least 0.9 m of wall | `design.min_door_width_m` |
| D5 | Upper floor | Sits over the ground floor; anything not built upstairs is open terrace | `generator.generate` |
| D6 | Duplex room split | Master suite upstairs; from 3BHK, one bedroom downstairs | `generator._duplex_program` |
| D7 | Vastu zones | Kitchen SE · master bedroom SW · pooja room NE · baths and stair away from NE | `generator.program` |
| D8 | `auto` FSI tier | Picks the cheapest tier the minimum room sizes fit in, so the owner doesn't pay for premium FSI or TDR unless needed | `cli.choose_envelope` |

## Sign-off

| ID | Verified by | Date | Notes |
|---|---|---|---|
| A1–A11 | — | — | Open |
