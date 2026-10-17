"""True-shape nesting engine using spyrrow (sparrow wrapper).

Spyrrow solves strip packing: fixed height, minimizes width.
We map this to sheet packing by using sheet.width as strip_height,
then slice the resulting strip into sheet-length segments.
"""

from __future__ import annotations

from dataclasses import dataclass

import spyrrow
from shapely.geometry import Polygon

from plate_nesting.geometry.polygon import loop_to_points
from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet


@dataclass
class _PartEntry:
    """Internal bookkeeping for a part in the nesting queue."""

    part: Part
    index: int
    points: list[tuple[float, float]]


def _part_to_points(
    part: Part, tol: float = 0.5
) -> list[tuple[float, float]]:
    """Convert part outer contour to polygon points for spyrrow."""
    if part.outer:
        pts = loop_to_points(part.outer, tol)
        if len(pts) >= 3:
            return pts
    return [
        (0.0, 0.0),
        (part.length, 0.0),
        (part.length, part.width),
        (0.0, part.width),
    ]


def _rotation_angles(options: NestOptions) -> list[float] | None:
    """Build the list of allowed rotation angles for spyrrow."""
    step = options.rotation_step
    if step <= 0:
        return [0.0]
    angles: list[float] = []
    a = 0.0
    while a < 360.0 - 1e-9:
        angles.append(a)
        a += step
    return angles if angles else [0.0]


def _offset_points(
    pts: list[tuple[float, float]], offset: float
) -> list[tuple[float, float]]:
    """Grow a polygon by a uniform offset using Shapely buffer."""
    if offset <= 0:
        return pts
    poly = Polygon(pts)
    if poly.is_empty or not poly.is_valid:
        return pts
    buffered = poly.buffer(offset, join_style="mitre", mitre_limit=2.0)
    if buffered.is_empty:
        return pts
    coords = list(buffered.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return coords


def _placed_bbox_x(
    pi: spyrrow.PlacedItem,
    entry: _PartEntry,
    spacing: float,
) -> tuple[float, float]:
    """Compute the x-extent of a placed item (with spacing offset).

    Returns (x_min, x_max) in strip coordinates.
    """
    import math

    pts = _offset_points(entry.points, spacing / 2)
    rad = math.radians(pi.rotation)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    tx, ty = pi.translation
    xs: list[float] = []
    for px, py in pts:
        rx = px * cos_r - py * sin_r + tx
        xs.append(rx)
    return min(xs), max(xs)


class TrueShapeEngine:
    """True-shape nesting engine backed by spyrrow."""

    def __init__(self, time_budget: int = 30) -> None:
        self.time_budget = time_budget

    def nest(
        self,
        parts: list[Part],
        sheets: list[Sheet],
        options: NestOptions,
    ) -> list[Layout]:
        """Nest parts onto sheets using true-shape packing."""
        sheet = sheets[0] if sheets else Sheet(6000, 2500)
        margin = options.edge_margin

        # Expand parts by quantity
        entries: list[_PartEntry] = []
        idx = 0
        prio = options.priorities
        for part in parts:
            for _ in range(part.qty):
                pts = _part_to_points(part)
                entries.append(
                    _PartEntry(part=part, index=idx, points=pts)
                )
                idx += 1

        # Sort by priority (descending), then area (descending)
        entries.sort(
            key=lambda e: (
                -prio.get(e.part.name, 0),
                -abs(_poly_area(e.points)),
            ),
        )

        if not entries:
            return []

        # Build spyrrow items
        orientations = _rotation_angles(options)
        items: list[spyrrow.Item] = []
        entry_by_id: dict[str, _PartEntry] = {}

        for entry in entries:
            item_id = f"{entry.part.name}_{entry.index}"
            entry_by_id[item_id] = entry
            offset = options.spacing / 2
            pts = _offset_points(entry.points, offset)
            items.append(
                spyrrow.Item(
                    id=item_id,
                    shape=pts,
                    demand=1,
                    allowed_orientations=orientations,
                )
            )

        effective_height = sheet.width - 2 * margin
        if effective_height <= 0:
            return []

        instance = spyrrow.StripPackingInstance(
            name="nest",
            strip_height=effective_height,
            items=items,
        )
        config = spyrrow.StripPackingConfig(
            total_computation_time=self.time_budget,
            seed=options.seed,
        )
        solution = instance.solve(config)

        # Slice the strip into sheet-length segments
        usable_length = sheet.length - 2 * margin
        if usable_length <= 0:
            return []

        # Compute each placed item's x-extent to assign to sheets
        placements_with_x: list[
            tuple[float, float, spyrrow.PlacedItem, _PartEntry]
        ] = []
        for pi in solution.placed_items:
            entry = entry_by_id.get(pi.id)
            if entry is None:
                continue
            x_min, x_max = _placed_bbox_x(pi, entry, options.spacing)
            placements_with_x.append((x_min, x_max, pi, entry))

        # Sort by x_min to assign greedily to sheets
        placements_with_x.sort(key=lambda t: t[0])

        layouts: list[Layout] = []
        sheet_idx = 0
        sheet_x_start = 0.0

        current_layout = Layout(sheet=sheet)

        for x_min, x_max, pi, entry in placements_with_x:
            # Check if this part fits on the current sheet
            local_x_max = x_max - sheet_x_start
            if local_x_max > usable_length and current_layout.placements:
                # Start a new sheet
                layouts.append(current_layout)
                current_layout = Layout(sheet=sheet)
                sheet_idx += 1
                sheet_x_start = x_min

            tx, ty = pi.translation
            current_layout.placements.append(
                PlacedPart(
                    part=entry.part,
                    x=tx - sheet_x_start + margin,
                    y=ty + margin,
                    rotation=pi.rotation,
                )
            )

        if current_layout.placements:
            layouts.append(current_layout)

        return layouts


def _poly_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area of a polygon."""
    n = len(pts)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return a / 2
