"""Detect shared collinear straight edges between neighboring placed parts.

Two edges from different parts can share a single cut line when they are
parallel, facing each other, separated by approximately the kerf spacing,
and have sufficient overlap along their shared direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from plate_nesting.geometry.seg import Point
from plate_nesting.models.layout import Layout


@dataclass
class WorldEdge:
    """A straight edge in world coordinates tied to a placement."""

    p0: Point
    p1: Point
    placement_index: int
    seg_index: int


@dataclass
class CommonCut:
    """A shared cut between two edges from different placements."""

    edge_a: WorldEdge
    edge_b: WorldEdge
    cut_start: Point
    cut_end: Point
    cut_length: float


def _edge_dir(e: WorldEdge) -> tuple[float, float]:
    dx = e.p1[0] - e.p0[0]
    dy = e.p1[1] - e.p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _edge_length(e: WorldEdge) -> float:
    return math.hypot(e.p1[0] - e.p0[0], e.p1[1] - e.p0[1])


def _outward_normal(d: tuple[float, float]) -> tuple[float, float]:
    """Right-hand normal of direction vector (outward for CCW outer contour)."""
    return (d[1], -d[0])


def _aabb(e: WorldEdge, inflate: float) -> tuple[float, float, float, float]:
    x0 = min(e.p0[0], e.p1[0]) - inflate
    y0 = min(e.p0[1], e.p1[1]) - inflate
    x1 = max(e.p0[0], e.p1[0]) + inflate
    y1 = max(e.p0[1], e.p1[1]) + inflate
    return (x0, y0, x1, y1)


def _aabb_overlap(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _angle_between(d1: tuple[float, float], d2: tuple[float, float]) -> float:
    """Angle in degrees between two unit vectors (0-90 range)."""
    dot = abs(d1[0] * d2[0] + d1[1] * d2[1])
    dot = min(dot, 1.0)
    return math.degrees(math.acos(dot))


def _perp_distance(
    e1: WorldEdge, e2: WorldEdge, d: tuple[float, float]
) -> float:
    """Perpendicular distance between the lines of two parallel edges."""
    n = _outward_normal(d)
    # Vector from e1.p0 to e2.p0 projected onto the normal
    vx = e2.p0[0] - e1.p0[0]
    vy = e2.p0[1] - e1.p0[1]
    return abs(vx * n[0] + vy * n[1])


def _overlap_range(
    e1: WorldEdge, e2: WorldEdge, d: tuple[float, float]
) -> tuple[float, float] | None:
    """Project both edges onto direction vector d and return overlap interval."""
    # Project e1
    t1a = e1.p0[0] * d[0] + e1.p0[1] * d[1]
    t1b = e1.p1[0] * d[0] + e1.p1[1] * d[1]
    lo1, hi1 = min(t1a, t1b), max(t1a, t1b)
    # Project e2
    t2a = e2.p0[0] * d[0] + e2.p0[1] * d[1]
    t2b = e2.p1[0] * d[0] + e2.p1[1] * d[1]
    lo2, hi2 = min(t2a, t2b), max(t2a, t2b)
    # Overlap
    lo = max(lo1, lo2)
    hi = min(hi1, hi2)
    if hi <= lo:
        return None
    return (lo, hi)


def _facing_each_other(
    e1: WorldEdge, e2: WorldEdge, d1: tuple[float, float], d2: tuple[float, float]
) -> bool:
    """Check that outward normals point toward each other."""
    n1 = _outward_normal(d1)
    n2 = _outward_normal(d2)
    # Vector from e1.p0 toward e2.p0
    vx = e2.p0[0] - e1.p0[0]
    vy = e2.p0[1] - e1.p0[1]
    # n1 should point toward e2 (positive dot with v)
    # n2 should point toward e1 (negative dot with v)
    dot1 = n1[0] * vx + n1[1] * vy
    dot2 = n2[0] * vx + n2[1] * vy
    return dot1 > 0 and dot2 < 0


def detect_common_cuts(
    layout: Layout,
    spacing: float,
    distance_tol: float = 1.0,
    angle_tol_deg: float = 0.5,
    min_length: float = 10.0,
) -> list[CommonCut]:
    """Detect shared collinear straight edges between placements.

    Args:
        layout: Layout with placed parts.
        spacing: Expected gap between parts (kerf spacing in mm).
        distance_tol: Tolerance for perpendicular distance match (mm).
        angle_tol_deg: Maximum angle between edges to be considered parallel.
        min_length: Minimum overlap length to count as a common cut (mm).

    Returns:
        List of CommonCut instances.
    """
    # Step 1: extract world-space straight edges
    edges: list[WorldEdge] = []
    for pi, pp in enumerate(layout.placements):
        for si, seg in enumerate(pp.world_outer_edges()):
            if seg.is_arc:
                continue
            if math.hypot(seg.p1[0] - seg.p0[0], seg.p1[1] - seg.p0[1]) < 1e-6:
                continue
            edges.append(WorldEdge(seg.p0, seg.p1, pi, si))

    if len(edges) < 2:
        return []

    # Step 2: build AABBs
    inflate = spacing + distance_tol
    aabbs = [_aabb(e, inflate) for e in edges]

    # Step 3: pairwise check
    results: list[CommonCut] = []
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            ea, eb = edges[i], edges[j]
            # Must be from different placements
            if ea.placement_index == eb.placement_index:
                continue
            # AABB pre-filter
            if not _aabb_overlap(aabbs[i], aabbs[j]):
                continue
            da = _edge_dir(ea)
            db = _edge_dir(eb)
            if da == (0.0, 0.0) or db == (0.0, 0.0):
                continue
            # Parallel check
            if _angle_between(da, db) > angle_tol_deg:
                continue
            # Facing each other check
            if not _facing_each_other(ea, eb, da, db):
                continue
            # Perpendicular distance check
            perp = _perp_distance(ea, eb, da)
            if perp < spacing - distance_tol or perp > spacing + distance_tol:
                continue
            # Overlap check
            overlap = _overlap_range(ea, eb, da)
            if overlap is None:
                continue
            lo, hi = overlap
            cut_len = hi - lo
            if cut_len < min_length:
                continue
            # Build cut endpoints along the midline between the two edges
            mid_offset = perp / 2
            na = _outward_normal(da)
            # Midline origin: shift ea.p0 by half the perpendicular distance toward eb
            mx = ea.p0[0] + na[0] * mid_offset
            my = ea.p0[1] + na[1] * mid_offset
            # Project midline origin onto direction to get base t
            base_t = mx * da[0] + my * da[1]
            # Cut endpoints
            cut_start = (
                mx + da[0] * (lo - base_t),
                my + da[1] * (lo - base_t),
            )
            cut_end = (
                mx + da[0] * (hi - base_t),
                my + da[1] * (hi - base_t),
            )
            results.append(
                CommonCut(
                    edge_a=ea,
                    edge_b=eb,
                    cut_start=cut_start,
                    cut_end=cut_end,
                    cut_length=cut_len,
                )
            )

    return results
