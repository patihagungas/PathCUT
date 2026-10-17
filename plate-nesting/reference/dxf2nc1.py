#!/usr/bin/env python3
"""
dxf2nc1 - Convert flat-plate DXF drawings to DSTV NC1 files.

Default layer conventions (change with command-line options):
  CUT      outer contour            -> AK block
  CUTOUT   inner contours / cutouts -> IK blocks
  SCRIBE   text (e.g. 63)           -> phase line of the header (+ SI block with --scribe)
  TEXT     "QTY+PLthk+GRADE"        -> e.g. "10+PL25+350W"
  any other layer: CIRCLE           -> holes (BO block)

Supported geometry: LINE, ARC, CIRCLE, LWPOLYLINE/POLYLINE (with bulges).
Splines/ellipses are approximated with line segments.

Usage:
  python dxf2nc1.py 6C-p1.dxf --order W8753   # writes 6C-p1.nc1 next to it
  python dxf2nc1.py folder/*.dxf -o out/     # batch
  python dxf2nc1.py part.dxf --qty 4 --thickness 20 --grade S355
"""
import argparse
import glob
import math
import os
import re
import sys

import ezdxf

DENSITY = 7.85e-6  # kg/mm^3 (steel)


# --------------------------------------------------------------------------- geometry
class Seg:
    """Line (center=None) or arc from p0 to p1."""
    __slots__ = ("p0", "p1", "center", "r", "ccw")

    def __init__(self, p0, p1, center=None, r=0.0, ccw=True):
        self.p0, self.p1, self.center, self.r, self.ccw = p0, p1, center, r, ccw

    @property
    def is_arc(self):
        return self.center is not None

    def reversed(self):
        return Seg(self.p1, self.p0, self.center, self.r, not self.ccw)

    def sweep(self):
        """Signed sweep angle in radians (+ = CCW)."""
        cx, cy = self.center
        a0 = math.atan2(self.p0[1] - cy, self.p0[0] - cx)
        a1 = math.atan2(self.p1[1] - cy, self.p1[0] - cx)
        d = (a1 - a0) % (2 * math.pi)
        if d < 1e-12:
            d = 2 * math.pi
        return d if self.ccw else -(2 * math.pi - d) if d != 2 * math.pi else -d

    def shifted(self, dx, dy):
        c = None if self.center is None else (self.center[0] + dx, self.center[1] + dy)
        return Seg((self.p0[0] + dx, self.p0[1] + dy), (self.p1[0] + dx, self.p1[1] + dy),
                   c, self.r, self.ccw)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def arc_segments(center, r, a_start, sweep):
    """Arc from angle a_start (rad) sweeping `sweep` (signed). Split into pieces <= 180 deg."""
    n = max(1, math.ceil(abs(sweep) / math.pi - 1e-9))
    out = []
    for i in range(n):
        a0 = a_start + sweep * i / n
        a1 = a_start + sweep * (i + 1) / n
        p0 = (center[0] + r * math.cos(a0), center[1] + r * math.sin(a0))
        p1 = (center[0] + r * math.cos(a1), center[1] + r * math.sin(a1))
        out.append(Seg(p0, p1, center, r, sweep > 0))
    return out


def bulge_segment(p0, p1, b):
    if abs(b) < 1e-12:
        return [Seg(p0, p1)]
    theta = 4 * math.atan(b)
    c = dist(p0, p1)
    r = c / (2 * math.sin(abs(theta) / 2))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    nx, ny = -(p1[1] - p0[1]) / c, (p1[0] - p0[0]) / c  # left normal
    h = (c / 2) / math.tan(theta / 2)
    center = (mx + nx * h, my + ny * h)
    a0 = math.atan2(p0[1] - center[1], p0[0] - center[0])
    return arc_segments(center, r, a0, theta)


