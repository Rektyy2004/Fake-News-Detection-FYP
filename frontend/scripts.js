const urlInput = document.getElementById("urlInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeBtnText = document.getElementById("analyzeBtnText");
const analyzeBtnSpinner = document.getElementById("analyzeBtnSpinner");
const loadingBar = document.getElementById("loadingBar");
const loadingBarInner = document.getElementById("loadingBarInner");

const resultBox = document.getElementById("resultBox");
const statusMsg = document.getElementById("statusMsg");

const historyBtn = document.getElementById("historyBtn");
const historySidebar = document.getElementById("historySidebar");
const closeSidebarBtn = document.getElementById("closeSidebarBtn");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const historyList = document.getElementById("historyList");
const clearHistoryBtn = document.getElementById("clearHistoryBtn");

// Snapshot
const historyModal = document.getElementById("historyModal");
const historyModalCloseBtn = document.getElementById("historyModalCloseBtn");
const historyModalTitle = document.getElementById("historyModalTitle");
const historyModalMeta = document.getElementById("historyModalMeta");
const historyModalImg = document.getElementById("historyModalImg");
const historyModalImgFallback = document.getElementById("historyModalImgFallback");
const historyModalOverlay = document.getElementById("historyModalOverlay");
const historyModalOpenLink = document.getElementById("historyModalOpenLink");
const historyModalRestoreBtn = document.getElementById("historyModalRestoreBtn");

const API_BASE = "http://127.0.0.1:8000";

// Theme Mode
const THEME_KEY = "fnc_theme";
const themeToggle = document.getElementById("themeToggle");

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.classList.toggle("dark", isDark);
  const icon = themeToggle.querySelector(".material-symbols-outlined");
  if (icon) icon.textContent = isDark ? "light_mode" : "dark_mode";
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || "light";
  applyTheme(saved);
}

