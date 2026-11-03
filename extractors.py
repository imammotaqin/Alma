"""Ekstraksi teks & rekapan data dari berbagai jenis file dan URL."""
import io
import os
import re
import math

import requests
from bs4 import BeautifulSoup
import pandas as pd

try:
    import pymupdf as fitz  # PyMuPDF (nama baru)
except ImportError:
    import fitz  # PyMuPDF (nama lama)
import docx  # python-docx
from pptx import Presentation

DATA_EXT = {".xlsx", ".xls", ".csv", ".tsv"}
DOC_EXT = {
    ".pdf", ".docx", ".ppt", ".pptx", ".txt", ".md", ".log",
    ".py", ".json", ".html", ".htm", ".r",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def classify(filename):
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in DATA_EXT:
        return "data"
    if ext in DOC_EXT:
        return "document"
    raise ValueError(f"Format file belum didukung: {ext or '(tanpa ekstensi)'}")


# ---------------------------------------------------------------- dokumen
def extract_document(filename, data):
    """Mengambil teks dari file dokumen. Kembalikan string teks."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        text = _extract_pdf(data)
    elif ext == ".docx":
        text = _extract_docx(data)
    elif ext in (".ppt", ".pptx"):
        text = _extract_pptx(data)
    else:
        # teks mentah (txt, md, log, py, json, html, dst.)
        text = _decode_text(data)  # otomatis buang BOM
    return _clean_text(text)


def _extract_pdf(data):
    doc = fitz.open(stream=data, filetype="pdf")
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts)


def _extract_docx(data):
    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_pptx(data):
    prs = Presentation(io.BytesIO(data))
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        parts.append(f"[Slide {i}]")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    txt = "".join(run.text for run in para.runs).strip()
                    if txt:
                        parts.append(txt)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    parts.append(" | ".join(cells))
    return "\n".join(parts)


# ---------------------------------------------------------------- URL
def extract_url(url):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    if r.encoding and r.encoding.lower() != "iso-8859-1":
        r.encoding = r.encoding
    else:
        r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    for tag in soup(["script", "style", "noscript", "nav", "footer",
                     "header", "aside", "iframe", "form", "svg"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body
    text = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _clean_text(text), (title or url)


# ---------------------------------------------------------------- data (Excel/CSV)
def _decode_text(data):
    # buang BOM UTF-8 (sering muncul dari Excel/Notepad) supaya header bersih
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="ignore")


def extract_data(filename, data):
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext in (".csv", ".txt"):
            # sniff otomatis: koma atau titik-koma (locale Excel Indonesia)
            text = _decode_text(data)
            df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
        elif ext == ".tsv":
            df = pd.read_csv(io.StringIO(_decode_text(data)), sep="\t", engine="python")
        elif ext == ".xls":
            df = pd.read_excel(io.BytesIO(data))
        else:
            df = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    except Exception as e:
        raise ValueError(
            f"Gagal membaca file: {e}. Coba simpan ulang sebagai .xlsx atau .csv."
        )
    columns = _build_recap_columns(df)
    shape = [int(df.shape[0]), int(df.shape[1])]
    text = _textualize(df, filename)
    return {"name": filename, "shape": shape, "columns": columns, "text": text}


def _num(x):
    try:
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except Exception:
        return None


def _build_recap_columns(df):
    columns = []
    # batasi jumlah kolom supaya ringkas
    for col in list(df.columns)[:30]:
        s = df[col]
        info = {"name": str(col), "missing": int(s.isna().sum())}
        if pd.api.types.is_numeric_dtype(s):
            info["dtype"] = "number"
            info["stats"] = {
                "count": int(s.count()),
                "mean": _num(s.mean()),
                "min": _num(s.min()),
                "max": _num(s.max()),
                "sum": _num(s.sum()),
            }
        else:
            info["dtype"] = "text"
            vc = s.dropna().value_counts().head(5)
            info["top"] = [[str(k), int(v)] for k, v in vc.items()]
        columns.append(info)
    return columns


def _textualize(df, filename):
    from io import StringIO
    lines = [
        f"File data: {filename}",
        f"Ukuran: {df.shape[0]} baris x {df.shape[1]} kolom",
        "Nama kolom: " + ", ".join(str(c) for c in df.columns[:30]),
    ]
    sample = df.head(15).iloc[:, :15]
    buf = StringIO()
    sample.to_csv(buf, index=False)
    lines.append("Contoh beberapa baris pertama:")
    lines.append(buf.getvalue())
    numeric = df.select_dtypes(include="number")
    if len(numeric.columns):
        lines.append("Ringkasan statistik kolom angka:")
        lines.append(numeric.describe().round(2).to_string())
    return "\n".join(lines)


# ---------------------------------------------------------------- helper
def _clean_text(text):
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()