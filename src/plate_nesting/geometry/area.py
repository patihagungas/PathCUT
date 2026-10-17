"""Area and perimeter calculations for segment loops."""

from __future__ import annotations

import math

from plate_nesting.geometry.seg import Seg, dist


def loop_area(loop: list[Seg]) -> float:
    """Signed area (+ = CCW), arcs included."""
    a = 0.0
    for s in loop:
        a += s.p0[0] * s.p1[1] - s.p1[0] * s.p0[1]
    a /= 2
    for s in loop:
        if s.is_arc:
            th = s.sweep()
            a += 0.5 * s.r**2 * (th - math.sin(th))
    return a


def loop_perimeter(loop: list[Seg]) -> float:
    return sum(abs(s.sweep()) * s.r if s.is_arc else dist(s.p0, s.p1) for s in loop)
