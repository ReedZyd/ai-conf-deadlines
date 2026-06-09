// ============================================================
//  渲染 + 实时倒计时 + 搜索/筛选 + 中英文切换
//  · 估算(est)项倒计时用「月/天/时」；确定项用「天/时/分」
// ============================================================

const listEl = document.getElementById("list");
const searchEl = document.getElementById("search");
const tagbarEl = document.getElementById("tagbar");
const hidePastEl = document.getElementById("hidePast");
const onlyStarEl = document.getElementById("onlyStar");
const langBtn = document.getElementById("langBtn");

// ---------- 国际化 ----------
const I18N = {
  zh: {
    title: "AI 会议 Deadline 追踪",
    sub: "所有时间已换算为你的本地时区 · 截稿默认 AoE (UTC−12)",
    search: "搜索会议…",
    hidePast: "隐藏已截稿",
    onlyStar: "只看 ⭐",
    deadline: "截稿",
    prevDeadline: "上届截稿",
    abstract: "摘要",
    confDate: "会期",
    place: "地点",
    empty: "没有匹配的会议",
    past: "已截稿",
    est: "估",
    estTip: "官方未公布，按上一届日期估计",
    other: "其他",
    switchTo: "EN",
    locale: "zh-CN",
  },
  en: {
    title: "AI Conference Deadline Tracker",
    sub: "All times in your local timezone · Deadlines default to AoE (UTC−12)",
    search: "Search conferences…",
    hidePast: "Hide past",
    onlyStar: "Starred only",
    deadline: "Deadline",
    prevDeadline: "Last edition",
    abstract: "Abstract",
    confDate: "Dates",
    place: "Place",
    empty: "No matching conferences",
    past: "Past",
    est: "EST",
    estTip: "Official CFP not out; estimated from last edition",
    other: "Other",
    switchTo: "中",
    locale: "en-US",
  },
};

// 分类中英文对照
const CAT_I18N = {
  "AI 三大会": "Top-3 AI",
  "ARR (ACL Rolling Review)": "ARR (ACL Rolling Review)",
  "综合 AI": "General AI",
  "多智能体": "Multi-Agent",
  "CV 三大会": "Top-3 CV",
  "Robotics": "Robotics",
};

let lang = localStorage.getItem("lang") === "en" ? "en" : "zh";
const t = () => I18N[lang];
const catLabel = (cat) => (lang === "en" ? CAT_I18N[cat] || cat : cat);

let activeTag = null;
const allTags = [...new Set(CONFERENCES.flatMap((c) => c.tags || []))].sort();

function buildTagbar() {
  tagbarEl.innerHTML = "";
  for (const tag of allTags) {
    const b = document.createElement("button");
    b.className = "tag-btn" + (activeTag === tag ? " active" : "");
    b.textContent = tag;
    b.onclick = () => {
      activeTag = activeTag === tag ? null : tag;
      buildTagbar();
      render();
    };
    tagbarEl.appendChild(b);
  }
}

