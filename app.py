"""Belajar bersama Alma — aplikasi Flask (entry point untuk Vercel & bisa dijalankan lokal).

Di Vercel: Vercel mendeteksi variabel `app` (Flask/WSGI) di file ini secara otomatis.
Secara lokal bisa dijalankan dengan:  python app.py
"""
import os
import io
import re
import sys

# Pastikan folder proyek masuk ke Python import path, supaya modul lokal
# (llm.py, extractors.py, websearch.py, config.py) selalu bisa di-import,
# baik saat dijalankan lokal maupun di serverless Vercel.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask import Flask, request, jsonify, render_template
from flask import send_file
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

import llm
import extractors
import websearch
from config import load_config, save_config, MODELS

# Gunakan path absolut agar template/static selalu ditemukan, di mana pun
# function dijalankan (lokal maupun serverless Vercel).
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static",
)
# Vercel membatasi ukuran body request serverless (~4.5 MB), jadi kita batasi sedikit
# di bawahnya supaya muncul pesan error yang jelas.
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB
app.config["JSON_AS_ASCII"] = False


@app.errorhandler(413)
def too_large(e):
    return jsonify({
        "error": "File terlalu besar (maksimal sekitar 4 MB). Coba kompres atau bagi filenya."
    }), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/health")
def api_health():
    return jsonify({"ok": True, "name": "Alma"})


# ---------------------------------------------------------------- ekstraksi
@app.post("/api/extract")
def api_extract():
    files = request.files.getlist("files")
    url = (request.form.get("url") or "").strip()

    documents = []
    datasets = []
    text_parts = []

    for f in files:
        if not f or not f.filename:
            continue
        name = os.path.basename(f.filename)
        data = f.read()
        try:
            kind = extractors.classify(name)
            if kind == "data":
                ds = extractors.extract_data(name, data)
                datasets.append(ds)
                text_parts.append(ds["text"])
            else:
                text = extractors.extract_document(name, data)
                if text:
                    documents.append({
                        "name": name,
                        "text": text,
                        "char_count": len(text),
                    })
                    text_parts.append(f"\n\n=== {name} ===\n{text}")
                else:
                    documents.append({
                        "name": name,
                        "error": "Tidak ada teks yang bisa diambil "
                                 "(mungkin PDF hasil scan/gambar).",
                    })
        except Exception as e:
            documents.append({"name": name, "error": str(e)})

    if url:
        try:
            text, title = extractors.extract_url(url)
            documents.append({
                "name": title or url,
                "text": text,
                "char_count": len(text),
                "is_url": True,
            })
            text_parts.append(f"\n\n=== {title or url} ===\n{text}")
        except Exception as e:
            documents.append({"name": url, "error": f"Gagal mengambil link: {e}"})

    all_text = "\n".join(text_parts)
    return jsonify({
        "documents": documents,
        "datasets": datasets,
        "all_text": all_text,
        "total_chars": len(all_text),
    })


