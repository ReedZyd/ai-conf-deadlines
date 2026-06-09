// ============================================================
//  会议地点地图：按年份着色，可按年份筛选
// ============================================================

const I18N = {
  zh: { title: "会议地点地图", back: "列表", switchTo: "EN",
        deadline: "截稿", place: "地点", prev: "（地点为往届，官方未定）",
        noGeo: "无坐标会议（线上/地点未公布）" },
  en: { title: "Conference Location Map", back: "List", switchTo: "中",
        deadline: "Deadline", place: "Place", prev: "(last-edition location; venue TBA)",
        noGeo: "Without coordinates (online / venue TBA)" },
};
let lang = localStorage.getItem("lang") === "en" ? "en" : "zh";
const t = () => I18N[lang];

// 按年份分配颜色
const YEAR_COLORS = ["#5b8cff", "#44d07b", "#ffb84d", "#ff5b6e", "#c06bff", "#33c4d8"];
const located = CONFERENCES.filter((c) => typeof c.lat === "number");
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

function draw() {
  markers.forEach((m) => map.removeLayer(m));
  markers = [];
  // 同城轻微散开，避免重叠
  const seen = {};
  for (const c of located) {
    if (!activeYears.has(c.year)) continue;
    const k = `${c.lat},${c.lon}`;
    const n = seen[k] = (seen[k] || 0) + 1;
    const off = (n - 1) * 0.6;
    const m = L.circleMarker([c.lat + off, c.lon + off], {
      radius: 8, color: "#fff", weight: 1.5,
      fillColor: colorOf(c.year), fillOpacity: 0.9,
    }).addTo(map);
    const prevNote = c.place_prev ? `<br><span class="est">${t().prev}</span>` : "";
    m.bindPopup(
      `<b>${c.name}</b><br>` +
      `📍 ${(c.place || "").replace("（往届）", "")}` + prevNote + `<br>` +
      `${t().deadline}: ${fmt(c.deadline)}`
    );
    markers.push(m);
  }
}

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
