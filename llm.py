"""Panggilan LLM (OpenAI-compatible) untuk catatan belajar, ringkasan, dan soal.

Semua fitur memakai SATU panggilan per fitur supaya cepat dan andal di serverless.
"""
import json
import re

import requests

from config import load_config


class LLMError(Exception):
    pass


def _chat(messages, temperature=0.4, max_tokens=2500, timeout=300, model=None):
    cfg = load_config()
    if not cfg.get("api_key"):
        raise LLMError("API key belum diisi. Buka tab Pengaturan dulu ya.")
    if not cfg.get("base_url"):
        raise LLMError("Base URL belum diisi. Buka tab Pengaturan dulu ya.")
    model = model or cfg.get("model") or cfg.get("model_summary") or "deepseek-v4-flash"
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise LLMError(f"Gagal terhubung ke server API: {e}")
    if r.status_code != 200:
        raise LLMError(f"API error {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except Exception:
        raise LLMError("Respon API tidak valid (bukan JSON).")

    choices = data.get("choices") or []
    if not choices:
        # Beberapa gateway model reasoning kadang balas format Responses
        # (`output`) alih-alih Chat (`choices`). Coba ambil dari situ dulu.
        texts = []
        for item in (data.get("output") or []):
            for c in (item.get("content") or []):
                if isinstance(c, dict) and (c.get("text") or c.get("type") in ("text", "output_text")):
                    if c.get("text"):
                        texts.append(c["text"])
        if texts:
            return "".join(texts).strip()
        raise LLMError("Respon API kosong (tidak ada hasil). Coba lagi.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    # beberapa API mengirim content sebagai daftar bagian teks
    if isinstance(content, list):
        content = "".join(
            (p.get("text") or "") for p in content if isinstance(p, dict)
        )
    # Jangan pernah memakai reasoning_content sebagai jawaban. Field tersebut
    # adalah proses berpikir internal dan tidak boleh ditampilkan ke pengguna.
    if content is None:
        content = ""
    return content.strip()


def test_connection():
    reply = _chat(
        [{"role": "user", "content": "Balas dengan satu kata saja: OK"}],
        temperature=0.0,
        max_tokens=256,
    )
    reply = (reply or "").strip()
    if not reply:
        raise LLMError("Server merespons tapi jawaban kosong. Coba lagi atau ganti model.")
    return reply


# ---------------------------------------------------------------- catatan belajar
SUMMARY_INSTRUCTION = (
    "Berdasarkan MATERI di atas, buatlah CATATAN BELAJAR yang SANGAT LENGKAP dan MENYELURUH dalam Bahasa Indonesia. "
    "Tulis SEMUA informasi penting dari materi, JANGAN ada yang terlewat. "
    "Materi bisa dari mata pelajaran/kuliah apa saja (matematika, fisika, kimia, biologi, sejarah, ekonomi, dll.).\n\n"
    "Tulis dengan format Markdown berikut, langsung mulai dari '## ' tanpa kata pembuka:\n\n"
    "## Judul / Topik\n(tulis judul materi)\n\n"
    "## Bidang / Mata Pelajaran\n(tulis bidangnya)\n\n"
    "## Ringkasan Singkat\n(satu paragraf merangkum inti materi)\n\n"
    "## Poin-Poin Penting\n- jelaskan TIAP poin secara lengkap, sertakan mekanisme/alasan/langkah\n\n"
    "## Istilah & Definisi\n- **istilah** — definisi lengkap. TULIS SEMUA istilah penting yang ada di materi, jangan cuma beberapa.\n\n"
    "## Rumus / Konsep Kunci\n- tulis SEMUA rumus/persamaan penting beserta keterangan TIAP simbolnya\n\n"
    "## Data, Angka & Fakta Penting\n- angka, tahun, tokoh, atau fakta kunci beserta konteksnya\n\n"
    "## Kesimpulan\n(1-2 kalimat kesimpulan)\n\n"
    "Aturan:\n"
    "- LENGKAP & MENYELURUH: tulis SEMUA istilah, SEMUA rumus, SEMUA poin penting, SEMUA angka/fakta dari materi.\n"
    "- Gunakan data yang BENAR-BENAR ada di materi, jangan mengarang.\n"
    "- Untuk matematika/fisika sertakan rumus dan langkah penyelesaian; untuk sejarah sertakan tahun, tokoh, sebab-akibat.\n"
    "- Jelaskan tiap poin secara rinci agar mudah dipahami."
)


def summarize(text, extra=""):
    text = (text or "").strip()
    if not text:
        raise LLMError("Belum ada bahan untuk diringkas.")
    # Satu panggilan saja. Kalau materinya sangat panjang, potong ke batas yang
    # masih aman untuk satu konteks (tinggi, supaya materi tidak kelewat).
    MAX_CHARS = 30000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rstrip() + "\n\n[Materi dipotong karena sangat panjang.]"

    cfg = load_config()
    primary = cfg.get("model_summary") or "deepseek-v4-flash"
    fallback = "deepseek-v4-flash" if primary != "deepseek-v4-flash" else "deepseek-v4-1-flash"

    last_err = None
    # coba model utama lalu fallback. Kumpulkan detail error agar mudah dilacak.
    details = []
    for model in (primary, fallback):
        try:
            result = _summary_once(text, extra, model=model)
            if result and len(result.strip()) >= 100:
                return result
            details.append(f"{model}: hasil terlalu pendek ({len(result)} char)")
        except LLMError as e:
            details.append(f"{model}: {e}")
    raise LLMError("Ringkasan gagal: " + (" | ".join(details) if details else "tidak ada hasil"))


def _summary_once(text, extra="", model=None):
    if model is None:
        cfg = load_config()
        model = cfg.get("model_summary") or "deepseek-v4-flash"
    prompt = (
        "Berikut MATERI yang harus kamu ubah menjadi catatan belajar:\n\n"
        f"<MATERI>\n{text}\n</MATERI>\n\n"
        + SUMMARY_INSTRUCTION
    )
    if extra:
        prompt += (
            "\n\nCATATAN PENTING: MATERI di atas adalah sumber UTAMA dan harus dirangkum LENGKAP.\n"
            "Informasi tambahan dari internet di bawah ini boleh dipakai HANYA untuk melengkapi "
            "bagian materi yang kosong/menjadi konteks, JANGAN menggantikan isi materi:\n" + extra
        )
    return _chat([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=8000, model=model)


# ---------------------------------------------------------------- soal
def _quiz_prompt(n, text, extra=""):
    mc = max(1, round(n * 0.6))
    es = n - mc
    prompt = (
        f"<MATERI>\n{text}\n</MATERI>\n\n"
        f"Berdasarkan MATERI di atas, buatkan {n} soal latihan dalam Bahasa Indonesia, "
        f"campuran: {mc} soal PILIHAN GANDA dan {es} soal ESAI/uraian, dari mudah sampai menantang. "
        "Materi bisa dari mata pelajaran/kuliah apa saja.\n\n"
        "Format setiap soal PILIHAN GANDA:\n"
        '{"type": "mc", "pertanyaan": "...", "pilihan": ["A", "B", "C", "D"], "jawaban": "B", "penjelasan": "..."}\n\n'
        "Format setiap soal ESAI:\n"
        '{"type": "essay", "pertanyaan": "...", "jawaban": "...", "penjelasan": "..."}\n\n'
        "Aturan:\n"
        "- Setiap soal WAJIB punya kunci jawaban yang benar + penjelasan singkat.\n"
        "- Pilihan ganda tepat 4 opsi (A-D), hanya SATU yang benar.\n"
        "- Usahakan urutannya selang-seling (PG, esai, PG, esai, ...).\n"
        "- Jawab HANYA dengan SATU array JSON berisi SEMUA soal, tanpa kata pembuka lain."
    )
    if extra:
        prompt += "\n\nInformasi tambahan dari internet (bila relevan):\n" + extra
    return prompt


def generate_quiz(text, n=12, extra=""):
    """SATU panggilan untuk menghasilkan campuran pilihan ganda + esai."""
    text = (text or "").strip()
    if not text:
        raise LLMError("Belum ada bahan untuk membuat soal.")

    # potong materi supaya muat di satu konteks dan tidak terlalu membebani model
    if len(text) > 8000:
        text = text[:8000].rstrip()

    cfg = load_config()
    model = cfg.get("model_quiz") or cfg.get("model") or "deepseek-v4-flash"

    last_err = None
    # coba dengan jumlah penuh, lalu fallback dengan jumlah lebih sedikit
    for target in (n, max(6, n // 2)):
        prompt = _quiz_prompt(target, text, extra)
        max_tokens = min(12000, 1400 * target + 1000)
        for attempt in range(2):
            raw = _chat(
                [{"role": "user", "content": prompt}],
                temperature=0.6 if attempt == 0 else 0.4,
                max_tokens=max_tokens,
                model=model,
            )
            try:
                questions = _parse_json_array(raw)
            except LLMError as e:
                last_err = e
                continue
            for q in questions:
                t = q.get("type")
                q["type"] = "mc" if (t == "mc" or "pilihan" in q) else "essay"
            return questions
    raise last_err or LLMError("Gagal membuat soal. Coba lagi.")


def _try_json(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def _parse_json_array(raw):
    if not raw:
        raise LLMError("Model tidak mengembalikan jawaban.")
    text = raw.strip()
    # buang code-fence markdown seperti ```json ... ```
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("Gagal mem-parsing soal (format tidak dikenali). Coba lagi.")
    snippet = text[start:end + 1]
    data = _try_json(snippet)
    if data is None:
        # coba perbaiki koma menggantung
        fixed = re.sub(r",\s*([\]}])", r"\1", snippet)
        data = _try_json(fixed)
    if data is None:
        raise LLMError("Gagal mem-parsing soal JSON. Coba lagi.")
    if not isinstance(data, list) or not data:
        raise LLMError("Soal yang dihasilkan kosong / tidak valid. Coba lagi.")
    return data
