// ============================================================
//  渲染 + 实时倒计时 + 搜索/标签/隐藏已截稿
// ============================================================

const listEl = document.getElementById("list");
const searchEl = document.getElementById("search");
const tagbarEl = document.getElementById("tagbar");
const hidePastEl = document.getElementById("hidePast");
const onlyStarEl = document.getElementById("onlyStar");

let activeTag = null;

// 收集所有标签
const allTags = [...new Set(CONFERENCES.flatMap((c) => c.tags || []))].sort();

function buildTagbar() {
  tagbarEl.innerHTML = "";
  for (const t of allTags) {
    const b = document.createElement("button");
    b.className = "tag-btn" + (activeTag === t ? " active" : "");
    b.textContent = t;
    b.onclick = () => {
      activeTag = activeTag === t ? null : t;
      buildTagbar();
      render();
    };
    tagbarEl.appendChild(b);
  }
}

function fmtLocal(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
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

function countdownText(msLeft) {
  if (msLeft < 0) return "已截稿";
  const s = Math.floor(msLeft / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d > 0) return `${d}天 ${h}时 ${m}分`;
  return `${h}时 ${m}分 ${sec}秒`;
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

  const star = c.highlight ? '<span class="star-badge" title="Highlight">⭐</span> ' : "";
  const estBadge = c.est ? '<span class="est-badge" title="官方未公布，按上一届日期估计">估</span>' : "";
  const title = c.link
    ? `<a href="${c.link}" target="_blank" rel="noopener">${c.name}</a>`
    : c.name;

  card.innerHTML = `
    <div class="card-top">
      <div>
        <h2>${star}${title} ${estBadge}</h2>
        ${c.full ? `<div class="full">${c.full}</div>` : ""}
      </div>
      <div class="countdown ${u}">${countdownText(msLeft)}</div>
    </div>
    <div class="meta">
      <span class="deadline-local">截稿：${fmtLocal(c.deadline)}</span>
      ${c.abstract ? `<span>摘要：${fmtLocal(c.abstract)}</span>` : ""}
      ${c.conf_date ? `<span>会期：${c.conf_date}</span>` : ""}
      ${c.place ? `<span>📍 ${c.place}</span>` : ""}
    </div>
    ${c.tags ? `<div class="tags">${c.tags.map((t) => `<span>${t}</span>`).join("")}</div>` : ""}
  `;
  return card;
}

function render() {
  const items = visibleConferences();
  if (items.length === 0) {
    listEl.innerHTML = '<div class="empty">没有匹配的会议</div>';
    return;
  }
  listEl.innerHTML = "";

  // 按分类分组；CATEGORIES 给出顺序，其余分类排在后面
  const order = typeof CATEGORIES !== "undefined" ? CATEGORIES : [];
  const cats = [...new Set(items.map((c) => c.category || "其他"))].sort(
    (a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99)
  );

  for (const cat of cats) {
    const group = items.filter((c) => (c.category || "其他") === cat);
    const h = document.createElement("h3");
    h.className = "cat-head";
    h.textContent = `${cat} (${group.length})`;
    listEl.appendChild(h);
    for (const c of group) listEl.appendChild(cardHTML(c));
  }
}

// 每秒只更新倒计时文字与紧急度，避免整页重建
function tick() {
  document.querySelectorAll(".card").forEach((card) => {
    const msLeft = new Date(card.dataset.deadline).getTime() - Date.now();
    const u = urgency(msLeft);
    const cd = card.querySelector(".countdown");
    cd.textContent = countdownText(msLeft);
    cd.className = `countdown ${u}`;
    card.className = `card ${u}` + (card.classList.contains("star") ? " star" : "");
  });
}

searchEl.addEventListener("input", render);
hidePastEl.addEventListener("change", render);
onlyStarEl.addEventListener("change", render);

buildTagbar();
render();
setInterval(tick, 1000);
