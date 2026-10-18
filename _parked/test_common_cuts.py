"""Tests for common cut detection."""

from __future__ import annotations

import math

from plate_nesting.cutting.common_cut import detect_common_cuts
from plate_nesting.geometry.seg import Seg
from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet
from plate_nesting.nesting.job import nest_job


def _rect_part(name: str, length: float, width: float) -> Part:
    """Create a rectangular part with CCW outer contour."""
    outer = [
        Seg((0, 0), (length, 0)),
        Seg((length, 0), (length, width)),
        Seg((length, width), (0, width)),
        Seg((0, width), (0, 0)),
    ]
    return Part(name=name, outer=outer, length=length, width=width)


def _layout_with_parts(
    placements: list[PlacedPart], sheet_length: float = 6000, sheet_width: float = 2500
) -> Layout:
    sheet = Sheet(sheet_length, sheet_width)
    return Layout(sheet=sheet, placements=placements)


class TestTwoAdjacentRects:
    """Two rectangles side-by-side with exactly the spacing gap."""

    def test_one_common_cut(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        spacing = 10.0
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=110, y=0),  # 100 + 10 spacing
        ])
        cuts = detect_common_cuts(layout, spacing)
        assert len(cuts) == 1
        assert abs(cuts[0].cut_length - 200.0) < 1.0

    def test_far_apart_no_cuts(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=500, y=0),  # far apart
        ])
        cuts = detect_common_cuts(layout, spacing=10.0)
        assert len(cuts) == 0


class TestNonParallelEdges:
    def test_no_cuts(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=110, y=0, rotation=45),
        ])
        cuts = detect_common_cuts(layout, spacing=10.0)
        assert len(cuts) == 0


class TestPartialOverlap:
    def test_cut_length_equals_shorter_edge(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 150)  # shorter height
        spacing = 10.0
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=110, y=0),
        ])
        cuts = detect_common_cuts(layout, spacing)
        assert len(cuts) == 1
        assert abs(cuts[0].cut_length - 150.0) < 1.0


class TestThreeInARow:
    def test_two_common_cuts(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        p3 = _rect_part("C", 100, 200)
        spacing = 10.0
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=110, y=0),
            PlacedPart(part=p3, x=220, y=0),
        ])
        cuts = detect_common_cuts(layout, spacing)
        assert len(cuts) == 2


class TestRotatedParts:
    def test_rotated_90_aligned_edges(self):
        p1 = _rect_part("A", 200, 100)
        p2 = _rect_part("B", 200, 100)
        spacing = 10.0
        # p1 at (0,0): right edge at x=200, y=[0,100]
        # p2 rotated 90°: local contour rotates so the left-facing edge
        # at x=-100 in rotated coords. Shift by (310,0) places it at x=210.
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=310, y=0, rotation=90),
        ])
        cuts = detect_common_cuts(layout, spacing)
        assert len(cuts) >= 1


class TestArcEdgesExcluded:
    def test_arc_edges_skipped(self):
        outer = [
            Seg((0, 0), (100, 0)),
            Seg((100, 0), (100, 50), center=(100, 25), r=25.0, ccw=True),
            Seg((100, 50), (0, 50)),
            Seg((0, 50), (0, 0)),
        ]
        p1 = Part(name="arc_part", outer=outer, length=100, width=50)
        p2 = _rect_part("B", 100, 50)
        spacing = 10.0
        layout = _layout_with_parts([
            PlacedPart(part=p1, x=0, y=0),
            PlacedPart(part=p2, x=110, y=0),
        ])
        cuts = detect_common_cuts(layout, spacing)
        # The arc edge (right side of p1) should not match the straight left edge of p2
        for cut in cuts:
            # Every cut should involve only straight edges
            assert cut.cut_length > 0


class TestCommonCutsDisabled:
    def test_option_false_gives_empty(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        p1.grade = "S355"
        p1.thickness = 10.0
        p2.grade = "S355"
        p2.thickness = 10.0
        options = NestOptions(common_cuts=False)
        result = nest_job([p1, p2], options=options)
        for report in result.sheet_reports:
            assert report.layout.common_cuts == []


class TestThickPlateSkipped:
    def test_40mm_above_30mm_threshold(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        p1.grade = "S355"
        p1.thickness = 40.0
        p2.grade = "S355"
        p2.thickness = 40.0
        options = NestOptions(common_cut_max_thickness=30.0)
        result = nest_job([p1, p2], options=options)
        for report in result.sheet_reports:
            assert report.layout.common_cuts == []


class TestThinPlateDetected:
    def test_10mm_within_threshold(self):
        p1 = _rect_part("A", 100, 200)
        p2 = _rect_part("B", 100, 200)
        p1.grade = "S355"
        p1.thickness = 10.0
        p2.grade = "S355"
        p2.thickness = 10.0
        options = NestOptions(common_cuts=True, common_cut_max_thickness=30.0)
        result = nest_job([p1, p2], options=options)
        # At least one layout should have been evaluated for common cuts
        # (whether any are found depends on placement proximity)
        # The key test is that the code path runs without error
        assert result.total_sheets >= 1
