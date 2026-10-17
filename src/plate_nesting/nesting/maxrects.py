"""MaxRects bin packing algorithm for rectangular nesting.

This is the baseline/fallback nester. It packs parts by their bounding boxes
using the Best Short Side Fit (BSSF) heuristic.

Reference: Jylänki, "A Thousand Ways to Pack the Bin" (2010).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from plate_nesting.models.layout import Layout, PlacedPart
from plate_nesting.models.nesting import NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet


@dataclass
class Rect:
    """An axis-aligned rectangle."""

    x: float
    y: float
    w: float
    h: float


class MaxRectsBin:
    """Single-bin MaxRects packer."""

    def __init__(self, width: float, height: float) -> None:
        self.bin_w = width
        self.bin_h = height
        self.free: list[Rect] = [Rect(0, 0, width, height)]
        self.used: list[Rect] = []

    def insert(self, w: float, h: float) -> Rect | None:
        """Try to place a rectangle of size w×h. Returns placement or None."""
        best: Rect | None = None
        best_short = float("inf")
        best_long = float("inf")

        for fr in self.free:
            # Try without rotation
            if w <= fr.w + 1e-9 and h <= fr.h + 1e-9:
                short = min(fr.w - w, fr.h - h)
                long = max(fr.w - w, fr.h - h)
                if short < best_short or (
                    short == best_short and long < best_long
                ):
                    best = Rect(fr.x, fr.y, w, h)
                    best_short = short
                    best_long = long

        if best is None:
            return None

        self._place(best)
        return best

    def _place(self, rect: Rect) -> None:
        """Place a rectangle and split free rects."""
        self.used.append(rect)
        new_free: list[Rect] = []
        for fr in self.free:
            splits = self._split(fr, rect)
            if splits is not None:
                new_free.extend(splits)
            else:
                new_free.append(fr)
        self.free = new_free
        self._prune()

    def _split(self, free: Rect, used: Rect) -> list[Rect] | None:
        """If `used` overlaps `free`, return the remaining pieces. Else None."""
        # No overlap check
        if (
            used.x >= free.x + free.w - 1e-9
            or used.x + used.w <= free.x + 1e-9
            or used.y >= free.y + free.h - 1e-9
            or used.y + used.h <= free.y + 1e-9
        ):
            return None

        result: list[Rect] = []
        # Left remainder
        if used.x > free.x + 1e-9:
            result.append(Rect(free.x, free.y, used.x - free.x, free.h))
        # Right remainder
        if used.x + used.w < free.x + free.w - 1e-9:
            result.append(
                Rect(
                    used.x + used.w,
                    free.y,
                    free.x + free.w - used.x - used.w,
                    free.h,
                )
            )
        # Bottom remainder
        if used.y > free.y + 1e-9:
            result.append(Rect(free.x, free.y, free.w, used.y - free.y))
        # Top remainder
        if used.y + used.h < free.y + free.h - 1e-9:
            result.append(
                Rect(
                    free.x,
                    used.y + used.h,
                    free.w,
                    free.y + free.h - used.y - used.h,
                )
            )
        return result

    def _prune(self) -> None:
        """Remove free rects fully contained in another."""
        pruned: list[Rect] = []
        n = len(self.free)
        contained = [False] * n
        for i in range(n):
            if contained[i]:
                continue
            for j in range(n):
                if i == j or contained[j]:
                    continue
                if self._contains(self.free[j], self.free[i]):
                    contained[i] = True
                    break
            if not contained[i]:
                pruned.append(self.free[i])
        self.free = pruned

    @staticmethod
    def _contains(outer: Rect, inner: Rect) -> bool:
        """Check if outer fully contains inner."""
        return (
            inner.x >= outer.x - 1e-9
            and inner.y >= outer.y - 1e-9
            and inner.x + inner.w <= outer.x + outer.w + 1e-9
            and inner.y + inner.h <= outer.y + outer.h + 1e-9
        )


@dataclass
class _PlaceCandidate:
    """A part placement candidate with its orientation."""

    part: Part
    w: float
    h: float
    rotation: float
    original_index: int


class MaxRectsEngine:
    """Rectangular nesting engine using MaxRects bin packing."""

    def nest(
        self,
        parts: list[Part],
        sheets: list[Sheet],
        options: NestOptions,
    ) -> list[Layout]:
        """Nest parts onto sheets using MaxRects BSSF."""
        rng = random.Random(options.seed)
        margin = options.edge_margin
        spacing = options.spacing

        # Expand parts by quantity and build candidates with rotations
        candidates: list[_PlaceCandidate] = []
        for idx, part in enumerate(parts):
            for _ in range(part.qty):
                best = self._best_orientation(
                    part, idx, options, spacing
                )
                candidates.append(best)

        # Sort by priority (descending), then area (descending) for greedy
        prio = options.priorities
        candidates.sort(
            key=lambda c: (
                -prio.get(c.part.name, 0),
                -(c.w * c.h),
            ),
        )

        # Shuffle within same priority+area groups for seed variation
        # (group by priority, then within each group shuffle same-size items)
        _shuffle_ties(candidates, rng)

        layouts: list[Layout] = []
        remaining = list(candidates)

        while remaining:
            # Pick the first available sheet type
            sheet = sheets[0] if sheets else Sheet(6000, 2500)
            usable_w = sheet.length - 2 * margin
            usable_h = sheet.width - 2 * margin

            if usable_w <= 0 or usable_h <= 0:
                break

            packer = MaxRectsBin(usable_w, usable_h)
            layout = Layout(sheet=sheet)
            still_remaining: list[_PlaceCandidate] = []

            for cand in remaining:
                # Try all orientations, pick the one that fits
                placed = False
                orientations = self._orientations(
                    cand.part, cand.original_index, options, spacing
                )
                for orient in orientations:
                    result = packer.insert(orient.w, orient.h)
                    if result is not None:
                        layout.placements.append(
                            PlacedPart(
                                part=orient.part,
                                x=result.x + margin,
                                y=result.y + margin,
                                rotation=orient.rotation,
                            )
                        )
                        placed = True
                        break
                if not placed:
                    still_remaining.append(cand)

            if layout.placements:
                layouts.append(layout)
            remaining = still_remaining

            # Safety: if nothing was placed, we can't fit any remaining parts
            if not layout.placements:
                break

        return layouts

    def _best_orientation(
        self,
        part: Part,
        idx: int,
        options: NestOptions,
        spacing: float,
    ) -> _PlaceCandidate:
        """Return the smallest-bounding-box orientation."""
        orientations = self._orientations(part, idx, options, spacing)
        return min(orientations, key=lambda c: c.w * c.h)

    def _orientations(
        self,
        part: Part,
        idx: int,
        options: NestOptions,
        spacing: float,
    ) -> list[_PlaceCandidate]:
        """Generate placement candidates for all allowed rotations."""
        candidates: list[_PlaceCandidate] = []
        step = options.rotation_step
        if step <= 0:
            angles = [0.0]
        else:
            angles = []
            a = 0.0
            while a < 360.0 - 1e-9:
                angles.append(a)
                a += step

        for angle in angles:
            cand = _PlaceCandidate(
                part=part,
                w=0,
                h=0,
                rotation=angle,
                original_index=idx,
            )
            cand.w = cand_width(part, angle) + spacing
            cand.h = cand_height(part, angle) + spacing
            candidates.append(cand)
        return candidates


def cand_width(part: Part, rotation: float) -> float:
    """Bounding width after rotation (degrees)."""
    import math

    if rotation in (0.0, 180.0):
        return part.length
    if rotation in (90.0, 270.0):
        return part.width
    rad = math.radians(rotation)
    return abs(part.length * math.cos(rad)) + abs(part.width * math.sin(rad))


def cand_height(part: Part, rotation: float) -> float:
    """Bounding height after rotation (degrees)."""
    import math

    if rotation in (0.0, 180.0):
        return part.width
    if rotation in (90.0, 270.0):
        return part.length
    rad = math.radians(rotation)
    return abs(part.length * math.sin(rad)) + abs(part.width * math.cos(rad))


def _shuffle_ties(
    candidates: list[_PlaceCandidate], rng: random.Random
) -> None:
    """Shuffle candidates that have the same priority and area."""
    i = 0
    while i < len(candidates):
        j = i + 1
        key_i = (
            -candidates[i].w * candidates[i].h,
        )
        while j < len(candidates):
            key_j = (
                -candidates[j].w * candidates[j].h,
            )
            if key_j != key_i:
                break
            j += 1
        if j - i > 1:
            sub = candidates[i:j]
            rng.shuffle(sub)
            candidates[i:j] = sub
        i = j