themeToggle.addEventListener("click", () => {
  const isDark = document.documentElement.classList.contains("dark");
  const next = isDark ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

initTheme();

// Helpers
const getTimeAgo = (date) => {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
};

const safeText = (x) => (x === null || x === undefined ? "" : String(x));

const toPercentNumber = (x) => {
  const n = Number(x);
  if (Number.isNaN(n)) return 0;
  let pct = n <= 1 ? n * 100 : n;
  pct = Math.max(0, Math.min(100, pct));
  return pct;
};

const formatPercent = (x, digits = 0) => {
  const pct = toPercentNumber(x);
  return `${pct.toFixed(digits)}%`;
};

const getLabelColor = (label) => {
  if (!label) return "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200";
  const low = label.toLowerCase();
  if (low.includes("likely real") || low.includes("probably real") || low.includes("real")) {
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200";
  }
  if (low.includes("likely fake") || low.includes("probably fake") || low.includes("fake")) {
    return "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200";
  }
  return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200";
};

const statusBadge = (status) => {
  const s = (status || "").toLowerCase();
  if (s === "pass") return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200";
  if (s === "fail") return "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200";
  return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200";
};

const disclosure = (title, inner) => `
  <details class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
    <summary class="px-4 py-3 cursor-pointer select-none flex items-center justify-between bg-gray-50 dark:bg-gray-800/40">
      <span class="text-sm font-semibold">${title}</span>
      <span class="material-symbols-outlined text-[18px] text-gray-500">expand_more</span>
    </summary>
    <div class="px-4 py-3 text-sm text-gray-700 dark:text-gray-200 space-y-2">${inner}</div>
  </details>
`;

// Quick frontend block list
const QUICK_BLOCKED = [
  "facebook.com", "fb.com", "instagram.com", "tiktok.com",
  "youtube.com", "youtu.be", "twitter.com", "x.com",
  "amazon.com", "ebay.com", "reddit.com"
];

function isQuickBlockedHost(host) {
  const h = (host || "").toLowerCase().replace(/^www\./, "");
  return QUICK_BLOCKED.some((d) => h === d || h.endsWith(`.${d}`));
}

// UX: Loading state control
let hadSuccessfulAnalysis = false;

function setLoadingUI(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtn.classList.toggle("opacity-70", isLoading);
  analyzeBtn.classList.toggle("cursor-not-allowed", isLoading);

  if (analyzeBtnSpinner) analyzeBtnSpinner.classList.toggle("hidden", !isLoading);
  if (loadingBar) loadingBar.classList.toggle("hidden", !isLoading);

  if (analyzeBtnText) {
    if (isLoading) analyzeBtnText.textContent = "Analyzing…";
    else analyzeBtnText.textContent = hadSuccessfulAnalysis ? "Analyze Again" : "Analyze";
  }

  if (isLoading) {
    statusMsg.textContent = "Analyzing article credibility… Please wait.";
    statusMsg.classList.add("loading");
  } else {
    statusMsg.classList.remove("loading");
  }
}

// Render Checks
const renderCheck = (check) => {
  let extra = "";

  const checkName = safeText(check?.name || "");
  const checkNameLow = checkName.toLowerCase();

  // Evidence (Headline-Body)
  const evidenceArr = (check && (check.evidence || (check.extra && check.extra.evidence))) || [];
  if (Array.isArray(evidenceArr) && evidenceArr.length) {
    const high = evidenceArr.filter((e) => e.tier !== "low").slice(0, 3);
    const low = evidenceArr.filter((e) => e.tier === "low").slice(0, 3);

    const renderEvidenceCard = (e, tier) => {
      const snippet = safeText(e.snippet || e.text || e.paragraph || "");
      const sim = formatPercent(e.similarity, 1);
      const lex = e.lexical_similarity !== undefined ? formatPercent(e.lexical_similarity, 1) : "—";
      const sem = e.semantic_similarity !== undefined ? formatPercent(e.semantic_similarity, 1) : "—";

      const badge =
        tier === "high"
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"
          : "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200";

      const label = tier === "high" ? "Relevant" : "Least relevant";

      return `
        <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 p-3">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded-md text-[11px] font-semibold ${badge}">${label}</span>
              <span class="text-[11px] text-gray-500 dark:text-gray-400">#${safeText(e.rank ?? "")}</span>
            </div>
            <div class="text-sm font-extrabold">${sim}</div>
          </div>

          <div class="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
            Lex <span class="font-semibold">${lex}</span> • Sem <span class="font-semibold">${sem}</span>
          </div>

          <div class="mt-2 text-sm leading-relaxed text-gray-800 dark:text-gray-200 clamp-4">
            ${snippet}
          </div>
        </div>
      `;
    };

    const highHtml = high.length
      ? `
        <div class="text-xs text-gray-500 dark:text-gray-400">Top relevant segments:</div>
        <div class="mt-2 grid gap-2">
          ${high.map((e) => renderEvidenceCard(e, "high")).join("")}
        </div>
      `
      : "";

    const lowHtml = low.length
      ? `
        <div class="text-xs text-gray-500 dark:text-gray-400 mt-3">Least relevant segments:</div>
        <div class="mt-2 grid gap-2">
          ${low.map((e) => renderEvidenceCard(e, "low")).join("")}
        </div>
      `
      : "";

    extra += disclosure("Semantic similarity evidence", `${highHtml}${lowHtml}`);
  }

  // Headline Classification (informational)
  if (checkNameLow.includes("headline classification") || check?.informational) {
    const pt = safeText(check.predicted_type || "");
    const pg = check.prob_general !== undefined && check.prob_general !== null ? formatPercent(check.prob_general, 0) : "—";
    const pf = check.prob_factcheck !== undefined && check.prob_factcheck !== null ? formatPercent(check.prob_factcheck, 0) : "—";

    extra += disclosure("Classifier details", `
      <div>Predicted type: <span class="font-semibold">${pt || "—"}</span></div>
      <div class="text-xs text-gray-600 dark:text-gray-300">General news: <span class="font-semibold">${pg}</span> • Fact-check: <span class="font-semibold">${pf}</span></div>
      <div class="text-[11px] text-gray-500 dark:text-gray-400">Note: This is informational and may not affect the credibility score directly.</div>
    `);
  }

  // Domain Reputation breakdown
  if (checkNameLow.includes("domain reputation") || (check?.score !== undefined && (check?.category || check?.datasets || check?.reasons))) {
    const score = check.score !== undefined ? toPercentNumber(check.score) : null; // score is already 0-100
    const category = safeText(check.category || "");
    const reasons = Array.isArray(check.reasons) ? check.reasons : [];

    const signals = Array.isArray(check.signals_used) ? check.signals_used : [];
    const datasets = check.datasets || check.datasets || check?.datasets;

    const rankLine = (() => {
      const parts = [];
      if (check.scimago?.global_rank) parts.push(`SCImago rank <span class="font-semibold">${safeText(check.scimago.global_rank)}</span>`);
      if (check.tranco_rank) parts.push(`Tranco rank <span class="font-semibold">${safeText(check.tranco_rank)}</span>`);
      if (check.majestic?.global_rank) parts.push(`Majestic rank <span class="font-semibold">${safeText(check.majestic.global_rank)}</span>`);
      return parts.length ? `<div class="text-xs text-gray-600 dark:text-gray-300">${parts.join(" • ")}</div>` : "";
    })();

    const dsHtml = (() => {
      const ds = check.datasets;
      if (!ds || typeof ds !== "object") return "";
      const items = ["scimago", "tranco", "majestic"].map((k) => {
        const m = ds[k];
        if (!m) return "";
        const updated = m.updated ? new Date(m.updated).toLocaleString() : "—";
        const file = safeText(m.file || "—");
        const found = m.found === false ? "not found" : "found";
        return `
          <div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-900/40 p-2">
            <div class="text-xs font-semibold uppercase tracking-wide">${k}</div>
            <div class="text-[11px] text-gray-600 dark:text-gray-300">File: <span class="font-semibold">${file}</span> • ${found}</div>
            <div class="text-[11px] text-gray-500 dark:text-gray-400">Updated: ${updated}</div>
          </div>
        `;
      }).filter(Boolean).join("");
      return items ? `<div class="grid grid-cols-1 gap-2">${items}</div>` : "";
    })();

    const reasonsHtml = reasons.length
      ? `<ul class="list-disc pl-5 space-y-1">${reasons.slice(0, 10).map((r) => `<li>${safeText(r)}</li>`).join("")}</ul>`
      : `<div class="text-xs text-gray-500 dark:text-gray-400">No explanation provided.</div>`;

    extra += disclosure("Domain reputation details", `
      <div class="flex items-center justify-between">
        <div>Score: <span class="font-extrabold">${score !== null ? score.toFixed(0) : "—"}</span>/100</div>
        <div class="text-xs text-gray-500 dark:text-gray-400">${safeText(category)}</div>
      </div>
      ${signals.length ? `<div class="text-xs text-gray-600 dark:text-gray-300">Signals used: <span class="font-semibold">${signals.join(", ")}</span></div>` : ""}
      ${rankLine}
      ${check.age_days !== undefined ? `<div class="text-xs text-gray-600 dark:text-gray-300">WHOIS age (days): <span class="font-semibold">${safeText(check.age_days)}</span></div>` : ""}
      <div class="mt-2">${reasonsHtml}</div>
      ${dsHtml ? `<div class="mt-3">${dsHtml}</div>` : ""}
    `);
  }

  // Recency breakdown
  if (checkNameLow.includes("recency") || check?.age_bucket || check?.days_since !== undefined) {
    const bucket = safeText(check.age_bucket || "");
    const days = check.days_since !== undefined ? safeText(check.days_since) : "";
    const published = safeText(check.published_date || "");
    const sens = safeText(check.topic_sensitivity || "");
    if (bucket || days || published) {
      extra += disclosure("Recency details", `
        <div>Published: <span class="font-semibold">${published || "—"}</span></div>
        <div>Age: <span class="font-semibold">${days ? `${days} days` : "—"}</span> • Bucket: <span class="font-semibold">${bucket || "—"}</span></div>
        ${sens ? `<div class="text-xs text-gray-600 dark:text-gray-300">Topic sensitivity: <span class="font-semibold">${sens}</span></div>` : ""}
      `);
    }
  }

  // Cross-source sources
  const sourcesArr = (check && (check.sources || (check.extra && check.extra.sources))) || [];
  if (Array.isArray(sourcesArr) && sourcesArr.length) {
    const rows = sourcesArr.slice(0, 10).map((s) => `
      <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-900/40">
        <div class="flex items-start gap-2">
          ${s.favicon ? `<img class="w-4 h-4 mt-0.5" src="${safeText(s.favicon)}" alt="">` : ""}
          <div class="min-w-0 flex-1">
            <div class="text-sm font-semibold truncate">${safeText(s.title)}</div>
            <a class="text-xs text-primary underline truncate block" href="${safeText(s.url)}" target="_blank" rel="noopener">${safeText(s.url)}</a>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
              ${safeText(s.domain)} • similarity ${formatPercent(s.similarity, 1)}${s.provider ? ` • ${safeText(s.provider)}` : ""}
            </div>
          </div>
        </div>
      </div>
    `).join("");

    extra += disclosure("Cross-source headline matches", rows);
  }

  // Clickbait breakdown
  if (check && (check.clickbait_probability !== undefined || check.neutral_probability !== undefined)) {
    const cb = check.clickbait_probability !== undefined ? `${toPercentNumber(check.clickbait_probability).toFixed(0)}%` : "—";
    const nb = check.neutral_probability !== undefined ? `${toPercentNumber(check.neutral_probability).toFixed(0)}%` : "—";
    const why = safeText(check.explanation || "");
    const mode = safeText((check.details || "").match(/\(mode:\s*([^)]+)\)/i)?.[1] || "");

    extra += disclosure("Clickbait breakdown", `
      <div>Clickbait: <span class="font-semibold">${cb}</span> • Neutral: <span class="font-semibold">${nb}</span>${mode ? ` • Mode: <span class="font-semibold">${mode}</span>` : ""}</div>
      ${why ? `<div class="text-xs text-gray-600 dark:text-gray-300">${why}</div>` : ""}
    `);
  }

  return `
    <div class="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-sm font-bold truncate">${safeText(check.name)}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">${safeText(check.details)}</div>
        </div>
        <span class="shrink-0 px-2 py-1 rounded text-xs font-semibold ${statusBadge(check.status)}">
          ${safeText(check.status || "unknown")}
        </span>
      </div>
      ${extra ? `<div class="mt-3 space-y-3">${extra}</div>` : ""}
    </div>
  `;
};

// Snapshot Storage (localStorage)
const SNAPSHOT_KEY = "fnc_history_snapshots_v1";
const SNAPSHOT_MAX = 20;

function loadSnapshots() {
  try { return JSON.parse(localStorage.getItem(SNAPSHOT_KEY) || "{}"); }
  catch { return {}; }
}

function saveSnapshots(obj) {
  try { localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(obj)); }
  catch (e) { console.warn("Snapshot save failed (storage full?)", e); }
}

