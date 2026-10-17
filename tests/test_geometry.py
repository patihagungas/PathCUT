"""Unit tests for geometry modules."""

import math

from plate_nesting.geometry.area import loop_area, loop_perimeter
from plate_nesting.geometry.contour import (
    chain,
    loop_bbox,
    reverse_loop,
    start_at_left,
)
from plate_nesting.geometry.seg import Seg, arc_segments, bulge_segment, dist


class TestSeg:
    def test_line_not_arc(self):
        s = Seg((0, 0), (1, 0))
        assert not s.is_arc

    def test_arc_is_arc(self):
        s = Seg((1, 0), (0, 1), center=(0, 0), r=1.0, ccw=True)
        assert s.is_arc

    def test_reversed(self):
        s = Seg((0, 0), (1, 0))
        r = s.reversed()
        assert r.p0 == (1, 0)
        assert r.p1 == (0, 0)

    def test_arc_reversed_flips_ccw(self):
        s = Seg((1, 0), (0, 1), center=(0, 0), r=1.0, ccw=True)
        r = s.reversed()
        assert r.ccw is False
        assert r.p0 == (0, 1)
        assert r.p1 == (1, 0)

    def test_sweep_quarter_ccw(self):
        s = Seg((1, 0), (0, 1), center=(0, 0), r=1.0, ccw=True)
        assert abs(s.sweep() - math.pi / 2) < 1e-10

    def test_sweep_quarter_cw(self):
        s = Seg((0, 1), (1, 0), center=(0, 0), r=1.0, ccw=False)
        assert abs(s.sweep() + math.pi / 2) < 1e-10

    def test_shifted(self):
        s = Seg((0, 0), (1, 1), center=(0.5, 0.5), r=0.707, ccw=True)
        s2 = s.shifted(10, 20)
        assert s2.p0 == (10, 20)
        assert s2.p1 == (11, 21)
        assert s2.center == (10.5, 20.5)


class TestSegRotated:
    def test_rotate_90_line(self):
        s = Seg((1, 0), (2, 0))
        r = s.rotated(90)
        assert abs(r.p0[0] - 0) < 1e-10
        assert abs(r.p0[1] - 1) < 1e-10
        assert abs(r.p1[0] - 0) < 1e-10
        assert abs(r.p1[1] - 2) < 1e-10

    def test_rotate_around_custom_origin(self):
        s = Seg((2, 0), (3, 0))
        r = s.rotated(90, ox=1.0, oy=0.0)
        assert abs(r.p0[0] - 1) < 1e-10
        assert abs(r.p0[1] - 1) < 1e-10
        assert abs(r.p1[0] - 1) < 1e-10
        assert abs(r.p1[1] - 2) < 1e-10

    def test_rotate_arc_preserves_center(self):
        s = Seg((1, 0), (0, 1), center=(0, 0), r=1.0, ccw=True)
        r = s.rotated(90)
        assert abs(r.center[0] - 0) < 1e-10
        assert abs(r.center[1] - 0) < 1e-10
        assert abs(r.p0[0] - 0) < 1e-10
        assert abs(r.p0[1] - 1) < 1e-10
        assert r.ccw is True

    def test_rotate_45(self):
        s = Seg((1, 0), (0, 0))
        r = s.rotated(45)
        expected_x = math.cos(math.radians(45))
        expected_y = math.sin(math.radians(45))
        assert abs(r.p0[0] - expected_x) < 1e-10
        assert abs(r.p0[1] - expected_y) < 1e-10


class TestSegMirroredX:
    def test_mirror_line(self):
        s = Seg((1, 2), (3, 4))
        m = s.mirrored_x()
        assert m.p0 == (-1, 2)
        assert m.p1 == (-3, 4)
        assert not m.is_arc

    def test_mirror_arc_flips_ccw(self):
        s = Seg((1, 0), (0, 1), center=(0, 0), r=1.0, ccw=True)
        m = s.mirrored_x()
        assert m.p0 == (-1, 0)
        assert m.p1 == (0, 1)
        assert m.center == (0, 0)
        assert m.ccw is False

    def test_mirror_line_preserves_ccw(self):
        s = Seg((1, 0), (2, 0))
        m = s.mirrored_x()
        assert m.ccw is True  # line ccw unchanged


