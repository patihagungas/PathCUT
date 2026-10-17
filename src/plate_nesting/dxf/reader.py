"""Read a DXF file into a Part object."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass

import ezdxf

from plate_nesting.geometry.area import loop_area
from plate_nesting.geometry.contour import (
    chain,
    entity_segments,
    loop_bbox,
    reverse_loop,
    start_at_left,
)
from plate_nesting.geometry.seg import Seg, arc_segments
from plate_nesting.models.part import Part


@dataclass
class DxfReadOptions:
    """Options for DXF reading."""

    cut_layer: str = "CUT"
    cutout_layer: str = "CUTOUT"
    scribe_layer: str = "SCRIBE"
    text_layer: str = "TEXT"
    max_hole: float = 40.0
    tol: float = 0.05
    hole_dia_from_layer: bool = False
    order: str = "W8753"
    phase: str = ""
    qty: int = 0
    thickness: float = 0.0
    grade: str = ""
    mark: str = ""


def _parse_info_text(text: str) -> tuple[int, float, str] | None:
    m = re.match(r"\s*(\d+)\s*\+\s*PL\s*([\d.]+)\s*\+\s*(\S+)", text, re.I)
    if m:
        return int(m.group(1)), float(m.group(2)), m.group(3)
    return None


def read_dxf(
    path: str | os.PathLike[str],
    opts: DxfReadOptions | None = None,
) -> Part:
    """Read a DXF file and return a Part."""
    if opts is None:
        opts = DxfReadOptions()

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    cut_l = opts.cut_layer.upper()
    cutout_l = opts.cutout_layer.upper()
    scribe_l = opts.scribe_layer.upper()
    text_l = opts.text_layer.upper()

    outer_segs: list[Seg] = []
    inner_segs: list[Seg] = []
    other_segs: list[Seg] = []
    holes: list[tuple[float, float, float]] = []
    mark: str | None = None
    info: tuple[int, float, str] | None = None

    for e in msp:
        layer = e.dxf.layer.upper()
        t = e.dxftype()
        if t in ("TEXT", "MTEXT"):
            txt = e.dxf.text if t == "TEXT" else e.plain_text()
            if layer == scribe_l:
                mark = txt.strip()
            elif layer == text_l:
                info = _parse_info_text(txt) or info
            continue
        if layer == cut_l:
            outer_segs += entity_segments(e)
        elif layer == cutout_l:
            inner_segs += entity_segments(e)
        elif t == "CIRCLE":
            d = 2 * e.dxf.radius
            if opts.hole_dia_from_layer:
                try:
                    d = float(e.dxf.layer)
                except ValueError:
                    pass
            holes.append((e.dxf.center.x, e.dxf.center.y, d))
        else:
            other_segs += entity_segments(e)

    if not outer_segs:
        outer_segs, other_segs = other_segs, []
        keep: list[tuple[float, float, float]] = []
        for x, y, d in holes:
            if d > opts.max_hole:
                outer_segs += arc_segments(
                    (x, y), d / 2, math.pi, 2 * math.pi
                )
            else:
                keep.append((x, y, d))
        holes = keep

    outer_loops, _ = chain(outer_segs, opts.tol)
    inner_loops, _ = chain(inner_segs, opts.tol)

    if not outer_loops:
        stem = os.path.splitext(os.path.basename(str(path)))[0]
        raise ValueError(
            f"{stem}: no closed outer contour found on layer '{opts.cut_layer}'"
        )

    outer_loops.sort(key=lambda lp: abs(loop_area(lp)), reverse=True)
    outer = outer_loops[0]
    if len(outer_loops) > 1:
        inner_loops += outer_loops[1:]

    # orientation: outer CCW, inner CW
    if loop_area(outer) < 0:
        outer = reverse_loop(outer)
    inner_loops = [
        reverse_loop(lp) if loop_area(lp) > 0 else lp for lp in inner_loops
    ]

    # move origin to lower-left of outer bounding box
    x0, y0, x1, y1 = loop_bbox(outer)
    dx, dy = -x0, -y0
    outer = [s.shifted(dx, dy) for s in outer]
    inner_loops = [[s.shifted(dx, dy) for s in lp] for lp in inner_loops]
    holes = [(x + dx, y + dy, d) for x, y, d in holes]
    length, width = x1 - x0, y1 - y0

    outer = start_at_left(outer)
    inner_loops = sorted(
        (start_at_left(lp) for lp in inner_loops),
        key=lambda lp: (round(lp[0].p0[0], 2), lp[0].p0[1]),
    )

    stem = os.path.splitext(os.path.basename(str(path)))[0]
    qty, thk, grade = info if info else (1, 0.0, "")
    qty = opts.qty or qty
    thk = opts.thickness or thk
    grade = opts.grade or grade
    phase = opts.phase or mark or "63"
    piece = opts.mark or stem

    return Part(
        name=piece,
        outer=outer,
        inners=inner_loops,
        holes=holes,
        grade=grade,
        thickness=thk,
        qty=qty,
        order=opts.order,
        phase=phase,
        length=length,
        width=width,
    )
