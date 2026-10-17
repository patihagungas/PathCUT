"""Convert tab — bidirectional DXF/NC1 conversion."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QDragEnterEvent, QDropEvent

from plate_nesting.dxf.reader import read_dxf
from plate_nesting.dxf.writer import write_dxf
from plate_nesting.models.part import Part
from plate_nesting.nc1.parser import parse_nc1
from plate_nesting.nc1.writer import write_nc1

# Column indices
COL_NUM, COL_FILE, COL_NAME, COL_SIZE, COL_QTY, COL_GRADE, COL_THK, COL_STATUS = range(8)

# Columns editable in DXF → NC1 mode
_EDITABLE_COLS = {COL_QTY, COL_GRADE, COL_THK}


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
        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["#", "Input File", "Name", "L \u00d7 W", "Qty", "Grade", "Thk", "Status"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
                    part = read_dxf(fp)
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
            dest = dest_dir / f"{part.name}{target_ext}"
            try:
                if to_nc1:
                    # Read user-edited values from table cells
                    self._apply_table_values_to_part(row, part)
                    text = write_nc1(part)
                    dest.write_text(text, encoding="utf-8", newline="\r\n")
                else:
                    write_dxf(part, dest)

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
        """Read Grade, Thk, Qty from editable table cells and update Part."""
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
        editable = self._is_dxf_to_nc1()
        default_grade = self._default_grade.text().strip()
        default_thk = self._default_thk.text().strip()

        self._table.setRowCount(len(self._items))
        for i, (fp, part) in enumerate(self._items):
            self._table.setItem(i, COL_NUM, QTableWidgetItem(str(i + 1)))
            self._table.setItem(i, COL_FILE, QTableWidgetItem(fp.name))
            self._table.setItem(i, COL_NAME, QTableWidgetItem(part.name))
            self._table.setItem(
                i, COL_SIZE,
                QTableWidgetItem(f"{part.length:.0f} \u00d7 {part.width:.0f}"),
            )
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
            for col in range(8):
                item = self._table.item(i, col)
                if item is None:
                    continue
                if editable and col in _EDITABLE_COLS:
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
