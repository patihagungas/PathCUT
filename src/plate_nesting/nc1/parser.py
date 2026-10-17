"""Parse NC1 (DSTV) text into a Part object."""

from __future__ import annotations

import math
import re

from plate_nesting.geometry.seg import Seg, arc_segments
from plate_nesting.models.part import Part


def _parse_contour_line(line: str) -> tuple[float, float, float]:
    """Parse one AK/IK contour point line.

    Format (fixed-width):
      head(3) + x(11) + flag(1) + y(10) + r(11) + 4*zeros(44)
    Returns (x, y, signed_radius).
    """
    # Strip the 3-char head ("  v" or "   ")
    rest = line[3:]
    x = float(rest[0:11])
    # skip 1-char flag (u or space)
    y = float(rest[12:22])
    r = float(rest[22:33])
    return x, y, r


def _reconstruct_arc(
    p0: tuple[float, float],
    p1: tuple[float, float],
    signed_r: float,
) -> list[Seg]:
    """Reconstruct arc segment(s) from two endpoints and a signed radius.

    +R = CCW (center to the left of the chord p0→p1)
    -R = CW (center to the right of the chord p0→p1)

    The arc may span > 180°, in which case arc_segments splits it.
    """
    r = abs(signed_r)
    ccw = signed_r > 0

    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    chord = math.hypot(dx, dy)

    if chord < 1e-12:
        # Degenerate: same point, skip
        return []

    # Half-chord vs radius
    half_chord = chord / 2.0
    if half_chord > r + 1e-6:
        # Chord longer than diameter — shouldn't happen, treat as line
        return [Seg(p0, p1)]

    # Distance from midpoint to center along perpendicular
    if half_chord >= r - 1e-9:
        # Semicircle
        d = 0.0
    else:
        d = math.sqrt(r * r - half_chord * half_chord)

    # Midpoint of chord
    mx = (p0[0] + p1[0]) / 2
    my = (p0[1] + p1[1]) / 2

    # Unit normal to the left of p0→p1
    nx = -dy / chord
    ny = dx / chord

    # For CCW (+R): center is to the left of chord direction
    # For CW (-R): center is to the right (negative left normal)
    if ccw:
        cx = mx + nx * d
        cy = my + ny * d
    else:
        cx = mx - nx * d
        cy = my - ny * d

    center = (cx, cy)

    # Compute start angle and sweep
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    a1 = math.atan2(p1[1] - cy, p1[0] - cx)

    if ccw:
        sweep = (a1 - a0) % (2 * math.pi)
        if sweep < 1e-12:
            sweep = 2 * math.pi
    else:
        sweep = -((a0 - a1) % (2 * math.pi))
        if sweep > -1e-12:
            sweep = -2 * math.pi

    return arc_segments(center, r, a0, sweep)


def _parse_contour_points(
    lines: list[str],
) -> list[Seg]:
    """Parse contour point lines into segments.

    Points list: each has (x, y, r) where r is the signed radius for the arc
    FROM this point TO the next point. The last point repeats the first
    (closing point) with r=0.
    """
    pts = [_parse_contour_line(line) for line in lines]
    segs: list[Seg] = []
    # Last point is the closing repeat — iterate up to len-1
    for i in range(len(pts) - 1):
        x0, y0, r0 = pts[i]
        x1, y1, _ = pts[i + 1]
        p0 = (x0, y0)
        p1 = (x1, y1)
        if abs(r0) < 1e-9:
            segs.append(Seg(p0, p1))
        else:
            segs += _reconstruct_arc(p0, p1, r0)
    return segs


def parse_nc1(text: str) -> Part:
    """Parse NC1 text into a Part object."""
    # Normalize line endings
    lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")

    # Header: lines 0-24 (ST header is 25 lines)
    # Line 0: ST
    # Line 1: ** name.nc1
    name_line = lines[1]
    name = name_line.strip().lstrip("*").strip()
    if name.lower().endswith(".nc1"):
        name = name[:-4]

    order = lines[2].strip()
    # line 3: drawing (= name)
    phase = lines[4].strip()
    # line 5: piece (= name)
    grade = lines[6].strip()
    qty = int(lines[7].strip())
    profile_line = lines[8].strip()  # e.g. "PL25" or "PL"
    m = re.match(r"PL([\d.]+)?", profile_line, re.I)
    thickness = float(m.group(1)) if m and m.group(1) else 0.0
    # line 9: "B"
    length = float(lines[10].strip())
    width = float(lines[11].strip())

    # Parse blocks starting after header (line 25 onward)
    outer: list[Seg] = []
    inners: list[list[Seg]] = []
    holes: list[tuple[float, float, float]] = []

    i = 25  # Start after the 25 header lines
    while i < len(lines):
        line = lines[i]
        tag = line.strip()

        if tag == "AK":
            # Collect contour lines until next block tag
            i += 1
            contour_lines: list[str] = []
            while i < len(lines) and lines[i].strip() not in (
                "AK", "IK", "BO", "SI", "EN",
            ):
                contour_lines.append(lines[i])
                i += 1
            outer = _parse_contour_points(contour_lines)

        elif tag == "IK":
            i += 1
            contour_lines = []
            while i < len(lines) and lines[i].strip() not in (
                "AK", "IK", "BO", "SI", "EN",
            ):
                contour_lines.append(lines[i])
                i += 1
            inners.append(_parse_contour_points(contour_lines))

        elif tag == "BO":
            i += 1
            while i < len(lines) and lines[i].strip() not in (
                "AK", "IK", "BO", "SI", "EN",
            ):
                # Format: "  v" + x(11) + "s" + y(10) + d(11)
                hl = lines[i]
                rest = hl[3:]  # skip "  v"
                hx = float(rest[0:11])
                # skip "s"
                hy = float(rest[12:22])
                hd = float(rest[22:33])
                holes.append((hx, hy, hd))
                i += 1

        elif tag in ("SI", "EN"):
            i += 1
        else:
            i += 1

    return Part(
        name=name,
        outer=outer,
        inners=inners,
        holes=holes,
        grade=grade,
        thickness=thickness,
        qty=qty,
        order=order,
        phase=phase,
        length=length,
        width=width,
    )
