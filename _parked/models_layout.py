"""Layout model: a sheet with placed parts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from plate_nesting.geometry.seg import Seg
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet


@dataclass
class PlacedPart:
    """A part placed on a sheet at a specific position and orientation."""

    part: Part
    x: float
    y: float
    rotation: float = 0.0  # degrees (0, 90, 180, 270, or free)
    mirrored: bool = False

    @property
    def placed_length(self) -> float:
        """Bounding width after rotation."""
        if self.rotation in (90.0, 270.0):
            return self.part.width
        if self.rotation in (0.0, 180.0):
            return self.part.length
        rad = math.radians(self.rotation)
        return abs(self.part.length * math.cos(rad)) + abs(
            self.part.width * math.sin(rad)
        )

    def world_outer_edges(self) -> list[Seg]:
        """Return outer contour Segs transformed to world (sheet) coords.

        Pipeline matches validator: mirror → rotate → translate.
        """
        segs = list(self.part.outer)
        if not segs:
            return []
        if self.mirrored:
            segs = [s.mirrored_x() for s in segs]
        if self.rotation != 0.0:
            segs = [s.rotated(self.rotation) for s in segs]
        return [s.shifted(self.x, self.y) for s in segs]

    @property
    def placed_width(self) -> float:
        """Bounding height after rotation."""
        if self.rotation in (90.0, 270.0):
            return self.part.length
        if self.rotation in (0.0, 180.0):
            return self.part.width
        rad = math.radians(self.rotation)
        return abs(self.part.length * math.sin(rad)) + abs(
            self.part.width * math.cos(rad)
        )


@dataclass
class Layout:
    """A nesting layout: one sheet with placed parts."""

    sheet: Sheet
    placements: list[PlacedPart] = field(default_factory=list)
    common_cuts: list = field(default_factory=list)

    @property
    def part_area(self) -> float:
        """Total bounding-box area of placed parts."""
        return sum(
            pp.placed_length * pp.placed_width for pp in self.placements
        )

    @property
    def utilization(self) -> float:
        """Material utilization as a fraction (0-1)."""
        if self.sheet.area == 0:
            return 0.0
        return self.part_area / self.sheet.area

    @property
    def weight(self) -> float:
        """Sheet weight in kg (thickness * density * area)."""
        return self.sheet.thickness * 7.85e-6 * self.sheet.area
