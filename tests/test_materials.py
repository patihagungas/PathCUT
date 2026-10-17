"""Tests for Phase 4: sheets, materials, inventory, and job orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from plate_nesting.geometry.seg import Seg
from plate_nesting.materials.inventory import Remnant, SheetInventory
from plate_nesting.models.nesting import EngineType, NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import GrainDirection, Sheet
from plate_nesting.nesting.job import nest_job
from plate_nesting.nesting.validator import validate_layout
from tests.conftest import NC1_DIR


def _rect_part(
    name: str,
    length: float,
    width: float,
    qty: int = 1,
    grade: str = "S355",
    thickness: float = 10.0,
) -> Part:
    outer = [
        Seg((0, 0), (length, 0)),
        Seg((length, 0), (length, width)),
        Seg((length, width), (0, width)),
        Seg((0, width), (0, 0)),
    ]
    return Part(
        name=name,
        outer=outer,
        length=length,
        width=width,
        qty=qty,
        grade=grade,
        thickness=thickness,
    )


# ---------------------------------------------------------------------------
# Sheet model
# ---------------------------------------------------------------------------


class TestSheet:
    def test_area(self):
        s = Sheet(6000, 2500)
        assert s.area == 15_000_000

    def test_weight(self):
        s = Sheet(6000, 2500, thickness=10.0)
        # 10mm * 7.85e-6 kg/mm³ * 15e6 mm² = 1177.5 kg
        assert abs(s.weight - 1177.5) < 0.1

    def test_grain_default_none(self):
        s = Sheet(1000, 500)
        assert s.grain == GrainDirection.NONE


# ---------------------------------------------------------------------------
# Sheet inventory
# ---------------------------------------------------------------------------


class TestSheetInventory:
    def test_default_has_standard_sizes(self):
        inv = SheetInventory.default()
        assert len(inv.standard_sizes) >= 3

    def test_sheets_for_group(self):
        inv = SheetInventory(
            standard_sizes=[
                Sheet(6000, 2500, label="big"),
                Sheet(3000, 1500, label="small"),
            ]
        )
        sheets = inv.sheets_for_group("S355", 10.0)
        assert len(sheets) == 2
        # Should be sorted largest first
        assert sheets[0].area >= sheets[1].area
        # All should have correct grade/thickness
        for s in sheets:
            assert s.grade == "S355"
            assert s.thickness == 10.0

    def test_remnants_included_in_sheets_for_group(self):
        inv = SheetInventory(
            standard_sizes=[Sheet(6000, 2500)],
            remnants=[
                Remnant(2000, 1000, grade="S355", thickness=10.0)
            ],
        )
        sheets = inv.sheets_for_group("S355", 10.0)
        assert len(sheets) == 2  # standard + remnant

    def test_remnants_filtered_by_material(self):
        inv = SheetInventory(
            remnants=[
                Remnant(2000, 1000, grade="S355", thickness=10.0),
                Remnant(3000, 1500, grade="S275", thickness=12.0),
            ]
        )
        sheets = inv.sheets_for_group("S355", 10.0)
        assert len(sheets) == 1
        assert sheets[0].grade == "S355"

    def test_save_and_load(self):
        inv = SheetInventory(
            standard_sizes=[
                Sheet(
                    6000,
                    2500,
                    label="std",
                    grain=GrainDirection.LENGTH,
                )
            ],
            remnants=[
                Remnant(
                    2000,
                    1000,
                    grade="S355",
                    thickness=10.0,
                    label="leftover",
                )
            ],
        )
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as f:
            path = f.name

        inv.save(path)
        loaded = SheetInventory.load(path)

        assert len(loaded.standard_sizes) == 1
        assert loaded.standard_sizes[0].length == 6000
        assert loaded.standard_sizes[0].grain == GrainDirection.LENGTH
        assert len(loaded.remnants) == 1
        assert loaded.remnants[0].grade == "S355"
        assert loaded.remnants[0].label == "leftover"

        Path(path).unlink()

    def test_add_remove_remnant(self):
        inv = SheetInventory()
        inv.add_remnant(Remnant(1000, 500, "S355", 10.0))
        assert len(inv.remnants) == 1
        inv.remove_remnant(0)
        assert len(inv.remnants) == 0


# ---------------------------------------------------------------------------
# Grain direction
# ---------------------------------------------------------------------------


class TestGrainDirection:
    def test_grain_limits_rotation(self):
        """With grain constraint, only 0° and 180° should be allowed."""
        from plate_nesting.nesting.job import _grain_options

        base = NestOptions(rotation_step=90.0)
        limited = _grain_options(base, GrainDirection.LENGTH)
        assert limited.rotation_step == 180.0

    def test_no_grain_keeps_rotation(self):
        from plate_nesting.nesting.job import _grain_options

        base = NestOptions(rotation_step=90.0)
        same = _grain_options(base, GrainDirection.NONE)
        assert same.rotation_step == 90.0


# ---------------------------------------------------------------------------
# Job orchestrator
# ---------------------------------------------------------------------------


class TestNestJob:
    def test_groups_by_material(self):
        """Parts of different grade+thickness go on separate sheets."""
        parts = [
            _rect_part("a", 500, 300, qty=2, grade="S355", thickness=10),
            _rect_part("b", 400, 200, qty=2, grade="S275", thickness=12),
        ]
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, options=opts)

        # Should have at least 2 sheets (one per material group)
        groups_seen = set()
        for sr in result.sheet_reports:
            groups_seen.add((sr.grade, sr.thickness))
        assert ("S355", 10.0) in groups_seen
        assert ("S275", 12.0) in groups_seen

        # No mixing: each sheet has one grade+thickness
        for sr in result.sheet_reports:
            for pp in sr.layout.placements:
                assert pp.part.grade == sr.grade
                assert pp.part.thickness == sr.thickness

    def test_all_parts_placed(self):
        parts = [
            _rect_part("x", 200, 100, qty=5, grade="S355", thickness=10),
        ]
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, options=opts)
        assert result.total_parts_placed == 5

    def test_weight_reporting(self):
        parts = [
            _rect_part("w", 1000, 500, qty=1, grade="S355", thickness=20),
        ]
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=0, edge_margin=0
        )
        result = nest_job(parts, options=opts)
        assert len(result.sheet_reports) >= 1
        sr = result.sheet_reports[0]
        assert sr.sheet_weight > 0
        assert sr.nested_weight > 0
        assert sr.scrap_weight >= 0

    def test_remnant_collection(self):
        parts = [
            _rect_part("r", 500, 400, qty=1, grade="S355", thickness=10),
        ]
        inv = SheetInventory(
            standard_sizes=[Sheet(6000, 2500, label="big")]
        )
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, inventory=inv, options=opts)
        # Large sheet with small part should produce a remnant
        assert len(result.remnants) >= 1
        rem = result.remnants[0]
        assert rem.grade == "S355"
        assert rem.thickness == 10.0
        assert rem.length > 0

    def test_custom_inventory(self):
        parts = [
            _rect_part("c", 200, 100, qty=3, grade="S355", thickness=10),
        ]
        inv = SheetInventory(
            standard_sizes=[Sheet(1000, 500, label="custom")]
        )
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, inventory=inv, options=opts)
        assert result.total_parts_placed == 3
        for sr in result.sheet_reports:
            assert sr.layout.sheet.length == 1000
            assert sr.layout.sheet.width == 500

    def test_validator_on_all_layouts(self):
        parts = [
            _rect_part("v", 300, 200, qty=5, grade="S355", thickness=10),
            _rect_part("u", 400, 150, qty=3, grade="S355", thickness=10),
        ]
        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, options=opts)
        for sr in result.sheet_reports:
            vr = validate_layout(
                sr.layout,
                spacing=opts.spacing,
                edge_margin=opts.edge_margin,
            )
            assert vr.valid, "Validation failed:\n" + "\n".join(vr.errors)


# ---------------------------------------------------------------------------
# Benchmark: full reference set through job orchestrator
# ---------------------------------------------------------------------------


class TestJobBenchmark:
    def test_full_reference_job(self):
        from plate_nesting.nc1.parser import parse_nc1

        nc1_files = sorted(NC1_DIR.glob("*.nc1"))
        parts = [parse_nc1(f.read_text()) for f in nc1_files]

        opts = NestOptions(
            engine=EngineType.MAXRECTS, spacing=10, edge_margin=10
        )
        result = nest_job(parts, options=opts)

        expected = sum(p.qty for p in parts)
        assert result.total_parts_placed == expected

        print("\n--- Job Benchmark (MaxRects) ---")
        print(f"Parts: {expected}")
        print(f"Sheets: {result.total_sheets}")
        print(f"Avg util: {result.avg_utilization:.1%}")
        print(
            f"Total weight: {result.total_sheet_weight:.0f} kg sheet, "
            f"{result.total_nested_weight:.0f} kg parts"
        )
        print(f"Remnants: {len(result.remnants)}")

        # Validate every layout
        for sr in result.sheet_reports:
            vr = validate_layout(
                sr.layout,
                spacing=opts.spacing,
                edge_margin=opts.edge_margin,
            )
            assert vr.valid, (
                f"Sheet {sr.grade}/{sr.thickness} invalid:\n"
                + "\n".join(vr.errors)
            )
