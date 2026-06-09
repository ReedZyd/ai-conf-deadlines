// ============================================================
//  会议地点地图：按年份着色，可按年份筛选
// ============================================================

const I18N = {
  zh: { title: "会议地点地图", back: "列表", switchTo: "EN",
        deadline: "截稿", dates: "会期", edition: "届", nextDl: "下一届截稿(估)" },
  en: { title: "Conference Location Map", back: "List", switchTo: "中",
        deadline: "Deadline", dates: "Dates", edition: "edition", nextDl: "Next deadline (est.)" },
};
let lang = localStorage.getItem("lang") === "en" ? "en" : "zh";
const t = () => I18N[lang];

// 按年份分配颜色
const YEAR_COLORS = ["#5b8cff", "#44d07b", "#ffb84d", "#ff5b6e", "#c06bff", "#33c4d8"];
// 只展示「未结束」的会议（会期结束日 ≥ 今天）
const _today = new Date().toISOString().slice(0, 10);
const located = CONFERENCES.filter(
  (c) => typeof c.lat === "number" && (!c.venue_end || c.venue_end >= _today)
);
const years = [...new Set(located.map((c) => c.year))].sort();
const colorOf = (y) => YEAR_COLORS[years.indexOf(y) % YEAR_COLORS.length];
const activeYears = new Set(years);

const map = L.map("map", { worldCopyJump: true }).setView([25, 10], 2);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19,
}).addTo(map);

let markers = [];

function fmt(iso) {
  return new Date(iso).toLocaleDateString(lang === "en" ? "en-US" : "zh-CN",
    { year: "numeric", month: "short", day: "numeric" });
}

const LABEL_ZOOM = 5;   // 放大到此级别才常驻显示标签，否则悬停显示

function draw() {
  markers.forEach((m) => map.removeLayer(m));
  markers = [];
  const permanent = map.getZoom() >= LABEL_ZOOM;
  // 同城轻微散开，避免重叠
  const seen = {};
  for (const c of located) {
    if (!activeYears.has(c.year)) continue;
    const k = `${c.lat},${c.lon}`;
    const n = seen[k] = (seen[k] || 0) + 1;
    const off = (n - 1) * 0.6;
    const m = L.circleMarker([c.lat + off, c.lon + off], {
      radius: 7, color: "#fff", weight: 1.5,
      fillColor: colorOf(c.year), fillOpacity: 0.9,
    }).addTo(map);
    const conf = c.name.split(" ")[0];
    const title = c.venue_year ? `${conf} ${c.venue_year}` : c.name;
    const dlLabel = c.est ? t().nextDl : t().deadline;
    const dateLine = c.venue_date ? `${t().dates}: ${c.venue_date}<br>` : "";
    m.bindPopup(
      `<b>${title}</b><br>` +
      `📍 ${c.venue || c.place || ""}<br>` +
      dateLine +
      `${dlLabel}: ${fmt(c.deadline)}`
    );
    // 标签：缩小时悬停显示、放大后常驻显示「会议 · 时间 · 地点」
    const labelDate = c.venue_date ? `<br><span class="lbl-date">${c.venue_date}</span>` : "";
    const city = (c.venue || c.place || "").split(",")[0];
    m.bindTooltip(
      `<b>${title}</b>${labelDate}<br><span class="lbl-city">📍 ${city}</span>`,
      { permanent, direction: "top", offset: [0, -6], className: "conf-label" }
    );
    markers.push(m);
  }
}

// 缩放跨越阈值时重建，切换标签常驻/悬停
let _wasPermanent = null;
map.on("zoomend", () => {
  const perm = map.getZoom() >= LABEL_ZOOM;
  if (perm !== _wasPermanent) { _wasPermanent = perm; draw(); }
});

function buildLegend() {
  const el = document.getElementById("yearLegend");
  el.innerHTML = "";
  for (const y of years) {
    const chip = document.createElement("span");
    chip.className = "year-chip" + (activeYears.has(y) ? " active" : "");
    chip.innerHTML = `<span class="dot" style="background:${colorOf(y)}"></span>${y}`;
    chip.onclick = () => {
      if (activeYears.has(y)) activeYears.delete(y); else activeYears.add(y);
      buildLegend();
      draw();
    };
    el.appendChild(chip);
  }
}

function applyI18n() {
  document.documentElement.lang = lang;
  document.title = t().title;
  document.getElementById("mapTitle").textContent = t().title;
  document.getElementById("backTxt").textContent = t().back;
  document.getElementById("langBtn").textContent = t().switchTo;
}

document.getElementById("langBtn").addEventListener("click", () => {
  lang = lang === "zh" ? "en" : "zh";
  localStorage.setItem("lang", lang);
  applyI18n();
  draw();
});

applyI18n();
buildLegend();
draw();