async function captureSnapshot(historyId) {
  if (!historyId || !window.html2canvas) return null;

  const node = resultBox.cloneNode(true);
  node.querySelectorAll("img").forEach((img) => img.remove());

  const holder = document.createElement("div");
  holder.style.position = "fixed";
  holder.style.left = "-99999px";
  holder.style.top = "0";
  holder.style.width = "900px";
  holder.style.padding = "16px";
  holder.style.background = document.documentElement.classList.contains("dark")
    ? "#101a22"
    : "#f6f7f8";
  holder.appendChild(node);
  document.body.appendChild(holder);

  try {
    const canvas = await html2canvas(holder, { backgroundColor: null, scale: 1 });
    return canvas.toDataURL("image/jpeg", 0.72);
  } catch (e) {
    console.warn("Snapshot capture failed:", e);
    return null;
  } finally {
    document.body.removeChild(holder);
  }
}

async function storeSnapshot(historyId) {
  const img = await captureSnapshot(historyId);
  if (!img) return;

  const snaps = loadSnapshots();
  snaps[historyId] = { img, savedAt: new Date().toISOString() };

  const entries = Object.entries(snaps).sort(
    (a, b) => (b[1]?.savedAt || "").localeCompare(a[1]?.savedAt || "")
  );
  const trimmed = Object.fromEntries(entries.slice(0, SNAPSHOT_MAX));
  saveSnapshots(trimmed);
}

