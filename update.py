#!/usr/bin/env python3
"""
每天自动抓取会议截稿日期，生成 data.js。
数据源：ccfddl/ccf-deadlines（社区维护，每日更新）。

规则：
- 若数据源已有「未来」的截稿日 → 直接用，est=False
- 若最近一届已过（下一届官方未公布）→ 取最近一届 +1 年估计，est=True
ARR 为滚动制，不在数据源内，作为手动占位保留。
"""
import io
import tarfile
import urllib.request
from datetime import datetime, timezone, timedelta

import yaml  # pip install pyyaml

REPO_TARBALL = "https://codeload.github.com/ccfddl/ccf-deadlines/tar.gz/refs/heads/main"

# 显示分类顺序
CATEGORIES = [
    "AI 三大会",
    "ARR (ACL Rolling Review)",
    "NLP",
    "综合 AI",
    "多智能体",
    "CV 三大会",
    "其他 CV/视觉",
    "Robotics",
    "机器学习/ML",
    "数据挖掘/检索",
    "图形/语音/多媒体",
    "Web/交叉应用",
]

# 纳入的 ccfddl 方向（只收 AI 直接相关，跳过系统/安全/网络/体系结构等）
INCLUDE_SUBS = {"AI", "CG", "DB", "MX"}

# 重点会议的精细分类与标签（覆盖默认按 sub 归类）
# title -> (category, highlight, tags)
SPECIAL = {
    "NeurIPS": ("AI 三大会", True, ["ML"]),
    "ICML":    ("AI 三大会", True, ["ML"]),
    "ICLR":    ("AI 三大会", True, ["ML"]),
    "AAAI":    ("综合 AI", False, ["AI"]),
    "IJCAI":   ("综合 AI", False, ["AI"]),
    "ECAI":    ("综合 AI", False, ["AI"]),
    "PRICAI":  ("综合 AI", False, ["AI"]),
    "AAMAS":   ("多智能体", False, ["MAS"]),
    "DAI":     ("多智能体", False, ["MAS"]),
    "CVPR":    ("CV 三大会", False, ["CV"]),
    "ICCV":    ("CV 三大会", False, ["CV"]),
    "ECCV":    ("CV 三大会", False, ["CV"]),
    "ACL":     ("NLP", False, ["NLP"]),
    "EMNLP":   ("NLP", False, ["NLP"]),
    "NAACL":   ("NLP", False, ["NLP"]),
    "EACL":    ("NLP", False, ["NLP"]),
    "COLING":  ("NLP", False, ["NLP"]),
    "CoNLL":   ("NLP", False, ["NLP"]),
    "IJCNLP":  ("NLP", False, ["NLP"]),
    "NLPCC":   ("NLP", False, ["NLP"]),
    "ICRA":    ("Robotics", False, ["Robotics"]),
    "IROS":    ("Robotics", False, ["Robotics"]),
    "RSS":     ("Robotics", False, ["Robotics"]),
    "CoRL":    ("Robotics", False, ["Robotics"]),
    "ACCV":    ("其他 CV/视觉", False, ["CV"]),
    "WACV":    ("其他 CV/视觉", False, ["CV"]),
    "BMVC":    ("其他 CV/视觉", False, ["CV"]),
    "3DV":     ("其他 CV/视觉", False, ["CV"]),
    "ICPR":    ("其他 CV/视觉", False, ["CV"]),
}

# 按 sub 的默认分类（未在 SPECIAL 中的会议）
SUB_DEFAULT = {
    "AI": ("机器学习/ML", ["ML"]),
    "CG": ("图形/语音/多媒体", ["CG"]),
    "DB": ("数据挖掘/检索", ["DM"]),
    "MX": ("Web/交叉应用", ["APP"]),
}

# ARR 手动维护（滚动制，10 周一轮；换轮时改这里的 name/deadline）
# 官方排期 https://aclrollingreview.org/dates ：
#   May 2026 轮 5/25(已过) → Aug 2026 轮 8/3 → Oct 2026 轮 10/12
ARR_ENTRY = {
    "name": "ARR — August 2026",
    "full": "ACL Rolling Review · 8 月轮（提交截稿 Aug 3；承诺日 Oct 11）",
    "category": "ARR (ACL Rolling Review)",
    "est": False, "highlight": False, "tags": ["NLP"],
    "deadline": "2026-08-03T23:59:00-12:00",
    "conf_date": "最近会议：EACL 2027（承诺日 Oct 11, 2026）",
    "place": "EACL 2027 · 线上提交至 ARR",
    "link": "https://aclrollingreview.org/dates",
}

