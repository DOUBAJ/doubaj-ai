"""Read uploaded files and turn them into text (with page / slide / sheet markers so the
model can cite its sources) plus images for vision-capable models."""
from __future__ import annotations

import base64
import csv
import io
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

MAX_CHARS = 400_000  # safety cap per document; the UI warns when reached

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".sql", ".php",
            ".css", ".scss", ".xml", ".yaml", ".yml", ".ini", ".toml", ".sh", ".bat", ".ps1", ".go", ".rs",
            ".kt", ".swift", ".rb", ".lua", ".m", ".r", ".vb", ".ino", ".asm", ".log"}
TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".tex"} | CODE_EXT
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}

SUPPORTED = sorted(TEXT_EXT | IMAGE_EXT | {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xlsm", ".xls",
                                          ".csv", ".json", ".html", ".htm"})


@dataclass
class ReadResult:
    name: str
    kind: str
    text: str = ""
    images: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False


def _img_to_payload(data: bytes, suffix: str) -> dict:
    """Normalise to PNG/JPEG, downscale big images (API limits ~5MB)."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((2000, 2000))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return {"media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}


def _read_pdf(path: Path, res: ReadResult) -> None:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts, empty_pages = [], []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(f"[Page {i}]\n{t.strip()}")
        else:
            empty_pages.append(i)
    res.text = "\n\n".join(parts)
    # Scanned pages: render to images so a vision model can read them (OCR).
    if empty_pages:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(str(path))
            for i in empty_pages[:20]:
                pil = pdf[i - 1].render(scale=1.6).to_pil()
                buf = io.BytesIO()
                pil.convert("RGB").save(buf, format="JPEG", quality=85)
                res.images.append({"media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode(),
                                   "label": f"{path.name} – page {i} (scanned)"})
            res.warnings.append(f"{len(empty_pages)} scanned page(s) sent as images (vision model required).")
            if len(empty_pages) > 20:
                res.warnings.append("Only the first 20 scanned pages were included.")
        except Exception as e:  # noqa: BLE001
            res.warnings.append(f"Scanned pages could not be rendered: {e}")


def _read_docx(path: Path, res: ReadResult) -> None:
    import docx
    d = docx.Document(str(path))
    out, para_no = [], 0
    body = d.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = docx.text.paragraph.Paragraph(child, d)
            if p.text.strip():
                para_no += 1
                style = (p.style.name or "") if p.style is not None else ""
                prefix = "#" * int(style[-1]) + " " if style.startswith("Heading") and style[-1].isdigit() else ""
                out.append(f"[§{para_no}] {prefix}{p.text}")
        elif tag == "tbl":
            t = docx.table.Table(child, d)
            rows = []
            for r in t.rows:
                rows.append("| " + " | ".join(c.text.strip().replace("\n", " ") for c in r.cells) + " |")
            if rows:
                out.append("[Table]\n" + "\n".join(rows))
    res.text = "\n".join(out)
    # embedded images (diagrams) for vision models
    for rel in list(d.part.rels.values())[:10]:
        if "image" in rel.reltype:
            try:
                res.images.append({**_img_to_payload(rel.target_part.blob, ".png"), "label": f"{path.name} – image"})
            except Exception:
                pass


def _read_doc(path: Path, res: ReadResult) -> None:
    """Legacy .doc: use Microsoft Word through COM if installed (Windows)."""
    try:
        import win32com.client  # type: ignore
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(path.resolve()), ReadOnly=True)
        res.text = doc.Content.Text
        doc.Close(False)
        word.Quit()
    except Exception:
        # Fallback: crude text extraction from the binary
        raw = path.read_bytes()
        txt = raw.decode("utf-16-le", errors="ignore")
        cleaned = "".join(ch for ch in txt if ch.isprintable() or ch in "\n\t")
        res.text = cleaned
        res.warnings.append("Legacy .doc read in degraded mode (Microsoft Word not available). "
                            "Save as .docx for best results.")


def _read_pptx(path: Path, res: ReadResult) -> None:
    from pptx import Presentation
    prs = Presentation(str(path))
    out = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shp in slide.shapes:
            if shp.has_text_frame:
                t = "\n".join(p.text for p in shp.text_frame.paragraphs if p.text.strip())
                if t:
                    texts.append(t)
            if getattr(shp, "has_table", False) and shp.has_table:
                for r in shp.table.rows:
                    texts.append("| " + " | ".join(c.text for c in r.cells) + " |")
            if shp.shape_type == 13 and len(res.images) < 10:  # picture
                try:
                    res.images.append({**_img_to_payload(shp.image.blob, "." + shp.image.ext),
                                       "label": f"{path.name} – slide {i}"})
                except Exception:
                    pass
        notes = ""
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        out.append(f"[Slide {i}]\n" + "\n".join(texts) + (f"\n(Notes: {notes})" if notes else ""))
    res.text = "\n\n".join(out)


def _read_xlsx(path: Path, res: ReadResult) -> None:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        rows = []
        for r_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
            if r_idx > 2000:
                res.warnings.append(f"Sheet {ws.title}: only first 2000 rows included.")
                break
            if any(v is not None for v in row):
                rows.append(f"R{r_idx}: " + " | ".join("" if v is None else str(v) for v in row))
        out.append(f"[Sheet: {ws.title}]\n" + "\n".join(rows))
    res.text = "\n\n".join(out)


def _read_xls(path: Path, res: ReadResult) -> None:
    import xlrd
    wb = xlrd.open_workbook(str(path))
    out = []
    for sh in wb.sheets():
        rows = [f"R{r + 1}: " + " | ".join(str(c) for c in sh.row_values(r)) for r in range(min(sh.nrows, 2000))]
        out.append(f"[Sheet: {sh.name}]\n" + "\n".join(rows))
    res.text = "\n\n".join(out)


def _read_csv(path: Path, res: ReadResult) -> None:
    raw = path.read_bytes()
    text = _decode(raw)
    try:
        dialect = csv.Sniffer().sniff(text[:4000])
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    res.text = "\n".join(f"R{i}: " + " | ".join(r) for i, r in enumerate(rows[:5000], 1))


def _read_html(path: Path, res: ReadResult) -> None:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_decode(path.read_bytes()), "html.parser")
    for s in soup(["script", "style"]):
        s.decompose()
    res.text = soup.get_text("\n", strip=True)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1256", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_file(path: str | Path) -> ReadResult:
    path = Path(path)
    ext = path.suffix.lower()
    res = ReadResult(name=path.name, kind=ext.lstrip(".") or "file")
    try:
        if ext == ".pdf":
            _read_pdf(path, res)
        elif ext == ".docx":
            _read_docx(path, res)
        elif ext == ".doc":
            _read_doc(path, res)
        elif ext == ".pptx":
            _read_pptx(path, res)
        elif ext in (".xlsx", ".xlsm"):
            _read_xlsx(path, res)
        elif ext == ".xls":
            _read_xls(path, res)
        elif ext == ".csv":
            _read_csv(path, res)
        elif ext in (".html", ".htm"):
            _read_html(path, res)
        elif ext == ".json":
            try:
                res.text = json.dumps(json.loads(_decode(path.read_bytes())), ensure_ascii=False, indent=2)
            except ValueError:
                res.text = _decode(path.read_bytes())
        elif ext in IMAGE_EXT:
            res.kind = "image"
            res.images.append({**_img_to_payload(path.read_bytes(), ext), "label": path.name})
        else:
            mt, _ = mimetypes.guess_type(str(path))
            if ext in TEXT_EXT or (mt or "").startswith("text"):
                res.text = _decode(path.read_bytes())
            else:
                # last resort: try to decode as text
                raw = path.read_bytes()
                if b"\x00" in raw[:2000]:
                    res.warnings.append("Unsupported binary file type.")
                else:
                    res.text = _decode(raw)
    except Exception as e:  # noqa: BLE001
        res.warnings.append(f"Error while reading {path.name}: {e}")
    if len(res.text) > MAX_CHARS:
        res.text = res.text[:MAX_CHARS]
        res.truncated = True
        res.warnings.append(f"Document truncated to {MAX_CHARS} characters.")
    return res