function getSnapshot(historyId) {
  const snaps = loadSnapshots();
  return snaps[historyId]?.img || null;
}

let historyCache = new Map();

// Rendering main result (adds tooltip + overall bar)
function displayResult(data) {
  const title = safeText(data.title || "Analysis result");
  const label = safeText(data.overall_label || "—");
  const scorePct = toPercentNumber(data.overall_score || 0);

  const checks = Array.isArray(data.checks) ? data.checks : [];

  const tooltipHtml = `
    <div class="relative group inline-flex items-center">
      <span class="material-symbols-outlined text-[16px] text-gray-400 cursor-help">info</span>
      <div class="absolute right-0 top-6 w-72 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 text-xs text-gray-700 dark:text-gray-200 shadow-xl opacity-0 group-hover:opacity-100 pointer-events-none transition">
        <div class="font-semibold mb-1">Credibility score guide</div>
        <div>80–100%: Likely real</div>
        <div>60–79%: Probably real</div>
        <div>40–59%: Mixed / uncertain</div>
        <div>20–39%: Probably fake</div>
        <div>0–19%: Likely fake</div>
      </div>
    </div>
  `;

  resultBox.innerHTML = `
    <div class="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 p-4">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="text-base font-extrabold leading-snug">${title}</div>
          <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">Overall label</div>
          <div class="mt-1">
            <span class="inline-flex items-center gap-2 px-3 py-1 rounded-lg text-sm font-semibold ${getLabelColor(label)}">
              ${label}
            </span>
          </div>
        </div>

        <div class="shrink-0 text-right">
          <div class="flex items-center justify-end gap-1 text-xs text-gray-500 dark:text-gray-400">
            <span>Overall score</span>
            ${tooltipHtml}
          </div>
          <div class="text-3xl font-extrabold">${scorePct.toFixed(0)}%</div>
        </div>
      </div>

      <div class="loading-bar-outer mt-3">
        <div class="overall-bar-inner" style="width:${scorePct}%"></div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-3">
      ${checks.map(renderCheck).join("")}
    </div>
  `;
}

