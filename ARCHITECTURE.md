# Architecture — PathCUT

## Package layout

```
src/plate_nesting/
├── gui/             PySide6 desktop application
│   ├── app.py       Main window, dark Fusion theme, entry point
│   └── converter.py Convert tab UI (settings ribbon, file table, conversion)
├── models/          Part dataclass (central model used by all modules)
│   └── part.py      Central Part model
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
│   └── writer.py    Part → DXF
├── cli/main.py      CLI entry point
├── orders/          CSV/folder import (planned)
├── reports/         XLSX/PDF reports (planned)
└── web/             FastAPI + frontend (planned)
```

### Build / installer tooling (project root)

```
pathcut.spec         PyInstaller spec (onedir, windowed)
installer.iss        Inno Setup 6 script
build_installer.bat  One-click build: PyInstaller + Inno Setup
generate_guide.py    Generates PathCUT_User_Guide.pdf
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
