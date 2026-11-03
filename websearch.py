"""Pencarian web (Wikipedia) untuk melengkapi catatan & soal."""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "BelajarAlma/1.0 (alat belajar pribadi)"}

# Coba Wikipedia Indonesia dulu, lalu bahasa Inggris sebagai cadangan.
API_HOSTS = ["id.wikipedia.org", "en.wikipedia.org"]


def _strip_html(s):
    try:
        return BeautifulSoup(s, "html.parser").get_text(" ", strip=True)
    except Exception:
        return s


def _search_wiki(host, query, n):
    api = f"https://{host}/w/api.php"
    r = requests.get(api, params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": n,
        "format": "json",
    }, headers=HEADERS, timeout=6)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        snippet = _strip_html(item.get("snippet", ""))
        if title and snippet:
            results.append({
                "title": title,
                "url": f"https://{host}/wiki/{requests.utils.quote(title.replace(' ', '_'))}",
                "snippet": snippet[:200],
            })
    return results[:n]


def search(query, n=5):
    """Kembalikan list [{title, url, snippet}]. Gagal -> []."""
    if not query:
        return []
    for host in API_HOSTS:
        try:
            results = _search_wiki(host, query, n)
            if results:
                return results
        except Exception:
            continue
    return []


def derive_query(text, max_words=8, max_len=80):
    """Ambil topik singkat dari baris pertama yang bermakna."""
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("===") or line.startswith("File data:"):
            continue
        if len(line) >= 6:
            return " ".join(line.split()[:max_words])[:max_len]
    return " ".join((text or "").split()[:max_words]).strip()[:max_len]


def enrich(text, n=5):
    """Kembalikan teks ringkasan hasil pencarian web (atau '' kalau gagal)."""
    query = derive_query(text)
    results = search(query, n)
    if not results:
        return ""
    lines = [f"- {r['title']}: {r['snippet']}" for r in results]
    return "\n".join(lines)