// Analyze flow (prevents spam + clearer feedback)
async function analyzeUrl() {
  const raw = urlInput.value.trim();
  if (!raw) {
    statusMsg.textContent = "Please enter a URL.";
    return;
  }

  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    statusMsg.textContent = "Invalid URL format. Example: https://example.com/news/article";
    return;
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    statusMsg.textContent = "Invalid URL scheme. Only http/https are allowed.";
    return;
  }

  if (isQuickBlockedHost(parsed.hostname)) {
    statusMsg.textContent = "Please enter a valid news/article webpage (not social media, video, or e-commerce).";
    return;
  }

  // Block obvious non-article pages
  if (!parsed.pathname || parsed.pathname === "/" || parsed.pathname.length < 2) {
    statusMsg.textContent = "Please paste a direct article URL (not the homepage).";
    return;
  }

  // Loading UI on
  setLoadingUI(true);
  resultBox.innerHTML = "";
  statusMsg.textContent = "";

  try {
    const resp = await fetch(`${API_BASE}/analyze?url=${encodeURIComponent(raw)}`);
    const data = await resp.json();

    if (!resp.ok) {
      hadSuccessfulAnalysis = false;
      statusMsg.textContent = data.detail || "Analysis failed. Please try another article URL.";
      return;
    }

    hadSuccessfulAnalysis = true;
    statusMsg.textContent = "Analysis complete. You can analyze again.";
    displayResult(data);

    if (data && data.history_id) {
      storeSnapshot(data.history_id);
    }

    await loadHistory();

  } catch (e) {
    console.error(e);
    hadSuccessfulAnalysis = false;
    statusMsg.textContent = "Failed to connect to backend. Is FastAPI running?";
  } finally {
    setLoadingUI(false);
  }
}

// Modal
function openModal() {
  historyModal.classList.remove("hidden");
}
function closeModal() {
  historyModal.classList.add("hidden");
  historyModalImg.src = "";
}

async function openHistoryModal(historyId) {
  let record = historyCache.get(historyId);
  if (!record) {
    try {
      const resp = await fetch(`${API_BASE}/history/${historyId}`);
      record = await resp.json();
    } catch {
      record = null;
    }
  }

  if (!record || record.detail) {
    statusMsg.textContent = "Failed to open history item.";
    return;
  }

  const snap = getSnapshot(historyId);

  historyModalTitle.textContent = record.title || "Analysis result";
  historyModalMeta.textContent = `${record.domain || ""} • ${new Date(record.timestamp).toLocaleString()}`;

  historyModalOpenLink.href = record.url || "#";

  if (snap) {
    historyModalImgFallback.classList.add("hidden");
    historyModalImg.classList.remove("hidden");
    historyModalImg.src = snap;
  } else {
    historyModalImg.classList.add("hidden");
    historyModalImgFallback.classList.remove("hidden");
  }

  historyModalRestoreBtn.onclick = () => {
    closeModal();
    loadHistoryItem(historyId);
  };

  openModal();
}

