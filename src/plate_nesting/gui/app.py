"""PathCUT desktop application — main window, options, nesting thread."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

from plate_nesting.dxf.reader import read_dxf
from plate_nesting.gui.canvas import SheetScene, SheetView, populate_scene
from plate_nesting.materials.inventory import SheetInventory
from plate_nesting.models.nesting import EngineType, NestOptions
from plate_nesting.models.part import Part
from plate_nesting.models.sheet import Sheet
from plate_nesting.nc1.parser import parse_nc1
from plate_nesting.nesting.job import JobResult, nest_job

# ---------------------------------------------------------------------------
# Options panel
# ---------------------------------------------------------------------------

class OptionsPanel(QGroupBox):
    """Form for NestOptions fields + sheet dimensions."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Options", parent)
        form = QFormLayout()

        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0, 100)
        self.spacing.setValue(10.0)
        self.spacing.setSuffix(" mm")
        form.addRow("Spacing:", self.spacing)

        self.edge_margin = QDoubleSpinBox()
        self.edge_margin.setRange(0, 100)
        self.edge_margin.setValue(10.0)
        self.edge_margin.setSuffix(" mm")
        form.addRow("Edge margin:", self.edge_margin)

        self.engine = QComboBox()
        self.engine.addItems(["TrueShape", "MaxRects"])
        form.addRow("Engine:", self.engine)

        self.rotation = QComboBox()
        self.rotation.addItems(["90°", "180°", "Free", "None"])
        form.addRow("Rotation:", self.rotation)

        self.mirror = QCheckBox()
        form.addRow("Allow mirror:", self.mirror)

        self.common_cuts = QCheckBox()
        self.common_cuts.setChecked(True)
        form.addRow("Common cuts:", self.common_cuts)

        self.time_budget = QSpinBox()
        self.time_budget.setRange(5, 300)
        self.time_budget.setValue(30)
        self.time_budget.setSuffix(" s")
        form.addRow("Time budget:", self.time_budget)

        # Sheet size
        self.sheet_length = QDoubleSpinBox()
        self.sheet_length.setRange(100, 20000)
        self.sheet_length.setValue(6000)
        self.sheet_length.setSuffix(" mm")
        self.sheet_length.setDecimals(0)
        form.addRow("Sheet length:", self.sheet_length)

        self.sheet_width = QDoubleSpinBox()
        self.sheet_width.setRange(100, 10000)
        self.sheet_width.setValue(2000)
        self.sheet_width.setSuffix(" mm")
        self.sheet_width.setDecimals(0)
        form.addRow("Sheet width:", self.sheet_width)

        self.setLayout(form)

    def to_nest_options(self) -> NestOptions:
        rot_map = {"90°": 90.0, "180°": 180.0, "Free": 1.0, "None": 0.0}
        eng_map = {"TrueShape": EngineType.TRUESHAPE, "MaxRects": EngineType.MAXRECTS}
        return NestOptions(
            engine=eng_map[self.engine.currentText()],
            spacing=self.spacing.value(),
            edge_margin=self.edge_margin.value(),
            rotation_step=rot_map[self.rotation.currentText()],
            allow_mirror=self.mirror.isChecked(),
            common_cuts=self.common_cuts.isChecked(),
            time_budget=self.time_budget.value(),
        )

    def to_sheet_inventory(self, parts: list[Part]) -> SheetInventory:
        combos = {(p.grade, p.thickness) for p in parts}
        sheets = [
            Sheet(
                length=self.sheet_length.value(),
                width=self.sheet_width.value(),
                grade=g,
                thickness=t,
            )
            for g, t in combos
        ]
        return SheetInventory(standard_sizes=sheets)


# ---------------------------------------------------------------------------
# Nesting worker thread
# ---------------------------------------------------------------------------

