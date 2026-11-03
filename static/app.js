// Belajar bersama Alma — logika frontend
const state = {
  documents: [],
  datasets: [],
  allText: "",
};

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- helper
let overlayTimer = null;

function showOverlay(messages = ["Tunggu ya, Alma lagi menyiapkan…"]) {
  $("overlay").classList.remove("hidden");
  if (Array.isArray(messages)) {
    let i = 0;
    const set = () => {
      $("overlay-text").textContent = messages[i % messages.length];
      i++;
    };
    set();
    overlayTimer = setInterval(set, 2200);
  } else {
    $("overlay-text").textContent = messages;
  }
}
function hideOverlay() {
  if (overlayTimer) { clearInterval(overlayTimer); overlayTimer = null; }
  $("overlay").classList.add("hidden");
}
function toast(msg, type = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast " + type;
  setTimeout(() => t.classList.add("hidden"), 3200);
}
function setStatus(el, msg, type) {
  el.textContent = msg;
  el.className = "status " + type;
  el.classList.remove("hidden");
}
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Kesalahan tidak diketahui.");
  return data;
}

// ---------------------------------------------------------------- escape & markdown
function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function md(text) {
  const lines = String(text).split("\n");
  let html = "";
  let listOpen = null; // "ul" | "ol"

  const closeList = () => { if (listOpen) { html += `</${listOpen}>`; listOpen = null; } };
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { closeList(); continue; }

    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      closeList();
      const level = h[1].length;
      html += `<h${level}>${inline(esc(h[2]))}</h${level}>`;
      continue;
    }

    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    if (bullet) {
      if (listOpen !== "ul") { closeList(); html += "<ul>"; listOpen = "ul"; }
      html += `<li>${inline(esc(bullet[1]))}</li>`;
      continue;
    }

    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (numbered) {
      if (listOpen !== "ol") { closeList(); html += "<ol>"; listOpen = "ol"; }
      html += `<li>${inline(esc(numbered[1]))}</li>`;
      continue;
    }

    closeList();
    html += `<p>${inline(esc(line))}</p>`;
  }
  closeList();
  return html;
}

// ---------------------------------------------------------------- tabs
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  $("tab-" + name).classList.add("active");
  document.querySelector(`.tab-btn[data-tab="${name}"]`).classList.add("active");
}

function enableTabs() {
  $("btn-ringkasan").disabled = false;
  $("btn-kuis").disabled = false;
  if (state.datasets.length) $("btn-rekap").disabled = false;
}

// ---------------------------------------------------------------- bahan (upload)
let selectedFiles = [];

function addFiles(files) {
  for (const f of files) selectedFiles.push(f);
  renderFileList();
}

function renderFileList() {
  const list = $("file-list");
  list.innerHTML = "";
  selectedFiles.forEach((f, i) => {
    const div = document.createElement("div");
    div.className = "file-item";
    const name = document.createElement("span");
    name.textContent = f.name;
    const del = document.createElement("button");
    del.textContent = "✕";
    del.title = "Hapus";
    del.onclick = (e) => { e.stopPropagation(); selectedFiles.splice(i, 1); renderFileList(); };
    div.appendChild(name);
    div.appendChild(del);
    list.appendChild(div);
  });
}

async function processMaterial() {
  const url = $("url-input").value.trim();
  if (!selectedFiles.length && !url) {
    toast("Pilih dulu file atau tempel link ya.", "err");
    return;
  }
  const fd = new FormData();
  selectedFiles.forEach((f) => fd.append("files", f));
  fd.append("url", url);

  showOverlay("Membaca bahan…");
  $("btn-process").disabled = true;
  try {
    const res = await fetch("/api/extract", { method: "POST", body: fd });
    const data = await res.json();
    state.documents = data.documents || [];
    state.datasets = data.datasets || [];
    state.allText = data.all_text || "";
    renderExtraction(data);
    enableTabs();
    $("result-card").classList.remove("hidden");
    if (data.total_chars) {
      setStatus($("status"), `✅ Berhasil! ${data.total_chars.toLocaleString("id-ID")} karakter siap dipelajari.`, "ok");
    }
    toast("Bahan berhasil diproses 🎉", "ok");
  } catch (e) {
    setStatus($("status"), "❌ " + e.message, "err");
  } finally {
    $("btn-process").disabled = false;
    hideOverlay();
  }
}

