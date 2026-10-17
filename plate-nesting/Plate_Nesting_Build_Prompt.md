# Build prompt: plate nesting + DXF→NC1 software

Paste everything below the line into Claude Code (or another coding agent). Put these files in the empty repo first:
- `reference/dxf2nc1.py`: the working converter
- `reference/nc1/*.nc1`: the 17 reference files (6C-p1 … 6C-p20)
- `reference/dxf/6C-p1.dxf`: the sample DXF

---

You are a senior software engineer. You are building an open, clean-room nesting application for **structural steel plates**: thick plates, typically 6–75 mm, cut by plasma or oxy-fuel. The application has three jobs:

1. **Convert part DXFs into DSTV NC1 files** in our exact house format. This already works and must stay byte-exact.
2. **Nest those parts automatically onto sheets**, with manual editing.
3. **Export cut-ready output:** nested sheet DXF, G-code, per-part NC1 files and production reports.

The app should cover the same feature categories as commercial nesting products, which are described publicly at a marketing level only. Build it from public algorithms and open-source libraries, with your own design, names and UI.

## Goal
Build in this order: a headless core library, then a CLI, then a simple local web UI. The user's workflow:
1. Import parts as DXF files, NC1 files, or a folder of either.
2. Set quantity, grade and thickness.
3. Choose sheets and run automatic nesting.
4. Adjust the layout by hand.
5. Export.

The user works on **Windows**. Everything must install and run there, and the web UI runs locally in the browser.

## Starting point (already done, do not redesign)
- `reference/dxf2nc1.py` converts one plate DXF into one NC1 file. It has been verified against the 17 files in `reference/nc1/`: 15 are byte-identical, and 2 differ only in the painting-surface value, by at most 0.002.
- Port it into the core library as the `nc1` module, with NC1 **import** (parse into the part model) and NC1 **export**.
- Write regression tests first:
  - Every reference NC1 must survive import → export byte-for-byte, except header line 18 (±0.002).
  - Every reference NC1 must survive NC1 → DXF → NC1 the same way.
- These tests must stay green in every later phase.
- The full format spec is in Appendix A.

## Hard constraints
- **Clean-room:** do not decompile, disassemble or copy anything from Metalix, Tekla, SigmaNEST, Lantek or any other commercial product. Do not use their product names, UI assets or proprietary file formats (such as DFT). Open formats only: DXF, DSTV NC1, SVG, CSV, XLSX, PDF.
- **Licenses:** only add dependencies under MIT, BSD, Apache-2.0 or MPL-2.0. Check each dependency's license on its own repo or package page before adding it. No GPL code (for example, the Nestform fork of Deepnest). Record every dependency and its license in THIRD_PARTY.md.
- **No guessed APIs:** read the actual docs or source before using a library.
- **Units:** all units are millimetres.

