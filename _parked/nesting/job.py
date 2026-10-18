"""Job-level nesting orchestrator.

Groups parts by grade+thickness, selects sheets, enforces grain rotation,
collects remnants, and reports per-sheet weight.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from plate_nesting.cutting.common_cut import detect_common_cuts
from plate_nesting.materials.inventory import Remnant, SheetInventory
from plate_nesting.models.layout import Layout
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import GrainDirection, Sheet
from plate_nesting.nesting import nest


@dataclass
class SheetReport:
    """Per-sheet summary."""

    layout: Layout
    grade: str
    thickness: float
    part_count: int
    sheet_weight: float  # kg, full sheet
    nested_weight: float  # kg, parts only
    utilization: float  # fraction 0-1

    @property
    def scrap_weight(self) -> float:
        return self.sheet_weight - self.nested_weight


@dataclass
class JobResult:
    """Result of a complete nesting job."""

    sheet_reports: list[SheetReport] = field(default_factory=list)
    remnants: list[Remnant] = field(default_factory=list)
    unplaced: list[Part] = field(default_factory=list)

    @property
    def total_sheets(self) -> int:
        return len(self.sheet_reports)

    @property
    def total_parts_placed(self) -> int:
        return sum(r.part_count for r in self.sheet_reports)

    @property
    def total_sheet_weight(self) -> float:
        return sum(r.sheet_weight for r in self.sheet_reports)

    @property
    def total_nested_weight(self) -> float:
        return sum(r.nested_weight for r in self.sheet_reports)

    @property
    def avg_utilization(self) -> float:
        if not self.sheet_reports:
            return 0.0
        return sum(r.utilization for r in self.sheet_reports) / len(
            self.sheet_reports
        )


def _grain_options(
    base: NestOptions, grain: GrainDirection
) -> NestOptions:
    """Adjust rotation step for grain direction constraints.

    When grain is constrained, parts can only rotate 0° or 180°
    (parallel to grain) to preserve rolling direction alignment.
    """
    if grain == GrainDirection.NONE:
        return base
    # With grain constraint, only allow 0° and 180° rotation
    from dataclasses import replace

    return replace(base, rotation_step=180.0)


def _compute_remnant(
    layout: Layout, options: NestOptions
) -> Remnant | None:
    """Compute the leftover rectangular remnant from a layout.

    The remnant is the unused strip to the right of the rightmost part.
    """
    if not layout.placements:
        return None

    margin = options.edge_margin
    max_x = 0.0
    for pp in layout.placements:
        right = pp.x + pp.placed_length
        if right > max_x:
            max_x = right

    # Remaining strip to the right
    remaining_length = layout.sheet.length - max_x - margin
    remaining_width = layout.sheet.width - 2 * margin

    # Only create remnant if it's at least 200mm in both dimensions
    min_dim = 200.0
    if remaining_length < min_dim or remaining_width < min_dim:
        return None

    return Remnant(
        length=remaining_length,
        width=remaining_width,
        grade=layout.sheet.grade,
        thickness=layout.sheet.thickness,
        label=f"remnant from {layout.sheet.label}",
        grain=layout.sheet.grain,
    )


def _sheet_weight(sheet: Sheet) -> float:
    """Sheet weight in kg."""
    return sheet.thickness * 7.85e-6 * sheet.area


def _nested_weight(layout: Layout) -> float:
    """Total weight of placed parts in kg."""
    thk = layout.sheet.thickness
    density = 7.85e-6  # kg/mm³
    w = 0.0
    for pp in layout.placements:
        # Use bounding-box area as approximation
        w += pp.placed_length * pp.placed_width * thk * density
    return w


def nest_job(
    parts: list[Part],
    inventory: SheetInventory | None = None,
    options: NestOptions | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> JobResult:
    """Run a complete nesting job.

    Groups parts by grade+thickness, nests each group onto matching sheets
    from the inventory, collects remnants, and returns a full report.

    Args:
        parts: All parts to nest.
        inventory: Sheet inventory. Defaults to standard sizes.
        options: Nesting options.
        on_progress: Optional callback for stage updates.

    Returns:
        JobResult with per-sheet reports and remnants.
    """
    def _emit(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    if inventory is None:
        inventory = SheetInventory.default()
    if options is None:
        options = NestOptions()

    # Group parts by grade+thickness
    total_parts = sum(p.qty for p in parts)
    groups: dict[tuple[str, float], list[Part]] = {}
    for part in parts:
        key = (part.grade, part.thickness)
        groups.setdefault(key, []).append(part)

    _emit(f"Grouped {total_parts} parts into {len(groups)} material group(s)")

    result = JobResult()
    group_list = sorted(groups.items())

    for gi, ((grade, thickness), group_parts) in enumerate(group_list, 1):
        group_qty = sum(p.qty for p in group_parts)
        label = f"{grade} {thickness:g}mm" if grade else f"{thickness:g}mm"
        _emit(f"Optimizing group {gi}/{len(group_list)}: {label} ({group_qty} parts)")

        available = inventory.sheets_for_group(grade, thickness)
        if not available:
            # Fallback: use default 6000x2500
            available = [
                Sheet(
                    6000,
                    2500,
                    grade=grade,
                    thickness=thickness,
                    label="6000x2500",
                )
            ]

        # Apply grain rotation constraints from the first sheet
        grain = available[0].grain
        group_options = _grain_options(options, grain)

        layouts = nest(group_parts, available, group_options, on_progress=on_progress)

        # Determine which parts were placed vs skipped (too large)
        placed_names: set[str] = set()
        for layout in layouts:
            for pp in layout.placements:
                placed_names.add(pp.part.name)
        for part in group_parts:
            if part.name not in placed_names:
                result.unplaced.append(part)

        # Detect common cuts if enabled and thickness within threshold
        if (
            options.common_cuts
            and thickness <= options.common_cut_max_thickness
        ):
            _emit(f"Detecting common cuts for group {gi}/{len(group_list)}")
            for layout in layouts:
                layout.common_cuts = detect_common_cuts(
                    layout, options.spacing
                )

        for layout in layouts:
            # Ensure sheet has correct material
            layout.sheet.grade = grade
            layout.sheet.thickness = thickness

            sw = _sheet_weight(layout.sheet)
            nw = _nested_weight(layout)

            report = SheetReport(
                layout=layout,
                grade=grade,
                thickness=thickness,
                part_count=len(layout.placements),
                sheet_weight=sw,
                nested_weight=nw,
                utilization=layout.utilization,
            )
            result.sheet_reports.append(report)

            # Collect remnant
            remnant = _compute_remnant(layout, options)
            if remnant:
                result.remnants.append(remnant)

    _emit("Finalizing results")
    return result
