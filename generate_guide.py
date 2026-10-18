"""Generate the PathCUT User Guide PDF."""

from fpdf import FPDF


class Guide(FPDF):
    DARK = (45, 45, 45)
    ACCENT = (42, 130, 218)
    TEXT = (50, 50, 50)
    LIGHT_BG = (245, 245, 245)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, "PathCUT User Guide", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R")
        self.ln(12)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(180, 180, 180)
        self.cell(0, 10, "PathCUT v0.1.0", align="C")

    def cover_page(self):
        self.add_page()
        self.ln(60)
        self.set_font("Helvetica", "B", 42)
        self.set_text_color(*self.DARK)
        self.cell(0, 20, "PathCUT", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 16)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "User Guide", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_draw_color(*self.ACCENT)
        self.set_line_width(0.8)
        cx = self.w / 2
        self.line(cx - 40, self.get_y(), cx + 40, self.get_y())
        self.ln(12)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "DXF / NC1 File Converter", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, "for Steel Plate Processing", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(30)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, "Version 0.1.0", align="C", new_x="LMARGIN", new_y="NEXT")

    def section(self, number, title):
        self.ln(6)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*self.ACCENT)
        self.cell(0, 12, f"{number}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.ACCENT)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)

    def subsection(self, title):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*self.DARK)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEXT)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.TEXT)
        indent = self.l_margin + 6
        self.set_x(self.l_margin)
        self.cell(6, 5.5, "-")
        self.multi_cell(self.w - indent - self.r_margin, 5.5, text)


    def note_box(self, text):
        self.ln(2)
        self.set_fill_color(*self.LIGHT_BG)
        self.set_draw_color(200, 200, 200)
        x = self.l_margin + 4
        y = self.get_y()
        w = self.w - self.l_margin - self.r_margin - 8
        self.set_xy(x, y)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.ACCENT)
        self.cell(w, 6, "  NOTE", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.set_xy(x, self.get_y())
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.TEXT)
        self.multi_cell(w, 5, "  " + text, fill=True)
        self.ln(4)

    def table_row(self, cells, bold=False):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, 9)
        if bold:
            self.set_fill_color(*self.ACCENT)
            self.set_text_color(255, 255, 255)
        else:
            self.set_fill_color(250, 250, 250)
            self.set_text_color(*self.TEXT)
        col_widths = [35, 140]
        h = 7
        for i, cell in enumerate(cells):
            w = col_widths[i] if i < len(col_widths) else 60
            self.cell(w, h, cell, border=1, fill=True)
        self.ln()