function fmtLocal(iso) {
  return new Date(iso).toLocaleString(t().locale, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function urgency(msLeft) {
  if (msLeft < 0) return "past";
  const days = msLeft / 86400000;
  if (days <= 7) return "urgent";
  if (days <= 30) return "soon";
  return "safe";
}

// est=true → 月/天/时；否则 天/时/分（临近 1 天内用 时/分/秒）
function countdownText(msLeft, est) {
  if (msLeft < 0) return t().past;
  const s = Math.floor(msLeft / 1000);
  const totalDays = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;

  if (est) {
    const months = Math.floor(totalDays / 30);
    const days = totalDays % 30;
    if (lang === "en") {
      return months > 0 ? `${months}mo ${days}d ${h}h` : `${days}d ${h}h`;
    }
    return months > 0 ? `${months}个月 ${days}天 ${h}时` : `${days}天 ${h}时`;
  }

  if (lang === "en") {
    return totalDays > 0 ? `${totalDays}d ${h}h ${m}m` : `${h}h ${m}m ${sec}s`;
  }
  return totalDays > 0 ? `${totalDays}天 ${h}时 ${m}分` : `${h}时 ${m}分 ${sec}秒`;
}

function visibleConferences() {
  const q = searchEl.value.trim().toLowerCase();
  return CONFERENCES.filter((c) => {
    if (activeTag && !(c.tags || []).includes(activeTag)) return false;
    if (onlyStarEl.checked && !c.highlight) return false;
    if (q && !(`${c.name} ${c.full || ""} ${c.place || ""}`.toLowerCase().includes(q))) return false;
    if (hidePastEl.checked && new Date(c.deadline).getTime() - Date.now() < 0) return false;
    return true;
  }).sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
}

function cardHTML(c) {
  const msLeft = new Date(c.deadline).getTime() - Date.now();
  const u = urgency(msLeft);
  const card = document.createElement("div");
  card.className = `card ${u}` + (c.highlight ? " star" : "");
  card.dataset.deadline = c.deadline;
  card.dataset.est = c.est ? "1" : "";

  const sep = lang === "en" ? ": " : "：";
  const star = c.highlight ? '<span class="star-badge" title="Highlight">⭐</span> ' : "";
  const estBadge = c.est ? `<span class="est-badge" title="${t().estTip}">${t().est}</span>` : "";
  const title = c.link
    ? `<a href="${c.link}" target="_blank" rel="noopener">${c.name}</a>`
    : c.name;
  // 「（往届）」是估算项地点的上一届标注，英文模式翻译
  const place = lang === "en" ? (c.place || "").replace("（往届）", " (prev. edition)") : c.place;

  card.innerHTML = `
    <div class="card-top">
      <div>
        <h2>${star}${title} ${estBadge}</h2>
        ${c.full ? `<div class="full">${c.full}</div>` : ""}
      </div>
      <div class="countdown ${u}">${countdownText(msLeft, c.est)}</div>
    </div>
    <div class="meta">
      <span class="deadline-local">${t().deadline}${sep}${fmtLocal(c.deadline)}</span>
      ${c.prev_deadline ? `<span class="prev-deadline">${t().prevDeadline}${sep}${fmtLocal(c.prev_deadline)}</span>` : ""}
      ${c.abstract ? `<span>${t().abstract}${sep}${fmtLocal(c.abstract)}</span>` : ""}
      ${c.conf_date ? `<span>${t().confDate}${sep}${c.conf_date}</span>` : ""}
      ${place ? `<span>📍 ${place}</span>` : ""}
    </div>
    ${c.tags ? `<div class="tags">${c.tags.map((x) => `<span>${x}</span>`).join("")}</div>` : ""}
  `;
  return card;
}

function render() {
  const items = visibleConferences();
  if (items.length === 0) {
    listEl.innerHTML = `<div class="empty">${t().empty}</div>`;
    return;
  }
  listEl.innerHTML = "";
  const order = typeof CATEGORIES !== "undefined" ? CATEGORIES : [];
  const cats = [...new Set(items.map((c) => c.category || t().other))].sort(
    (a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99)
  );
  for (const cat of cats) {
    const group = items.filter((c) => (c.category || t().other) === cat);
    const h = document.createElement("h3");
    h.className = "cat-head";
    h.textContent = `${catLabel(cat)} (${group.length})`;
    listEl.appendChild(h);
    for (const c of group) listEl.appendChild(cardHTML(c));
  }
}

// 每秒只更新倒计时文字与紧急度
function tick() {
  document.querySelectorAll(".card").forEach((card) => {
    const msLeft = new Date(card.dataset.deadline).getTime() - Date.now();
    const u = urgency(msLeft);
    const cd = card.querySelector(".countdown");
    cd.textContent = countdownText(msLeft, card.dataset.est === "1");
    cd.className = `countdown ${u}`;
    card.className = `card ${u}` + (card.classList.contains("star") ? " star" : "");
  });
}

// 应用静态文案（标题、副标题、占位符、开关、按钮）
function applyStaticI18n() {
  document.documentElement.lang = lang;
  document.title = t().title;
  document.getElementById("pageTitle").textContent = t().title;
  document.getElementById("pageSub").textContent = t().sub;
  searchEl.placeholder = t().search;
  document.getElementById("hidePastLabel").textContent = t().hidePast;
  document.getElementById("onlyStarLabel").textContent = t().onlyStar + " ";
  langBtn.textContent = t().switchTo;
}

langBtn.addEventListener("click", () => {
  lang = lang === "zh" ? "en" : "zh";
  localStorage.setItem("lang", lang);
  applyStaticI18n();
  render();
});

searchEl.addEventListener("input", render);
hidePastEl.addEventListener("change", render);
onlyStarEl.addEventListener("change", render);

applyStaticI18n();
buildTagbar();
render();
setInterval(tick, 1000);