class TestDist:
    def test_zero(self):
        assert dist((0, 0), (0, 0)) == 0.0

    def test_unit(self):
        assert abs(dist((0, 0), (3, 4)) - 5.0) < 1e-10


class TestArcSegments:
    def test_semicircle_splits_none(self):
        # 180 deg CCW from (1,0) to (-1,0)
        segs = arc_segments((0, 0), 1.0, 0, math.pi)
        assert len(segs) == 1
        assert segs[0].ccw is True

    def test_full_circle_splits_two(self):
        segs = arc_segments((0, 0), 1.0, 0, 2 * math.pi)
        assert len(segs) == 2


class TestBulgeSegment:
    def test_zero_bulge_is_line(self):
        segs = bulge_segment((0, 0), (1, 0), 0.0)
        assert len(segs) == 1
        assert not segs[0].is_arc

    def test_nonzero_bulge_is_arc(self):
        segs = bulge_segment((0, 0), (2, 0), 1.0)
        assert len(segs) >= 1
        assert segs[0].is_arc


class TestChain:
    def test_simple_triangle(self):
        segs = [
            Seg((0, 0), (1, 0)),
            Seg((1, 0), (0.5, 1)),
            Seg((0.5, 1), (0, 0)),
        ]
        loops, open_ = chain(segs, 0.01)
        assert len(loops) == 1
        assert len(open_) == 0

    def test_reversed_segments(self):
        segs = [
            Seg((0, 0), (1, 0)),
            Seg((0.5, 1), (1, 0)),  # reversed
            Seg((0.5, 1), (0, 0)),
        ]
        loops, open_ = chain(segs, 0.01)
        assert len(loops) == 1


class TestLoopArea:
    def test_unit_square_ccw(self):
        loop = [
            Seg((0, 0), (1, 0)),
            Seg((1, 0), (1, 1)),
            Seg((1, 1), (0, 1)),
            Seg((0, 1), (0, 0)),
        ]
        assert abs(loop_area(loop) - 1.0) < 1e-10

    def test_unit_square_cw(self):
        loop = [
            Seg((0, 0), (0, 1)),
            Seg((0, 1), (1, 1)),
            Seg((1, 1), (1, 0)),
            Seg((1, 0), (0, 0)),
        ]
        assert abs(loop_area(loop) + 1.0) < 1e-10

    def test_circle_area(self):
        r = 10.0
        segs = arc_segments((0, 0), r, 0, 2 * math.pi)
        area = loop_area(segs)
        assert abs(area - math.pi * r**2) < 0.01


class TestLoopPerimeter:
    def test_unit_square(self):
        loop = [
            Seg((0, 0), (1, 0)),
            Seg((1, 0), (1, 1)),
            Seg((1, 1), (0, 1)),
            Seg((0, 1), (0, 0)),
        ]
        assert abs(loop_perimeter(loop) - 4.0) < 1e-10

    def test_circle_perimeter(self):
        r = 10.0
        segs = arc_segments((0, 0), r, 0, 2 * math.pi)
        perim = loop_perimeter(segs)
        assert abs(perim - 2 * math.pi * r) < 0.01


class TestLoopBbox:
    def test_square(self):
        loop = [
            Seg((1, 2), (3, 2)),
            Seg((3, 2), (3, 5)),
            Seg((3, 5), (1, 5)),
            Seg((1, 5), (1, 2)),
        ]
        xmin, ymin, xmax, ymax = loop_bbox(loop)
        assert abs(xmin - 1) < 1e-10
        assert abs(ymin - 2) < 1e-10
        assert abs(xmax - 3) < 1e-10
        assert abs(ymax - 5) < 1e-10


class TestStartAtLeft:
    def test_rotates_to_leftmost(self):
        loop = [
            Seg((5, 0), (5, 5)),
            Seg((5, 5), (0, 5)),
            Seg((0, 5), (0, 0)),
            Seg((0, 0), (5, 0)),
        ]
        rotated = start_at_left(loop)
        assert rotated[0].p0[0] < 1e-6


class TestReverseLoop:
    def test_reverses(self):
        loop = [
            Seg((0, 0), (1, 0)),
            Seg((1, 0), (1, 1)),
        ]
        rev = reverse_loop(loop)
        assert rev[0].p0 == (1, 1)
        assert rev[0].p1 == (1, 0)
        assert rev[1].p0 == (1, 0)
        assert rev[1].p1 == (0, 0)