# ---------------------------------------------------------------- ringkasan
@app.post("/api/summary")
def api_summary():
    payload = request.get_json(force=True, silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Belum ada bahan. Proses dulu file/link-nya ya."}), 400
    extra = ""
    if payload.get("enrich", True):
        try:
            extra = websearch.enrich(text)
        except Exception:
            extra = ""
    try:
        summary = llm.summarize(text, extra=extra)
        summary = _clean_ai_output(summary)
        return jsonify({"summary": summary})
    except llm.LLMError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Terjadi kesalahan: {e}"}), 500


# ---------------------------------------------------------------- soal
def _auto_question_count(text):
    """Jumlah soal otomatis, dibatasi supaya satu panggilan tetap andal."""
    chars = len(text)
    if chars < 1500:
        return 6
    if chars < 4000:
        return 8
    return 10


@app.post("/api/quiz")
def api_quiz():
    payload = request.get_json(force=True, silent=True) or {}
    text = (payload.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Belum ada bahan. Proses dulu file/link-nya ya."}), 400

    n = _auto_question_count(text)
    extra = ""
    if payload.get("enrich", True):
        try:
            extra = websearch.enrich(text)
        except Exception:
            extra = ""

    try:
        questions = llm.generate_quiz(text, n, extra=extra)
        return jsonify({"questions": questions, "count": len(questions), "target": n})
    except llm.LLMError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Terjadi kesalahan: {e}"}), 500


# ---------------------------------------------------------------- export
def _clean_ai_output(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:markdown|md|text)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    markers = [
        "We need answer in user",
        "We need answer in Indonesian",
        "Let's inspect the user message",
        "This appears as though",
        "The top says:",
        "Need final since",
    ]
    positions = [text.find(m) for m in markers if text.find(m) >= 0]
    if positions:
        cut = min(positions)
        if cut > 80:
            text = text[:cut].rstrip()
    return text


def _markdown_blocks(text):
    blocks = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            blocks.append(("blank", ""))
        elif line.startswith("### "):
            blocks.append(("h3", line[4:]))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif re.match(r"^[-*•]\s+", line):
            blocks.append(("bullet", re.sub(r"^[-*•]\s+", "", line)))
        else:
            blocks.append(("p", line))
    return blocks


@app.post("/api/export")
def api_export():
    payload = request.get_json(force=True, silent=True) or {}
    content = _clean_ai_output(payload.get("content") or "")
    kind = (payload.get("format") or "docx").lower()
    filename = payload.get("filename") or "hasil-belajar"
    if not content:
        return jsonify({"error": "Belum ada hasil untuk di-download."}), 400

    if kind == "docx":
        document = Document()
        document.add_heading("Belajar bersama Alma", level=0)
        for typ, value in _markdown_blocks(content):
            if typ == "blank":
                continue
            if typ == "h1":
                document.add_heading(value, level=1)
            elif typ == "h2":
                document.add_heading(value, level=2)
            elif typ == "h3":
                document.add_heading(value, level=3)
            elif typ == "bullet":
                document.add_paragraph(value, style="List Bullet")
            else:
                document.add_paragraph(value)
        stream = io.BytesIO()
        document.save(stream)
        stream.seek(0)
        return send_file(stream, as_attachment=True, download_name=f"{filename}.docx",
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    if kind == "pdf":
        stream = io.BytesIO()
        doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=1.7 * cm,
                                leftMargin=1.7 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="TitleAlma", parent=styles["Title"], alignment=TA_CENTER,
                                  textColor="#4f46e5", spaceAfter=16))
        story = [Paragraph("Belajar bersama Alma", styles["TitleAlma"])]
        for typ, value in _markdown_blocks(content):
            if typ == "blank":
                story.append(Spacer(1, 6))
            else:
                safe = (value.replace("&", "&amp;").replace("<", "&lt;")
                        .replace(">", "&gt;"))
                if typ == "h1":
                    style = styles["Heading1"]
                elif typ == "h2":
                    style = styles["Heading2"]
                elif typ == "h3":
                    style = styles["Heading3"]
                else:
                    style = styles["BodyText"]
                prefix = "• " if typ == "bullet" else ""
                story.append(Paragraph(prefix + safe, style))
                story.append(Spacer(1, 4))
        doc.build(story)
        stream.seek(0)
        return send_file(stream, as_attachment=True, download_name=f"{filename}.pdf",
                         mimetype="application/pdf")

    return jsonify({"error": "Format hanya docx atau pdf."}), 400


# ---------------------------------------------------------------- konfigurasi
@app.get("/api/config")
def api_config_get():
    cfg = load_config()
    from_env = bool(os.environ.get("KENARI_API_KEY"))
    # Jangan membocorkan API key dari environment variable ke browser.
    return jsonify({
        "base_url": cfg.get("base_url", ""),
        "model_summary": cfg.get("model_summary", ""),
        "model_quiz": cfg.get("model_quiz", ""),
        "models": MODELS,
        "api_key": "" if from_env else cfg.get("api_key", ""),
        "api_key_set": bool(cfg.get("api_key")),
    })


@app.post("/api/config")
def api_config_set():
    cfg = request.get_json(force=True, silent=True) or {}
    save_config({
        "base_url": (cfg.get("base_url") or "").strip(),
        "api_key": (cfg.get("api_key") or "").strip(),
        "model_summary": (cfg.get("model_summary") or "").strip(),
        "model_quiz": (cfg.get("model_quiz") or "").strip(),
    })
    return jsonify({"ok": True})


@app.post("/api/test_connection")
def api_test_connection():
    try:
        reply = llm.test_connection()
        return jsonify({"ok": True, "reply": reply[:120]})
    except llm.LLMError as e:
        return jsonify({"ok": False, "error": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ---------------------------------------------------------------- lokal
if __name__ == "__main__":
    # Hanya dipakai kalau dijalankan langsung di laptop (bukan di Vercel).
    port = int(os.environ.get("PORT", 8765))
    print(f"Belajar bersama Alma berjalan di http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