class NestWorker(QThread):
    """Run nest_job() off the main thread."""

    finished = Signal(object)   # JobResult
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        parts: list[Part],
        inventory: SheetInventory,
        options: NestOptions,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._parts = parts
        self._inventory = inventory
        self._options = options

    def run(self) -> None:
        try:
            self.progress.emit("Nesting parts…")
            result = nest_job(self._parts, self._inventory, self._options)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class PathCutApp(QMainWindow):
    """PathCUT desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PathCUT — Plate Nesting")
        self.resize(1400, 900)
        self.setAcceptDrops(True)

        self._parts: list[Part] = []
        self._result: JobResult | None = None
        self._worker: NestWorker | None = None

        self._build_ui()
        self._connect_signals()

    # ---- UI construction ----

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Toolbar row
        toolbar = QHBoxLayout()
        self._import_btn = QPushButton("Import Files")
        self._nest_btn = QPushButton("Nest")
        self._nest_btn.setEnabled(False)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedWidth(160)

        toolbar.addWidget(self._import_btn)
        toolbar.addWidget(self._nest_btn)
        toolbar.addStretch()
        title = QLabel("PathCUT")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._progress)
        root.addLayout(toolbar)

        # Splitter: left panel | right panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- left ---
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Name", "L", "W", "Qty", "Material"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        left_lay.addWidget(self._table, stretch=1)

        self._options = OptionsPanel()
        left_lay.addWidget(self._options)

        splitter.addWidget(left)

        # --- right ---
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        self._summary = QLabel("")
        self._summary.setStyleSheet("padding:4px;")
        right_lay.addWidget(self._summary)

        self._tabs = QTabWidget()
        right_lay.addWidget(self._tabs, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1080])
        root.addWidget(splitter, stretch=1)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — import DXF or NC1 files to begin")

    def _connect_signals(self) -> None:
        self._import_btn.clicked.connect(self._on_import)
        self._nest_btn.clicked.connect(self._on_nest)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ---- file import ----

    def _on_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Parts",
            "",
            "Part files (*.dxf *.nc1);;DXF (*.dxf);;NC1 (*.nc1)",
        )
        if paths:
            self._import_files(paths)

    def _import_files(self, paths: list[str]) -> None:
        errors: list[str] = []
        count_before = len(self._parts)
        for p in paths:
            try:
                fp = Path(p)
                ext = fp.suffix.lower()
                if ext == ".dxf":
                    part = read_dxf(fp)
                elif ext == ".nc1":
                    part = parse_nc1(fp.read_text(encoding="utf-8", errors="replace"))
                else:
                    continue
                self._parts.append(part)
            except Exception as exc:
                errors.append(f"{Path(p).name}: {exc}")

        added = len(self._parts) - count_before
        self._refresh_table()
        self._nest_btn.setEnabled(bool(self._parts))
        self._statusbar.showMessage(
            f"{len(self._parts)} parts loaded (+{added} new)"
        )
        if errors:
            QMessageBox.warning(
                self, "Import Errors", "\n".join(errors)
            )

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._parts))
        for i, p in enumerate(self._parts):
            self._table.setItem(i, 0, QTableWidgetItem(p.name))
            self._table.setItem(i, 1, QTableWidgetItem(f"{p.length:.0f}"))
            self._table.setItem(i, 2, QTableWidgetItem(f"{p.width:.0f}"))
            self._table.setItem(i, 3, QTableWidgetItem(str(p.qty)))
            mat = p.grade
            if p.thickness:
                mat = f"{mat} {p.thickness:.0f}mm" if mat else f"{p.thickness:.0f}mm"
            self._table.setItem(i, 4, QTableWidgetItem(mat))
        self._table.resizeColumnsToContents()

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".dxf", ".nc1")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith((".dxf", ".nc1"))
        ]
        if paths:
            self._import_files(paths)

    # ---- nesting ----

    def _on_nest(self) -> None:
        if not self._parts:
            return
        options = self._options.to_nest_options()
        inventory = self._options.to_sheet_inventory(self._parts)

        self._nest_btn.setEnabled(False)
        self._progress.setVisible(True)

        self._worker = NestWorker(self._parts, inventory, options, self)
        self._worker.finished.connect(self._on_nest_done)
        self._worker.error.connect(self._on_nest_error)
        self._worker.progress.connect(self._statusbar.showMessage)
        self._worker.start()

    def _on_nest_done(self, result: JobResult) -> None:
        self._worker = None
        self._result = result
        self._nest_btn.setEnabled(True)
        self._progress.setVisible(False)

        n = result.total_sheets
        util = result.avg_utilization * 100
        placed = result.total_parts_placed
        unplaced = len(result.unplaced)
        self._summary.setText(
            f"{n} sheet{'s' if n != 1 else ''} | "
            f"{util:.1f}% utilization | "
            f"{placed} placed"
            + (f" | {unplaced} unplaced" if unplaced else "")
        )

        self._tabs.clear()
        for i, report in enumerate(result.sheet_reports):
            scene = SheetScene()
            populate_scene(scene, report.layout)
            view = SheetView()
            view.setScene(scene)
            view.part_clicked.connect(self._on_canvas_select)
            label = f"Sheet {i + 1} ({report.utilization * 100:.0f}%)"
            self._tabs.addTab(view, label)

        self._statusbar.showMessage(f"Nesting complete — {n} sheets")

        # Defer fit_sheet until the view has a valid viewport size
        if self._tabs.count():
            QTimer.singleShot(0, lambda: self._on_tab_changed(0))

    def _on_nest_error(self, msg: str) -> None:
        self._worker = None
        self._nest_btn.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.critical(self, "Nesting Error", msg)
        self._statusbar.showMessage("Nesting failed")

    # ---- tab / selection sync ----

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        view = self._tabs.widget(index)
        if isinstance(view, SheetView):
            view.fit_sheet()

    def _on_canvas_select(self, placement_index: int) -> None:
        tab = self._tabs.currentIndex()
        if tab < 0 or self._result is None:
            return
        report = self._result.sheet_reports[tab]
        pp = report.layout.placements[placement_index]
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.text() == pp.part.name:
                self._table.selectRow(row)
                break


# ---------------------------------------------------------------------------
# Dark Fusion theme
# ---------------------------------------------------------------------------

def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    p = QPalette()
    dark = QColor(45, 45, 45)
    text = QColor(208, 208, 208)
    base = QColor(30, 30, 30)
    highlight = QColor(42, 130, 218)

    p.setColor(QPalette.ColorRole.Window, dark)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, dark)
    p.setColor(QPalette.ColorRole.ToolTipBase, dark)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, dark)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    p.setColor(QPalette.ColorRole.Link, highlight)
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(p)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    window = PathCutApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