# 手动地点覆盖：官方已公布但数据源尚未收录的届
# key = 会议显示名(name)；可给 place / venue_year / venue_date / lat / lon
VENUE_OVERRIDE = {
    "ICLR 2027": {
        "place": "West Coast, North America",
        "venue_year": 2027,
        "venue_date": "TBD",
        "lat": 37.77, "lon": -122.42,   # 北美西海岸（旧金山一带代表点）
    },
}


# 命名时区 → UTC 偏移小时
_TZ_NAMED = {
    "AOE": -12, "UTC": 0, "GMT": 0,
    "PT": -8, "PST": -8, "PDT": -7,
    "ET": -5, "EST": -5, "EDT": -4,
    "CT": -6, "CST": -6, "MT": -7,
    "CET": 1, "CEST": 2, "BST": 1, "JST": 9, "KST": 9, "AEST": 10,
}


def tz_offset(tzstr):
    """'UTC-12' / 'AoE' / 'UTC+8' / 'PT' -> '-12:00' 形式；无法解析则按 AoE。"""
    if not tzstr:
        return "-12:00"
    s = str(tzstr).upper().strip()
    if s in _TZ_NAMED:
        h = _TZ_NAMED[s]
        return f"{'+' if h >= 0 else '-'}{abs(h):02d}:00"
    s = s.replace("UTC", "").replace("GMT", "").strip()
    if not s:
        return "+00:00"
    try:
        sign = "-" if s[0] == "-" else "+"
        num = int(s.lstrip("+-").split(":")[0])
        return f"{sign}{num:02d}:00"
    except (ValueError, IndexError):
        return "-12:00"  # 兜底按 AoE


def to_iso(date_str, tzstr):
    """'2025-05-15 23:59:59' + tz -> '2025-05-15T23:59:59-12:00'"""
    d = str(date_str).strip().replace(" ", "T")
    if "T" not in d:
        d += "T23:59:59"
    return d + tz_offset(tzstr)


def parse_iso(iso):
    return datetime.fromisoformat(iso)


def add_one_year(iso):
    dt = parse_iso(iso)
    try:
        dt = dt.replace(year=dt.year + 1)
    except ValueError:  # 2/29
        dt = dt.replace(year=dt.year + 1, day=28)
    return dt.isoformat()


def download_yaml_entries():
    raw = urllib.request.urlopen(REPO_TARBALL, timeout=60).read()
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            if "/conference/" not in m.name or not m.name.endswith((".yml", ".yaml")):
                continue
            data = yaml.safe_load(tar.extractfile(m).read())
            if not isinstance(data, list):
                continue
            for conf in data:
                t = conf.get("title")
                if t:
                    entries[t] = conf
    return entries


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_conf_end(date_str):
    """把会期文字解析成结束日 ISO (YYYY-MM-DD)，解析失败返回 None。
    支持：'July 6-12, 2026' / 'September 27 - October 1, 2026' / 'December 6, 2026' 等。"""
    if not date_str:
        return None
    s = str(date_str).lower()
    ym = _re.search(r"(20\d{2})", s)
    if not ym:
        return None
    year = int(ym.group(1))
    months = [(m.start(), _MONTHS[m.group(0)[:3]])
              for m in _re.finditer(r"jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*", s)]
    if not months:
        return None
    month = months[-1][1]                       # 最后出现的月份 = 结束月
    tail = s[months[-1][0]:]                     # 该月之后的文字
    days = [int(d) for d in _re.findall(r"\b(\d{1,2})\b", tail) if int(d) <= 31]
    day = min(max(days), 28) if days else 28     # 用 28 封顶，避免非法日期
    return f"{year:04d}-{month:02d}-{day:02d}"


def latest_announced_venue(conf):
    """返回该会议「最新已公布地点」的 (year, place, date)，含没有截稿日的未来届。"""
    best = None
    for c in conf.get("confs", []) or []:
        place = (c.get("place") or "").strip()
        yr = c.get("year")
        if place and place.upper() != "TBD" and yr:
            if best is None or yr > best[0]:
                best = (yr, place, str(c.get("date", "")).strip())
    return best