function renderExtraction(data) {
  const box = $("doc-summary");
  box.innerHTML = "";
  (data.documents || []).forEach((d) => {
    const chip = document.createElement("div");
    chip.className = "doc-chip";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = (d.is_url ? "🔗 " : "📄 ") + d.name;
    const info = document.createElement("span");
    if (d.error) { info.className = "err"; info.textContent = "⚠ " + d.error; }
    else { info.className = "muted"; info.textContent = (d.char_count || 0).toLocaleString("id-ID") + " karakter"; }
    chip.appendChild(name);
    chip.appendChild(info);
    box.appendChild(chip);
  });
  (data.datasets || []).forEach((d) => {
    const chip = document.createElement("div");
    chip.className = "doc-chip";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = "📊 " + d.name;
    const info = document.createElement("span");
    info.className = "muted";
    info.textContent = `${d.shape[0]} baris × ${d.shape[1]} kolom`;
    chip.appendChild(name);
    chip.appendChild(info);
    box.appendChild(chip);
  });
  renderRecap();
}

// ---------------------------------------------------------------- ringkasan
let summaryText = "";

async function makeSummary() {
  if (!state.allText) { toast("Proses bahan dulu ya.", "err"); return; }
  const enrich = $("sum-enrich").checked;
  showOverlay([
    "Tunggu ya, Alma lagi menyiapkan…",
    "Lagi baca materinya dulu… 📖",
    "Lagi nyari poin-poin penting… 🔍",
    "Lagi susun istilah & rumus… ✍️",
    "Lagi rapikan catatannya… 📝",
  ]);
  $("btn-summary").disabled = true;
  const out = $("summary-out");
  out.classList.remove("placeholder");
  out.innerHTML = "<p class='muted'>Menyusun catatan…</p>";
  try {
    const data = await postJSON("/api/summary", { text: state.allText, enrich });
    summaryText = data.summary || "";
    out.innerHTML = md(summaryText);
    $("btn-dl-summary-docx").classList.remove("hidden");
    $("btn-dl-summary-pdf").classList.remove("hidden");
    toast("Catatan belajar jadi ✨", "ok");
  } catch (e) {
    out.innerHTML = "";
    out.classList.add("placeholder");
    out.textContent = e.message;
    toast(e.message, "err");
  } finally {
    $("btn-summary").disabled = false;
    hideOverlay();
  }
}

// ---------------------------------------------------------------- rekap data
function renderRecap() {
  const box = $("recap-out");
  const btn = $("btn-recap-ai");
  if (!state.datasets.length) {
    box.classList.add("placeholder");
    box.textContent = "Belum ada file data. Unggah file Excel/CSV di tab Bahan.";
    btn.classList.add("hidden");
    return;
  }
  box.classList.remove("placeholder");
  btn.classList.remove("hidden");
  let html = "";
  state.datasets.forEach((ds) => {
    html += `<div class="dataset"><h3>📊 ${esc(ds.name)}</h3>`;
    html += `<div class="meta">${ds.shape[0].toLocaleString("id-ID")} baris × ${ds.shape[1]} kolom</div>`;
    html += "<table class='recap'><thead><tr><th>Kolom</th><th>Tipe</th><th>Kosong</th><th>Ringkasan</th></tr></thead><tbody>";
    (ds.columns || []).forEach((c) => {
      let ringkasan = "";
      if (c.dtype === "number" && c.stats) {
        const s = c.stats;
        ringkasan = `rata ${s.mean ?? "-"} · min ${s.min ?? "-"} · maks ${s.max ?? "-"}`;
      } else if (c.top) {
        ringkasan = c.top.map(([v, n]) => `${esc(v)} (${n})`).join(", ");
      }
      html += `<tr><td><strong>${esc(c.name)}</strong></td><td>${c.dtype === "number" ? "Angka" : "Teks"}</td><td>${c.missing}</td><td>${ringkasan}</td></tr>`;
    });
    html += "</tbody></table></div>";
  });
  box.innerHTML = html;
}

async function recapExplain() {
  const text = state.datasets.map((d) => d.text).join("\n\n");
  if (!text) return;
  showOverlay("AI sedang membaca datanya…");
  try {
    const data = await postJSON("/api/summary", { text: text + "\n\nJelaskan isi dan insight dari data ini." });
    const box = $("recap-out");
    box.insertAdjacentHTML("beforeend", `<div class="md-out">${md(data.summary)}</div>`);
    toast("Penjelasan data jadi ✨", "ok");
  } catch (e) {
    toast(e.message, "err");
  } finally {
    hideOverlay();
  }
}

// ---------------------------------------------------------------- kuis
let quizData = [];