// History Functions
async function loadHistory() {
  try {
    const resp = await fetch(`${API_BASE}/history?limit=20`);
    const data = await resp.json();

    (data.records || []).forEach((r) => {
      if (r && !r.id) r.id = btoa(unescape(encodeURIComponent(r.url || ""))).replace(/=+$/, "");
    });

    if (!data.records || data.records.length === 0) {
      historyList.innerHTML = `
        <div class="text-center text-gray-500 dark:text-gray-400 py-8">
          <span class="material-symbols-outlined text-4xl mb-2">history</span>
          <p>No analysis history yet</p>
        </div>
      `;
      return;
    }

    historyCache = new Map();
    data.records.forEach((r) => { if (r && r.id) historyCache.set(r.id, r); });

    historyList.innerHTML = data.records.map(record => {
      const date = new Date(record.timestamp);
      const timeAgo = getTimeAgo(date);
      const snap = record.id ? getSnapshot(record.id) : null;

      return `
        <div class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-primary cursor-pointer transition-colors"
             onclick="openHistoryModal('${record.id}')">
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1 min-w-0">
              <div class="text-sm font-semibold truncate">${safeText(record.title || "Untitled")}</div>
              <div class="text-xs text-gray-500 dark:text-gray-400">${safeText(record.domain || "")}</div>
            </div>
            <span class="ml-2 px-2 py-1 rounded text-xs font-medium ${getLabelColor(record.overall_label)}">
              ${safeText(record.overall_label)}
            </span>
          </div>
          <div class="text-xs text-gray-600 dark:text-gray-300 truncate">
            ${safeText(record.url)}
          </div>
          ${snap ? `<img class="snapshot-thumb mt-2 border border-gray-200 dark:border-gray-700" src="${snap}" alt="snapshot">` : ""}
          <div class="mt-2 text-[11px] text-gray-500 dark:text-gray-400">${timeAgo}</div>
        </div>
      `;
    }).join("");

  } catch (error) {
    console.error("Failed to load history:", error);
    historyList.innerHTML = `
      <div class="text-center text-red-600 py-8">
        Failed to load history
      </div>
    `;
  }
}

async function loadHistoryItem(historyId) {
  try {
    const resp = await fetch(`${API_BASE}/history/${historyId}`);
    const data = await resp.json();

    if (!resp.ok) {
      statusMsg.textContent = data.detail || "Failed to load history item";
      return;
    }

    urlInput.value = data.url || "";
    statusMsg.textContent = "Loaded from history.";
    displayResult({
      title: data.title,
      overall_label: data.overall_label,
      overall_score: data.overall_score,
      checks: data.checks,
    });

  } catch (e) {
    console.error(e);
    statusMsg.textContent = "Failed to load history item.";
  }
}

async function clearHistory() {
  try {
    await fetch(`${API_BASE}/history`, { method: "DELETE" });
    historyList.innerHTML = `
      <div class="text-center text-gray-500 dark:text-gray-400 py-8">
        History cleared.
      </div>
    `;
  } catch (e) {
    console.error(e);
  }
}

// Sidebar Toggle
function openSidebar() {
  historySidebar.classList.remove("translate-x-full");
  sidebarBackdrop.classList.remove("hidden");
  loadHistory();
}
function closeSidebar() {
  historySidebar.classList.add("translate-x-full");
  sidebarBackdrop.classList.add("hidden");
}
function toggleSidebar() {
  const isOpen = !historySidebar.classList.contains("translate-x-full");
  if (isOpen) closeSidebar();
  else openSidebar();
}

// Event Listeners
historyModalCloseBtn.addEventListener("click", closeModal);
historyModalOverlay.addEventListener("click", closeModal);

historyBtn.addEventListener("click", toggleSidebar);
closeSidebarBtn.addEventListener("click", closeSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);

clearHistoryBtn.addEventListener("click", async () => {
  await clearHistory();
  await loadHistory();
});

analyzeBtn.addEventListener("click", analyzeUrl);
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") analyzeUrl();
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !historyModal.classList.contains("hidden")) closeModal();
});

window.openHistoryModal = openHistoryModal;