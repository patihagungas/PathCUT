"""Sheet and remnant inventory with JSON persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from plate_nesting.models.sheet import GrainDirection, Sheet


@dataclass
class Remnant:
    """A leftover piece of sheet after nesting.

    Stored as a simplified rectangle (the bounding box of usable area).
    For rectangular remnants from strip packing, this is exact.
    """

    length: float
    width: float
    grade: str
    thickness: float
    label: str = ""
    grain: GrainDirection = GrainDirection.NONE

    @property
    def area(self) -> float:
        return self.length * self.width

    def to_sheet(self) -> Sheet:
        """Convert this remnant to a Sheet for nesting."""
        return Sheet(
            length=self.length,
            width=self.width,
            grade=self.grade,
            thickness=self.thickness,
            label=self.label or "remnant",
            grain=self.grain,
        )


@dataclass
class SheetInventory:
    """Inventory of available sheet sizes and remnants."""

    standard_sizes: list[Sheet] = field(default_factory=list)
    remnants: list[Remnant] = field(default_factory=list)

    def sheets_for_group(
        self, grade: str, thickness: float
    ) -> list[Sheet]:
        """Get all available sheets for a grade+thickness group.

        Returns matching standard sheets plus any remnants,
        sorted largest-first so the nester tries big sheets first.
        """
        result: list[Sheet] = []

        # Standard sheets matching this material
        for s in self.standard_sizes:
            if (not s.grade or s.grade == grade) and (
                s.thickness == 0 or s.thickness == thickness
            ):
                result.append(
                    Sheet(
                        length=s.length,
                        width=s.width,
                        grade=grade,
                        thickness=thickness,
                        label=s.label,
                        grain=s.grain,
                    )
                )

        # Remnants matching this material
        for r in self.remnants:
            if r.grade == grade and r.thickness == thickness:
                result.append(r.to_sheet())

        # Sort: largest area first
        result.sort(key=lambda s: s.area, reverse=True)
        return result

    def add_remnant(self, remnant: Remnant) -> None:
        """Add a remnant to inventory."""
        self.remnants.append(remnant)

    def remove_remnant(self, index: int) -> None:
        """Remove a remnant by index."""
        if 0 <= index < len(self.remnants):
            self.remnants.pop(index)

    def save(self, path: str | Path) -> None:
        """Save inventory to JSON."""
        data = {
            "standard_sizes": [
                {
                    "length": s.length,
                    "width": s.width,
                    "grade": s.grade,
                    "thickness": s.thickness,
                    "label": s.label,
                    "grain": s.grain.value,
                }
                for s in self.standard_sizes
            ],
            "remnants": [
                {
                    "length": r.length,
                    "width": r.width,
                    "grade": r.grade,
                    "thickness": r.thickness,
                    "label": r.label,
                    "grain": r.grain.value,
                }
                for r in self.remnants
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> SheetInventory:
        """Load inventory from JSON."""
        data = json.loads(Path(path).read_text())
        inv = cls()
        for s in data.get("standard_sizes", []):
            inv.standard_sizes.append(
                Sheet(
                    length=s["length"],
                    width=s["width"],
                    grade=s.get("grade", ""),
                    thickness=s.get("thickness", 0.0),
                    label=s.get("label", ""),
                    grain=GrainDirection(s.get("grain", "none")),
                )
            )
        for r in data.get("remnants", []):
            inv.remnants.append(
                Remnant(
                    length=r["length"],
                    width=r["width"],
                    grade=r["grade"],
                    thickness=r["thickness"],
                    label=r.get("label", ""),
                    grain=GrainDirection(r.get("grain", "none")),
                )
            )
        return inv

    @classmethod
    def default(cls) -> SheetInventory:
        """Create inventory with common structural steel sheet sizes."""
        return cls(
            standard_sizes=[
                Sheet(6000, 2500, label="6000x2500"),
                Sheet(6000, 2000, label="6000x2000"),
                Sheet(3000, 1500, label="3000x1500"),
                Sheet(2500, 1250, label="2500x1250"),
                Sheet(12000, 2500, label="12000x2500"),
            ]
        )
