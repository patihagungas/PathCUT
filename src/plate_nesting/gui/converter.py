"""Convert tab — bidirectional DXF/NC1 conversion."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

from plate_nesting.dxf.reader import DxfReadOptions, read_dxf
from plate_nesting.dxf.writer import write_dxf
from plate_nesting.models.part import Part
from plate_nesting.nc1.parser import parse_nc1
from plate_nesting.nc1.writer import write_nc1

# Column indices
COL_NUM, COL_FILE, COL_NAME, COL_L, COL_W, COL_QTY, COL_GRADE, COL_THK, COL_STATUS = range(9)

# Columns the user can edit (all meaningful fields)
_EDITABLE_COLS = {COL_NAME, COL_L, COL_W, COL_QTY, COL_GRADE, COL_THK}


class SettingsRibbon(QWidget):
    """Ribbon bar with DXF layer names, defaults, and output settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # DXF Layers group
        layers = QGroupBox("DXF Layers")
        lg = QFormLayout()
        self._cut_layer = QLineEdit("CUT")
        self._cutout_layer = QLineEdit("CUTOUT")
        self._text_layer = QLineEdit("TEXT")
        self._scribe_layer = QLineEdit("SCRIBE")
        lg.addRow("Cut:", self._cut_layer)
        lg.addRow("Cutout:", self._cutout_layer)
        lg.addRow("Text:", self._text_layer)
        lg.addRow("Scribe:", self._scribe_layer)
        layers.setLayout(lg)
        layout.addWidget(layers)

        # Defaults group
        defaults = QGroupBox("Defaults")
        dg = QFormLayout()
        self._order = QLineEdit("W8753")
        self._phase = QLineEdit("63")
        self._max_hole = QDoubleSpinBox()
        self._max_hole.setRange(0, 9999)
        self._max_hole.setValue(40.0)
        self._max_hole.setSuffix(" mm")
        dg.addRow("Order:", self._order)
        dg.addRow("Phase:", self._phase)
        dg.addRow("Max hole:", self._max_hole)
        defaults.setLayout(dg)
        layout.addWidget(defaults)

        # Output group
        output = QGroupBox("Output")
        og = QFormLayout()
        self._dxf_ver = QComboBox()
        self._dxf_ver.addItems(["R2010", "R2013", "R2018"])
        self._encoding = QComboBox()
        self._encoding.addItems(["UTF-8", "Latin-1"])
        self._precision = QSpinBox()
        self._precision.setRange(1, 6)
        self._precision.setValue(2)
        og.addRow("DXF Ver:", self._dxf_ver)
        og.addRow("Encoding:", self._encoding)
        og.addRow("Precision:", self._precision)
        output.setLayout(og)
        layout.addWidget(output)

    def to_read_options(self) -> DxfReadOptions:
        """Build DxfReadOptions from current ribbon values."""
        return DxfReadOptions(
            cut_layer=self._cut_layer.text().strip() or "CUT",
            cutout_layer=self._cutout_layer.text().strip() or "CUTOUT",
            text_layer=self._text_layer.text().strip() or "TEXT",
            scribe_layer=self._scribe_layer.text().strip() or "SCRIBE",
            max_hole=self._max_hole.value(),
            order=self._order.text().strip() or "W8753",
            phase=self._phase.text().strip(),
        )

    def dxf_version(self) -> str:
        return self._dxf_ver.currentText()

    def encoding(self) -> str:
        return self._encoding.currentText().lower()

    def precision(self) -> int:
        return self._precision.value()

    def cut_layer(self) -> str:
        return self._cut_layer.text().strip() or "CUT"

    def cutout_layer(self) -> str:
        return self._cutout_layer.text().strip() or "CUTOUT"

    def text_layer(self) -> str:
        return self._text_layer.text().strip() or "TEXT"


class ConvertTab(QWidget):
    """Bidirectional DXF <-> NC1 converter UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._items: list[tuple[Path, Part]] = []
        self._build_ui()
        self._connect_signals()

    # ---- UI ----

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Settings ribbon
        self._ribbon = SettingsRibbon()
        root.addWidget(self._ribbon)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Direction:"))
        self._direction = QComboBox()
        self._direction.addItems(["DXF \u2192 NC1", "NC1 \u2192 DXF"])
        toolbar.addWidget(self._direction)

        self._add_btn = QPushButton("Add Files")
        self._clear_btn = QPushButton("Clear")
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setEnabled(False)
        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._convert_btn)
        root.addLayout(toolbar)

        # Output directory row
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output:"))
        self._output_dir = QLineEdit()
        self._output_dir.setPlaceholderText("Same as source file directory")
        out_row.addWidget(self._output_dir, stretch=1)
        self._browse_btn = QPushButton("Browse")
        out_row.addWidget(self._browse_btn)
        root.addLayout(out_row)

        # Defaults row (visible only for DXF → NC1)
        self._defaults_row = QHBoxLayout()
        self._defaults_row_label = QLabel("Defaults:")
        self._defaults_row.addWidget(self._defaults_row_label)

        self._default_grade = QLineEdit()
        self._default_grade.setPlaceholderText("Grade e.g. 350W")
        self._default_grade.setMaximumWidth(160)
        self._defaults_row.addWidget(QLabel("Grade:"))
        self._defaults_row.addWidget(self._default_grade)

        self._default_thk = QLineEdit()
        self._default_thk.setPlaceholderText("Thickness (mm)")
        self._default_thk.setMaximumWidth(120)
        self._defaults_row.addWidget(QLabel("Thk:"))
        self._defaults_row.addWidget(self._default_thk)

        self._apply_defaults_btn = QPushButton("Apply to All")
        self._defaults_row.addWidget(self._apply_defaults_btn)
        self._defaults_row.addStretch()

        # Wrap in a widget so we can show/hide it
        self._defaults_widget = QWidget()
        self._defaults_widget.setLayout(self._defaults_row)
        root.addWidget(self._defaults_widget)

        # Table
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            ["#", "Input File", "Name", "L", "W", "Qty", "Grade", "Thk", "Status"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, stretch=1)

        # Log
        root.addWidget(QLabel("Log:"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        root.addWidget(self._log)

    def _connect_signals(self) -> None:
        self._add_btn.clicked.connect(self._add_files)
        self._clear_btn.clicked.connect(self._clear)
        self._convert_btn.clicked.connect(self._convert)
        self._browse_btn.clicked.connect(self._browse_output)
        self._direction.currentIndexChanged.connect(self._on_direction_changed)
        self._apply_defaults_btn.clicked.connect(self._apply_defaults)

    # ---- helpers ----

    def _is_dxf_to_nc1(self) -> bool:
        return self._direction.currentIndex() == 0

    def _source_ext(self) -> str:
        return ".dxf" if self._is_dxf_to_nc1() else ".nc1"

    def _target_ext(self) -> str:
        return ".nc1" if self._is_dxf_to_nc1() else ".dxf"

    def _log_msg(self, msg: str) -> None:
        self._log.append(msg)

    # ---- actions ----

    def _add_files(self) -> None:
        ext = self._source_ext()
        label = ext.upper().lstrip(".")
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            "",
            f"{label} files (*{ext})",
        )
        if paths:
            self._load_files([Path(p) for p in paths])

    def _load_files(self, paths: list[Path]) -> None:
        errors: list[str] = []
        ext = self._source_ext()
        for fp in paths:
            if fp.suffix.lower() != ext:
                continue
            try:
                if ext == ".dxf":
                    part = read_dxf(fp, opts=self._ribbon.to_read_options())
                else:
                    part = parse_nc1(fp.read_text(encoding="utf-8", errors="replace"))
                self._items.append((fp, part))
            except Exception as exc:
                errors.append(f"{fp.name}: {exc}")
                self._log_msg(f"ERROR reading {fp.name}: {exc}")

        self._refresh_table()
        self._convert_btn.setEnabled(bool(self._items))

        # Default output dir to first file's parent
        if self._items and not self._output_dir.text():
            self._output_dir.setText(str(self._items[0][0].parent))

        if errors:
            QMessageBox.warning(self, "Read Errors", "\n".join(errors))

    def _clear(self) -> None:
        self._items.clear()
        self._table.setRowCount(0)
        self._convert_btn.setEnabled(False)
        self._log.clear()

    def _on_direction_changed(self) -> None:
        if self._items:
            reply = QMessageBox.question(
                self,
                "Change Direction",
                "Changing direction will clear the current file list. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                # Revert combo without re-triggering
                self._direction.blockSignals(True)
                self._direction.setCurrentIndex(1 - self._direction.currentIndex())
                self._direction.blockSignals(False)
                return
            self._clear()
        self._defaults_widget.setVisible(self._is_dxf_to_nc1())

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Output Directory")
        if d:
            self._output_dir.setText(d)

    def _apply_defaults(self) -> None:
        """Apply default grade/thickness to all rows."""
        grade = self._default_grade.text().strip()
        thk = self._default_thk.text().strip()
        for row in range(self._table.rowCount()):
            if grade:
                item = self._table.item(row, COL_GRADE)
                if item:
                    item.setText(grade)
            if thk:
                item = self._table.item(row, COL_THK)
                if item:
                    item.setText(thk)

    def _convert(self) -> None:
        if not self._items:
            return

        target_ext = self._target_ext()
        to_nc1 = target_ext == ".nc1"

        # Validate Grade + Thickness for DXF → NC1
        if to_nc1:
            missing: list[str] = []
            for row in range(self._table.rowCount()):
                name = self._table.item(row, COL_NAME)
                name_text = name.text() if name else f"Row {row + 1}"
                grade = self._table.item(row, COL_GRADE)
                thk = self._table.item(row, COL_THK)
                grade_ok = grade and grade.text().strip()
                thk_ok = thk and thk.text().strip()
                if not grade_ok or not thk_ok:
                    parts: list[str] = []
                    if not grade_ok:
                        parts.append("Grade")
                    if not thk_ok:
                        parts.append("Thickness")
                    missing.append(f"  {name_text}: {', '.join(parts)}")
            if missing:
                QMessageBox.warning(
                    self,
                    "Missing Details",
                    "Fill in Grade and Thickness before converting:\n\n"
                    + "\n".join(missing)
                    + "\n\nEdit the cells directly or use Defaults + Apply to All.",
                )
                return

        out_dir = Path(self._output_dir.text()) if self._output_dir.text() else None
        failures: list[str] = []

        for row, (src, part) in enumerate(self._items):
            dest_dir = out_dir or src.parent
            try:
                # Sync user-edited values from table cells
                self._apply_table_values_to_part(row, part)
                dest = dest_dir / f"{part.name}{target_ext}"
                if to_nc1:
                    text = write_nc1(part, precision=self._ribbon.precision())
                    dest.write_text(
                        text,
                        encoding=self._ribbon.encoding(),
                        newline="\r\n",
                    )
                else:
                    write_dxf(
                        part,
                        dest,
                        dxf_version=self._ribbon.dxf_version(),
                        cut_layer=self._ribbon.cut_layer(),
                        cutout_layer=self._ribbon.cutout_layer(),
                        text_layer=self._ribbon.text_layer(),
                    )

                self._set_status(row, "Done")
                self._log_msg(f"OK: {src.name} -> {dest.name}")
            except Exception:
                self._set_status(row, "Error")
                tb = traceback.format_exc()
                failures.append(f"{src.name}: {tb.splitlines()[-1]}")
                self._log_msg(f"FAIL: {src.name}\n{tb}")

        if failures:
            QMessageBox.warning(
                self, "Conversion Errors", "\n".join(failures)
            )
        else:
            self._log_msg(f"All {len(self._items)} file(s) converted successfully.")

    def _apply_table_values_to_part(self, row: int, part: Part) -> None:
        """Read all editable table cells back into Part."""
        name_item = self._table.item(row, COL_NAME)
        if name_item and name_item.text().strip():
            part.name = name_item.text().strip()

        l_item = self._table.item(row, COL_L)
        if l_item:
            try:
                part.length = float(l_item.text().strip())
            except ValueError:
                pass

        w_item = self._table.item(row, COL_W)
        if w_item:
            try:
                part.width = float(w_item.text().strip())
            except ValueError:
                pass

        grade_item = self._table.item(row, COL_GRADE)
        if grade_item:
            part.grade = grade_item.text().strip()

        thk_item = self._table.item(row, COL_THK)
        if thk_item:
            text = thk_item.text().strip()
            try:
                part.thickness = float(text) if text else 0.0
            except ValueError:
                pass

        qty_item = self._table.item(row, COL_QTY)
        if qty_item:
            text = qty_item.text().strip()
            try:
                part.qty = int(text) if text else 1
            except ValueError:
                pass

    # ---- table ----

    def _refresh_table(self) -> None:
        default_grade = self._default_grade.text().strip()
        default_thk = self._default_thk.text().strip()

        self._table.setRowCount(len(self._items))
        for i, (fp, part) in enumerate(self._items):
            self._table.setItem(i, COL_NUM, QTableWidgetItem(str(i + 1)))
            self._table.setItem(i, COL_FILE, QTableWidgetItem(fp.name))
            self._table.setItem(i, COL_NAME, QTableWidgetItem(part.name))
            self._table.setItem(i, COL_L, QTableWidgetItem(f"{part.length:.0f}"))
            self._table.setItem(i, COL_W, QTableWidgetItem(f"{part.width:.0f}"))
            self._table.setItem(i, COL_QTY, QTableWidgetItem(str(part.qty)))

            # Grade: use part value if set, else fall back to default
            grade_text = part.grade if part.grade else default_grade
            self._table.setItem(i, COL_GRADE, QTableWidgetItem(grade_text))

            # Thickness: use part value if > 0, else fall back to default
            if part.thickness:
                thk_text = f"{part.thickness:g}"
            else:
                thk_text = default_thk
            self._table.setItem(i, COL_THK, QTableWidgetItem(thk_text))

            self._table.setItem(i, COL_STATUS, QTableWidgetItem(""))

            # Set cell editability
            for col in range(9):
                item = self._table.item(i, col)
                if item is None:
                    continue
                if col in _EDITABLE_COLS:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self._table.resizeColumnsToContents()

    def _set_status(self, row: int, text: str) -> None:
        item = self._table.item(row, COL_STATUS)
        if item:
            item.setText(text)

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            ext = self._source_ext()
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(ext):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        ext = self._source_ext()
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.toLocalFile().lower().endswith(ext)
        ]
        if paths:
            self._load_files(paths)
