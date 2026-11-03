# 📚 Belajar bersama Alma (Vercel)

Versi online dari alat belajar yang memakai **Flask** dan bisa di-deploy langsung ke **Vercel**.

Fitur:
- 📄 Baca materi: PDF, Word, PowerPoint, Excel/CSV, TXT, dan link web.
- 📝 Catatan belajar otomatis (ringkasan terstruktur) untuk semua mata pelajaran.
- 🧠 Soal pilihan ganda + esai otomatis, jumlah menyesuaikan materi, lengkap jawaban + penjelasan.
- 🌐 Pelengkap info dari Wikipedia (bisa dimatikan).
- ⬇️ Download catatan & soal ke Word / PDF.

---

## 🚀 Cara deploy ke Vercel

### 1. Siapkan Environment Variable di Vercel
Buka dashboard proyek Vercel → **Settings → Environment Variables**, tambah:

| Name | Contoh nilai |
|---|---|
| `KENARI_API_KEY` | `kn-xxxxxxxx...` (API key kamu) |
| `KENARI_MODEL` | `deepseek-v4-pro` |
| `KENARI_BASE_URL` | `https://kenari.id/v1` |

> `KENARI_MODEL` dan `KENARI_BASE_URL` punya nilai default, jadi cukup `KENARI_API_KEY` yang wajib.
> Hanya `KENARI_API_KEY` yang benar-benar perlu diisi.

### 2. Upload ke GitHub lalu hubungkan ke Vercel
- Push semua file di folder ini ke repository GitHub (termasuk `app.py` di root).
- Di Vercel: **Add New Project → Import** repo tadi → Vercel otomatis mendeteksi **Flask** (framework preset).
- Deploy. Selesai, aplikasi bisa diakses lewat URL `xxxxx.vercel.app`.

### 3. (Opsional) Tes lokal
```bash
pip install -r requirements.txt
python app.py
# buka http://127.0.0.1:8765
```

---

## Struktur proyek
```
app.py            # entry point Flask (WSGI app) -> semua route
llm.py            # panggilan AI (catatan + soal)
extractors.py     # pembacaan file & rekap data
websearch.py      # pencarian pelengkap (Wikipedia)
config.py         # baca env var (Vercel) / config.json (lokal)
templates/index.html
static/style.css, app.js, alma.svg
requirements.txt
```

## ⚠️ Batasan yang perlu diketahui
- **Ukuran file upload** dibatasi Vercel sekitar **4 MB**. Kalau PDF/PPT besar, kompres dulu atau bagi jadi beberapa file.
- API key di online version **tidak** tersimpan di UI — di-set lewat Environment Variable di Vercel. Menu "Pengaturan" di aplikasi hanya berlaku untuk versi lokal.
- Model reasoning (seperti `deepseek-v4-pro`) bisa butuh waktu agak lama untuk materi panjang. Batas eksekusi Vercel adalah 5 menit, masih aman.

## 🔒 Catatan keamanan
Jangan pernah commit `config.json` atau API key ke repository publik. Pakai Environment Variable di Vercel.