## Suggested stack (verify before committing)
- Python 3.13, with pyproject.toml, pytest, ruff and mypy. Package it so `pip install .` works on Windows, and add a PyInstaller build for a double-click .exe later.
- ezdxf for DXF import and export. Shapely or Clipper2 for polygon math (offsets, contour closing, overlap checks).
- True-shape engine behind a small interface, `NestingEngine.nest(parts, sheets, options) -> Layout`. First candidates: sparrow via the spyrrow wrapper (check spyrrow's license first), or ironnest (check its license, maturity and API). Keep the engine swappable.
- FastAPI plus a plain SVG or canvas frontend for the UI.

## Part model
One `Part` holds:
- name (the DXF/NC1 file name without its extension)
- outer contour and inner contours, with true arcs kept (not only polylines)
- holes, kept separate from contours because they may be drilled rather than cut
- grade, thickness, quantity (may be blank)
- order (default `W8753`), phase (default `63`)

NC1 export, nesting and reports all use this same model.

## Build in this order. Do not start a phase until the previous one passes its tests.

0. **Setup:** repo layout, tooling, CI (Windows and Linux), THIRD_PARTY.md, and a short ARCHITECTURE.md describing the modules.

1. **Geometry and NC1 I/O:**
   - Port `dxf2nc1.py` and add NC1 import. Add the regression tests above.
   - DXF reading must handle lines, arcs, circles, polylines with bulges and splines.
   - Layer rules: `CUT` = outer contour, `CUTOUT` = inner contours, other layers' circles = holes. If no layer names are present, the largest closed shape is the outline, circles of 40 mm or less are holes, and larger circles are cut contours. The 40 mm limit is configurable.
   - Close nearly-closed contours, and report invalid parts clearly with the file name and gap location.
   - Missing grade or thickness is allowed: leave it blank and let the user fill it in later.
   - Keep true arcs for NC1 output. Convert curves to polylines within a configurable tolerance only for nesting math.

2. **Baseline rectangular nester:** implement MaxRects or skyline yourself. It is the fallback and the benchmark.

3. **True-shape nesting:** an adapter for the chosen engine. Support:
   - rotation steps (default 90°; allow free angles)
   - mirroring
   - part spacing that accounts for kerf, configurable per process (plasma vs. oxy-fuel; thick plate needs more spacing)
   - sheet edge margin
   - part priority
   - part-in-part placement, for example small plates inside the cutout of the ring flange 6C-p1

4. **Sheets and materials:**
   - Group parts by **grade + thickness**. Never mix different groups on one sheet.
   - Allow multiple standard sheet sizes.
   - Keep a sheet and remnant inventory: store each leftover polygon and reuse it in later jobs.
   - Support rolling-direction (grain) rotation limits.
   - Choose the minimum number of sheets.
   - Report the nested weight per sheet: thickness × 7.85 kg/m² × area.

5. **Common cuts:** detect shared collinear edges between neighboring parts within a tolerance and merge them into a single cut. Make this optional per thickness, because it is often unsuitable on very thick plate. Show the merged edges in the layout.

6. **Cut path and machine output:**
   - Lead-in and lead-out, kerf compensation, pierce points (keep them away from part edges on thick plate), and cut order: holes and inner contours before outer contours, with nearest-neighbor sequencing.
   - A post-processor interface with these first outputs:
     - (a) a nested sheet DXF
     - (b) generic G-code in one configurable dialect
     - (c) the per-part NC1 files from Phase 1, so existing machines keep working
   - Ask me which cutting machine and controller we use **before** building any machine-specific dialect.

7. **Orders and reports:**
   - Order import from a CSV (part file, quantity, grade, thickness) **or** directly from a folder of NC1 files, which already contain quantity, grade and thickness in their headers.
   - Reports in XLSX and PDF: order summary, per-sheet utilization and weight, part lists, and labels or barcodes per part showing the part name, order and phase.

8. **Web UI:**
   - Preview each sheet, with drag-and-drop manual placement, snapping, rotate and mirror.
   - Re-run common-cut detection and the validator after every move.
   - Include an editable parts table for filling in blank grade, thickness and quantity before nesting. Changing thickness must update the NC1 weight and painting-surface values.

## Quality bar
- **Independent validator:** a separate function that checks every layout for part overlap, parts outside the sheet, and spacing violations using Shapely. Run it in every nesting test.
- **Deterministic runs:** expose a seed option, and make equal seeds give equal layouts.
- **Benchmarks:** report material utilization on public 2D irregular benchmark datasets (for example from the OR-Datasets collection), on the 17 reference parts with their real quantities, and on at least three more realistic plate fixtures you create. Compare true-shape against the rectangular baseline.
- **Tests:** unit tests for geometry cleanup, the NC1 regression suite, integration tests for DXF → layout → G-code/NC1, and fixture files in the repo.
- Type hints everywhere, docstrings on public functions, no dead code.

## Working rules
- Start by writing a short plan with the module list and the main risks, then begin Phase 0 without waiting for approval.
- Make small, reviewable commits with clear messages.
- Ask me a question only when you are blocked on a decision that cannot be made from this prompt (the machine dialect in Phase 6 is one). For anything else, choose a sensible default, note it in DECISIONS.md, and continue.
- After each phase, run the tests and report: what works, what the numbers are (utilization, runtime), and what is still missing.

## Deliverables
A working repo containing:
- README with install steps (Windows first), quickstart and example commands
- ARCHITECTURE.md, DECISIONS.md, THIRD_PARTY.md
- tests, sample DXF and NC1 files
- an end-to-end demo script that goes from a folder of DXFs (or NC1s) plus an optional CSV order to nested layouts, G-code, per-part NC1 files and a report

---

## Appendix A: NC1 house format (must match `reference/nc1/` exactly)

**General:** one file per part, named `<name>.nc1`. Windows CRLF line endings. Every part is a flat plate (profile code `B`), with all geometry on face `v`.

### Geometry placement
- Shift the part so the lower-left corner of the outer contour's bounding box is at (0,0). Arcs count at their real extreme points.
- The outer contour (AK) runs counter-clockwise. Inner contours (IK) run clockwise.
- Each contour starts at its leftmost vertex (lowest y on ties) and ends by repeating that point with radius 0.
- Split arcs larger than 180° into equal pieces. A full circle becomes two 180° arcs, split at its leftmost point.
- Inner contours are listed by start x. Holes are listed by x, then y.

### Arcs
The radius goes on the **start point** of the arc segment, and the arc runs from that point to the next one.
- **+R** = counter-clockwise
- **−R** = clockwise
- **0** = straight line

### ST header

| Line | Content |
|---|---|
| 1 | `ST` |
| 2 | `** <name>.nc1` |
| 3 | order (`W8753`) |
| 4 | drawing (`<name>`) |
| 5 | phase (`63`) |
| 6 | piece (`<name>`) |
| 7 | grade (blank if unknown) |
| 8 | quantity (1 if unknown) |
| 9 | `PL<t>` (`PL` if unknown) |
| 10 | `B` |
| 11 | length = bounding-box X |
| 12 | width = bounding-box Y |
| 13–15 | thickness (three times) |
| 16 | `0.00` |
| 17 | kg/m² = t × 7.85 |
| 18 | painting surface = 2 + t × (perimeter of outer + inner contours) ÷ (outer area − inner areas); holes ignored |
| 19–22 | `0.000` (four lines) |
| 23–25 | three empty lines |

- Text lines 3–10 are indented by two spaces.
- Lines 11–16 use `%11.2f`.
- Lines 17–22 use `%11.3f`.

### AK / IK lines
- First line: `"  v"` + x`%11.2f` + `"u"` + y`%10.2f` + r`%11.2f` + 4 × `%11.2f` of 0
- Following lines: `"   "` (3 spaces, no face letter) + x`%11.2f` + `" "` + y`%10.2f` + r`%11.2f` + 4 zero columns

### BO lines
- One `BO` line, then each hole as `"  v"` + x`%11.2f` + `"s"` + y`%10.2f` + diameter`%11.2f`
- No depth column. Leave the block out if there are no holes.
- Use the drawn hole diameter (for example 24.23), not the nominal size from the layer name.

### Finish
- End with `EN`.
- Do not write an SI marking block unless the user turns it on.

### Example: 6C-p13.nc1 (lug with arcs and a round cutout)
```
ST
** 6C-p13.nc1
  W8753
  6C-p13
  63
  6C-p13
  350W
  28
  PL25
  B
     200.00
     162.80
      25.00
      25.00
      25.00
       0.00
    196.250
      2.910
      0.000
      0.000
      0.000
      0.000



AK
  v       0.00u      0.00       0.00       0.00       0.00       0.00       0.00
        200.00       0.00       0.00       0.00       0.00       0.00       0.00
        169.81     109.56      72.50       0.00       0.00       0.00       0.00
         99.91     162.80       0.00       0.00       0.00       0.00       0.00
         76.90     158.99      72.50       0.00       0.00       0.00       0.00
         30.19     109.56       0.00       0.00       0.00       0.00       0.00
          0.00       0.00       0.00       0.00       0.00       0.00       0.00
IK
  v      72.50u     90.00     -27.50       0.00       0.00       0.00       0.00
        127.50      90.00     -27.50       0.00       0.00       0.00       0.00
         72.50      90.00       0.00       0.00       0.00       0.00       0.00
EN
```
See `reference/nc1/` for the other 16 files, including the ring flange with 16 holes (6C-p1) and the chamfered plates (6C-p3, p8, p10).
