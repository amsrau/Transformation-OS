"""Render a plan to a standalone SVG: plot, setback lines, rooms, road and north arrow."""
from __future__ import annotations

from xml.sax.saxutils import escape

from .generator import Room, local_axes
from .rules import Envelope
from .spec import PlanSpec

SCALE = 50          # px per metre
PAD = 70
FILL = {"habitable": "#f3ead9", "habitable_secondary": "#efe3cc", "kitchen": "#e3eedb",
        "bath": "#dce8f2", "wc": "#dce8f2", "pooja": "#f6dede"}
SQFT = 10.7639


def render_svg(spec: PlanSpec, env: Envelope, rooms: list[Room], title: str = "") -> str:
    pw, pd = env.plot_w_m * SCALE, env.plot_d_m * SCALE
    vw, vh = pw + 2 * PAD, pd + 2 * PAD + 30
    # SVG y grows downward; the road sits at the bottom, so flip local y.
    def px(x: float) -> float:
        return PAD + (env.side_m + x) * SCALE

    def py(y: float) -> float:
        return PAD + pd - (env.front_m + y) * SCALE

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw:.0f} {vh:.0f}" '
           f'font-family="Helvetica, Arial, sans-serif" font-size="11">',
           f'<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<text x="{PAD}" y="22" font-size="13" font-weight="bold">{escape(title)}</text>',
           f'<rect x="{PAD}" y="{PAD}" width="{pw:.1f}" height="{pd:.1f}" fill="#fafafa" stroke="#333" stroke-width="2"/>',
           f'<rect x="{px(0):.1f}" y="{py(env.d_m):.1f}" width="{env.w_m * SCALE:.1f}" height="{env.d_m * SCALE:.1f}" '
           f'fill="none" stroke="#999" stroke-dasharray="6 4"/>']
    for r in rooms:
        x0, y0 = px(r.x), py(r.y + r.h)
        w, h = r.w * SCALE, r.h * SCALE
        out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{h:.1f}" '
                   f'fill="{FILL.get(r.kind, "#eee")}" stroke="#222" stroke-width="1.5"/>')
        cx, cy = x0 + w / 2, y0 + h / 2
        # Narrow rooms get their labels turned to run along the long side.
        rot = f' transform="rotate(-90 {cx:.1f} {cy:.1f})"' if w < 110 and h > w else ""
        out.append(f'<g{rot}><text x="{cx:.1f}" y="{cy - 4:.1f}" text-anchor="middle" font-weight="bold">{escape(r.name)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{cy + 10:.1f}" text-anchor="middle" fill="#555">'
                   f'{r.w:.1f}×{r.h:.1f} m · {r.area * SQFT:.0f} sq ft</text></g>')
    # Road and entrance.
    road_y = PAD + pd + 8
    out.append(f'<rect x="{PAD}" y="{road_y}" width="{pw:.1f}" height="18" fill="#ddd"/>')
    out.append(f'<text x="{PAD + pw / 2:.1f}" y="{road_y + 13}" text-anchor="middle">'
               f'ROAD ({spec.road_width_m:g} m) · {spec.facing.upper()}-FACING</text>')
    # North arrow: compass north expressed in drawing coordinates.
    right, rear = local_axes(spec.facing)
    nx, ny = right[1], -rear[1]           # drawing x, drawing y (down) of compass north
    ax, ay = vw - 35, 40
    out.append(f'<line x1="{ax - 14 * nx}" y1="{ay - 14 * ny}" x2="{ax + 14 * nx}" y2="{ay + 14 * ny}" '
               f'stroke="#c00" stroke-width="2.5"/>')
    out.append(f'<text x="{ax + 24 * nx}" y="{ay + 24 * ny + 4}" text-anchor="middle" fill="#c00" font-weight="bold">N</text>')
    foot = vh - 10
    out.append(f'<text x="{PAD}" y="{foot}" fill="#555">Plot {spec.plot_w_ft:g}×{spec.plot_d_ft:g} ft · '
               f'setbacks F{env.front_m:g}/S{env.side_m:g}/R{env.rear_m:g} m · footprint {env.footprint_sqm:.1f} sqm · '
               f'FSI {env.fsi:g} → {env.floors_by_fsi} floor(s) · rules UNVERIFIED</text>')
    out.append("</svg>")
    return "\n".join(out)
