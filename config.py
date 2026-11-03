"""Konfigurasi API key & model.

Mendukung beberapa model: satu untuk Ringkasan, satu untuk Kuis.
Prioritas pembacaan setting (yang lebih atas menang):
1. Environment Variable (dipakai di Vercel)
2. Hardcoded di DEFAULTS (di bawah)
3. config.json lokal (di laptop)
"""
import os
import json

# =====================================================================
#  TARUH API KEY DI SINI (satu baris) — cara paling simpel buat deploy
#  ⚠️ Repo GitHub harus PRIVATE, karena kalau public key ini bisa bocor.
# =====================================================================
HARDCODED_API_KEY = "kn-52e4f25823b96a2da3e309803e72e48314a6cbafb0f6b57e"
# =====================================================================

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Daftar model yang bisa dipilih. Tambah/copot di sini sesuai kebutuhan.
MODELS = [
    "deepseek-v4-flash",     # cepat & handal (disarankan untuk kuis)
    "deepseek-v4-1-flash",   # lebih cepat lagi
    "deepseek-v4-pro",       # paling teliti tapi lambat (cocok untuk ringkasan)
]

DEFAULTS = {
    "base_url": "https://kenari.id/v1",
    "api_key": HARDCODED_API_KEY,
    "model_summary": "deepseek-v4-flash",     # model untuk Ringkasan (cepat + detail)
    "model_quiz": "deepseek-v4-flash",        # model untuk Kuis (cepat & handal)
}

# nama environment variable yang dipakai di Vercel
ENV_MAP = {
    "base_url": "KENARI_BASE_URL",
    "api_key": "KENARI_API_KEY",
    "model_summary": "KENARI_MODEL_SUMMARY",
    "model_quiz": "KENARI_MODEL_QUIZ",
}


def load_config():
    cfg = dict(DEFAULTS)

    # 1) Environment variable (dipakai di Vercel)
    for field, env in ENV_MAP.items():
        val = os.environ.get(env)
        if val:
            cfg[field] = val.strip()

    # 2) Fallback ke config.json lokal (dipakai di laptop)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                local = json.load(f)
            for field in ENV_MAP:
                if not cfg.get(field) and local.get(field):
                    cfg[field] = local[field]
        except Exception:
            pass

    return cfg


def save_config(cfg):
    """Simpan ke config.json. Di Vercel filesystem read-only -> diabaikan."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass