/* Klien web vnswap — vanilla JS, tanpa dependensi. Marker ASCII, tanpa emoji. */
const $ = (id) => document.getElementById(id);
const state = {
  targets: [], sources: [],
  target: null, source: null, sourcePath: "",
  channels: 1, dryRun: false,
  jobId: null, poll: null,
  shared: "",
};

/* token API (mode LAN): ?token= di URL, diingat per tab. */
const TOKEN = (() => {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) { try { sessionStorage.setItem("vnswap-token", fromUrl); } catch (e) {} return fromUrl; }
  try { return sessionStorage.getItem("vnswap-token") || ""; } catch (e) { return ""; }
})();

function fileUrl(endpoint, filePath) {
  const q = new URLSearchParams({ path: filePath });
  if (TOKEN) q.set("token", TOKEN);
  return endpoint + "?" + q.toString();
}

async function api(path, opts) {
  if (TOKEN && path.startsWith("/api/")) {
    path += (path.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(TOKEN);
  }
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) throw new Error(j.error || "butuh token — buka URL lengkap dari terminal.");
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}

async function copyFix(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (_e) {}
    ta.remove();
  }
  if (btn) {
    const old = btn.textContent;
    btn.textContent = "Disalin";
    setTimeout(() => { btn.textContent = old; }, 1200);
  }
}

function go(n) {
  for (let i = 1; i <= 4; i++) {
    $("step-" + i).classList.toggle("hidden", i !== n);
    document.querySelectorAll('#stepper button').forEach((b) => {
      const s = Number(b.dataset.step);
      b.classList.toggle("active", s === n);
      b.classList.toggle("done", s < n);
    });
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}
document.querySelectorAll('#stepper button').forEach((b) =>
  b.addEventListener("click", () => {
    const s = Number(b.dataset.step);
    if (s === 4) return; // proses hanya lewat swap
    if (s === 2 && !state.target) return;
    if (s === 3 && (!state.target || !state.sourcePath)) return;
    go(s);
  }));

async function refreshHealth() {
  try {
    const h = await api("/api/health");
    state.shared = h.shared_dir;
    $("shared-input").value = "";
    const sel = $("shared-select");
    if (sel && sel.options.length &&
        [...sel.options].some((o) => o.value === h.shared_dir)) {
      sel.value = h.shared_dir;
    }
    $("foot-shared").textContent = h.shared_dir;
    if (h.version) $("foot-ver").textContent = "v" + h.version;
    $("shared-current").textContent = h.shared_dir || "otomatis";
    if (!h.shared_exists) $("shared-card").open = true;
    $("shared-hint").textContent = h.shared_exists ? "" : "[!!] folder tidak ada";
    const ok = h.ffmpeg_ok && h.shared_exists;
    $("health-dot").className = "dot " + (ok ? "ok" : "bad");
    $("health-text").textContent =
      (h.ffmpeg_ok ? "[OK] ffmpeg" : "[XX] ffmpeg hilang") +
      " · " + h.targets + " target · " + h.sources + " sumber";
    // Banner kesehatan awal: daftar cek gagal + perintah perbaikan.
    const hb = $("health-banner");
    const failed = (h.checks || []).filter((c) => !c.ok);
    if (hb) {
      if (!failed.length) {
        hb.classList.add("hidden");
        hb.innerHTML = "";
      } else {
        hb.classList.remove("hidden");
        hb.innerHTML = "";
        const title = document.createElement("div");
        title.className = "banner-title";
        title.textContent = "[!!] Pemeriksaan kesehatan (" + failed.length + " masalah)";
        const ul = document.createElement("ul");
        ul.className = "health-list";
        ul.id = "health-list";
        failed.slice(0, 5).forEach((c) => {
          const li = document.createElement("li");
          const label = document.createElement("div");
          label.className = "health-label";
          label.textContent = "[XX] " + c.label;
          li.appendChild(label);
          const detail = document.createElement("div");
          detail.className = "health-detail";
          detail.textContent = c.detail;
          li.appendChild(detail);
          if (c.fix) {
            const row = document.createElement("div");
            row.className = "fix-row";
            const code = document.createElement("code");
            code.textContent = c.fix;
            const btn = document.createElement("button");
            btn.className = "fix-copy";
            btn.type = "button";
            btn.textContent = "Salin";
            btn.addEventListener("click", () => copyFix(c.fix, btn));
            row.appendChild(code);
            row.appendChild(btn);
            li.appendChild(row);
          }
          ul.appendChild(li);
        });
        const foot = document.createElement("div");
        foot.className = "health-foot";
        foot.textContent = "Detail penuh: jalankan `vnswap health` di Termux.";
        hb.appendChild(title);
        hb.appendChild(ul);
        hb.appendChild(foot);
      }
    }
  } catch (e) {
    $("health-dot").className = "dot bad";
    $("health-text").textContent = "[XX] " + (e.message || "server tidak merespons");
  }
}

async function loadCandidates() {
  let j = null;
  try { j = await api("/api/shared-candidates"); } catch (e) { return; }
  const sel = $("shared-select");
  sel.innerHTML = "";
  j.candidates.forEach((c) => {
    const o = document.createElement("option");
    o.value = c.path;
    o.textContent = c.path + " (" + c.targets + " target)";
    sel.appendChild(o);
  });
  if (j.selected) {
    if (![...sel.options].some((o) => o.value === j.selected)) {
      const o = document.createElement("option");
      o.value = j.selected;
      o.textContent = j.selected + " (0 target)";
      sel.appendChild(o);
    }
    sel.value = j.selected;
  }
  if (!j.candidates.length) {
    $("shared-hint").textContent = "[!!] .Shared tidak terdeteksi — putar satu VN di WhatsApp lalu Pindai Ulang, atau isi path manual.";
    $("shared-card").open = true;
  } else if (j.selected) {
    $("shared-current").textContent = j.selected;
  }
}

/* ---- langkah 1: target ---- */
async function loadTargets() {
  const tb = document.querySelector("#target-table tbody");
  let data;
  try {
    const q = state.shared ? ("?shared=" + encodeURIComponent(state.shared)) : "";
    data = await api("/api/targets" + q);
  } catch (e) {
    tb.innerHTML = "";
    const empty = $("target-empty");
    empty.classList.remove("hidden");
    empty.textContent = "[XX] gagal memuat target: " + e.message + "\nPath: " + (state.shared || "-");
    return;
  }
  const { targets, shared_dir } = data;
  state.targets = targets;
  if (shared_dir) { state.shared = shared_dir; $("foot-shared").textContent = shared_dir; }
  const needle = $("target-filter").value.trim().toLowerCase();
  const rows = targets.filter((t) =>
    !needle || t.name.toLowerCase().includes(needle) || t.base_name.toLowerCase().includes(needle));
  tb.innerHTML = "";
  $("target-empty").classList.toggle("hidden", targets.length > 0);
  if (!targets.length) {
    $("target-empty").textContent =
      "Belum ada target di folder .Shared\n1. Buka WhatsApp, putar satu voice note\n2. Kembali ke sini, tekan Pindai Ulang\nPath: " + state.shared;
  }
  rows.slice(0, 50).forEach((t) => {
    const tr = document.createElement("tr");
    if (state.target && state.target.path === t.path) tr.className = "sel";
    tr.innerHTML = "<td class='mark'>" + (state.target && state.target.path === t.path ? "[x]" : "[ ]") + "</td>" +
      "<td class='name" + "' data-label='Nama' title='" + esc(t.name) + "'>" + esc(t.short_name) + "</td>" +
      "<td data-label='Durasi'>" + esc(t.duration_str) + "</td>" +
      "<td data-label='Lama'>" + esc(t.rel) + "</td>" +
      "<td data-label='Ukuran'>" + esc(t.size_str) + "</td>" +
      "<td data-label='Status'>" + (t.has_opus ? "[OK] opus" : "[--] tanpa opus") + "</td>";
    tr.addEventListener("click", () => { state.target = t; paintTargets(); paintSourceContext(); });
    tr.addEventListener("dblclick", () => { if (state.target) { loadSources(); go(2); } });
    tb.appendChild(tr);
  });
  if (!state.target && targets.length) state.target = targets[0];
  paintSourceContext();
}
function paintTargets() { loadTargets().catch(() => {}); }

/* ---- langkah 2: sumber ---- */
async function loadSources() {
  const { sources } = await api("/api/sources");
  state.sources = sources;
  paintSources();
  paintSourceContext();
}
function paintSources() {
  const needle = $("source-filter").value.trim().toLowerCase();
  const rows = state.sources.filter((s) =>
    !needle || s.name.toLowerCase().includes(needle));
  const tb = document.querySelector("#source-table tbody");
  tb.innerHTML = "";
  const manual = $("manual-path").value.trim();
  if (!rows.length && !manual) {
    const tr = document.createElement("tr");
    tr.innerHTML = "<td class='mark' data-label='Pilih'>--</td>" +
      "<td class='name' data-label='Nama'>Upload file atau ketik path manual</td>" +
      "<td data-label='Tipe'>--</td><td data-label='Ukuran'>--</td>";
    tb.appendChild(tr);
    return;
  }
  rows.slice(0, 60).forEach((s) => {
    const tr = document.createElement("tr");
    if (state.sourcePath === s.path) tr.className = "sel";
    tr.innerHTML = "<td class='mark'>" + (state.sourcePath === s.path ? "[x]" : "[ ]") + "</td>" +
      "<td class='name' data-label='Nama' title='" + esc(s.path) + "'>" + esc(s.name) + (s.uploaded ? " (unggahan)" : "") + "</td>" +
      "<td data-label='Tipe'>" + esc(s.tag) + "</td>" +
      "<td data-label='Ukuran'>" + esc(s.size_str) + "</td>";
    tr.addEventListener("click", () => {
      state.source = s; state.sourcePath = s.path;
      $("manual-path").value = "";
      paintSources(); checkManual();
    });
    tr.addEventListener("dblclick", () => { refreshConfirm(); go(3); });
    tb.appendChild(tr);
  });
  if (!state.sourcePath && state.sources.length) {
    state.source = state.sources[0];
    state.sourcePath = state.sources[0].path;
    paintSources();
  }
}
function paintSourceContext() {
  $("source-context").textContent = state.target
    ? ("Target: " + state.target.short_name + " (" + state.target.duration_str + ")")
    : "—";
}
function checkManual() {
  const v = $("manual-path").value.trim();
  const el = $("manual-status");
  if (!v) { el.textContent = ""; el.className = "manual-status"; return; }
  state.sourcePath = v;
  state.source = { name: v.split(/[\\/]/).pop(), path: v, size_str: "?", tag: "?" };
  // petunjuk ringan lewat kecocokan daftar sumber
  const known = state.sources.find((s) => s.path === v);
  if (known) { el.textContent = "[OK] file ada di daftar sumber"; el.className = "manual-status ok"; }
  else { el.textContent = "[!!] path manual — dicek saat proses berjalan"; el.className = "manual-status warn"; }
  paintSources();
}

/* bagian upload */
async function uploadFile(f) {
  const fd = new FormData();
  fd.append("file", f, f.name);
  $("manual-status").textContent = "[info] upload berjalan…";
  const upUrl = TOKEN ? ("/api/upload?token=" + encodeURIComponent(TOKEN)) : "/api/upload";
  const r = await fetch(upUrl, { method: "POST", body: fd });
  const j = await r.json();
  if (r.status === 401) throw new Error(j.error || "butuh token.");
  if (!r.ok) throw new Error(j.error || "upload gagal");
  state.source = { name: j.name, path: j.path, size_str: j.size_str, tag: "upload" };
  state.sourcePath = j.path;
  await loadSources();
  state.sourcePath = j.path;
  paintSources();
  $("manual-status").textContent = "[OK] upload: " + j.name + " (" + j.size_str + ")" +
    (j.warning ? " — " + j.warning : "");
  $("manual-status").className = "manual-status ok";
}

/* ---- langkah 3: cek ---- */
function drawWave(bars, id, color) {
  const cv = $(id || "wave");
  // samakan resolusi kanvas dengan lebar layar x DPR agar tajam di HP
  const dpr = Math.min(3, window.devicePixelRatio || 1);
  const cw = cv.clientWidth || 640, chh = 96;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(chh * dpr)) {
    cv.width = Math.round(cw * dpr);
    cv.height = Math.round(chh * dpr);
  }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cw, chh);
  if (!bars || !bars.length) return;
  const n = bars.length;
  const bw = Math.max(1, cw / n - 1);
  ctx.fillStyle = color || "#CBA6F7";
  bars.forEach((v, i) => {
    const h = Math.max(2, (Math.min(100, v) / 100) * (chh - 8));
    const x = Math.round(i * (cw / n));
    const w = Math.max(1, Math.round(bw));
    const y = Math.round((chh - h) / 2);
    ctx.fillRect(x, y, w, Math.round(h));
  });
}
async function refreshConfirm() {
  const t = state.target;
  $("confirm-target").textContent = t
    ? ("TARGET\n" + t.name + "\n" + t.duration_str + ", " + t.size_str + "\n" +
       (t.has_opus ? "[OK] opus pendamping ada" : "[--] tanpa opus"))
    : "TARGET\n--";
  const sp = state.sourcePath;
  state.lastTargetBars = null;
  state.lastSourceBars = null;
  $("confirm-source").textContent = sp
    ? ("SUMBER\n" + (state.source ? state.source.name : sp.split(/[\\/]/).pop()) + "\n" + sp)
    : "SUMBER\n--";
  // gelombang
  if (t) {
    try {
      const j = await api("/api/bars?path=" + encodeURIComponent(t.path));
      drawWave(j.bars, "wave", "#CBA6F7");
      state.lastTargetBars = j.bars;
      const glyphs = " .-=+#";
      const vals = j.bars.filter((_, i) => i % Math.max(1, Math.floor(j.bars.length / 40)) === 0).slice(0, 40);
      $("wave-ascii").textContent = "Pola: " + vals.map((v) =>
        glyphs[Math.min(glyphs.length - 1, Math.floor(v * glyphs.length / 101))]).join("");
      // heuristik ukuran mencerminkan TUI
      const src = state.sources.find((s) => s.path === sp);
      if (src && t.length > 0 && src.size > t.length * 1024 * 20) {
        $("size-warn").textContent = "[!!] Sumber jauh lebih besar dari target. Audio akan dipadatkan ke sidecar target.";
        $("size-warn").classList.remove("hidden");
      } else $("size-warn").classList.add("hidden");
    } catch (e) {
      $("wave-ascii").textContent = "pola tidak terbaca: " + e.message;
    }
  }
  // preview sumber vs target + pemutar audio
  const topus = t && t.opus_path;
  $("aud-target").src = topus ? fileUrl("/api/audio", topus) : "";
  $("aud-target").style.display = topus ? "" : "none";
  const sext = ((sp.split(".").pop()) || "").toLowerCase();
  const isVid = ["mp4", "m4v", "mov", "mkv", "3gp", "webm"].includes(sext);
  $("aud-source").classList.toggle("hidden", !sp || isVid);
  $("vid-source").classList.toggle("hidden", !sp || !isVid);
  if (sp) ((isVid ? $("vid-source") : $("aud-source"))).src = fileUrl("/api/audio", sp);
  if (t && sp) {
    try {
      const pv = await api("/api/preview?target=" + encodeURIComponent(t.path) +
        "&source=" + encodeURIComponent(sp));
      drawWave(pv.source_bars, "wave-src", "#94E2D5");
      state.lastSourceBars = pv.source_bars;
      $("preview-info").textContent = "Sumber: " + pv.source_bars_raw + " bar (" +
        pv.source_duration_str + ") -> " + pv.target_length + " bar target.";
    } catch (e) {
      drawWave([], "wave-src");
      $("preview-info").textContent = "preview sumber: " + e.message;
    }
  } else {
    drawWave([], "wave-src");
    $("preview-info").textContent = "";
  }
  const plan = await api("/api/plan?channels=" + state.channels).catch(() => null);
  const recipe = plan ? ("opus " + plan.bitrate + " " + plan.application + " " + plan.label) : "opus";
  const banner = $("mode-banner");
  if (state.dryRun) {
    banner.textContent = "Mode: PREVIEW - tidak ubah file\nResep: " + recipe;
    banner.className = "banner";
  } else {
    banner.textContent = "Mode: TULIS LANGSUNG + backup .bak otomatis\nResep: " + recipe;
    banner.className = "banner danger";
  }
}

/* ---- langkah 4: jalan ---- */
function paintStages(stages) {
  document.querySelectorAll("#stages li").forEach((li) => {
    const s = stages[Number(li.dataset.i)] || "todo";
    li.className = s;
  });
}
function logLine(l) {
  const el = $("log");
  el.textContent += "[" + l.level + "] " + l.msg + "\n";
  el.scrollTop = el.scrollHeight;
}
async function pollJob() {
  try {
    const j = await api("/api/jobs/" + state.jobId);
    $("bar").style.width = j.progress + "%";
    $("percent").textContent = j.progress + "%";
    paintStages(j.stages);
    const el = $("log");
    const seen = Number(el.dataset.n || 0);
    j.logs.slice(seen).forEach(logLine);
    el.dataset.n = j.logs.length;
    if (j.status === "done" || j.status === "error") {
      clearInterval(state.poll); state.poll = null;
      const rc = $("result-card");
      rc.classList.remove("hidden");
      if (j.status === "done" && j.result) {
        const r = j.result;
        rc.className = "banner ok";
        rc.textContent = r.mode === "preview"
          ? ("[OK] PREVIEW selesai - tidak ada file diubah.\nVendor: " + (r.vendor || "tak terbaca"))
          : ("[OK] TERTUKAR: " + r.opus_path.split(/[\\/]/).pop() +
             "\nBackup opus: " + (r.backup_opus || "--") +
             "\nBackup data: " + (r.backup_data || "--") +
             "\nBuka WhatsApp dan putar VN untuk verifikasi.");
        $("rollback").disabled = !r.backup_opus;
      } else {
        rc.className = "banner danger";
        rc.textContent = "[XX] " + (j.error || "gagal.");
        $("rollback").disabled = !(j.result && j.result.backup_opus);
      }
    }
  } catch (e) {
    // tetap polling saat galat sementara
  }
}
async function startSwap() {
  if (!state.target || !state.sourcePath) return;
  $("log").textContent = ""; $("log").dataset.n = 0;
  $("bar").style.width = "0%"; $("percent").textContent = "0%";
  paintStages(["todo", "todo", "todo", "todo"]);
  $("result-card").classList.add("hidden");
  $("rollback").disabled = true;
  go(4);
  const body = {
    target: state.target.path, source: state.sourcePath,
    channels: state.channels, dry_run: state.dryRun,
  };
  const { id } = await api("/api/jobs", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch((e) => { 
    $("result-card").classList.remove("hidden");
    $("result-card").className = "banner danger";
    $("result-card").textContent = "[XX] " + e.message;
    throw e;
  });
  state.jobId = id;
  if (state.poll) clearInterval(state.poll);
  state.poll = setInterval(pollJob, 800);
  pollJob();
}

/* ---- event ---- */
$("target-filter").addEventListener("input", () => loadTargets().catch(() => {}));
$("target-rescan").addEventListener("click", () => {
  loadCandidates().catch(() => {});
  loadTargets().catch(() => {});
  refreshHealth();
});
$("source-filter").addEventListener("input", paintSources);
$("manual-path").addEventListener("input", checkManual);
$("upload").addEventListener("change", async (e) => {
  if (e.target.files[0]) { await uploadFile(e.target.files[0]).catch((err) => {
    $("manual-status").textContent = "[XX] " + err.message;
    $("manual-status").className = "manual-status"; }); }
  e.target.value = "";
});
const dz = $("dropzone");
["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
dz.addEventListener("drop", async (e) => {
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) await uploadFile(f).catch((err) => { $("manual-status").textContent = "[XX] " + err.message; });
});
dz.addEventListener("click", () => $("upload").click());
dz.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("upload").click(); }
});
let resizeT = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => {
    if ($("step-3").classList.contains("hidden")) return;
    if (state.lastTargetBars) drawWave(state.lastTargetBars, "wave", "#CBA6F7");
    if (state.lastSourceBars) drawWave(state.lastSourceBars, "wave-src", "#94E2D5");
  }, 150);
});
document.querySelectorAll('input[name=mode]').forEach((r) =>
  r.addEventListener("change", () => {
    state.dryRun = document.querySelector('input[name=mode]:checked').value === "preview";
    refreshConfirm();
  }));
document.querySelectorAll('input[name=channels]').forEach((r) =>
  r.addEventListener("change", () => {
    state.channels = Number(document.querySelector('input[name=channels]:checked').value) === 2 ? 2 : 1;
    refreshConfirm();
  }));
$("shared-apply").addEventListener("click", () => {
  const manual = $("shared-input").value.trim();
  state.shared = manual || $("shared-select").value || state.shared;
  loadTargets().catch(() => {}); refreshHealth();
  loadCandidates().catch(() => {});
});
$("to-2").addEventListener("click", () => { if (state.target) { loadSources(); go(2); } });
$("back-1").addEventListener("click", () => go(1));
$("to-3").addEventListener("click", () => {
  const manual = $("manual-path").value.trim();
  if (manual) { state.sourcePath = manual; }
  if (state.sourcePath) { refreshConfirm(); go(3); }
});
$("back-2").addEventListener("click", () => go(2));
$("swap-now").addEventListener("click", startSwap);
$("rollback").addEventListener("click", async () => {
  if (!state.jobId) return;
  try {
    const j = await api("/api/jobs/" + state.jobId + "/rollback", { method: "POST" });
    $("log").textContent += "[warn] rollback selesai: " + (j.restored || []).join(", ") + "\n";
  } catch (e) { $("log").textContent += "[error] rollback gagal: " + e.message + "\n"; }
});
$("again").addEventListener("click", () => {
  state.target = null; state.source = null; state.sourcePath = "";
  $("manual-path").value = ""; $("target-filter").value = ""; $("source-filter").value = "";
  loadTargets().catch(() => {}); go(1);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && document.activeElement && document.activeElement.tagName !== "INPUT") {
    if (!$("step-1").classList.contains("hidden")) $("to-2").click();
    else if (!$("step-3").classList.contains("hidden")) $("swap-now").click();
  }
});

/* mulai */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
refreshHealth().then(() => {
  loadCandidates().catch(() => {});
  loadTargets().catch(() => {});
}).catch(() => {});
