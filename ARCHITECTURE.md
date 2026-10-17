# Architecture

## Package layout

```
src/plate_nesting/
├── models/          Part, Sheet, Layout, Order dataclasses
│   └── part.py      Central Part model used by all modules
├── geometry/        Seg class, contour operations, area/perimeter
│   ├── seg.py       Line/arc segment
│   ├── contour.py   chain, orient, start_at_left, bbox
│   └── area.py      loop_area, loop_perimeter
├── nc1/             DSTV NC1 file I/O
│   ├── parser.py    NC1 text → Part
│   ├── writer.py    Part → NC1 text
│   └── _format.py   Shared constants and formatting helpers
├── dxf/             DXF file I/O (via ezdxf)
│   ├── reader.py    DXF → Part
│   └── writer.py    Part → DXF (Phase 6)
├── nesting/         Nesting engines and orchestrator
│   ├── __init__.py  nest() dispatcher (routes by EngineType)
│   ├── maxrects.py  MaxRects BSSF bin packing engine
│   ├── trueshape.py spyrrow-based true-shape strip packer
│   ├── partinpart.py Post-proc: fit parts inside cutouts
│   ├── validator.py Independent Shapely layout validator
│   └── job.py       Job orchestrator (group, nest, report)
├── materials/       Sheet/remnant inventory
│   └── inventory.py SheetInventory, Remnant, JSON persistence
├── cutting/         Common cuts, cut path, G-code generation
│   └── common_cut.py Detect shared collinear edges between parts
├── orders/          CSV/folder import (Phase 7)
├── reports/         XLSX/PDF reports (Phase 7)
├── cli/main.py      CLI entry point
└── web/             FastAPI + frontend (Phase 8)
```

## Data flow

```
DXF file ──→ dxf.reader ──→ Part ──→ nc1.writer ──→ NC1 file
NC1 file ──→ nc1.parser ──→ Part ──┐
                                    ├──→ nest_job() ──→ JobResult
SheetInventory ─────────────────────┘       │
  (standard sizes + remnants)               ├── SheetReport (per sheet)
                                            ├── Remnants (leftover strips)
                                            └── Layouts ──→ reports / DXF
```

## Nesting pipeline

1. **nest_job()** groups parts by grade+thickness
2. For each group, selects sheets from SheetInventory
3. Applies grain rotation constraints
4. Dispatches to MaxRects or TrueShape engine via `nest()`
5. Detects common cuts between adjacent parts (if enabled and thickness ≤ threshold)
6. Collects per-sheet reports (utilization, weight) and remnants

## Key design decisions

- **Part is the central model.** All I/O modules produce or consume Part objects.
- **True arcs preserved.** Geometry uses Seg (line or arc), not just polylines. Arcs are only flattened for nesting polygon math.
- **NestingEngine protocol.** Engines are swappable behind a common interface (`EngineType.MAXRECTS` / `EngineType.TRUESHAPE`).
- **Grade+thickness grouping.** Parts never mix materials on one sheet.
- **Independent validator.** Shapely-based validation checks every layout for overlap, bounds, and spacing.
- **All units in millimetres.**
