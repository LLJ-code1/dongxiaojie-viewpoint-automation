# GitHub 同步与迭代

## 仓库地址

`https://github.com/LLJ-code1/dongxiaojie-viewpoint-automation`

## 同步范围

提交到 GitHub：

- `README.md`
- `.gitignore`
- `00_流程记录/`
- `01_当前资料/董小姐观点自动化_项目说明_v0.1.md`
- `02_OCR工作流/` 中的生产脚本、说明和双击命令

不提交到 GitHub：

- `03_整理输出/`
- `02_OCR工作流/待整理截图/`
- `02_OCR工作流/整理结果/`
- 原始图片、OCR 正文、Excel、CSV、缓存、临时切图

## 每次更新步骤

1. 跑完当天流程后，先确认每日输出包在本地 `03_整理输出/YYYY-MM-DD/`。
2. 更新 `00_流程记录/董小姐观点每日流程.md` 的执行日志和待观察问题。
3. 如果流程规则、目录约定、边界发生变化，同步更新项目说明。
4. 如果修改 OCR 脚本，运行：

```bash
cd /Users/a123/Downloads/董小姐/02_OCR工作流
python3 extract_article_text.py --help
```

5. 提交前检查：

```bash
git status --short
git diff --stat
git check-ignore -v 03_整理输出/2026-04-26/2026-04-26_IMG_4499.JPG
```

确认没有图片、OCR 正文、Excel 被纳入后再提交。

## 推荐提交节奏

- 日常试跑：每跑 1-3 天提交一次流程日志。
- 脚本修复：每个明确修复单独提交。
- 规则变化：项目说明和流程文档一起提交。
- Excel 写回能力上线前，继续只提交候选表规则，不提交 Excel 文件。

## 提交信息格式

建议短句：

- `init dongxiaojie workflow`
- `update daily run log`
- `document output package rules`
- `fix ocr title extraction`

