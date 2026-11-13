"""Create real files (DOCX, PDF, PPTX, XLSX, CSV, HTML, MD, TXT, code, ZIP projects) from the
structured blocks the assistant writes in its answer.

Protocol (explained to the model in the system prompt):

```doubaj-file name="rapport.docx"
# Markdown content ...
```
- docx / pdf / html / md / txt  → Markdown content
- pptx / xlsx                   → JSON content (schemas below)
- csv / code / anything else    → raw file content
- names with folders ("gestion_notes/main.py") are additionally zipped per top folder.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..core.markdown_render import is_rtl, md_to_html, wrap_document

FILE_BLOCK = re.compile(r"^(`{3,}|~{3,})doubaj-file\s+name=\"([^\"]+)\"[^\n]*\n(.*?)\n\1[ \t]*$", re.S | re.M)

PPTX_SCHEMA = """{"title": "...", "subtitle": "...", "theme": "blue|green|orange|purple|dark",
 "slides": [
   {"title": "...", "bullets": ["...", "..."], "notes": "speaker notes"},
   {"title": "...", "table": [["Header1","Header2"],["a","b"]]},
   {"title": "...", "chart": {"type": "bar|line|pie", "categories": ["A","B"],
                               "series": [{"name": "S1", "values": [1, 2]}]}},
   {"title": "...", "left": ["..."], "right": ["..."]},
   {"title": "...", "diagram": ["Step 1", "Step 2", "Step 3"]}
 ]}"""

XLSX_SCHEMA = """{"sheets": [{"name": "Notes", "columns": ["Nom", "Note 1", "Moyenne"],
  "rows": [["Ali", 14, "=AVERAGE(B2:B2)"]], "col_widths": [20, 10, 12],
  "chart": {"type": "bar|line|pie", "title": "...", "data_cols": [2], "category_col": 1}}]}"""


@dataclass
class GeneratedFile:
    name: str
    path: Path
    kind: str
    error: str = ""


def _safe_name(name: str) -> str:
    parts = [re.sub(r'[<>:"|?*\\]', "_", p).strip(". ") for p in name.replace("\\", "/").split("/")]
    parts = [p for p in parts if p and p != ".."]
    return "/".join(parts) or "fichier.txt"


# ---------------------------------------------------------------- DOCX
def _add_runs(par, text: str) -> None:
    """Inline **bold**, *italic* and `code`."""
    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            par.add_run(tok[2:-2]).bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = par.add_run(tok[1:-1])
            r.font.name = "Consolas"
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            par.add_run(tok[1:-1]).italic = True
        else:
            par.add_run(tok)


def _set_rtl(par) -> None:
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    ppr = par._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    ppr.append(bidi)
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for r in par.runs:
        rpr = r._r.get_or_add_rPr()
        rtl = OxmlElement("w:rtl")
        rtl.set(qn("w:val"), "1")
        rpr.append(rtl)


def markdown_to_docx(md: str, out: Path, title: str = "") -> None:
    import docx
    from docx.shared import Pt, RGBColor

    doc = docx.Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    rtl_doc = is_rtl(md)

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            p = doc.add_paragraph()
            r = p.add_run("\n".join(code))
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0x1F, 0x2D, 0x3D)
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\s*\|?\s*:?-{2,}", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            ncols = max(len(r) for r in rows)
            table = doc.add_table(rows=len(rows), cols=ncols)
            table.style = "Light Grid Accent 1"
            for ri, row in enumerate(rows):
                for ci in range(ncols):
                    cell = table.cell(ri, ci)
                    cell.text = ""
                    _add_runs(cell.paragraphs[0], row[ci] if ci < len(row) else "")
                    if ri == 0:
                        for r in cell.paragraphs[0].runs:
                            r.bold = True
                    if rtl_doc:
                        _set_rtl(cell.paragraphs[0])
            doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            level = min(len(m.group(1)), 4)
            p = doc.add_heading(level=0 if (level == 1 and not doc.paragraphs) else level)
            _add_runs(p, m.group(2))
        elif re.match(r"^[-*+]\s+", stripped):
            p = doc.add_paragraph(style="List Bullet")
            _add_runs(p, re.sub(r"^[-*+]\s+", "", stripped))
        elif re.match(r"^\d+[.)]\s+", stripped):
            p = doc.add_paragraph(style="List Number")
            _add_runs(p, re.sub(r"^\d+[.)]\s+", "", stripped))
        elif stripped in ("---", "***", "<pagebreak>"):
            doc.add_page_break()
            p = None
        elif stripped.startswith(">"):
            p = doc.add_paragraph(style="Intense Quote")
            _add_runs(p, stripped.lstrip("> "))
        elif stripped:
            p = doc.add_paragraph()
            _add_runs(p, stripped)
        else:
            p = None
        if p is not None and (rtl_doc or is_rtl(stripped)):
            _set_rtl(p)
        i += 1
    if title:
        doc.core_properties.title = title
    doc.core_properties.author = "DOUBAJ AI"
    doc.save(str(out))


# ---------------------------------------------------------------- PDF (Qt: native Arabic shaping)
def markdown_to_pdf(md: str, out: Path, title: str = "") -> None:
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument, QTextOption

    body = md_to_html(md)
    if is_rtl(md):
        body = body.replace("<table>", '<table align="right" dir="rtl">')
    html_doc = wrap_document(body, title, rtl=is_rtl(md))
    writer = QPdfWriter(str(out))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)
    writer.setResolution(150)
    writer.setTitle(title or out.stem)
    writer.setCreator("DOUBAJ AI")
    doc = QTextDocument()
    doc.documentLayout().setPaintDevice(writer)  # use the PDF resolution for font metrics
    from PySide6.QtGui import QFont
    doc.setDefaultFont(QFont("Segoe UI", 11))
    if is_rtl(md):
        opt = QTextOption()
        opt.setTextDirection(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.RightToLeft)
        doc.setDefaultTextOption(opt)
    doc.setHtml(html_doc)
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
    doc.print_(writer)


# ---------------------------------------------------------------- PPTX
THEMES = {
    "blue": ((0x0F, 0x3D, 0x5C), (0x1E, 0x88, 0xE5)),
    "green": ((0x1B, 0x4D, 0x3E), (0x2E, 0xA0, 0x6B)),
    "orange": ((0x5C, 0x2E, 0x0F), (0xF0, 0x8A, 0x24)),
    "purple": ((0x3A, 0x1C, 0x5C), (0x8E, 0x5C, 0xE0)),
    "dark": ((0x15, 0x1A, 0x24), (0x22, 0xC5, 0xB8)),
}


def json_to_pptx(spec: dict, out: Path) -> None:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Emu, Inches, Pt

    dark, accent = THEMES.get(spec.get("theme", "blue"), THEMES["blue"])
    DARK, ACCENT = RGBColor(*dark), RGBColor(*accent)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    all_text = json.dumps(spec, ensure_ascii=False)
    rtl = is_rtl(all_text)
    align = PP_ALIGN.RIGHT if rtl else PP_ALIGN.LEFT

    def _align_for(text):
        if rtl or is_rtl(str(text)):
            return PP_ALIGN.RIGHT
        return PP_ALIGN.LEFT

    def textbox(slide, x, y, w, h, text, size=20, bold=False, color=DARK, al=None):
        tb = slide.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.alignment = al if al is not None else _align_for(text)
        if is_rtl(text):
            p._pPr.set("rtl", "1") if p._pPr is not None else p._p.get_or_add_pPr().set("rtl", "1")
        for r in p.runs:
            r.font.size, r.font.bold, r.font.color.rgb = Pt(size), bold, color
        return tb

    def header(slide, title, num):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.15))
        bar.fill.solid()
        bar.fill.fore_color.rgb = DARK
        bar.line.fill.background()
        textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.9), title, 30, True, WHITE)
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.15), prs.slide_width, Inches(0.07))
        strip.fill.solid()
        strip.fill.fore_color.rgb = ACCENT
        strip.line.fill.background()
        textbox(slide, Inches(12.2), Inches(7.0), Inches(1), Inches(0.4), str(num), 11, False, DARK, PP_ALIGN.RIGHT)

    def bullets(slide, items, x, y, w, h, size=20):
        tb = slide.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        for k, item in enumerate(items):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            level = 1 if str(item).startswith(("  ", "\t", "- ")) else 0
            p.text = ("• " if level == 0 else "– ") + str(item).strip().lstrip("- ")
            p.level = level
            p.alignment = _align_for(str(item))
            if is_rtl(str(item)):
                p._p.get_or_add_pPr().set("rtl", "1")
            p.space_after = Pt(10)
            for r in p.runs:
                r.font.size = Pt(size - 4 * level)
                r.font.color.rgb = DARK

    # Title slide
    s = prs.slides.add_slide(blank)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = DARK
    bg.line.fill.background()
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.25), Inches(3), Inches(0.08))
    band.fill.solid()
    band.fill.fore_color.rgb = ACCENT
    band.line.fill.background()
    textbox(s, Inches(0.8), Inches(2.2), Inches(11.7), Inches(2), spec.get("title", out.stem), 44, True, WHITE)
    if spec.get("subtitle"):
        textbox(s, Inches(0.8), Inches(4.5), Inches(11.7), Inches(1.2), spec["subtitle"], 22, False, WHITE)

    chart_types = {"bar": XL_CHART_TYPE.COLUMN_CLUSTERED, "line": XL_CHART_TYPE.LINE_MARKERS,
                   "pie": XL_CHART_TYPE.PIE}
    for n, sd in enumerate(spec.get("slides", []), 2):
        s = prs.slides.add_slide(blank)
        header(s, sd.get("title", ""), n)
        top, left, width, height = Inches(1.5), Inches(0.6), Inches(12.1), Inches(5.5)
        if sd.get("table"):
            rows = sd["table"]
            ncols = max(len(r) for r in rows)
            shape = s.shapes.add_table(len(rows), ncols, left, top, width, Inches(0.5) * len(rows))
            for ri, row in enumerate(rows):
                for ci in range(ncols):
                    cell = shape.table.cell(ri, ci)
                    cell.text = str(row[ci]) if ci < len(row) else ""
                    for p in cell.text_frame.paragraphs:
                        p.alignment = align
                        for r in p.runs:
                            r.font.size = Pt(16)
            if sd.get("bullets"):
                bullets(s, sd["bullets"], left, top + Inches(0.5) * len(rows) + Inches(0.3), width, Inches(2), 16)
        elif sd.get("chart"):
            ch = sd["chart"]
            data = CategoryChartData()
            data.categories = ch.get("categories", [])
            for ser in ch.get("series", []):
                data.add_series(ser.get("name", ""), [float(v) for v in ser.get("values", [])])
            cw = width if not sd.get("bullets") else Inches(7.5)
            gf = s.shapes.add_chart(chart_types.get(ch.get("type", "bar"), XL_CHART_TYPE.COLUMN_CLUSTERED),
                                    left, top, cw, height, data)
            gf.chart.has_legend = True
            gf.chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            gf.chart.legend.include_in_layout = False
            if sd.get("bullets"):
                bullets(s, sd["bullets"], left + Inches(7.8), top, Inches(4.3), height, 18)
        elif sd.get("left") or sd.get("right"):
            bullets(s, sd.get("left", []), left, top, Inches(5.9), height)
            bullets(s, sd.get("right", []), left + Inches(6.2), top, Inches(5.9), height)
        elif sd.get("diagram"):
            steps = sd["diagram"][:6]
            k = len(steps)
            gap = Inches(0.35)
            bw = Emu(int((width - gap * (k - 1)) / max(k, 1)))
            order = list(range(k))[::-1] if rtl else list(range(k))
            for pos, idx in enumerate(order):
                x = left + (bw + gap) * pos
                box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(3), bw, Inches(1.6))
                box.fill.solid()
                box.fill.fore_color.rgb = ACCENT if idx % 2 == 0 else DARK
                box.line.fill.background()
                tf = box.text_frame
                tf.word_wrap = True
                tf.paragraphs[0].text = str(steps[idx])
                tf.paragraphs[0].alignment = PP_ALIGN.CENTER
                for r in tf.paragraphs[0].runs:
                    r.font.size, r.font.color.rgb, r.font.bold = Pt(16), WHITE, True
                if pos < k - 1:
                    arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + bw + Emu(int(gap * 0.1)), Inches(3.6),
                                             Emu(int(gap * 0.8)), Inches(0.4))
                    arr.fill.solid()
                    arr.fill.fore_color.rgb = DARK
                    arr.line.fill.background()
            if sd.get("bullets"):
                bullets(s, sd["bullets"], left, Inches(5.0), width, Inches(2), 16)
        else:
            bullets(s, sd.get("bullets", []), left, top, width, height)
        if sd.get("notes"):
            s.notes_slide.notes_text_frame.text = sd["notes"]
    prs.save(str(out))


# ---------------------------------------------------------------- XLSX
def json_to_xlsx(spec: dict, out: Path) -> None:
    import openpyxl
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    thin = Side(style="thin", color="C8D1DC")
    for sh in spec.get("sheets", []):
        ws = wb.create_sheet(str(sh.get("name", "Feuille"))[:31])
        cols = sh.get("columns", [])
        rows = sh.get("rows", [])
        if cols:
            ws.append(cols)
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="0F3D5C")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=max(len(cols), 1)):
            for c in row:
                c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        widths = sh.get("col_widths") or [max(12, min(45, max((len(str(v)) for v in
                                           [cols[i] if i < len(cols) else ""] + [r[i] if i < len(r) else "" for r in rows]), default=10) + 2))
                                          for i in range(len(cols))]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        if is_rtl(json.dumps(sh, ensure_ascii=False)):
            ws.sheet_view.rightToLeft = True
        ch = sh.get("chart")
        if ch and rows:
            kind = {"bar": BarChart, "line": LineChart, "pie": PieChart}.get(ch.get("type", "bar"), BarChart)
            chart = kind()
            chart.title = ch.get("title", "")
            cat_col = int(ch.get("category_col", 1))
            for dc in ch.get("data_cols", [2]):
                data = Reference(ws, min_col=int(dc), min_row=1, max_row=len(rows) + 1)
                chart.add_data(data, titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=cat_col, min_row=2, max_row=len(rows) + 1))
            ws.add_chart(chart, f"{get_column_letter(len(cols) + 2)}2")
    if not wb.worksheets:
        wb.create_sheet("Feuille1")
    wb.save(str(out))


# ---------------------------------------------------------------- dispatcher
def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("{"):]
    try:
        return json.loads(content)
    except ValueError:
        # tolerate trailing commas from small local models
        return json.loads(re.sub(r",\s*([}\]])", r"\1", content))


def write_file(name: str, content: str, out_dir: Path) -> GeneratedFile:
    name = _safe_name(name)
    path = out_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    title = Path(name).stem.replace("_", " ")
    try:
        if ext == ".docx":
            markdown_to_docx(content, path, title)
        elif ext == ".pdf":
            markdown_to_pdf(content, path, title)
        elif ext == ".pptx":
            json_to_pptx(_parse_json(content), path)
        elif ext in (".xlsx", ".xlsm"):
            json_to_xlsx(_parse_json(content), path)
        elif ext in (".html", ".htm") and not content.lstrip().lower().startswith(("<!doctype", "<html")):
            path.write_text(wrap_document(md_to_html(content), title, rtl=is_rtl(content)), encoding="utf-8")
        elif ext == ".csv":
            # normalise and add BOM so Excel opens Arabic/French accents correctly
            rows = list(csv.reader(io.StringIO(content.strip())))
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows(rows)
        else:
            path.write_text(content, encoding="utf-8")
        return GeneratedFile(name, path, ext.lstrip("."))
    except Exception as e:  # noqa: BLE001
        return GeneratedFile(name, path, ext.lstrip("."), error=str(e))


def extract_and_generate(answer: str, out_dir: Path) -> list[GeneratedFile]:
    """Find every ```doubaj-file block in an answer, write the files, zip multi-file projects."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[GeneratedFile] = []
    for _fence, name, content in FILE_BLOCK.findall(answer):
        results.append(write_file(name, content, out_dir))
    # zip every project folder
    folders: dict[str, list[GeneratedFile]] = {}
    for r in results:
        if "/" in r.name and not r.error:
            folders.setdefault(r.name.split("/")[0], []).append(r)
    for folder, files in folders.items():
        zpath = out_dir / f"{folder}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in (out_dir / folder).rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(out_dir))
        results.append(GeneratedFile(f"{folder}.zip", zpath, "zip"))
    return results


def strip_file_blocks(answer: str, placeholder: str = "📎 {name}") -> str:
    """Replace big file blocks in the displayed answer by a short placeholder."""
    return FILE_BLOCK.sub(lambda m: "\n" + placeholder.format(name=m.group(2)) + "\n", answer)
