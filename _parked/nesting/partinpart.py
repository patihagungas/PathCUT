"""Part-in-part placement: fit small parts inside cutouts of larger ones.

After initial nesting, this post-processor checks whether any unplaced or
loosely-placed parts can fit inside the inner cutouts of already-placed parts.
"""

from __future__ import annotations

from shapely.affinity import rotate as shapely_rotate
from shapely.affinity import translate as shapely_translate
from shapely.geometry import Polygon

from plate_nesting.geometry.polygon import (
    loop_to_points,
    part_outer_polygon,
)
from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part


def _inner_polygon(
    placed: PlacedPart, inner_idx: int, tol: float = 0.5
) -> Polygon:
    """Get the Shapely polygon for one inner cutout of a placed part."""
    inner_loop = placed.part.inners[inner_idx]
    pts = loop_to_points(inner_loop, tol)
    if len(pts) < 3:
        return Polygon()
    poly = Polygon(pts)
    # Apply same transform as the placed part
    if placed.rotation != 0.0:
        poly = shapely_rotate(poly, placed.rotation, origin=(0, 0))
    poly = shapely_translate(poly, placed.x, placed.y)
    return poly


def _candidate_polygon(
    part: Part, rotation: float, tol: float = 0.5
) -> Polygon:
    """Get the outer polygon of a part at a given rotation."""
    poly = part_outer_polygon(part, tol)
    if poly.is_empty:
        return poly
    if rotation != 0.0:
        poly = shapely_rotate(poly, rotation, origin=(0, 0))
    return poly


def fill_cutouts(
    layouts: list[Layout],
    unplaced: list[Part],
    options: NestOptions,
) -> list[Part]:
    """Try to place unplaced parts inside cutouts of placed parts.

    Modifies layouts in-place by adding placements.
    Returns the list of parts that still couldn't be placed.

    Args:
        layouts: Existing layouts with placed parts.
        unplaced: Parts (qty=1 each, already expanded) to try fitting.
        options: Nesting options (spacing, rotation_step).

    Returns:
        Parts that could not be placed in any cutout.
    """
    spacing = options.spacing
    step = options.rotation_step
    angles = [0.0]
    if step > 0:
        a = 0.0
        while a < 360.0 - 1e-9:
            angles.append(a)
            a += step
        angles = sorted(set(angles))

    still_unplaced: list[Part] = []

    for part in unplaced:
        placed = False
        for layout in layouts:
            if placed:
                break
            for pp in list(layout.placements):
                if placed:
                    break
                for inner_idx in range(len(pp.part.inners)):
                    if placed:
                        break
                    cutout = _inner_polygon(pp, inner_idx)
                    if cutout.is_empty:
                        continue
                    # Shrink cutout by spacing
                    shrunk = cutout.buffer(-spacing)
                    if shrunk.is_empty or not shrunk.is_valid:
                        continue

                    for angle in angles:
                        candidate = _candidate_polygon(part, angle)
                        if candidate.is_empty:
                            continue

                        # Try placing at cutout centroid
                        cx, cy = shrunk.centroid.x, shrunk.centroid.y
                        cand_cx = candidate.centroid.x
                        cand_cy = candidate.centroid.y
                        dx = cx - cand_cx
                        dy = cy - cand_cy
                        shifted = shapely_translate(candidate, dx, dy)

                        if shrunk.contains(shifted):
                            # Check no overlap with existing parts
                            overlap = False
                            for existing in layout.placements:
                                if existing is pp:
                                    continue
                                ex_poly = part_outer_polygon(
                                    existing.part
                                )
                                if ex_poly.is_empty:
                                    continue
                                if existing.rotation != 0.0:
                                    ex_poly = shapely_rotate(
                                        ex_poly,
                                        existing.rotation,
                                        origin=(0, 0),
                                    )
                                ex_poly = shapely_translate(
                                    ex_poly, existing.x, existing.y
                                )
                                if shifted.intersects(ex_poly):
                                    inter = shifted.intersection(
                                        ex_poly
                                    )
                                    if inter.area > 0.25:
                                        overlap = True
                                        break
                            if not overlap:
                                layout.placements.append(
                                    PlacedPart(
                                        part=part,
                                        x=dx,
                                        y=dy,
                                        rotation=angle,
                                    )
                                )
                                placed = True
                                break

        if not placed:
            still_unplaced.append(part)

    return still_unplaced
