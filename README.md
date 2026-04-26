# 董小姐观点自动化

把董小姐日度市场观点从长截图或文本稿整理成可追溯的观点档案。

当前项目重点不是 OCR 本身，而是把每日观点沉淀成结构化候选表，后续再进入 Excel 追踪和跨日比较。

## 当前状态

- `2026-04-26` 已跑通单日 MVP。
- 当前策略：先生成 Excel 候选表，人工审核后再决定是否写回 Excel。
- 下一步：连续跑 3-5 天，观察 OCR、骨架归类、标签和拆解颗粒度。

## 仓库放什么

本仓库只保存可复用流程、脚本和说明文档：

- 项目说明和每日流程。
- OCR 上游取文本工具。
- GitHub 同步和迭代规则。
- 后续稳定模板或非敏感配置。

本仓库不保存：

- 原始截图、长图、OCR 正文、每日候选表。
- Excel 成品或样例表。
- 公司资料、内部 PDF、历史大文件。
- Swift/Python 缓存和临时切图。

## 目录结构

```text
.
├── 00_流程记录/
│   ├── 董小姐观点每日流程.md
│   └── GitHub同步与迭代.md
├── 01_当前资料/
│   └── 董小姐观点自动化_项目说明_v0.1.md
├── 02_OCR工作流/
│   ├── extract_article_text.py
│   ├── ocr_tsv.swift
│   ├── 使用说明.md
│   ├── 本地AI接手说明.md
│   ├── 自动整理截图.command
│   ├── 自动监控截图.command
│   ├── 拖拽图片到这里整理.command
│   ├── 待整理截图/
│   └── 整理结果/
└── .gitignore
```

## 每日流程

每日正式输出放在本地，不提交 GitHub：

```text
03_整理输出/YYYY-MM-DD/
├── YYYY-MM-DD_IMG_xxxx.JPG
├── YYYY-MM-DD_IMG_xxxx_正文.txt
├── YYYY-MM-DD_IMG_xxxx_正文.md
└── YYYY-MM-DD_Excel候选表.md
```

执行方式：

```bash
cd /Users/a123/Downloads/董小姐/02_OCR工作流
python3 extract_article_text.py \
  --out-dir /Users/a123/Downloads/董小姐/03_整理输出/YYYY-MM-DD \
  --format both \
  --no-combined \
  /Users/a123/Downloads/董小姐/02_OCR工作流/待整理截图/YYYY-MM-DD_IMG_xxxx.JPG
```

然后人工抽查 OCR 正文，并生成 Excel 候选表。

## 迭代原则

- 每跑一天，在 `00_流程记录/董小姐观点每日流程.md` 更新执行日志。
- 流程规则变化，更新 `01_当前资料/董小姐观点自动化_项目说明_v0.1.md`。
- 脚本变化后，至少运行 `python3 extract_article_text.py --help` 做基本验证。
- 不提交每日输出包、Excel、截图和 OCR 正文。
- 等 3-5 天试跑稳定后，再考虑 Excel 写回副本和完整骨架接入。

