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
    "综合 AI",
    "多智能体",
    "CV 三大会",
    "Robotics",
]

# 目标会议：title 必须与 ccfddl 中的 title 一致
# (title, category, highlight, tags)
TARGETS = [
    ("NeurIPS", "AI 三大会", True, ["ML"]),
    ("ICML",    "AI 三大会", True, ["ML"]),
    ("ICLR",    "AI 三大会", True, ["ML"]),
    ("AAAI",    "综合 AI",   False, ["AI"]),
    ("IJCAI",   "综合 AI",   False, ["AI"]),
    ("AAMAS",   "多智能体",  False, ["MAS"]),
    ("CVPR",    "CV 三大会", False, ["CV"]),
    ("ICCV",    "CV 三大会", False, ["CV"]),
    ("ECCV",    "CV 三大会", False, ["CV"]),
    ("ICRA",    "Robotics",  False, ["Robotics"]),
    ("IROS",    "Robotics",  False, ["Robotics"]),
    ("RSS",     "Robotics",  False, ["Robotics"]),
    ("CoRL",    "Robotics",  False, ["Robotics"]),
]

# ARR 手动维护（滚动制，10 周一轮；换轮时改这里的 name/deadline）
# 官方排期 https://aclrollingreview.org/dates ：
#   May 2026 轮 5/25(已过) → Aug 2026 轮 8/3 → Oct 2026 轮 10/12
ARR_ENTRY = {
    "name": "ARR — August 2026",
    "full": "ACL Rolling Review · 8 月轮（提交截稿 Aug 3；承诺日 Oct 11，对应 EACL 2027）",
    "category": "ARR (ACL Rolling Review)",
    "est": False, "highlight": False, "tags": ["NLP"],
    "deadline": "2026-08-03T23:59:00-12:00",
    "conf_date": "Commit: Oct 11, 2026", "place": "线上提交",
    "link": "https://aclrollingreview.org/dates",
}


def tz_offset(tzstr):
    """'UTC-12' / 'AoE' / 'UTC+8' -> '-12:00' 形式"""
    if not tzstr or str(tzstr).upper() == "AOE":
        return "-12:00"
    s = str(tzstr).upper().replace("UTC", "").strip()
    if not s:
        return "+00:00"
    sign = "+" if s[0] != "-" else "-"
    num = s.lstrip("+-").split(":")[0]
    return f"{sign}{int(num):02d}:00"


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
        return e
    # 全部已过：取最近一届，逐年 +1 直到落到未来（兼容隔年会议如 ICCV/ECCV）
    e = dict(editions[-1])
    e["est"] = True
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
    e["place"] = "TBD"
    return e


def build():
    now = datetime.now(timezone(timedelta(hours=-12)))  # 用 AoE 当前时刻
    src = download_yaml_entries()
    out = []
    for title, category, highlight, tags in TARGETS:
        conf = src.get(title)
        if not conf:
            print(f"  ! 数据源未找到 {title}，跳过")
            continue
        e = pick_edition(conf, now)
        if not e:
            print(f"  ! {title} 无可用截稿日，跳过")
            continue
        year = e.get("year") or ""
        out.append({
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
        })
        flag = "估" if e["est"] else "真"
        print(f"  ✓ {title} {year} [{flag}] {e['deadline']}")

    # 插入 ARR（放到 AI 三大会之后）
    out_with_arr = []
    inserted = False
    for item in out:
        out_with_arr.append(item)
        if not inserted and item["category"] == "AI 三大会":
            # 在最后一个 AI 三大会后插入；简单起见循环结束统一插，这里跳过
            pass
    # 直接按分类顺序，ARR 单独加入
    out.append(ARR_ENTRY)
    return out


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
