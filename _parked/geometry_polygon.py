"""Convert segment loops to polygons for nesting and validation."""

from __future__ import annotations

import math

from shapely.geometry import Polygon

from plate_nesting.geometry.seg import Seg
from plate_nesting.models.part import Part


def _flatten_arc(seg: Seg, tol: float) -> list[tuple[float, float]]:
    """Approximate an arc segment as a series of points.

    tol: maximum deviation from the true arc (mm).
    """
    assert seg.center is not None
    sweep = abs(seg.sweep())
    r = seg.r
    # Number of segments: ensure sagitta <= tol
    # sagitta = r * (1 - cos(step/2))
    if r * (1 - math.cos(sweep / 2)) <= tol:
        # Single chord is close enough
        return [seg.p0]
    step = 2 * math.acos(max(-1, min(1, 1 - tol / r)))
    n = max(2, math.ceil(sweep / step))
    cx, cy = seg.center
    a0 = math.atan2(seg.p0[1] - cy, seg.p0[0] - cx)
    signed_sweep = seg.sweep()
    pts: list[tuple[float, float]] = []
    for i in range(n):
        a = a0 + signed_sweep * i / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def loop_to_points(
    loop: list[Seg], tol: float = 0.5
) -> list[tuple[float, float]]:
    """Convert a segment loop to a list of (x, y) points.

    Arcs are flattened to polylines within the given tolerance (mm).
    """
    pts: list[tuple[float, float]] = []
    for seg in loop:
        if seg.is_arc:
            pts.extend(_flatten_arc(seg, tol))
        else:
            pts.append(seg.p0)
    return pts


def part_outer_polygon(part: Part, tol: float = 0.5) -> Polygon:
    """Convert a part's outer contour to a Shapely Polygon."""
    pts = loop_to_points(part.outer, tol)
    if len(pts) < 3:
        return Polygon()
    return Polygon(pts)


def part_polygon_with_holes(part: Part, tol: float = 0.5) -> Polygon:
    """Convert a part to a Shapely Polygon with inner cutout holes."""
    outer_pts = loop_to_points(part.outer, tol)
    if len(outer_pts) < 3:
        return Polygon()
    holes = [loop_to_points(inner, tol) for inner in part.inners]
    holes = [h for h in holes if len(h) >= 3]
    return Polygon(outer_pts, holes)
