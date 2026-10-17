"""Write a Part to NC1 (DSTV) format."""

from __future__ import annotations

from plate_nesting.geometry.area import loop_area, loop_perimeter
from plate_nesting.geometry.seg import Seg
from plate_nesting.models.part import Part
from plate_nesting.nc1._format import DENSITY, f


def _contour_lines(loop: list[Seg], face: str) -> list[str]:
    """Format contour points for NC1 output.

    Face letter only on the first line; 'u' reference flag on the first x;
    x, y, radius, then 4 weld-prep columns (all zero).
    """
    out: list[str] = []
    pts: list[tuple[float, float, float]] = []
    for s in loop:
        r = 0.0
        if s.is_arc:
            r = s.r if s.ccw else -s.r
        pts.append((s.p0[0], s.p0[1], r))
    pts.append((loop[0].p0[0], loop[0].p0[1], 0.0))
    for i, (x, y, r) in enumerate(pts):
        head = f"  {face}" if i == 0 else "   "
        flag = "u" if i == 0 else " "
        out.append(
            f"{head}{f(x)}{flag}{f(y, 10)}{f(r)}" + f(0.0) * 4
        )
    return out


def write_nc1(part: Part) -> str:
    """Produce NC1 text for a Part. Returns string with \\n line endings.

    The caller must write with CRLF (newline='\\r\\n') if needed.
    """
    thk = part.thickness
    kg_per_m2 = thk * DENSITY * 1e6

    # painting surface: 2 + t * perimeter / plate_area (holes ignored)
    outer_area = abs(loop_area(part.outer))
    inner_area = sum(abs(loop_area(lp)) for lp in part.inners)
    plate_area = outer_area - inner_area
    perim = sum(
        loop_perimeter(lp) for lp in [part.outer] + part.inners
    )
    if plate_area > 0 and thk > 0:
        paint = 2 + thk * perim / plate_area
    else:
        paint = 0.0

    lines = [
        "ST",
        f"** {part.name}.nc1",
        f"  {part.order}",
        f"  {part.name}",
        f"  {part.phase}",
        f"  {part.name}",
        f"  {part.grade}",
        f"  {part.qty}",
        f"  PL{thk:g}" if thk else "  PL",
        "  B",
        f(part.length),
        f(part.width),
        f(thk),
        f(thk),
        f(thk),
        f(0.0),
        f(kg_per_m2, d=3),
        f(paint, d=3),
        f(0.0, d=3),
        f(0.0, d=3),
        f(0.0, d=3),
        f(0.0, d=3),
        "",
        "",
        "",
    ]

    lines.append("AK")
    lines += _contour_lines(part.outer, "v")

    for inner in part.inners:
        lines.append("IK")
        lines += _contour_lines(inner, "v")

    if part.holes:
        lines.append("BO")
        for x, y, d in sorted(
            part.holes, key=lambda h: (round(h[0], 2), h[1])
        ):
            lines.append(f"  v{f(x)}s{f(y, 10)}{f(d)}")

    lines.append("EN")
    return "\n".join(lines) + "\n"
