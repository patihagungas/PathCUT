"""Tests for the true-shape nesting engine (spyrrow) and part-in-part."""

from __future__ import annotations

from plate_nesting.geometry.seg import Seg
from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet
from plate_nesting.nesting.partinpart import fill_cutouts
from plate_nesting.nesting.trueshape import TrueShapeEngine
from plate_nesting.nesting.validator import validate_layout
from tests.conftest import NC1_DIR


def _rect_part(
    name: str, length: float, width: float, qty: int = 1
) -> Part:
    """Create a rectangular Part with actual outer contour."""
    outer = [
        Seg((0, 0), (length, 0)),
        Seg((length, 0), (length, width)),
        Seg((length, width), (0, width)),
        Seg((0, width), (0, 0)),
    ]
    return Part(
        name=name, outer=outer, length=length, width=width, qty=qty
    )


def _validate_all(
    layouts: list[Layout], opts: NestOptions, true_shape: bool = True
) -> None:
    """Assert all layouts pass validation."""
    for ly in layouts:
        r = validate_layout(
            ly,
            spacing=opts.spacing,
            edge_margin=opts.edge_margin,
            true_shape=true_shape,
        )
        assert r.valid, (
            f"Validation failed ({len(ly.placements)} parts):\n"
            + "\n".join(r.errors)
        )


class TestTrueShapeEngine:
    def test_single_part(self):
        engine = TrueShapeEngine(time_budget=3)
        parts = [_rect_part("a", 200, 100)]
        sheets = [Sheet(2000, 1000)]
        opts = NestOptions(spacing=0, edge_margin=0, seed=42)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 1
        _validate_all(layouts, opts)

    def test_multiple_parts(self):
        engine = TrueShapeEngine(time_budget=5)
        parts = [
            _rect_part("a", 200, 100, qty=3),
            _rect_part("b", 150, 150, qty=2),
        ]
        sheets = [Sheet(2000, 1000)]
        opts = NestOptions(spacing=10, edge_margin=10, seed=42)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 5
        _validate_all(layouts, opts)

    def test_multi_sheet_overflow(self):
        engine = TrueShapeEngine(time_budget=5)
        parts = [_rect_part("big", 2000, 800, qty=4)]
        sheets = [Sheet(3000, 1000)]
        opts = NestOptions(spacing=10, edge_margin=10, seed=42)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 4
        assert len(layouts) >= 2
        _validate_all(layouts, opts)

    def test_rotation_helps(self):
        engine = TrueShapeEngine(time_budget=5)
        # 300x80 part in a 200x400 sheet — needs 90° rotation
        parts = [_rect_part("r", 300, 80)]
        sheets = [Sheet(200, 400)]
        opts = NestOptions(
            spacing=0, edge_margin=0, rotation_step=90, seed=42
        )
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 1
        _validate_all(layouts, opts)


class TestTrueShapeDeterminism:
    def test_same_seed_same_result(self):
        engine = TrueShapeEngine(time_budget=3)
        parts = [
            _rect_part("a", 200, 100, qty=3),
            _rect_part("b", 150, 80, qty=2),
        ]
        sheets = [Sheet(2000, 1000)]
        opts = NestOptions(spacing=10, edge_margin=10, seed=42)

        r1 = engine.nest(parts, sheets, opts)
        r2 = engine.nest(parts, sheets, opts)
        assert len(r1) == len(r2)
        for ly1, ly2 in zip(r1, r2):
            assert len(ly1.placements) == len(ly2.placements)
            for p1, p2 in zip(ly1.placements, ly2.placements):
                assert p1.part.name == p2.part.name
                assert abs(p1.x - p2.x) < 0.01
                assert abs(p1.y - p2.y) < 0.01


class TestPartInPart:
    def test_small_part_in_ring_cutout(self):
        """6C-p5 (615x350) should fit inside 6C-p1's cutout (r=722)."""
        from plate_nesting.nc1.parser import parse_nc1

        ring = parse_nc1((NC1_DIR / "6C-p1.nc1").read_text())
        small = parse_nc1((NC1_DIR / "6C-p5.nc1").read_text())

        sheet = Sheet(6000, 2500)
        layout = Layout(
            sheet=sheet,
            placements=[PlacedPart(part=ring, x=10, y=10)],
        )

        unplaced_part = Part(
            name=small.name,
            outer=small.outer,
            inners=small.inners,
            holes=small.holes,
            grade=small.grade,
            thickness=small.thickness,
            qty=1,
            length=small.length,
            width=small.width,
        )
        still = fill_cutouts(
            [layout],
            [unplaced_part],
            NestOptions(spacing=10),
        )
        assert len(still) == 0, "Small part should fit in ring cutout"
        assert len(layout.placements) == 2

        # Validate with true-shape (polygon with holes)
        r = validate_layout(
            layout, spacing=10, edge_margin=0, true_shape=True
        )
        assert r.valid, f"Validation failed: {r.errors}"

    def test_too_big_part_stays_unplaced(self):
        """A part larger than the cutout should not be placed."""
        from plate_nesting.nc1.parser import parse_nc1

        ring = parse_nc1((NC1_DIR / "6C-p1.nc1").read_text())

        sheet = Sheet(6000, 2500)
        layout = Layout(
            sheet=sheet,
            placements=[PlacedPart(part=ring, x=10, y=10)],
        )

        big_part = _rect_part("huge", 2000, 2000)
        still = fill_cutouts(
            [layout],
            [big_part],
            NestOptions(spacing=10),
        )
        assert len(still) == 1
        assert len(layout.placements) == 1


class TestBenchmarkTrueShape:
    """Benchmark true-shape nester on all reference parts.

    Compare utilization against MaxRects baseline (68.2% on 91 sheets).
    """

    def test_nest_all_reference_parts(self):
        from plate_nesting.nc1.parser import parse_nc1

        nc1_files = sorted(NC1_DIR.glob("*.nc1"))
        assert len(nc1_files) == 144

        groups: dict[tuple[str, float], list[Part]] = {}
        for fp in nc1_files:
            part = parse_nc1(fp.read_text())
            key = (part.grade, part.thickness)
            groups.setdefault(key, []).append(part)

        engine = TrueShapeEngine(time_budget=10)
        opts = NestOptions(spacing=10, edge_margin=10, seed=42)

        total_parts = 0
        total_placed = 0
        total_sheets = 0
        utils: list[float] = []

        for (grade, thk), parts in sorted(groups.items()):
            group_sheets = [
                Sheet(6000, 2500, grade=grade, thickness=thk)
            ]
            layouts = engine.nest(parts, group_sheets, opts)

            placed = sum(len(ly.placements) for ly in layouts)
            expected = sum(p.qty for p in parts)
            total_parts += expected
            total_placed += placed
            total_sheets += len(layouts)

            for ly in layouts:
                if ly.sheet.area > 0:
                    utils.append(ly.utilization)
                r = validate_layout(
                    ly,
                    spacing=opts.spacing,
                    edge_margin=opts.edge_margin,
                    true_shape=True,
                )
                assert r.valid, (
                    f"Validation failed for {grade}/{thk}:\n"
                    + "\n".join(r.errors)
                )

        avg_util = sum(utils) / len(utils) if utils else 0
        print("\n--- TrueShape Benchmark (reference parts) ---")
        print(f"Total: {total_placed}/{total_parts}")
        print(f"Sheets: {total_sheets}")
        print(f"Avg utilization: {avg_util:.1%}")
        print("(MaxRects baseline: 68.2% on 91 sheets)")

        assert total_placed == total_parts