async function makeQuiz() {
  if (!state.allText) { toast("Proses bahan dulu ya.", "err"); return; }
  const enrich = $("quiz-enrich").checked;
  showOverlay([
    "Tunggu ya, Alma lagi menyiapkan…",
    "Lagi baca materinya dulu… 📖",
    "Lagi nyusun soal pilihan ganda… 🔍",
    "Lagi bikin soal esai… ✍️",
    "Lagi cek jawaban & penjelasannya… ✅",
  ]);
  $("btn-quiz").disabled = true;
  const out = $("quiz-out");
  out.classList.remove("placeholder");
  out.innerHTML = "<p class='muted'>Menyusun soal…</p>";
  try {
    const data = await postJSON("/api/quiz", { text: state.allText, enrich });
    quizData = data.questions || [];
    renderQuiz();
    $("btn-dl-quiz-docx").classList.remove("hidden");
    $("btn-dl-quiz-pdf").classList.remove("hidden");
    const mc = quizData.filter((q) => q.type === "mc").length;
    const es = quizData.length - mc;
    toast(`${quizData.length} soal jadi (${mc} PG + ${es} esai) 🎉`, "ok");
  } catch (e) {
    out.innerHTML = "";
    out.classList.add("placeholder");
    out.textContent = e.message;
    toast(e.message, "err");
  } finally {
    $("btn-quiz").disabled = false;
    hideOverlay();
  }
}

function renderQuiz() {
  const out = $("quiz-out");
  const mcCount = quizData.filter((q) => q.type === "mc").length;
  const esCount = quizData.length - mcCount;
  let html = `<div class="quiz-head">🧠 <strong>${quizData.length} soal</strong> dibuat otomatis — ${mcCount} pilihan ganda + ${esCount} esai</div>`;
  quizData.forEach((q, qi) => {
    const isMC = q.type === "mc" && Array.isArray(q.pilihan) && q.pilihan.length > 0;
    const tag = isMC ? "Pilihan Ganda" : "Esai";
    html += `<div class="q" data-q="${qi}">`;
    html += `<div class="q-text">${qi + 1}. ${esc(q.pertanyaan || "(tanpa pertanyaan)")} <span class="q-type">${tag}</span></div>`;
    if (isMC) {
      html += "<ul class='q-opts'>";
      q.pilihan.forEach((opt, oi) => {
        html += `<li data-oi="${oi}">${esc(opt)}</li>`;
      });
      html += "</ul>";
    }
    html += `<button class="toggle-ans" onclick="toggleAnswer(${qi})">Lihat Jawaban</button>`;
    html += `<div class="q-ans" id="ans-${qi}">`;
    html += `<div class="lbl">✅ Jawaban: ${esc(q.jawaban ?? "-")}</div>`;
    if (q.penjelasan) html += `<div style="margin-top:6px">${esc(q.penjelasan)}</div>`;
    html += "</div></div>";
  });
  out.innerHTML = html;

  out.querySelectorAll(".q-opts li").forEach((li) => {
    li.addEventListener("click", () => {
      const qIdx = parseInt(li.closest(".q").dataset.q, 10);
      const oi = parseInt(li.dataset.oi, 10);
      markAnswer(qIdx, oi);
    });
  });
}

function markAnswer(qIdx, oi) {
  const q = quizData[qIdx];
  const card = document.querySelector(`.q[data-q="${qIdx}"]`);
  const lis = card.querySelectorAll(".q-opts li");
  // reset
  lis.forEach((li, i) => { li.classList.remove("picked", "correct", "wrong"); });
  const chosen = lis[oi];
  chosen.classList.add("picked");

  // bandingkan dengan jawaban (huruf / isi)
  const ans = String(q.jawaban ?? "").trim();
  const isCorrect =
    ans === oi ||
    ans === String.fromCharCode(65 + oi) ||
    ((q.pilihan[oi] || "").trim() === ans);

  chosen.classList.remove("picked");
  chosen.classList.add(isCorrect ? "correct" : "wrong");
  if (!isCorrect) {
    // tandai jawaban benar
    let correctIdx = ans;
    if (/^[A-Da-d]$/.test(ans)) correctIdx = ans.toUpperCase().charCodeAt(0) - 65;
    else correctIdx = (q.pilihan || []).findIndex((p) => p.trim() === ans);
    if (Number.isInteger(correctIdx) && lis[correctIdx]) lis[correctIdx].classList.add("correct");
  }
}

function toggleAnswer(qIdx) {
  const ans = $("ans-" + qIdx);
  ans.classList.toggle("show");
}

