# AI 会议 Deadline 追踪

纯静态网站，按分类展示 AI / CV / Robotics 等会议截稿倒计时。
数据每天由 GitHub Actions 自动从 [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines) 抓取刷新。

## 文件结构
| 文件 | 作用 |
|------|------|
| `index.html` / `style.css` / `app.js` | 前端页面（实时倒计时、分类、⭐ highlight、搜索/筛选） |
| `data.js` | 会议数据，**由 `update.py` 自动生成，勿手改**（ARR 那条除外） |
| `update.py` | 抓取脚本：拉社区数据 → 生成 `data.js` |
| `.github/workflows/update.yml` | 每天定时抓取 + 部署到 GitHub Pages |

## 规则
- 数据源已有未来真实 ddl → 直接用（卡片无「估」标记）
- 下一届官方未公布 → 取最近一届逐年 +1 至未来，标橙色「估」
- AI 三大会（NeurIPS/ICML/ICLR）默认 ⭐ highlight

## 本地预览
```bash
pip install -r requirements.txt
python update.py          # 刷新 data.js（需联网）
python -m http.server 8000
# 打开 http://localhost:8000
```

## 部署到 GitHub Pages（一次性设置）
1. 新建 GitHub 仓库，把本目录推上去：
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin git@github.com:<你>/<仓库>.git
   git push -u origin main
   ```
2. 仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**。
3. 之后每天 UTC 01:00（北京 09:00）自动抓取并部署；也可在 **Actions** 页点 *Run workflow* 手动触发。

## 增删会议
编辑 `update.py` 里的 `TARGETS` 列表：`(title, 分类, 是否highlight, 标签)`。
`title` 必须与 ccfddl 中的会议名一致。ARR 为滚动制，改 `update.py` 里的 `ARR_ENTRY`。
