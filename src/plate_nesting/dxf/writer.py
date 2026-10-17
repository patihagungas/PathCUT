"""Write a Part to DXF format using ezdxf."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf

from plate_nesting.geometry.contour import loop_bbox
from plate_nesting.geometry.seg import Seg
from plate_nesting.models.part import Part


def _add_seg(msp: ezdxf.entities.Modelspace, seg: Seg, layer: str) -> None:
    """Add a single Seg to the modelspace as a LINE or ARC."""
    if not seg.is_arc:
        msp.add_line(seg.p0, seg.p1, dxfattribs={"layer": layer})
        return

    assert seg.center is not None
    cx, cy = seg.center
    start_deg = math.degrees(math.atan2(seg.p0[1] - cy, seg.p0[0] - cx))
    end_deg = math.degrees(math.atan2(seg.p1[1] - cy, seg.p1[0] - cx))

    # ezdxf add_arc expects CCW angles; swap if CW
    if not seg.ccw:
        start_deg, end_deg = end_deg, start_deg

    msp.add_arc(
        center=seg.center,
        radius=seg.r,
        start_angle=start_deg,
        end_angle=end_deg,
        dxfattribs={"layer": layer},
    )


def write_dxf(part: Part, path: str | Path) -> None:
    """Write a Part to a DXF file.

    Layers:
        CUT (color 7/white) — outer contour + holes
        CUTOUT (color 2/yellow) — inner contours
        TEXT (color 3/green) — part info text
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add("CUT", color=7)
    doc.layers.add("CUTOUT", color=2)
    doc.layers.add("TEXT", color=3)

    # Outer contour
    for seg in part.outer:
        _add_seg(msp, seg, "CUT")

    # Inner contours (cutouts)
    for inner in part.inners:
        for seg in inner:
            _add_seg(msp, seg, "CUTOUT")

    # Holes
    for x, y, d in part.holes:
        msp.add_circle(
            center=(x, y),
            radius=d / 2,
            dxfattribs={"layer": "CUT"},
        )

    # Info text above part bbox
    if part.outer:
        _, _, _, y_max = loop_bbox(part.outer)
        thk = f"PL{part.thickness:g}" if part.thickness else "PL"
        text = f"{part.qty} + {thk} + {part.grade}"
        msp.add_mtext(
            text,
            dxfattribs={
                "layer": "TEXT",
                "insert": (0, y_max + 20),
            },
        )

    doc.saveas(str(path))