// ---------------------------------------------------------------- download
function downloadText(filename, text) {
  const blob = new Blob(["\uFEFF" + text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function downloadExport(content, format, filename) {
  const res = await fetch("/api/export", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, format, filename }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Export gagal.");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadSummary(format) {
  if (!summaryText) { toast("Buat catatan dulu ya.", "err"); return; }
  downloadExport(summaryText, format, "catatan-belajar")
    .then(() => toast("Catatan berhasil di-download.", "ok"))
    .catch((e) => toast(e.message, "err"));
}

function quizToMarkdown(withAnswers) {
  let out = "# Soal Latihan — Alma\n\n";
  quizData.forEach((q, i) => {
    const t = q.type === "mc" ? "Pilihan Ganda" : "Esai";
    out += `## ${i + 1}. [${t}] ${q.pertanyaan || "(tanpa pertanyaan)"}\n\n`;
    if (q.type === "mc" && Array.isArray(q.pilihan)) {
      q.pilihan.forEach((p, oi) => { out += `- ${String.fromCharCode(65 + oi)}. ${p}\n`; });
      out += "\n";
    }
    if (withAnswers) {
      out += `**Jawaban:** ${q.jawaban || "-"}\n\n`;
      if (q.penjelasan) out += `**Penjelasan:** ${q.penjelasan}\n\n`;
    }
  });
  return out;
}

function downloadQuiz(format) {
  if (!quizData.length) { toast("Buat soal dulu ya.", "err"); return; }
  downloadExport(quizToMarkdown(true), format, "soal-dan-jawaban")
    .then(() => toast("Soal dan jawaban berhasil di-download.", "ok"))
    .catch((e) => toast(e.message, "err"));
}

// ---------------------------------------------------------------- pengaturan
async function loadSettings() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    $("cfg-base").value = cfg.base_url || "";
    $("cfg-key").value = cfg.api_key || "";
    const models = cfg.models && cfg.models.length ? cfg.models : ["deepseek-v4-flash", "deepseek-v4-pro"];
    fillSelect("cfg-model-summary", models, cfg.model_summary || models[0]);
    fillSelect("cfg-model-quiz", models, cfg.model_quiz || models[0]);
  } catch (e) { /* abaikan */ }
}

function fillSelect(id, options, selected) {
  const sel = $(id);
  sel.innerHTML = "";
  options.forEach((m) => {
    const o = document.createElement("option");
    o.value = m;
    o.textContent = m;
    if (m === selected) o.selected = true;
    sel.appendChild(o);
  });
}

async function saveSettings() {
  const body = {
    base_url: $("cfg-base").value.trim(),
    api_key: $("cfg-key").value.trim(),
    model_summary: $("cfg-model-summary").value,
    model_quiz: $("cfg-model-quiz").value,
  };
  try {
    await postJSON("/api/config", body);
    setStatus($("cfg-status"), "✅ Tersimpan.", "ok");
    toast("Pengaturan tersimpan 💾", "ok");
  } catch (e) {
    setStatus($("cfg-status"), "❌ " + e.message, "err");
  }
}

async function testConnection() {
  await saveSettings();
  const st = $("cfg-status");
  setStatus(st, "⏳ Menghubungi server API…", "info");
  try {
    const res = await fetch("/api/test_connection", { method: "POST" });
    const data = await res.json();
    if (data.ok) setStatus(st, "✅ Koneksi berhasil! Balasan: " + data.reply, "ok");
    else setStatus(st, "❌ " + data.error, "err");
  } catch (e) {
    setStatus(st, "❌ " + e.message, "err");
  }
}

// ---------------------------------------------------------------- init
function init() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  const dz = $("dropzone");
  const fi = $("file-input");
  dz.addEventListener("click", () => fi.click());
  fi.addEventListener("change", () => addFiles(Array.from(fi.files)));
  ["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => {
    e.preventDefault(); dz.classList.remove("drag");
  }));
  dz.addEventListener("drop", (e) => addFiles(Array.from(e.dataTransfer.files)));

  $("btn-process").addEventListener("click", processMaterial);
  $("btn-summary").addEventListener("click", makeSummary);
  $("btn-quiz").addEventListener("click", makeQuiz);
  $("btn-recap-ai").addEventListener("click", recapExplain);
  $("btn-save-cfg").addEventListener("click", saveSettings);
  $("btn-test-cfg").addEventListener("click", testConnection);
  $("btn-dl-summary-docx").addEventListener("click", () => downloadSummary("docx"));
  $("btn-dl-summary-pdf").addEventListener("click", () => downloadSummary("pdf"));
  $("btn-dl-quiz-docx").addEventListener("click", () => downloadQuiz("docx"));
  $("btn-dl-quiz-pdf").addEventListener("click", () => downloadQuiz("pdf"));

  loadSettings();
}

document.addEventListener("DOMContentLoaded", init);
