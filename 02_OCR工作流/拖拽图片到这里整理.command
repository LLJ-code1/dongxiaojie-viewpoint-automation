#!/bin/zsh
set -e

cd "$(dirname "$0")"

if [ "$#" -eq 0 ]; then
  echo "把图片文件或整个文件夹拖到这个脚本上。"
  echo "结果会输出到：$PWD/整理结果"
  echo
  echo "按任意键关闭窗口。"
  read -k 1
  exit 0
fi

python3 extract_article_text.py \
  --out-dir "$PWD/整理结果" \
  "$@"

echo
echo "整理完成。结果在：$PWD/整理结果"
echo "按任意键关闭窗口。"
read -k 1
