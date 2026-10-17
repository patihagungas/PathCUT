# Technical Decisions

## D001: Python version target ≥3.11
We target Python 3.11+ for broad compatibility. No 3.12+ features (like type parameter syntax) are used. The user's environment has Python 3.11.9.

## D002: hatchling as build backend
Lightweight, standards-compliant, no compiled extensions needed.

## D003: Seg class uses tuples for points
Points are `(x, y)` tuples rather than a Point class. This keeps the geometry layer simple and avoids overhead for the millions of point comparisons in nesting.

## D004: NC1 painting surface tolerance ±0.002
The reference files show that the painting surface value (header line 18) can differ by up to 0.002 due to floating-point precision. The roundtrip test allows this tolerance.

## D005: Default order "W8753", default phase "63"
These are the house defaults matching the reference files.

## D006: Arc sign convention
In NC1 output: +R = counter-clockwise, −R = clockwise, 0 = straight line. The radius is written on the start point of each arc segment.

## D007: CRLF line endings in NC1 files
NC1 files use Windows CRLF (`\r\n`) line endings per DSTV convention.

## D008: MaxRects BSSF as baseline nester
Best Short Side Fit heuristic chosen for the rectangular baseline nester. It provides good packing density for mixed-size rectangles and is simple to implement. This serves as the fallback and benchmark for comparison with Phase 3 true-shape nesting.

## D009: NestingEngine protocol for swappable engines
Nesting engines implement `nest(parts, sheets, options) -> list[Layout]`. This allows the MaxRects baseline and future true-shape engines to be swapped without changing calling code.

## D010: Independent Shapely validator
Layout validation uses Shapely polygon operations, completely independent of the nesting engine. It checks overlap, sheet bounds, and spacing. Run on every layout in every nesting test.

## D011: Default nesting parameters
- Spacing: 10mm (accounts for kerf + clearance)
- Edge margin: 10mm
- Rotation step: 90° (4 orientations)
- Seed: 42 (deterministic)

## D012: spyrrow (MIT) as true-shape nesting engine
spyrrow wraps the Rust-based sparrow strip packer. MIT license. It solves strip packing (fixed height, minimizes width). We map to sheet packing by slicing the strip into sheet-length segments. This gives true-shape nesting with proper collision detection.

## D013: Strip-to-sheet mapping strategy
spyrrow produces one long strip. We slice it into sheets by sorting placements by x-coordinate and starting a new sheet when a placement's bounding box exceeds the sheet length. This is simple and works well for greedy packing.

## D014: Part-in-part as post-processing
spyrrow doesn't support holes. Part-in-part placement is a separate post-processing step that checks if small parts fit inside the cutouts of already-placed parts using Shapely containment tests.

## D015: Validator uses polygon-with-holes for overlap
The true-shape validator subtracts inner cutouts from part polygons when checking overlap. This allows parts placed inside cutouts (part-in-part) to pass validation correctly.

## D016: True-shape vs MaxRects comparison
On the 144 reference parts (1877 instances, 9 grade/thickness groups):
- MaxRects: 91 sheets, 68.2% avg utilization (bounding-box)
- TrueShape: 92 sheets, 67.4% avg utilization (10s/group budget)
These parts are mostly rectangular, so the advantage of true-shape shows on more irregular parts. Longer time budgets improve spyrrow results.

## D017: Grade+thickness material grouping
Parts are grouped by `(grade, thickness)` before nesting. Each sheet contains only one material group — never mixed. This matches real fabrication where each plate has a specific grade and thickness.

## D018: Sheet inventory with JSON persistence
SheetInventory holds standard sheet sizes and remnants. Standard sizes are material-agnostic templates (grade/thickness assigned at nesting time). Remnants are material-specific. Inventory serializes to JSON for persistence between sessions.

## D019: Grain direction rotation limits
GrainDirection enum (NONE, LENGTH, WIDTH) on Sheet. When grain is constrained, rotation_step is forced to 180° so parts can only orient at 0° or 180° (parallel to rolling direction). GrainDirection.NONE leaves rotation unconstrained.

## D020: Remnant collection strategy
After nesting, the unused strip to the right of the rightmost part on each sheet is computed as a rectangular remnant. Minimum dimension is 200mm in both directions to avoid collecting unusably small scraps. Remnants carry grade, thickness, and grain from their source sheet.

## D021: Job orchestrator design
`nest_job()` is the top-level entry point that groups parts, selects sheets from inventory, applies grain constraints, runs the nesting engine per group, and collects results. Returns `JobResult` with per-sheet reports (weight, utilization) and remnants. Default inventory provides 5 common structural steel sheet sizes (2500×1250 to 12000×2500).

## D022: Common cuts as post-processing
Common cut detection runs after nesting, not during. The nester places parts normally; then `detect_common_cuts()` identifies which adjacent edges can share a single cut line. This keeps the nesting engine simple and the feature toggleable.

## D023: Thickness threshold for common cuts
`common_cut_max_thickness` (default 30mm) disables detection for thick plate. Thick plate has wider kerf and more heat distortion, making shared cuts impractical. The threshold is configurable per job.

## D024: Straight edges only for common cuts
Only straight (line) segments are candidates for common cuts. Arc edges are excluded because matching collinear arcs is geometrically complex and rarely occurs in practice between adjacent parts.

## D025: Common cuts stored on Layout
`Layout.common_cuts` is a generic list to avoid circular imports with the `cutting/` module. Each entry is a `CommonCut` dataclass with edge references, cut endpoints, and cut length.