def pick_edition(conf, now):
    """从一个会议的多届里挑出要展示的那届，返回 dict 或 None"""
    editions = []
    for c in conf.get("confs", []) or []:
        tzstr = c.get("timezone", "AoE")
        for tl in c.get("timeline", []) or []:
            dl = tl.get("deadline")
            if not dl or str(dl).lower() == "tbd":
                continue
            iso = to_iso(dl, tzstr)
            abs_iso = to_iso(tl["abstract_deadline"], tzstr) if tl.get("abstract_deadline") else None
            editions.append({
                "year": c.get("year"),
                "deadline": iso,
                "abstract": abs_iso,
                "link": c.get("link") or conf.get("dblp", ""),
                "place": c.get("place", "TBD"),
                "conf_date": str(c.get("date", "")).strip(),
            })
    if not editions:
        return None
    editions.sort(key=lambda e: parse_iso(e["deadline"]))

    future = [e for e in editions if parse_iso(e["deadline"]) >= now]
    if future:
        e = future[0]
        e["est"] = False
    else:
        # 截稿已过且下一届 CFP 未公布：截稿按最近一届逐年 +1 估算
        e = dict(editions[-1])
        e["est"] = True
        e["prev_deadline"] = e["deadline"]  # 上一届真实截稿（bump 前）
        e["prev_year"] = e["year"]
        years = 0
        while parse_iso(e["deadline"]) < now:
            e["deadline"] = add_one_year(e["deadline"])
            years += 1
        for _ in range(years):
            if e["abstract"]:
                e["abstract"] = add_one_year(e["abstract"])
        if e["year"]:
            e["year"] = e["year"] + years
        e["conf_date"] = "TBD"

    # 地点：始终用「最新已公布地点」的真实城市与年份（地点通常早于 CFP 公布）
    v = latest_announced_venue(conf)
    if v:
        e["venue_year"], e["venue"], e["venue_date"] = v
        e["place"] = v[1]                       # 真实城市，不再标「往届」
    return e


def build():
    now = datetime.now(timezone(timedelta(hours=-12)))  # 用 AoE 当前时刻
    src = download_yaml_entries()
    out = []
    skipped = 0
    for title in sorted(src.keys()):
        conf = src[title]
        sub = str(conf.get("sub", ""))
        if sub not in INCLUDE_SUBS or not title or title == "None":
            continue
        if title in SPECIAL:
            category, highlight, tags = SPECIAL[title]
        else:
            category, tags = SUB_DEFAULT.get(sub, ("Web/交叉应用", ["APP"]))
            highlight = False
        e = pick_edition(conf, now)
        if not e:
            skipped += 1
            continue
        year = e.get("year") or ""
        item = {
            "name": f"{title} {year}".strip(),
            "full": conf.get("description", "") or "",
            "category": category,
            "highlight": highlight,
            "est": e["est"],
            "tags": tags,
            "abstract": e["abstract"],
            "deadline": e["deadline"],
            "conf_date": e["conf_date"] or "TBD",
            "place": e["place"] or "TBD",
            "link": e["link"],
        }
        if e.get("prev_deadline"):
            item["prev_deadline"] = e["prev_deadline"]
            item["prev_year"] = e.get("prev_year")
        if e.get("venue"):
            item["venue"] = e["venue"]
            item["venue_year"] = e.get("venue_year")
            item["venue_date"] = e.get("venue_date")
            item["venue_end"] = parse_conf_end(e.get("venue_date"))
        out.append(item)

    out.append(ARR_ENTRY)
    print(f"  纳入 {len(out)} 个会议（跳过 {skipped} 个无可用截稿日）")

    # 手动地点覆盖（官方已公布、数据源未收录）
    for item in out:
        ov = VENUE_OVERRIDE.get(item.get("name"))
        if ov:
            item.update(ov)
            item["venue"] = ov.get("place", item.get("venue"))
            item["venue_end"] = parse_conf_end(item.get("venue_date"))  # 重算，避免沿用旧届

    # 地理编码 + 提取年份，供地图使用
    for item in out:
        geocode(item)
    return out


