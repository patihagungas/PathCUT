"""Line/arc segment and primitive geometry helpers."""

from __future__ import annotations

import math

Point = tuple[float, float]


class Seg:
    """Line (center=None) or arc from p0 to p1."""

    __slots__ = ("p0", "p1", "center", "r", "ccw")

    def __init__(
        self,
        p0: Point,
        p1: Point,
        center: Point | None = None,
        r: float = 0.0,
        ccw: bool = True,
    ) -> None:
        self.p0 = p0
        self.p1 = p1
        self.center = center
        self.r = r
        self.ccw = ccw

    @property
    def is_arc(self) -> bool:
        return self.center is not None

    def reversed(self) -> Seg:
        return Seg(self.p1, self.p0, self.center, self.r, not self.ccw)

    def sweep(self) -> float:
        """Signed sweep angle in radians (+ = CCW)."""
        assert self.center is not None
        cx, cy = self.center
        a0 = math.atan2(self.p0[1] - cy, self.p0[0] - cx)
        a1 = math.atan2(self.p1[1] - cy, self.p1[0] - cx)
        d = (a1 - a0) % (2 * math.pi)
        if d < 1e-12:
            d = 2 * math.pi
        return d if self.ccw else -(2 * math.pi - d) if d != 2 * math.pi else -d

    def rotated(self, angle_deg: float, ox: float = 0.0, oy: float = 0.0) -> Seg:
        """Rotate segment around (ox, oy) by *angle_deg* degrees CCW."""
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        def _rot(p: Point) -> Point:
            dx, dy = p[0] - ox, p[1] - oy
            return (ox + dx * cos_a - dy * sin_a, oy + dx * sin_a + dy * cos_a)

        c = None if self.center is None else _rot(self.center)
        return Seg(_rot(self.p0), _rot(self.p1), c, self.r, self.ccw)

    def mirrored_x(self) -> Seg:
        """Mirror across the Y-axis (negate x). Flips arc winding."""
        c = None if self.center is None else (-self.center[0], self.center[1])
        return Seg(
            (-self.p0[0], self.p0[1]),
            (-self.p1[0], self.p1[1]),
            c,
            self.r,
            not self.ccw if self.is_arc else self.ccw,
        )

    def shifted(self, dx: float, dy: float) -> Seg:
        c = None if self.center is None else (self.center[0] + dx, self.center[1] + dy)
        return Seg(
            (self.p0[0] + dx, self.p0[1] + dy),
            (self.p1[0] + dx, self.p1[1] + dy),
            c,
            self.r,
            self.ccw,
        )

    def __repr__(self) -> str:
        if self.is_arc:
            d = "CCW" if self.ccw else "CW"
            return f"Seg(arc {d} r={self.r:.2f} {self.p0}->{self.p1})"
        return f"Seg(line {self.p0}->{self.p1})"


def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def arc_segments(center: Point, r: float, a_start: float, sweep: float) -> list[Seg]:
    """Arc from a_start sweeping `sweep` (signed). Split <= 180 deg."""
    n = max(1, math.ceil(abs(sweep) / math.pi - 1e-9))
    out: list[Seg] = []
    for i in range(n):
        a0 = a_start + sweep * i / n
        a1 = a_start + sweep * (i + 1) / n
        p0 = (center[0] + r * math.cos(a0), center[1] + r * math.sin(a0))
        p1 = (center[0] + r * math.cos(a1), center[1] + r * math.sin(a1))
        out.append(Seg(p0, p1, center, r, sweep > 0))
    return out


def bulge_segment(p0: Point, p1: Point, b: float) -> list[Seg]:
    """Convert a polyline segment with bulge to Seg(s)."""
    if abs(b) < 1e-12:
        return [Seg(p0, p1)]
    theta = 4 * math.atan(b)
    c = dist(p0, p1)
    r = c / (2 * math.sin(abs(theta) / 2))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    nx, ny = -(p1[1] - p0[1]) / c, (p1[0] - p0[0]) / c  # left normal
    h = (c / 2) / math.tan(theta / 2)
    center = (mx + nx * h, my + ny * h)
    a0 = math.atan2(p0[1] - center[1], p0[0] - center[0])
    return arc_segments(center, r, a0, theta)
