"""Independent layout validator using Shapely.

Checks every layout for:
1. Part overlap
2. Parts outside the sheet
3. Spacing violations between parts
4. Spacing violations between parts and sheet edges
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely.affinity import rotate as shapely_rotate
from shapely.affinity import translate as shapely_translate
from shapely.geometry import Polygon, box

from plate_nesting.geometry.polygon import part_outer_polygon, part_polygon_with_holes
from plate_nesting.models.layout import Layout, PlacedPart


@dataclass
class ValidationResult:
    """Result of layout validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False


def _part_polygon_bbox(pp: PlacedPart) -> Polygon:
    """Create a Shapely polygon for a placed part's bounding box."""
    w = pp.part.length
    h = pp.part.width
    rect = box(0, 0, w, h)
    if pp.rotation != 0.0:
        rect = shapely_rotate(rect, pp.rotation, origin="center")
    cx = pp.placed_length / 2
    cy = pp.placed_width / 2
    dx = pp.x + cx - rect.centroid.x
    dy = pp.y + cy - rect.centroid.y
    rect = shapely_translate(rect, dx, dy)
    return rect


def _part_polygon_true(pp: PlacedPart) -> Polygon:
    """Create a Shapely polygon from a placed part's true contour with holes."""
    if not pp.part.outer:
        return _part_polygon_bbox(pp)
    poly = part_polygon_with_holes(pp.part, tol=0.5)
    if poly.is_empty:
        return _part_polygon_bbox(pp)
    if pp.mirrored:
        from shapely.affinity import scale

        poly = scale(poly, xfact=-1, origin=(0, 0))
    if pp.rotation != 0.0:
        poly = shapely_rotate(poly, pp.rotation, origin=(0, 0))
    poly = shapely_translate(poly, pp.x, pp.y)
    return poly


def _part_polygon_true_outer(pp: PlacedPart) -> Polygon:
    """True outer contour only (no holes) — for bounds checking."""
    if not pp.part.outer:
        return _part_polygon_bbox(pp)
    poly = part_outer_polygon(pp.part, tol=0.5)
    if poly.is_empty:
        return _part_polygon_bbox(pp)
    if pp.mirrored:
        from shapely.affinity import scale

        poly = scale(poly, xfact=-1, origin=(0, 0))
    if pp.rotation != 0.0:
        poly = shapely_rotate(poly, pp.rotation, origin=(0, 0))
    poly = shapely_translate(poly, pp.x, pp.y)
    return poly


def validate_layout(
    layout: Layout,
    spacing: float = 0.0,
    edge_margin: float = 0.0,
    tol: float = 0.5,
    true_shape: bool = False,
) -> ValidationResult:
    """Validate a nesting layout.

    Args:
        layout: The layout to validate.
        spacing: Required minimum spacing between parts (mm).
        edge_margin: Required minimum margin from sheet edges (mm).
        tol: Tolerance for floating-point comparisons (mm).
        true_shape: If True, use true part contours instead of bboxes.

    Returns:
        ValidationResult with any errors found.
    """
    result = ValidationResult()
    placements = layout.placements

    if not placements:
        return result

    # For overlap: use polygon with holes (part-in-part is OK)
    # For bounds: use outer polygon only
    poly_fn = _part_polygon_true if true_shape else _part_polygon_bbox
    polys = [poly_fn(pp) for pp in placements]
    if true_shape:
        outer_polys = [_part_polygon_true_outer(pp) for pp in placements]
    else:
        outer_polys = polys

    # Check 1: Parts inside sheet (with edge margin tolerance)
    inner_sheet = box(
        edge_margin - tol,
        edge_margin - tol,
        layout.sheet.length - edge_margin + tol,
        layout.sheet.width - edge_margin + tol,
    )
    for pp, poly in zip(placements, outer_polys):
        if not inner_sheet.contains(poly):
            diff = poly.difference(inner_sheet)
            if diff.area > tol * tol:
                result.add_error(
                    f"Part '{pp.part.name}' at ({pp.x:.1f}, {pp.y:.1f}) "
                    f"extends outside sheet by {diff.area:.1f} mm²"
                )

    # Check 2: No overlap between parts
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            intersection = polys[i].intersection(polys[j])
            if intersection.area > tol * tol:
                result.add_error(
                    f"Parts '{placements[i].part.name}' and "
                    f"'{placements[j].part.name}' overlap by "
                    f"{intersection.area:.1f} mm²"
                )

    # Check 3: Spacing between parts
    if spacing > tol:
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                d = polys[i].distance(polys[j])
                if d < spacing - tol:
                    result.add_error(
                        f"Parts '{placements[i].part.name}' and "
                        f"'{placements[j].part.name}' spacing "
                        f"{d:.1f} mm < required {spacing:.1f} mm"
                    )

    return result
