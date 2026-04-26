#!/bin/zsh
set -e

cd "$(dirname "$0")"

python3 extract_article_text.py \
  --folder "$PWD/待整理截图" \
  --out-dir "$PWD/整理结果"

echo
echo "整理完成。结果在：$PWD/整理结果"
echo "按任意键关闭窗口。"
read -k 1
