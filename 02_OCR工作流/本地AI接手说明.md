# 本地 AI 接手说明

## 工作目录

`/Users/a123/Downloads/董小姐/02_OCR工作流`

## 这套工具做什么

用于把手机长截图里的课程文稿 OCR 成正文文本。

- 默认只保留真正正文，从“每天10分钟……”开始
- 默认同时输出 `.txt` 和 `.md`
- 多张图时会自动生成合并版

## 关键文件

- 脚本入口：`extract_article_text.py`
- OCR helper：`ocr_tsv.swift`
- 待处理文件夹：`待整理截图`
- 输出文件夹：`整理结果`
- 双击批量整理：`自动整理截图.command`
- 拖拽即整理：`拖拽图片到这里整理.command`

## 最常用命令

### 1）处理待整理截图文件夹

```bash
cd /Users/a123/Downloads/董小姐/02_OCR工作流
python3 extract_article_text.py --folder 待整理截图
```

### 2）直接处理指定图片

```bash
cd /Users/a123/Downloads/董小姐/02_OCR工作流
python3 extract_article_text.py /Users/a123/Downloads/IMG_4460.JPG /Users/a123/Downloads/IMG_4398.JPG
```

### 3）处理某个文件夹

```bash
cd /Users/a123/Downloads/董小姐/02_OCR工作流
python3 extract_article_text.py /Users/a123/Downloads/课程截图
```

### 4）如果要保留“今日解读要点 / 优惠券 / 常见问题”

```bash
python3 extract_article_text.py --folder 待整理截图 --include-meta
```

### 5）如果只要 Markdown

```bash
python3 extract_article_text.py --folder 待整理截图 --format md
```

## 默认输出

输出到：`整理结果`

常见结果包括：

- `IMG_xxxx_正文.txt`
- `IMG_xxxx_正文.md`
- `全部正文_合并.txt`
- `全部正文_合并.md`

董小姐观点每日流程的正式输出不放在本目录的 `整理结果`，而是放到：

`/Users/a123/Downloads/董小姐/03_整理输出/YYYY-MM-DD`

每天最终保留 4 个文件：原图、正文 `.txt`、正文 `.md`、Excel 候选表。OCR 工作区里的截图只做临时输入，用完清空。

## 已知行为

- Markdown 标题会优先尝试识别截图里的真实课程标题
- 如果标题 OCR 识别不完整，会自动回退或保留接近结果
- 中文 OCR 偶尔会有少数字词误识别，重要标题和数字建议抽查

## 本地 AI 可直接执行的接手提示词

你现在接手一个本地 OCR 整理工具项目。

工作目录：
`/Users/a123/Downloads/董小姐/02_OCR工作流`

目标：
1. 使用 `extract_article_text.py` 识别用户给出的截图或文件夹
2. 默认输出正文版 `.txt` 和 `.md`
3. 结果写入 `整理结果`
4. 不要改动正文内容，只在必要时调整 OCR 流程或输出格式
5. 如果用户说“只要正文”，默认不要保留优惠券、常见问题、评论区

常用命令：
`python3 extract_article_text.py --folder 待整理截图`

如果用户要保留前置信息：
`python3 extract_article_text.py --folder 待整理截图 --include-meta`

如果用户给的是具体图片路径，就直接把图片路径传给脚本。