def build():
    pdf = Guide()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ---- Cover ----
    pdf.cover_page()

    # ---- Table of Contents ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*Guide.DARK)
    pdf.cell(0, 14, "Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    toc = [
        ("1", "Installation"),
        ("2", "Getting Started"),
        ("3", "The Main Window"),
        ("4", "Converting DXF to NC1"),
        ("5", "Converting NC1 to DXF"),
        ("6", "Settings Reference"),
        ("7", "Drag and Drop"),
        ("8", "Editing Part Data"),
        ("9", "Output Options"),
        ("10", "Troubleshooting"),
    ]
    for num, title in toc:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*Guide.TEXT)
        pdf.cell(0, 7, f"  {num}.   {title}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ---- 1. Installation ----
    pdf.add_page()
    pdf.section("1", "Installation")

    pdf.subsection("Using the Installer (Recommended)")
    pdf.body(
        "PathCUT is distributed as a Windows installer. No Python installation is required."
    )
    pdf.bullet("Double-click PathCUT-Setup.exe to launch the installer.")
    pdf.bullet("Follow the on-screen wizard. The default install location is "
               "C:\\Program Files\\PathCUT.")
    pdf.bullet("Optionally create a Desktop shortcut when prompted.")
    pdf.bullet('Click "Install" to complete the setup.')
    pdf.ln(2)

    pdf.subsection("Launching PathCUT")
    pdf.body(
        "After installation, launch PathCUT from the Start Menu (Start > PathCUT > PathCUT) "
        "or from the Desktop shortcut if you created one. The application opens with a dark-themed "
        "window ready to accept files."
    )

    pdf.subsection("Uninstalling")
    pdf.body(
        'To uninstall, use "Add or Remove Programs" in Windows Settings, or run the '
        "uninstaller from the Start Menu group (Start > PathCUT > Uninstall PathCUT)."
    )

    # ---- 2. Getting Started ----
    pdf.section("2", "Getting Started")
    pdf.body(
        "PathCUT converts between two common steel fabrication file formats:"
    )
    pdf.ln(1)
    pdf.bullet(
        "DXF (Drawing Exchange Format) - 2D CAD drawings with layer-based geometry. "
        "Used by most CAD software including AutoCAD and similar programs."
    )
    pdf.bullet(
        "NC1 (also known as DSTV) - a CNC machine-readable format used by plate processing "
        "equipment for cutting steel plates. Contains outer contours, inner cutouts, holes, "
        "and part metadata (grade, thickness, quantity)."
    )
    pdf.ln(2)
    pdf.body(
        "The typical workflow is:"
    )
    pdf.bullet("1.  Open PathCUT.")
    pdf.bullet("2.  Select the conversion direction (DXF to NC1, or NC1 to DXF).")
    pdf.bullet("3.  Add one or more source files.")
    pdf.bullet("4.  Review and edit part details in the table if needed.")
    pdf.bullet("5.  Set the output directory (optional).")
    pdf.bullet('6.  Click "Convert".')
    pdf.ln(2)
    pdf.note_box(
        "You can also drag and drop files directly onto the PathCUT window instead "
        "of using the Add Files button."
    )

    # ---- 3. Main Window ----
    pdf.add_page()
    pdf.section("3", "The Main Window")
    pdf.body(
        "The PathCUT window is organized into the following areas from top to bottom:"
    )
    pdf.ln(2)

    pdf.subsection("Settings Ribbon")
    pdf.body(
        "The ribbon bar at the top contains three groups of settings:"
    )
    pdf.bullet(
        "DXF Layers - defines which DXF layer names correspond to cut lines, cutouts, "
        "text, and scribe marks."
    )
    pdf.bullet(
        "Defaults - order number, phase, and maximum hole diameter for DXF reading."
    )
    pdf.bullet(
        "Output - DXF version, file encoding, and numeric precision."
    )

    pdf.subsection("Toolbar Row")
    pdf.body(
        "Below the ribbon is a toolbar with:"
    )
    pdf.bullet('Direction selector - choose "DXF -> NC1" or "NC1 -> DXF".')
    pdf.bullet('"Add Files" button - opens a file browser to select source files.')
    pdf.bullet('"Clear" button - removes all loaded files from the list.')
    pdf.bullet('"Convert" button - starts the conversion (enabled once files are loaded).')

    pdf.subsection("Output Directory")
    pdf.body(
        "A text field showing where converted files will be saved. By default, output files "
        "are saved alongside the source files. Click Browse to choose a different folder."
    )

    pdf.subsection("Defaults Row (DXF to NC1 only)")
    pdf.body(
        'When converting DXF to NC1, a "Defaults" row appears with Grade and Thickness '
        'fields plus an "Apply to All" button. This lets you set Grade and Thickness for '
        "all parts at once."
    )

    pdf.subsection("Parts Table")
    pdf.body(
        "The central table lists all loaded parts with the following columns:"
    )
    rows = [
        ("Column", "Description"),
        ("#", "Row number (read-only)"),
        ("Input File", "Source filename (read-only)"),
        ("Name", "Part name / mark (editable)"),
        ("L", "Length in mm (editable)"),
        ("W", "Width in mm (editable)"),
        ("Qty", "Quantity (editable)"),
        ("Grade", "Steel grade, e.g. 350W (editable)"),
        ("Thk", "Thickness in mm (editable)"),
        ("Status", "Conversion status: Done or Error (read-only)"),
    ]
    for i, (a, b) in enumerate(rows):
        pdf.table_row([a, b], bold=(i == 0))

    pdf.ln(4)
    pdf.subsection("Log Panel")
    pdf.body(
        "At the bottom, a read-only log panel shows conversion progress, success messages, "
        "and any error details."
    )

    # ---- 4. DXF to NC1 ----
    pdf.add_page()
    pdf.section("4", "Converting DXF to NC1")
    pdf.body(
        "This is the most common workflow: taking 2D CAD drawings and producing "
        "NC1 files for CNC plate-cutting machines."
    )
    pdf.ln(2)

    pdf.subsection("Step 1: Select Direction")
    pdf.body(
        'Ensure the Direction dropdown is set to "DXF -> NC1". '
        "This is the default when PathCUT starts."
    )

    pdf.subsection("Step 2: Configure DXF Layer Names")
    pdf.body(
        "In the DXF Layers group of the settings ribbon, verify that the layer names match "
        "your DXF files:"
    )
    pdf.bullet("Cut - the layer containing the outer profile (default: CUT).")
    pdf.bullet("Cutout - the layer containing inner cutouts (default: CUTOUT).")
    pdf.bullet("Text - the layer for info text with qty, thickness, grade (default: TEXT).")
    pdf.bullet("Scribe - the layer for scribe/mark text (default: SCRIBE).")
    pdf.ln(1)
    pdf.note_box(
        "If your DXF files do not use dedicated layers, PathCUT will attempt to identify "
        "the outer contour automatically by selecting the largest closed loop."
    )

    pdf.subsection("Step 3: Add DXF Files")
    pdf.body(
        'Click "Add Files" and select one or more .dxf files. They will appear in the '
        "parts table with auto-detected Name, Length, Width, and any embedded metadata."
    )

    pdf.subsection("Step 4: Fill in Grade and Thickness")
    pdf.body(
        "NC1 files require steel grade and plate thickness. If these values were not "
        "embedded in the DXF, the table cells will be empty and you must fill them in."
    )
    pdf.bullet(
        'Quick method: type the Grade and Thickness in the Defaults row and click '
        '"Apply to All" to populate every row at once.'
    )
    pdf.bullet(
        "Individual edit: double-click any Grade or Thk cell to edit it directly."
    )
    pdf.ln(1)
    pdf.note_box(
        "The Convert button will warn you if any rows are missing Grade or Thickness. "
        "Conversion will not proceed until all rows are filled in."
    )

    pdf.subsection("Step 5: Set Output Directory (Optional)")
    pdf.body(
        "By default, NC1 files are saved in the same folder as the source DXF files. "
        "To save them elsewhere, type a path in the Output field or click Browse."
    )

    pdf.subsection("Step 6: Convert")
    pdf.body(
        'Click "Convert". Each file is processed and the Status column updates to '
        '"Done" or "Error". Check the Log panel at the bottom for details.'
    )

    # ---- 5. NC1 to DXF ----
    pdf.add_page()
    pdf.section("5", "Converting NC1 to DXF")
    pdf.body(
        "This workflow converts NC1 (DSTV) files into DXF drawings that can be opened "
        "in any CAD application."
    )
    pdf.ln(2)

    pdf.subsection("Step 1: Select Direction")
    pdf.body(
        'Change the Direction dropdown to "NC1 -> DXF". If files are already loaded, '
        "PathCUT will ask if you want to clear them before switching."
    )

    pdf.subsection("Step 2: Add NC1 Files")
    pdf.body(
        'Click "Add Files" and select one or more .nc1 files. Part data (name, dimensions, '
        "grade, thickness, quantity) is parsed from the NC1 header and displayed in the table."
    )

    pdf.subsection("Step 3: Configure Output Settings")
    pdf.body(
        "In the Output group of the settings ribbon, choose:"
    )
    pdf.bullet("DXF Ver - the DXF version to write (R2010, R2013, or R2018).")
    pdf.bullet("Encoding - character encoding for the DXF file (UTF-8 or Latin-1).")
    pdf.bullet("Precision - number of decimal places for coordinates.")
    pdf.ln(1)
    pdf.body(
        "Also verify the DXF layer names in the DXF Layers group. These control which "
        "layers the outer profile, cutouts, and text are written to in the output DXF."
    )

    pdf.subsection("Step 4: Convert")
    pdf.body(
        'Click "Convert". DXF files are created in the output directory with the part name '
        "as the filename. The outer contour is placed on the Cut layer, inner cutouts on the "
        "Cutout layer, and the part mark on the Text layer."
    )

    # ---- 6. Settings Reference ----
    pdf.add_page()
    pdf.section("6", "Settings Reference")

    pdf.subsection("DXF Layers")
    rows = [
        ("Setting", "Description"),
        ("Cut", "Layer for the outer profile contour (default: CUT)"),
        ("Cutout", "Layer for inner cutouts / notches (default: CUTOUT)"),
        ("Text", "Layer for info text: qty + thickness + grade (default: TEXT)"),
        ("Scribe", "Layer for scribe marks / part marks (default: SCRIBE)"),
    ]
    for i, (a, b) in enumerate(rows):
        pdf.table_row([a, b], bold=(i == 0))
    pdf.ln(4)

    pdf.subsection("Defaults")
    rows = [
        ("Setting", "Description"),
        ("Order", "Order/job number written into NC1 header (default: W8753)"),
        ("Phase", "Phase/assembly mark for NC1 output (default: 63)"),
        ("Max hole", "Circles smaller than this are treated as holes (default: 40 mm)"),
    ]
    for i, (a, b) in enumerate(rows):
        pdf.table_row([a, b], bold=(i == 0))
    pdf.ln(4)

    pdf.subsection("Output")
    rows = [
        ("Setting", "Description"),
        ("DXF Ver", "AutoCAD DXF version: R2010, R2013, or R2018"),
        ("Encoding", "File encoding: UTF-8 (recommended) or Latin-1"),
        ("Precision", "Decimal places for NC1 coordinates (1 to 6, default: 2)"),
    ]
    for i, (a, b) in enumerate(rows):
        pdf.table_row([a, b], bold=(i == 0))
    pdf.ln(4)

    # ---- 7. Drag and Drop ----
    pdf.section("7", "Drag and Drop")
    pdf.body(
        "PathCUT supports drag and drop for loading files quickly:"
    )
    pdf.ln(1)
    pdf.bullet(
        "Drag one or more DXF or NC1 files from Windows Explorer directly onto the "
        "PathCUT window."
    )
    pdf.bullet(
        "Only files matching the current direction are accepted. In DXF -> NC1 mode, "
        "only .dxf files are accepted. In NC1 -> DXF mode, only .nc1 files are accepted."
    )
    pdf.bullet(
        "Dropped files are added to the existing list (they do not replace it). Use "
        '"Clear" to start fresh.'
    )

    # ---- 8. Editing ----
    pdf.section("8", "Editing Part Data")
    pdf.body(
        "Most columns in the parts table are editable. Double-click a cell to edit its value."
    )
    pdf.ln(1)
    pdf.bullet("Name - the part mark or identifier. Used as the output filename.")
    pdf.bullet("L (Length) and W (Width) - dimensions in millimeters.")
    pdf.bullet("Qty - number of pieces.")
    pdf.bullet("Grade - steel grade (e.g. 350W, S355, A36).")
    pdf.bullet("Thk - plate thickness in millimeters.")
    pdf.ln(2)
    pdf.body(
        "The # (row number), Input File, and Status columns are read-only."
    )
    pdf.ln(1)
    pdf.note_box(
        "Edited values are written into the converted output. For example, if you change "
        "the Name from PART1 to BEAM-A1, the output file will be named BEAM-A1.nc1."
    )

    # ---- 9. Output ----
    pdf.add_page()
    pdf.section("9", "Output Options")

    pdf.subsection("Output Directory")
    pdf.body(
        "By default, converted files are saved in the same directory as the source file. "
        "To change this:"
    )
    pdf.bullet("Type a path directly in the Output field.")
    pdf.bullet("Or click Browse to pick a folder.")
    pdf.ln(1)
    pdf.body(
        "The output directory is set automatically to the first loaded file's directory, "
        "but you can change it at any time before converting."
    )

    pdf.subsection("DXF Output Details (NC1 to DXF)")
    pdf.body(
        "When writing DXF files, PathCUT uses the ezdxf library. The output contains:"
    )
    pdf.bullet("Outer contour on the Cut layer (lines and arcs).")
    pdf.bullet("Inner cutouts on the Cutout layer.")
    pdf.bullet("Holes as circles on the default layer.")
    pdf.bullet("Part info text on the Text layer (qty, thickness, grade).")

    pdf.subsection("NC1 Output Details (DXF to NC1)")
    pdf.body(
        "NC1 output follows the DSTV standard format with:"
    )
    pdf.bullet("25-line ST header block with part metadata.")
    pdf.bullet("AK block for the outer contour.")
    pdf.bullet("IK blocks for each inner cutout.")
    pdf.bullet("BO block for round holes.")
    pdf.bullet("EN end marker.")

    # ---- 10. Troubleshooting ----
    pdf.section("10", "Troubleshooting")

    pdf.subsection('"No closed outer contour found" Error')
    pdf.body(
        "This means PathCUT could not find a closed shape on the Cut layer. Check that:"
    )
    pdf.bullet("Your DXF file uses the correct layer name for the outer profile.")
    pdf.bullet(
        "The outer contour is a fully closed shape (all endpoints connect within 0.05 mm)."
    )
    pdf.bullet(
        'If your DXF does not use named layers, PathCUT will try to auto-detect '
        'the outer contour from all entities. Large circles above the "Max hole" '
        "diameter will also be treated as outer contours."
    )

    pdf.subsection('"Missing Details" Warning')
    pdf.body(
        "When converting DXF to NC1, every part needs a Grade and Thickness value. "
        "Use the Defaults row to fill these in quickly with Apply to All, "
        "or double-click individual cells to set them per-part."
    )

    pdf.subsection("App Does Not Launch")
    pdf.body(
        "If PathCUT does not start after installation:"
    )
    pdf.bullet("Try running PathCUT.exe directly from the install folder.")
    pdf.bullet(
        "Check if Windows SmartScreen blocked it. Click More Info > Run Anyway."
    )
    pdf.bullet(
        "Make sure you are on a 64-bit version of Windows 10 or later."
    )

    pdf.subsection("Incorrect Geometry in Output")
    pdf.body(
        "If arcs or contours look wrong in the converted file:"
    )
    pdf.bullet("Verify the source file is valid by opening it in a CAD viewer.")
    pdf.bullet(
        "Check that the correct DXF layers are configured in the settings ribbon."
    )
    pdf.bullet(
        "For DXF files without layers, try adjusting the Max Hole setting to control "
        "which circles are treated as holes versus contours."
    )

    # ---- Save ----
    pdf.output("PathCUT_User_Guide.pdf")
    print("Created: PathCUT_User_Guide.pdf")


if __name__ == "__main__":
    build()