def entity_segments(e):
    t = e.dxftype()
    if t == "LINE":
        s, en = e.dxf.start, e.dxf.end
        return [Seg((s.x, s.y), (en.x, en.y))]
    if t == "ARC":
        c = (e.dxf.center.x, e.dxf.center.y)
        a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
        sw = (a1 - a0) % (2 * math.pi) or 2 * math.pi
        return arc_segments(c, e.dxf.radius, a0, sw)
    if t == "CIRCLE":
        c = (e.dxf.center.x, e.dxf.center.y)
        return arc_segments(c, e.dxf.radius, math.pi, 2 * math.pi)
    if t in ("LWPOLYLINE", "POLYLINE"):
        if t == "LWPOLYLINE":
            pts = [(p[0], p[1], p[4]) for p in e.get_points("xyseb")]
            closed = e.closed
        else:
            pts = [(v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0)) for v in e.vertices]
            closed = e.is_closed
        segs = []
        n = len(pts)
        for i in range(n if closed else n - 1):
            a, b = pts[i], pts[(i + 1) % n]
            if dist(a, b) > 1e-9:
                segs += bulge_segment((a[0], a[1]), (b[0], b[1]), a[2])
        return segs
    if t in ("SPLINE", "ELLIPSE"):
        pts = [(p.x, p.y) for p in e.flattening(0.05)]
        return [Seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return []


def chain(segs, tol):
    """Join loose segments into closed loops."""
    pool = list(segs)
    loops, open_ = [], []
    while pool:
        cur = [pool.pop(0)]
        while dist(cur[-1].p1, cur[0].p0) > tol:
            for i, s in enumerate(pool):
                if dist(s.p0, cur[-1].p1) <= tol:
                    cur.append(pool.pop(i)); break
                if dist(s.p1, cur[-1].p1) <= tol:
                    cur.append(pool.pop(i).reversed()); break
            else:
                open_.append(cur); cur = None; break
        if cur:
            loops.append(cur)
    return loops, open_


def loop_area(loop):
    """Signed area (+ = CCW), arcs included."""
    a = 0.0
    for s in loop:
        a += s.p0[0] * s.p1[1] - s.p1[0] * s.p0[1]
    a /= 2
    for s in loop:
        if s.is_arc:
            th = s.sweep()
            a += 0.5 * s.r ** 2 * (th - math.sin(th))
    return a


def loop_perimeter(loop):
    return sum(abs(s.sweep()) * s.r if s.is_arc else dist(s.p0, s.p1) for s in loop)


def reverse_loop(loop):
    return [s.reversed() for s in reversed(loop)]


def loop_bbox(loop):
    xs, ys = [], []
    for s in loop:
        xs += [s.p0[0], s.p1[0]]; ys += [s.p0[1], s.p1[1]]
        if s.is_arc:
            cx, cy = s.center
            a0 = math.atan2(s.p0[1] - cy, s.p0[0] - cx)
            th = s.sweep()
            for k in range(4):
                ang = k * math.pi / 2
                d = ((ang - a0) % (2 * math.pi)) if th > 0 else ((a0 - ang) % (2 * math.pi))
                if d <= abs(th) + 1e-12:
                    xs.append(cx + s.r * math.cos(ang)); ys.append(cy + s.r * math.sin(ang))
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------- NC1 writing
def f(v, w=11, d=2):
    return f"{v:{w}.{d}f}"


def start_at_left(loop):
    """Rotate loop so it starts at the left-most vertex (lowest y on ties)."""
    i = min(range(len(loop)), key=lambda k: (round(loop[k].p0[0], 3), round(loop[k].p0[1], 3)))
    return loop[i:] + loop[:i]


def contour_lines(loop, face, flip_sign):
    """Face letter only on the first line; 'u' reference flag on the first x;
    x, y, radius, then 4 weld-prep columns (all zero)."""
    out = []
    pts = []
    for s in loop:
        r = 0.0
        if s.is_arc:
            r = s.r if s.ccw else -s.r
            if flip_sign:
                r = -r
        pts.append((s.p0[0], s.p0[1], r))
    pts.append((loop[0].p0[0], loop[0].p0[1], 0.0))
    for i, (x, y, r) in enumerate(pts):
        head = f"  {face}" if i == 0 else "   "
        flag = "u" if i == 0 else " "
        out.append(f"{head}{f(x)}{flag}{f(y, 10)}{f(r)}" + f(0.0) * 4)
    return out


def parse_info_text(text):
    m = re.match(r"\s*(\d+)\s*\+\s*PL\s*([\d.]+)\s*\+\s*(\S+)", text, re.I)
    if m:
        return int(m.group(1)), float(m.group(2)), m.group(3)
    return None


def convert(path, args):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    cut_l, cutout_l = args.cut_layer.upper(), args.cutout_layer.upper()
    scribe_l, text_l = args.scribe_layer.upper(), args.text_layer.upper()

    outer_segs, inner_segs, other_segs, holes, warnings = [], [], [], [], []
    mark, scribe_pos, info = None, None, None

    for e in msp:
        layer = e.dxf.layer.upper()
        t = e.dxftype()
        if t in ("TEXT", "MTEXT"):
            txt = e.dxf.text if t == "TEXT" else e.plain_text()
            ins = e.dxf.insert
            if layer == scribe_l:
                mark, scribe_pos = txt.strip(), (ins.x, ins.y, e.dxf.get("height", 10))
            elif layer == text_l:
                info = parse_info_text(txt) or info
            continue
        if layer == cut_l:
            outer_segs += entity_segments(e)
        elif layer == cutout_l:
            inner_segs += entity_segments(e)
        elif t == "CIRCLE":
            d = 2 * e.dxf.radius
            if args.hole_dia_from_layer:
                try:
                    d = float(e.dxf.layer)
                except ValueError:
                    pass
            holes.append((e.dxf.center.x, e.dxf.center.y, d))
        else:
            other_segs += entity_segments(e)

    if not outer_segs:
        # No CUT layer: largest closed loop is the outline, other loops are cutouts.
        warnings.append(f"no '{args.cut_layer}' layer - outline taken from largest closed shape")
        outer_segs, other_segs = other_segs, []
        # circles bigger than --max-hole are cut as contours, not drilled
        keep = []
        for x, y, d in holes:
            if d > args.max_hole:
                outer_segs += arc_segments((x, y), d / 2, math.pi, 2 * math.pi)
            else:
                keep.append((x, y, d))
        holes = keep

    outer_loops, open1 = chain(outer_segs, args.tol)
    inner_loops, open2 = chain(inner_segs, args.tol)
    for o in open1 + open2:
        warnings.append(f"open contour skipped (gap at {o[-1].p1[0]:.2f},{o[-1].p1[1]:.2f})")
    if not outer_loops:
        raise SystemExit(f"{path}: no closed outer contour found on layer '{args.cut_layer}'")
    outer_loops.sort(key=lambda l: abs(loop_area(l)), reverse=True)
    outer = outer_loops[0]
    if len(outer_loops) > 1:
        warnings.append(f"{len(outer_loops)-1} extra closed loop(s) on {args.cut_layer} treated as cutouts")
        inner_loops += outer_loops[1:]

    # orientation: outer CCW, inner CW
    if loop_area(outer) < 0:
        outer = reverse_loop(outer)
    inner_loops = [reverse_loop(l) if loop_area(l) > 0 else l for l in inner_loops]

    # move origin to lower-left of the outer contour
    x0, y0, x1, y1 = loop_bbox(outer)
    dx, dy = -x0, -y0
    outer = [s.shifted(dx, dy) for s in outer]
    inner_loops = [[s.shifted(dx, dy) for s in l] for l in inner_loops]
    holes = [(x + dx, y + dy, d) for x, y, d in holes]
    length, width = x1 - x0, y1 - y0

    outer = start_at_left(outer)
    inner_loops = sorted((start_at_left(l) for l in inner_loops),
                         key=lambda l: (round(l[0].p0[0], 2), l[0].p0[1]))

    stem = os.path.splitext(os.path.basename(path))[0]
    qty, thk, grade = info if info else (1, 0.0, "")
    qty = args.qty or qty
    thk = args.thickness or thk
    grade = args.grade or grade
    piece = args.mark or stem                  # piece mark = DXF file name (e.g. 6C-p1)
    phase = args.phase or mark or "63"         # SCRIBE text (e.g. 63) goes in the phase line
    if not thk:
        warnings.append("no thickness/grade in DXF - header left blank to fill in later")

    net_area = abs(loop_area(outer)) - sum(abs(loop_area(l)) for l in inner_loops) \
        - sum(math.pi * d * d / 4 for _, _, d in holes)
    weight = net_area * thk * DENSITY
    kg_per_m2 = thk * DENSITY * 1e6             # plate weight field = kg per m^2
    # painting surface (m2 per m2 of plate) = both faces + cut edges:  2 + t * perimeter / area
    # (holes ignored) - matches the reference NC1 files
    perim = sum(loop_perimeter(l) for l in [outer] + inner_loops)
    plate_area = abs(loop_area(outer)) - sum(abs(loop_area(l)) for l in inner_loops)
    paint = args.paint if args.paint is not None else 2 + thk * perim / plate_area

    L = ["ST",
         f"** {piece}.nc1",
         f"  {args.order}", f"  {args.drawing or stem}",
         f"  {phase}", f"  {piece}", f"  {grade}", f"  {qty}",
         f"  PL{thk:g}" if thk else "  PL", "  B",
         f(length), f(width), f(thk), f(thk), f(thk), f(0.0),
         f(kg_per_m2, d=3), f(paint, d=3),
         f(0.0, d=3), f(0.0, d=3), f(0.0, d=3), f(0.0, d=3),
         "", "", ""]
    L.append("AK")
    L += contour_lines(outer, "v", args.flip_arc_sign)
    for l in inner_loops:
        L.append("IK")
        L += contour_lines(l, "v", args.flip_arc_sign)
    if holes:
        L.append("BO")
        for x, y, d in sorted(holes, key=lambda h: (round(h[0], 2), h[1])):
            L.append(f"  v{f(x)}s{f(y, 10)}{f(d)}")
    if scribe_pos and mark and args.scribe:
        sx, sy, sh = scribe_pos
        L.append("SI")
        L.append(f"  v{f(sx + dx)}s{f(sy + dy, 10)}{f(0.0)}{int(round(sh)):4d} {mark}")
    L.append("EN")
    mark = piece

    out_dir = args.output or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{piece}.nc1")
    with open(out_path, "w", newline="\r\n") as fh:
        fh.write("\n".join(L) + "\n")

    print(f"{os.path.basename(path)} -> {out_path}")
    print(f"   mark {mark} | qty {qty} | PL{thk:g} {grade} | {length:.1f} x {width:.1f} mm | "
          f"{len(inner_loops)} cutout(s) | {len(holes)} hole(s) | {weight:.1f} kg each")
    for w in warnings:
        print("   WARNING:", w)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Convert plate DXF files to DSTV NC1")
    ap.add_argument("inputs", nargs="+", help="DXF files or glob patterns")
    ap.add_argument("-o", "--output", help="output folder (default: next to each DXF)")
    ap.add_argument("--cut-layer", default="CUT")
    ap.add_argument("--cutout-layer", default="CUTOUT")
    ap.add_argument("--scribe-layer", default="SCRIBE")
    ap.add_argument("--text-layer", default="TEXT")
    ap.add_argument("--mark", help="override piece mark")
    ap.add_argument("--qty", type=int)
    ap.add_argument("--thickness", type=float)
    ap.add_argument("--grade")
    ap.add_argument("--order", default="W8753", help="order / job number, e.g. W8753")
    ap.add_argument("--drawing", help="drawing number (default: DXF file name)")
    ap.add_argument("--phase", help="phase (default: SCRIBE text in the DXF)")
    ap.add_argument("--paint", type=float, help="override the painting-surface header value")
    ap.add_argument("--max-hole", type=float, default=40.0,
                    help="without a CUT layer: circles larger than this (mm) are cut as contours, not holes")
    ap.add_argument("--tol", type=float, default=0.05, help="contour joining tolerance (mm)")
    ap.add_argument("--hole-dia-from-layer", action="store_true",
                    help="use numeric layer name (e.g. '24') as hole diameter instead of drawn size")
    ap.add_argument("--flip-arc-sign", action="store_true",
                    help="invert radius sign if your machine reads arcs the other way")
    ap.add_argument("--scribe", action="store_true",
                    help="also write the SCRIBE text as an SI marking block (off by default)")
    args = ap.parse_args()

    files = []
    for p in args.inputs:
        files += glob.glob(p) or [p]
    for p in files:
        try:
            convert(p, args)
        except Exception as ex:  # keep batch going
            print(f"{p}: ERROR {ex}", file=sys.stderr)


if __name__ == "__main__":
    main()
