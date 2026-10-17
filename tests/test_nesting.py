"""Tests for the MaxRects nesting engine and layout validator."""

from __future__ import annotations

from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet
from plate_nesting.nesting.maxrects import MaxRectsBin, MaxRectsEngine
from plate_nesting.nesting.validator import validate_layout
from tests.conftest import NC1_DIR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rect_part(name: str, length: float, width: float, qty: int = 1) -> Part:
    """Create a simple rectangular Part (no contour needed for bbox nesting)."""
    return Part(name=name, length=length, width=width, qty=qty)


def _validate(layouts: list[Layout], opts: NestOptions) -> None:
    """Run validator on every layout and assert all pass."""
    for layout in layouts:
        result = validate_layout(
            layout, spacing=opts.spacing, edge_margin=opts.edge_margin
        )
        assert result.valid, (
            f"Validation failed on sheet with {len(layout.placements)} parts:\n"
            + "\n".join(result.errors)
        )


# ---------------------------------------------------------------------------
# MaxRectsBin unit tests
# ---------------------------------------------------------------------------

class TestMaxRectsBin:
    def test_single_fit(self):
        packer = MaxRectsBin(100, 100)
        r = packer.insert(50, 50)
        assert r is not None
        assert r.x == 0 and r.y == 0
        assert r.w == 50 and r.h == 50

    def test_does_not_fit(self):
        packer = MaxRectsBin(100, 100)
        r = packer.insert(150, 50)
        assert r is None

    def test_two_side_by_side(self):
        packer = MaxRectsBin(100, 50)
        r1 = packer.insert(50, 50)
        r2 = packer.insert(50, 50)
        assert r1 is not None
        assert r2 is not None
        # They should not overlap
        assert (
            r1.x + r1.w <= r2.x + 0.01
            or r2.x + r2.w <= r1.x + 0.01
            or r1.y + r1.h <= r2.y + 0.01
            or r2.y + r2.h <= r1.y + 0.01
        )

    def test_fill_bin(self):
        packer = MaxRectsBin(100, 100)
        placed = 0
        for _ in range(4):
            r = packer.insert(50, 50)
            if r:
                placed += 1
        assert placed == 4

    def test_no_fifth_in_full_bin(self):
        packer = MaxRectsBin(100, 100)
        for _ in range(4):
            packer.insert(50, 50)
        assert packer.insert(50, 50) is None


# ---------------------------------------------------------------------------
# MaxRectsEngine integration tests
# ---------------------------------------------------------------------------

class TestMaxRectsEngine:
    def test_single_part(self):
        engine = MaxRectsEngine()
        parts = [_rect_part("a", 100, 50)]
        sheets = [Sheet(1000, 1000)]
        opts = NestOptions(spacing=0, edge_margin=0)
        layouts = engine.nest(parts, sheets, opts)
        assert len(layouts) == 1
        assert len(layouts[0].placements) == 1
        _validate(layouts, opts)

    def test_multiple_parts_same_sheet(self):
        engine = MaxRectsEngine()
        parts = [
            _rect_part("a", 200, 100, qty=3),
            _rect_part("b", 150, 150, qty=2),
        ]
        sheets = [Sheet(2000, 2000)]
        opts = NestOptions(spacing=10, edge_margin=10)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 5  # 3 + 2
        _validate(layouts, opts)

    def test_overflow_to_second_sheet(self):
        engine = MaxRectsEngine()
        # Each part is 500x500, sheet is 1000x1000, so 4 fit per sheet
        parts = [_rect_part("big", 500, 500, qty=5)]
        sheets = [Sheet(1000, 1000)]
        opts = NestOptions(spacing=0, edge_margin=0)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 5
        assert len(layouts) == 2  # 4 on first, 1 on second
        _validate(layouts, opts)

    def test_respects_edge_margin(self):
        engine = MaxRectsEngine()
        parts = [_rect_part("a", 100, 100)]
        sheets = [Sheet(200, 200)]
        opts = NestOptions(spacing=0, edge_margin=20)
        layouts = engine.nest(parts, sheets, opts)
        assert len(layouts) == 1
        pp = layouts[0].placements[0]
        assert pp.x >= 20 - 0.01
        assert pp.y >= 20 - 0.01
        _validate(layouts, opts)

    def test_part_too_big_for_sheet(self):
        engine = MaxRectsEngine()
        parts = [_rect_part("huge", 5000, 5000)]
        sheets = [Sheet(1000, 1000)]
        opts = NestOptions(spacing=0, edge_margin=0)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 0  # cannot fit

    def test_spacing_between_parts(self):
        engine = MaxRectsEngine()
        parts = [_rect_part("s", 100, 100, qty=2)]
        sheets = [Sheet(1000, 1000)]
        opts = NestOptions(spacing=20, edge_margin=0)
        layouts = engine.nest(parts, sheets, opts)
        assert len(layouts) == 1
        _validate(layouts, opts)

    def test_rotation_allows_fit(self):
        """A 900x100 part shouldn't fit in a 500x500 sheet without rotation,
        but with 90° rotation it becomes 100x900... still doesn't fit.
        Use a case where rotation helps."""
        engine = MaxRectsEngine()
        # 300x100 part, sheet 200x400 — at 0° doesn't fit (300>200),
        # at 90° becomes 100x300 which fits in 200x400
        parts = [_rect_part("r", 300, 100)]
        sheets = [Sheet(200, 400)]
        opts = NestOptions(spacing=0, edge_margin=0, rotation_step=90)
        layouts = engine.nest(parts, sheets, opts)
        total = sum(len(ly.placements) for ly in layouts)
        assert total == 1
        _validate(layouts, opts)