# 城市/国家 → (lat, lon)，按 place 子串匹配（不区分大小写）
GEO = {
    "austin": (30.27, -97.74),
    "brazil": (-22.91, -43.17),       # Rio de Janeiro
    "rio de janeiro": (-22.91, -43.17),
    "bremen": (53.08, 8.80),
    "denver": (39.74, -104.99),
    "honolulu": (21.31, -157.86),
    "hawaii": (21.31, -157.86),
    "malmö": (55.60, 13.00),
    "malmo": (55.60, 13.00),
    "montréal": (45.50, -73.57),
    "montreal": (45.50, -73.57),
    "paphos": (34.77, 32.42),
    "cyprus": (34.77, 32.42),
    "pittsburgh": (40.44, -79.99),
    "seoul": (37.57, 126.98),
    "sydney": (-33.87, 151.21),
    "vienna": (48.21, 16.37),
    "wien": (48.21, 16.37),
    "singapore": (1.35, 103.82),
    "vancouver": (49.28, -123.12),
    "new orleans": (29.95, -90.07),
    "london": (51.51, -0.13),
    "paris": (48.86, 2.35),
    # 常见会议城市（北美）
    "seattle": (47.61, -122.33),
    "san francisco": (37.77, -122.42),
    "los angeles": (34.05, -118.24),
    "san diego": (32.72, -117.16),
    "nashville": (36.16, -86.78),
    "atlanta": (33.75, -84.39),
    "detroit": (42.33, -83.05),
    "philadelphia": (39.95, -75.17),
    "washington": (38.91, -77.04),
    "new york": (40.71, -74.01),
    "boston": (42.36, -71.06),
    "chicago": (41.88, -87.63),
    "phoenix": (33.45, -112.07),
    "toronto": (43.65, -79.38),
    "mexico city": (19.43, -99.13),
    # 欧洲
    "amsterdam": (52.37, 4.90),
    "barcelona": (41.39, 2.17),
    "madrid": (40.42, -3.70),
    "berlin": (52.52, 13.40),
    "munich": (48.14, 11.58),
    "milan": (45.46, 9.19),
    "milano": (45.46, 9.19),
    "rome": (41.90, 12.50),
    "zurich": (47.37, 8.54),
    "geneva": (46.20, 6.14),
    "lisbon": (38.72, -9.14),
    "dublin": (53.35, -6.26),
    "copenhagen": (55.68, 12.57),
    "stockholm": (59.33, 18.06),
    "helsinki": (60.17, 24.94),
    "prague": (50.08, 14.44),
    "warsaw": (52.23, 21.01),
    "athens": (37.98, 23.73),
    "istanbul": (41.01, 28.98),
    "delft": (52.01, 4.36),
    "edinburgh": (55.95, -3.19),
    "glasgow": (55.86, -4.25),
    "kigali": (-1.94, 30.06),
    "tel-aviv": (32.08, 34.78),
    "tel aviv": (32.08, 34.78),
    "abu dhabi": (24.45, 54.38),
    "cape town": (-33.92, 18.42),
    # 亚太
    "tokyo": (35.68, 139.69),
    "yokohama": (35.44, 139.64),
    "kyoto": (35.01, 135.77),
    "osaka": (34.69, 135.50),
    "beijing": (39.90, 116.41),
    "shanghai": (31.23, 121.47),
    "hangzhou": (30.27, 120.15),
    "shenzhen": (22.54, 114.06),
    "guangzhou": (23.13, 113.26),
    "hong kong": (22.32, 114.17),
    "macau": (22.20, 113.54),
    "taipei": (25.03, 121.57),
    "jeju": (33.50, 126.53),
    "daegu": (35.87, 128.60),
    "busan": (35.18, 129.08),
    "bangkok": (13.76, 100.50),
    "mumbai": (19.08, 72.88),
    "new delhi": (28.61, 77.21),
    "delhi": (28.61, 77.21),
    "bangalore": (12.97, 77.59),
    "auckland": (-36.85, 174.76),
    "melbourne": (-37.81, 144.96),
    "brisbane": (-27.47, 153.03),
}

import re as _re


def geocode(item):
    """给会议附加 lat/lon 及地图年份；匹配不到坐标则不加 lat/lon。"""
    # 地图年份用「真实已公布届」的年份；没有则退回名字里的年份
    if item.get("venue_year"):
        item["year"] = item["venue_year"]
    else:
        m = _re.search(r"(20\d{2})", item.get("name", ""))
        if m:
            item["year"] = int(m.group(1))
    place = (item.get("venue") or item.get("place") or "")
    clean = place.lower()
    if "线上" in place or "online" in clean:
        return  # 线上提交，不标点
    for key, (lat, lon) in GEO.items():
        if key in clean:
            item["lat"] = lat
            item["lon"] = lon
            return


def render_js(confs):
    import json
    lines = ["// 本文件由 update.py 自动生成，请勿手改（ARR 除外）。",
             f"// 生成时间: {datetime.now(timezone.utc).isoformat()}",
             "",
             "const CATEGORIES = " + json.dumps(CATEGORIES, ensure_ascii=False) + ";",
             "",
             "const CONFERENCES = " + json.dumps(confs, ensure_ascii=False, indent=2) + ";",
             ""]
    return "\n".join(lines)


if __name__ == "__main__":
    print("抓取 ccfddl 数据中…")
    confs = build()
    js = render_js(confs)
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(js)
    print(f"已写入 data.js，共 {len(confs)} 个会议")
