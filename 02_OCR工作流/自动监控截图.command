#!/bin/zsh
set -e

cd "$(dirname "$0")"

python3 extract_article_text.py \
  --folder "$PWD/待整理截图" \
  --out-dir "$PWD/整理结果" \
  --watch \
  --interval 30
