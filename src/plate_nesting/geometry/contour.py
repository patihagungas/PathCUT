"""Contour operations: chaining, orientation, bounding box, DXF entity conversion."""

from __future__ import annotations

import math

import ezdxf

from plate_nesting.geometry.seg import Seg, arc_segments, bulge_segment, dist


def entity_segments(e: ezdxf.entities.DXFGraphic) -> list[Seg]:
    """Convert an ezdxf entity to a list of Seg."""
    t = e.dxftype()
    if t == "LINE":
        s, en = e.dxf.start, e.dxf.end
        return [Seg((s.x, s.y), (en.x, en.y))]
    if t == "ARC":
        c = (e.dxf.center.x, e.dxf.center.y)
        a0 = math.radians(e.dxf.start_angle)
        a1 = math.radians(e.dxf.end_angle)
        sw = (a1 - a0) % (2 * math.pi) or 2 * math.pi
        return arc_segments(c, e.dxf.radius, a0, sw)
    if t == "CIRCLE":
        c = (e.dxf.center.x, e.dxf.center.y)
        return arc_segments(c, e.dxf.radius, math.pi, 2 * math.pi)
    if t in ("LWPOLYLINE", "POLYLINE"):
        if t == "LWPOLYLINE":
            pts = [(p[0], p[1], p[4]) for p in e.get_points("xyseb")]
            closed = e.closed
        else:
            pts = [
                (v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0))
                for v in e.vertices
            ]
            closed = e.is_closed
        segs: list[Seg] = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            if dist(a, b) > 1e-9:
                segs += bulge_segment((a[0], a[1]), (b[0], b[1]), a[2])
        return segs
    if t in ("SPLINE", "ELLIPSE"):
        flat = [(p.x, p.y) for p in e.flattening(0.05)]
        return [Seg(flat[i], flat[i + 1]) for i in range(len(flat) - 1)]
    return []


def chain(segs: list[Seg], tol: float) -> tuple[list[list[Seg]], list[list[Seg]]]:
    """Join loose segments into closed loops. Returns (closed, open)."""
    pool = list(segs)
    loops: list[list[Seg]] = []
    open_: list[list[Seg]] = []
    while pool:
        cur = [pool.pop(0)]
        while dist(cur[-1].p1, cur[0].p0) > tol:
            for i, s in enumerate(pool):
                if dist(s.p0, cur[-1].p1) <= tol:
                    cur.append(pool.pop(i))
                    break
                if dist(s.p1, cur[-1].p1) <= tol:
                    cur.append(pool.pop(i).reversed())
                    break
            else:
                open_.append(cur)
                cur = None  # type: ignore[assignment]
                break
        if cur:
            loops.append(cur)
    return loops, open_


def reverse_loop(loop: list[Seg]) -> list[Seg]:
    return [s.reversed() for s in reversed(loop)]


def start_at_left(loop: list[Seg]) -> list[Seg]:
    """Rotate loop so it starts at the leftmost vertex (lowest y on ties)."""
    i = min(
        range(len(loop)),
        key=lambda k: (round(loop[k].p0[0], 3), round(loop[k].p0[1], 3)),
    )
    return loop[i:] + loop[:i]


def loop_bbox(loop: list[Seg]) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) including arc extremes."""
    xs: list[float] = []
    ys: list[float] = []
    for s in loop:
        xs += [s.p0[0], s.p1[0]]
        ys += [s.p0[1], s.p1[1]]
        if s.is_arc:
            assert s.center is not None
            cx, cy = s.center
            a0 = math.atan2(s.p0[1] - cy, s.p0[0] - cx)
            th = s.sweep()
            for k in range(4):
                ang = k * math.pi / 2
                d = (
                    ((ang - a0) % (2 * math.pi))
                    if th > 0
                    else ((a0 - ang) % (2 * math.pi))
                )
                if d <= abs(th) + 1e-12:
                    xs.append(cx + s.r * math.cos(ang))
                    ys.append(cy + s.r * math.sin(ang))
    return min(xs), min(ys), max(xs), max(ys)