# ---------------------------------------------------------------------------
# Deterministic seed test
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_same_result(self):
        engine = MaxRectsEngine()
        parts = [
            _rect_part("a", 200, 100, qty=5),
            _rect_part("b", 150, 80, qty=4),
            _rect_part("c", 300, 200, qty=3),
        ]
        sheets = [Sheet(2000, 1500)]

        for seed in [42, 123, 999]:
            opts = NestOptions(spacing=10, edge_margin=10, seed=seed)
            r1 = engine.nest(parts, sheets, opts)
            r2 = engine.nest(parts, sheets, opts)
            assert len(r1) == len(r2)
            for ly1, ly2 in zip(r1, r2):
                assert len(ly1.placements) == len(ly2.placements)
                for p1, p2 in zip(ly1.placements, ly2.placements):
                    assert p1.part.name == p2.part.name
                    assert abs(p1.x - p2.x) < 0.01
                    assert abs(p1.y - p2.y) < 0.01
                    assert p1.rotation == p2.rotation


# ---------------------------------------------------------------------------
# Validator-specific tests
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid_layout(self):
        sheet = Sheet(1000, 1000)
        pp = PlacedPart(
            part=_rect_part("a", 100, 100), x=10, y=10
        )
        layout = Layout(sheet=sheet, placements=[pp])
        result = validate_layout(layout, spacing=0, edge_margin=0)
        assert result.valid

    def test_overlap_detected(self):
        sheet = Sheet(1000, 1000)
        p = _rect_part("a", 100, 100)
        layout = Layout(
            sheet=sheet,
            placements=[
                PlacedPart(part=p, x=0, y=0),
                PlacedPart(part=p, x=50, y=50),  # overlaps
            ],
        )
        result = validate_layout(layout, spacing=0, edge_margin=0)
        assert not result.valid
        assert any("overlap" in e for e in result.errors)

    def test_outside_sheet_detected(self):
        sheet = Sheet(100, 100)
        pp = PlacedPart(
            part=_rect_part("a", 200, 200), x=0, y=0
        )
        layout = Layout(sheet=sheet, placements=[pp])
        result = validate_layout(layout, spacing=0, edge_margin=0)
        assert not result.valid
        assert any("outside" in e for e in result.errors)

    def test_spacing_violation_detected(self):
        sheet = Sheet(1000, 1000)
        p = _rect_part("a", 100, 100)
        layout = Layout(
            sheet=sheet,
            placements=[
                PlacedPart(part=p, x=0, y=0),
                PlacedPart(part=p, x=105, y=0),  # 5mm gap
            ],
        )
        result = validate_layout(layout, spacing=20, edge_margin=0)
        assert not result.valid
        assert any("spacing" in e for e in result.errors)

    def test_empty_layout_is_valid(self):
        layout = Layout(sheet=Sheet(1000, 1000))
        result = validate_layout(layout)
        assert result.valid


# ---------------------------------------------------------------------------
# Benchmark with reference parts
# ---------------------------------------------------------------------------

class TestBenchmarkReference:
    """Nest the 144 reference parts at their real quantities onto sheets."""

    def test_nest_reference_parts(self):
        from plate_nesting.nc1.parser import parse_nc1

        nc1_files = sorted(NC1_DIR.glob("*.nc1"))
        assert len(nc1_files) == 144

        # Group parts by grade+thickness
        groups: dict[tuple[str, float], list[Part]] = {}
        for f in nc1_files:
            part = parse_nc1(f.read_text())
            key = (part.grade, part.thickness)
            groups.setdefault(key, []).append(part)

        engine = MaxRectsEngine()
        opts = NestOptions(spacing=10, edge_margin=10, seed=42)

        total_parts = 0
        total_placed = 0
        total_sheets = 0
        utilizations: list[float] = []

        for (grade, thk), parts in sorted(groups.items()):
            # Set sheet material to match
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
                    utilizations.append(ly.utilization)

            # Validate every layout
            for ly in layouts:
                result = validate_layout(
                    ly, spacing=opts.spacing, edge_margin=opts.edge_margin
                )
                assert result.valid, (
                    f"Validation failed for {grade}/{thk}:\n"
                    + "\n".join(result.errors)
                )

        # Report
        avg_util = (
            sum(utilizations) / len(utilizations) if utilizations else 0
        )
        print("\n--- MaxRects Benchmark (reference parts) ---")
        print(f"Part types: {len(nc1_files)}")
        print(f"Total part instances: {total_parts}")
        print(f"Placed: {total_placed}")
        print(f"Sheets used: {total_sheets}")
        print(f"Avg utilization: {avg_util:.1%}")
        print(f"Groups: {len(groups)}")

        # All parts should be placed
        assert total_placed == total_parts, (
            f"Not all parts placed: {total_placed}/{total_parts}"
        )
