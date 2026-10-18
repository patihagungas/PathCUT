"""True-shape nesting engine using spyrrow (sparrow wrapper).

Spyrrow solves strip packing: fixed height, minimizes width.
We map this to sheet packing by using sheet.width as strip_height,
then slice the resulting strip into sheet-length segments.

Quality improvements:
- Multi-seed: runs the solver N times with different seeds and keeps
  the shortest strip (fewest sheets, best utilization).
- Polygon simplification: reduces vertex count for faster solving.
- Part-size validation: skips parts that can't fit the sheet.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

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
    # Offset applied to normalise polygon to origin (0,0).
    # Needed to reverse the shift when creating PlacedPart coordinates.
    origin_x: float = 0.0
    origin_y: float = 0.0


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


def _normalize_to_origin(
    pts: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], float, float]:
    """Shift polygon so its bounding-box lower-left is at (0, 0).

    Returns (shifted_pts, origin_x, origin_y) where origin_x/y are
    the original min-x/y values (needed to reverse the shift later).
    """
    if not pts:
        return pts, 0.0, 0.0
    ox = min(p[0] for p in pts)
    oy = min(p[1] for p in pts)
    if abs(ox) < 1e-6 and abs(oy) < 1e-6:
        return pts, 0.0, 0.0
    return [(p[0] - ox, p[1] - oy) for p in pts], ox, oy


def _simplify_points(
    pts: list[tuple[float, float]], max_verts: int = 40
) -> list[tuple[float, float]]:
    """Reduce polygon vertex count using Shapely simplify.

    Fewer vertices = faster collision detection in spyrrow.
    """
    if len(pts) <= max_verts:
        return pts
    poly = Polygon(pts)
    if poly.is_empty or not poly.is_valid:
        return pts
    # Iteratively increase tolerance until under max_verts
    tol = 0.5
    for _ in range(10):
        simplified = poly.simplify(tol, preserve_topology=True)
        coords = list(simplified.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) <= max_verts and len(coords) >= 3:
            return coords
        tol *= 2.0
    return pts


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
    pts = _offset_points(entry.points, spacing / 2)
    rad = math.radians(pi.rotation)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    tx, ty = pi.translation
    xs: list[float] = []
    for px, py in pts:
        rx = px * cos_r - py * sin_r + tx
        xs.append(rx)
    return min(xs), max(xs)


def _bbox_size(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Bounding-box width and height of a polygon."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def _poly_area(pts: list[tuple[float, float]]) -> float:
    """Shoelace area of a polygon."""
    n = len(pts)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return a / 2


def _strip_width(solution: spyrrow.StripPackingSolution) -> float:
    """Total strip width (x-extent) of a solution."""
    if not solution.placed_items:
        return 0.0
    # The solution's strip_width attribute if available; otherwise compute
    return getattr(solution, "strip_width", 0.0) or 0.0


def _solution_to_layouts(
    solution: spyrrow.StripPackingSolution,
    entry_by_id: dict[str, _PartEntry],
    sheet: Sheet,
    margin: float,
    spacing: float,
) -> list[Layout]:
    """Convert a spyrrow solution into sheet Layouts.

    Each layout gets an independent copy of the sheet so mutations in
    job.py (setting grade/thickness) don't leak across layouts.

    When polygon points were normalised to origin before sending to the
    solver, the inverse offset is applied here so that the renderer
    (which uses the *original* part contour) draws parts in the correct
    position.
    """
    usable_length = sheet.length - 2 * margin

    # Compute each placed item's x-extent (in strip coordinates)
    placements_with_x: list[
        tuple[float, float, spyrrow.PlacedItem, _PartEntry]
    ] = []
    for pi in solution.placed_items:
        entry = entry_by_id.get(pi.id)
        if entry is None:
            continue
        x_min, x_max = _placed_bbox_x(pi, entry, spacing)
        placements_with_x.append((x_min, x_max, pi, entry))

    # Sort by x_min to assign greedily to sheets
    placements_with_x.sort(key=lambda t: t[0])

    layouts: list[Layout] = []
    sheet_x_start = 0.0
    current_layout = Layout(sheet=replace(sheet))

    for x_min, x_max, pi, entry in placements_with_x:
        local_x_max = x_max - sheet_x_start
        if local_x_max > usable_length and current_layout.placements:
            layouts.append(current_layout)
            current_layout = Layout(sheet=replace(sheet))
            sheet_x_start = x_min

        tx, ty = pi.translation
        rot = pi.rotation
        ox, oy = entry.origin_x, entry.origin_y

        # Reverse the normalisation shift so the *original* part contour
        # renders at the correct position.
        # Solver saw normalised points (shifted by -ox, -oy).
        # Renderer rotates original contour around (0,0) then translates.
        # Correction: pp = (tx, ty) - rotate((ox, oy), rot)
        if ox != 0.0 or oy != 0.0:
            rad = math.radians(rot)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            pp_x = tx - (ox * cos_r - oy * sin_r) - sheet_x_start + margin
            pp_y = ty - (ox * sin_r + oy * cos_r) + margin
        else:
            pp_x = tx - sheet_x_start + margin
            pp_y = ty + margin

        current_layout.placements.append(
            PlacedPart(
                part=entry.part,
                x=pp_x,
                y=pp_y,
                rotation=rot,
            )
        )

    if current_layout.placements:
        layouts.append(current_layout)

    return layouts


class TrueShapeEngine:
    """True-shape nesting engine backed by spyrrow.

    Runs multiple attempts with different random seeds (within the time
    budget) and keeps the best result.
    """

    def __init__(self, time_budget: int = 30) -> None:
        self.time_budget = time_budget

    def nest(
        self,
        parts: list[Part],
        sheets: list[Sheet],
        options: NestOptions,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[Layout]:
        """Nest parts onto sheets using true-shape packing."""
        def _emit(msg: str) -> None:
            if on_progress:
                on_progress(msg)
        sheet = sheets[0] if sheets else Sheet(6000, 2500)
        margin = options.edge_margin
        effective_height = sheet.width - 2 * margin

        if effective_height <= 0:
            return []

        # Expand parts by quantity
        entries: list[_PartEntry] = []
        idx = 0
        prio = options.priorities
        for part in parts:
            for _ in range(part.qty):
                pts = _part_to_points(part)
                pts = _simplify_points(pts)
                # Normalise polygon to origin so rotation is always
                # around the bounding-box corner, not an arbitrary offset.
                pts, ox, oy = _normalize_to_origin(pts)
                entries.append(
                    _PartEntry(
                        part=part, index=idx, points=pts,
                        origin_x=ox, origin_y=oy,
                    )
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

        # Build spyrrow items, filtering out parts that can't fit the sheet
        orientations = _rotation_angles(options)
        items: list[spyrrow.Item] = []
        entry_by_id: dict[str, _PartEntry] = {}

        for entry in entries:
            offset = options.spacing / 2
            pts = _offset_points(entry.points, offset)
            bbox_w, bbox_h = _bbox_size(pts)

            # Check if part can fit the sheet in any allowed orientation
            fits = False
            for angle in (orientations or [0.0]):
                rad = math.radians(angle)
                rot_h = abs(bbox_w * math.sin(rad)) + abs(bbox_h * math.cos(rad))
                if rot_h <= effective_height + 1e-3:
                    fits = True
                    break
            if not fits:
                continue

            item_id = f"{entry.part.name}_{entry.index}"
            entry_by_id[item_id] = entry
            items.append(
                spyrrow.Item(
                    id=item_id,
                    shape=pts,
                    demand=1,
                    allowed_orientations=orientations,
                )
            )

        if not items:
            return []

        instance = spyrrow.StripPackingInstance(
            name="nest",
            strip_height=effective_height,
            items=items,
        )

        # Multi-seed: split time budget across attempts, keep best
        n_attempts = max(1, min(5, self.time_budget // 5))
        time_per_attempt = max(3, self.time_budget // n_attempts)
        usable_length = sheet.length - 2 * margin

        best_solution = None
        best_width = float("inf")
        best_sheets = float("inf")

        _emit(f"Running {n_attempts} attempts ({time_per_attempt}s each)")

        for attempt in range(n_attempts):
            seed = options.seed + attempt
            status = f"Attempt {attempt + 1}/{n_attempts}"
            if best_sheets < float("inf"):
                status += f" (best: {best_sheets} sheet{'s' if best_sheets != 1 else ''})"
            _emit(status)

            config = spyrrow.StripPackingConfig(
                total_computation_time=time_per_attempt,
                seed=seed,
            )
            try:
                solution = instance.solve(config)
            except Exception:
                continue

            # Compute strip width
            width = _strip_width(solution)
            if width <= 0 and solution.placed_items:
                max_x = 0.0
                for pi in solution.placed_items:
                    entry = entry_by_id.get(pi.id)
                    if entry:
                        _, x_max = _placed_bbox_x(pi, entry, options.spacing)
                        max_x = max(max_x, x_max)
                width = max_x

            # Score: prefer fewer sheets, then shorter strip as tiebreaker.
            # A strip that barely overflows a sheet boundary wastes an
            # entire sheet, so sheet count matters more than raw width.
            n_sheets = (
                max(1, math.ceil(width / usable_length))
                if usable_length > 0
                else 1
            )
            if n_sheets < best_sheets or (
                n_sheets == best_sheets and width < best_width
            ):
                best_width = width
                best_solution = solution
                best_sheets = n_sheets

        if best_solution is None:
            return []

        return _solution_to_layouts(
            best_solution, entry_by_id, sheet, margin, options.spacing
        )
