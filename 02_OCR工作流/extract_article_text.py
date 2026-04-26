#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
OCR_SWIFT = ROOT / "ocr_tsv.swift"
CACHE_DIR = ROOT / ".swift-module-cache"
DEFAULT_OUT_DIR = ROOT / "整理结果"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic"}


@dataclass(frozen=True)
class CropInfo:
    path: Path
    y: int
    height: int


@dataclass(frozen=True)
class OCRLine:
    text: str
    y: float
    confidence: float


@dataclass(frozen=True)
class TextLine:
    text: str
    y: float


@dataclass(frozen=True)
class ExtractedArticle:
    image: Path
    title: str
    text: str
    output_paths: list[Path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract article body text from long mobile screenshots with macOS Vision OCR."
    )
    parser.add_argument("images", nargs="*", type=Path, help="Screenshot image paths")
    parser.add_argument("-f", "--folder", type=Path, help="Process every image in this folder")
    parser.add_argument("-o", "--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--watch", action="store_true", help="Keep watching --folder for new/changed images")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between --watch scans")
    parser.add_argument("--include-meta", action="store_true", help="Keep intro bullets, coupon link, and FAQ")
    parser.add_argument("--top", type=int, default=1750, help="Pixels to skip from top")
    parser.add_argument("--bottom", type=int, default=1450, help="Pixels to skip from bottom")
    parser.add_argument("--slice-height", type=int, default=1050, help="Vertical crop height")
    parser.add_argument("--overlap", type=int, default=160, help="Overlap between crops")
    parser.add_argument("--scale", type=int, default=3, help="OCR crop scale factor")
    parser.add_argument("--format", choices=("txt", "md", "both"), default="both", help="Output format")
    parser.add_argument("--raw-lines", action="store_true", help="Keep OCR line breaks")
    parser.add_argument("--no-combined", action="store_true", help="Do not write a combined text file")
    parser.add_argument("--print", action="store_true", help="Also print extracted text")
    return parser.parse_args()


def make_crops(
    image_path: Path,
    crop_dir: Path,
    top: int,
    bottom: int,
    slice_height: int,
    overlap: int,
    scale: int,
) -> list[CropInfo]:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    x0 = int(width * 0.035)
    x1 = int(width * 0.965)
    y0 = min(max(top, 0), height)
    y1 = max(y0, height - bottom)
    step = max(1, slice_height - overlap)

    crops: list[CropInfo] = []
    y = y0
    index = 0
    while y < y1:
        crop_bottom = min(y + slice_height, y1)
        crop = image.crop((x0, y, x1, crop_bottom))
        crop = ImageOps.grayscale(crop)
        crop = ImageOps.autocontrast(crop)
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
        crop = crop.filter(ImageFilter.SHARPEN)
        out = crop_dir / f"{image_path.stem}_{index:03d}_{y}.png"
        crop.save(out)
        crops.append(CropInfo(path=out, y=y, height=crop_bottom - y))
        index += 1
        y += step

    return crops


def make_title_crop(image_path: Path, crop_dir: Path, top: int) -> CropInfo:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    x0 = int(width * 0.03)
    x1 = int(width * 0.97)
    y0 = min(max(top - 300, 0), height)
    y1 = min(max(y0 + 1, top + 180), height)

    crop = image.crop((x0, y0, x1, y1))
    crop = ImageOps.grayscale(crop)
    crop = ImageOps.autocontrast(crop)
    crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.LANCZOS)
    crop = crop.filter(ImageFilter.SHARPEN)
    out = crop_dir / f"{image_path.stem}_title.png"
    crop.save(out)
    return CropInfo(path=out, y=y0, height=y1 - y0)


def is_duplicate(a: str, b: str) -> bool:
    na = norm(a)
    nb = norm(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.78


def run_ocr(crops: list[CropInfo]) -> list[OCRLine]:
    if not OCR_SWIFT.exists():
        raise FileNotFoundError(f"Missing OCR helper: {OCR_SWIFT}")

    CACHE_DIR.mkdir(exist_ok=True)
    command = [
        "swift",
        "-Xcc",
        f"-fmodules-cache-path={CACHE_DIR}",
        str(OCR_SWIFT),
        *[str(crop.path) for crop in crops],
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise RuntimeError("Vision OCR failed")

    raw_lines = result.stdout.splitlines()
    has_text = any(
        line.strip()
        and line.strip() != "nilError"
        and not (line.strip().startswith("===") and line.strip().endswith("==="))
        for line in raw_lines
    )
    if not has_text:
        detail = result.stderr.strip() or result.stdout.strip() or "no OCR output"
        raise RuntimeError(f"Vision OCR returned no text: {detail}")

    crop_by_path = {str(crop.path): (index, crop) for index, crop in enumerate(crops)}
    parsed: list[OCRLine] = []

    for raw in raw_lines:
        parts = raw.split("\t", 6)
        if len(parts) != 7:
            continue

        path, _min_x, min_y, _max_x, max_y, confidence, text = parts
        if path not in crop_by_path:
            continue

        index, crop = crop_by_path[path]
        min_y_f = float(min_y)
        max_y_f = float(max_y)

        # Discard text that touches the hard crop edges. With overlap enabled,
        # the same real line should appear intact in a neighboring crop.
        if index > 0 and max_y_f > 0.985:
            continue
        if index < len(crops) - 1 and min_y_f < 0.015:
            continue

        local_mid_from_top = (1.0 - ((min_y_f + max_y_f) / 2.0)) * crop.height
        parsed.append(OCRLine(text=text.strip(), y=crop.y + local_mid_from_top, confidence=float(confidence)))

    parsed.sort(key=lambda line: line.y)

    deduped: list[OCRLine] = []
    for line in parsed:
        duplicate_index: int | None = None
        for idx in range(len(deduped) - 1, max(-1, len(deduped) - 12), -1):
            previous = deduped[idx]
            if abs(line.y - previous.y) > 42:
                continue
            if is_duplicate(line.text, previous.text):
                duplicate_index = idx
                break

        if duplicate_index is None:
            deduped.append(line)
            continue

        previous = deduped[duplicate_index]
        if (line.confidence, len(norm(line.text))) > (previous.confidence, len(norm(previous.text))):
            deduped[duplicate_index] = line

    return deduped


def norm(line: str) -> str:
    return re.sub(r"\s+", "", line).strip()


def is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("===") and stripped.endswith("==="):
        return True
    if stripped == "nilError":
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped):
        return True
    if stripped in {"商品介绍＞", "商品介绍>", "暂无评分", "去评分", "G 关注公众号>", "G 关注公众号＞"}:
        return True
    if stripped.startswith("店铺主页") or stripped.startswith("小鹅通提供技术支持"):
        return True
    return False


def is_stop_line(line: str) -> bool:
    stripped = line.strip()
    stop_patterns = (
        "思投社",
        "评论",
        "发表评论",
        "加入学习",
        "进店看看",
        "店铺主页",
        "个人中心",
        "关注我们",
        "投诉建议",
    )
    return any(stripped.startswith(pattern) for pattern in stop_patterns)


def clean_lines(lines: list[OCRLine], include_meta: bool) -> list[TextLine]:
    cleaned: list[TextLine] = []
    started = False
    seen_transcript_marker = False
    recent: list[str] = []

    for raw in lines:
        line = raw.text.strip()
        if is_noise(line):
            continue

        if not started:
            if include_meta:
                if "今日解读要点" in line or "常见问题" in line or "文稿为机器转录" in line:
                    started = True
                else:
                    continue
            else:
                if "文稿为机器转录" in line:
                    seen_transcript_marker = True
                    continue
                if "每天10分钟" in line or (seen_transcript_marker and line):
                    started = True
                else:
                    continue

        line = fix_common_ocr(line)

        if is_stop_line(line):
            break

        key = norm(line)
        if key and key in recent:
            continue

        cleaned.append(TextLine(text=line, y=raw.y))
        recent.append(key)
        recent = recent[-16:]

    return cleaned


def fix_common_ocr(line: str) -> str:
    replacements = {
        "https://scxop.xets/k.com/s/470DWS": "https://scxop.xetslk.com/s/470DWS",
        "https://scxop.xetslk.com/s/470DWS": "https://scxop.xetslk.com/s/470DWS",
        "（文稿内机器转录": "（文稿为机器转录",
        "回撒": "回调",
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    return line


def fix_title_ocr(title: str) -> str:
    title = title.strip()
    title = title.replace("“", "\"").replace("”", "\"")
    title = re.sub(r'^【[^】]{1,6}】', "【★★★】", title)
    title = re.sub(r'^【[^】]{1,6}$', "【★★★】", title)
    title = re.sub(r'^"([^"]+)"', r'“\1”', title)
    title = re.sub(r'"([^"]+)"', r'“\1”', title)
    title = title.replace("【大**】", "【★★★】")
    title = title.replace("【**大】", "【★★★】")
    title = title.replace("【大*大】", "【★★★】")
    title = title.replace("【大大大】", "【★★★】")
    title = title.replace("【★*★】", "【★★★】")
    title = title.replace("【★★大】", "【★★★】")
    title = title.replace("【大★★】", "【★★★】")
    title = title.replace("【*★★】", "【★★★】")
    title = title.replace("【★★*】", "【★★★】")
    title = re.sub(r"“([^”]+)“", r"“\1”", title)
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"(\d月\d+日)解$", r"\1解读要点", title)
    title = re.sub(r"(\d月\d+日)解读$", r"\1解读要点", title)
    title = re.sub(r"(\d月\d+日)解读要$", r"\1解读要点", title)
    return title


def is_title_stop(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped)
        or "商品介绍" in stripped
        or "暂无评分" in stripped
        or "去评分" in stripped
        or "关注公众号" in stripped
        or norm(stripped) in {"介绍评论", "评论介绍"}
    )


def looks_like_title_piece(line: str) -> bool:
    stripped = line.strip()
    if len(norm(stripped)) < 6:
        return False
    if stripped.startswith("【") or stripped.startswith("["):
        return True
    if "解读要点" in stripped:
        return True
    return False


def extract_title(lines: list[OCRLine], image_path: Path) -> str:
    parts: list[str] = []

    for raw in lines:
        line = fix_common_ocr(raw.text.strip())
        if is_noise(line):
            continue
        if is_title_stop(line):
            if parts:
                break
            continue
        if looks_like_title_piece(line):
            parts.append(line)
            continue
        if parts:
            break

    if parts:
        return fix_title_ocr("".join(parts))
    return image_path.stem.replace("_", " ")


def is_hard_break(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in {"今日解读要点：", "常见问题：", "几句话总结："}:
        return True
    if re.match(r"^[一二三四五六七八九十\d]+、", stripped) and len(stripped) <= 30:
        return True
    if stripped.startswith("（") or stripped.startswith("("):
        return True
    if stripped.startswith("https://") or stripped.startswith("http://"):
        return True
    return False


def starts_new_paragraph(line: str) -> bool:
    return bool(re.match(r"^[一二三四五六七八九十\d]+、", line.strip()))


def ends_paragraph(line: str) -> bool:
    return bool(re.search(r"[。！？；：）)」』”’]$", line.strip()))


def paragraph_gap_threshold(lines: list[TextLine]) -> float:
    gaps = [
        lines[index + 1].y - lines[index].y
        for index in range(len(lines) - 1)
        if 20 <= lines[index + 1].y - lines[index].y <= 160
    ]
    if not gaps:
        return 92
    gaps.sort()
    median = gaps[len(gaps) // 2]
    return max(88, median * 1.45)


def to_paragraphs(lines: list[TextLine]) -> str:
    paragraphs: list[str] = []
    buffer = ""
    gap_threshold = paragraph_gap_threshold(lines)
    previous: TextLine | None = None

    for item in lines:
        line = item.text
        if previous is not None and item.y - previous.y > gap_threshold and buffer:
            paragraphs.append(buffer)
            buffer = ""

        if is_hard_break(line):
            if buffer:
                paragraphs.append(buffer)
                buffer = ""
            paragraphs.append(line)
            previous = item
            continue

        if starts_new_paragraph(line) and buffer:
            paragraphs.append(buffer)
            buffer = ""

        if not buffer:
            buffer = line
        else:
            buffer += line

        if ends_paragraph(line):
            paragraphs.append(buffer)
            buffer = ""

        previous = item

    if buffer:
        paragraphs.append(buffer)

    return "\n\n".join(paragraphs).strip() + "\n"


def markdown_title(image_path: Path, extracted_title: str | None = None) -> str:
    if extracted_title and extracted_title.strip():
        return extracted_title.strip()
    return image_path.stem.replace("_", " ")


def to_markdown(image_path: Path, title: str, text: str) -> str:
    body = text.strip()
    title = markdown_title(image_path, title)
    return f"# {title}\n\n来源：`{image_path}`\n\n---\n\n{body}\n"


def expected_suffixes(output_format: str) -> list[str]:
    if output_format == "txt":
        return [".txt"]
    if output_format == "md":
        return [".md"]
    return [".txt", ".md"]


def output_paths_for(image_path: Path, out_dir: Path, output_format: str) -> list[Path]:
    base = out_dir / f"{image_path.stem}_正文"
    return [base.with_suffix(suffix) for suffix in expected_suffixes(output_format)]


def write_text_outputs(image_path: Path, title: str, text: str, out_dir: Path, output_format: str) -> list[Path]:
    written: list[Path] = []

    if output_format in {"txt", "both"}:
        txt_path = (out_dir / f"{image_path.stem}_正文").with_suffix(".txt")
        txt_path.write_text(text, encoding="utf-8")
        written.append(txt_path)

    if output_format in {"md", "both"}:
        md_path = (out_dir / f"{image_path.stem}_正文").with_suffix(".md")
        md_path.write_text(to_markdown(image_path, title, text), encoding="utf-8")
        written.append(md_path)

    return written


def extract_one(image_path: Path, args: argparse.Namespace) -> ExtractedArticle:
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    with tempfile.TemporaryDirectory(prefix=f"{image_path.stem}_ocr_", dir=ROOT) as tmp:
        crop_dir = Path(tmp)
        title_crop = make_title_crop(image_path=image_path, crop_dir=crop_dir, top=args.top)
        crops = make_crops(
            image_path=image_path,
            crop_dir=crop_dir,
            top=args.top,
            bottom=args.bottom,
            slice_height=args.slice_height,
            overlap=args.overlap,
            scale=args.scale,
        )
        title = extract_title(run_ocr([title_crop]), image_path)
        lines = clean_lines(run_ocr(crops), include_meta=args.include_meta)

    text = "\n".join(line.text for line in lines).strip() + "\n" if args.raw_lines else to_paragraphs(lines)
    text = text.replace("共同成\n\n长。", "共同成长。")
    text = text.replace("泸深", "沪深")
    return ExtractedArticle(
        image=image_path,
        title=title,
        text=text,
        output_paths=write_text_outputs(image_path, title, text, args.out_dir, args.format),
    )


def find_images(folder: Path) -> list[Path]:
    if not folder.exists():
        raise FileNotFoundError(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )


def resolve_images(args: argparse.Namespace) -> list[Path]:
    images: list[Path] = []
    if args.folder:
        images.extend(find_images(args.folder.expanduser()))
    for path in args.images:
        expanded = path.expanduser()
        if expanded.is_dir():
            images.extend(find_images(expanded))
        else:
            images.append(expanded)

    seen: set[Path] = set()
    unique: list[Path] = []
    for image in images:
        resolved = image.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def needs_processing(image_path: Path, out_dir: Path, output_format: str) -> bool:
    expected = output_paths_for(image_path, out_dir, output_format)
    if not expected:
        return True
    source_mtime = image_path.stat().st_mtime
    for out_path in expected:
        if not out_path.exists() or out_path.stat().st_mtime < source_mtime:
            return True
    return False


def combined_txt(images: list[Path], texts: dict[Path, str]) -> str:
    sections = []
    for image in images:
        text = texts.get(image, "").strip()
        if text:
            sections.append(f"===== {image.name} =====\n\n{text}\n")
    return "\n\n".join(sections).strip() + "\n"


def combined_md(images: list[Path], titles: dict[Path, str], texts: dict[Path, str]) -> str:
    sections = []
    for image in images:
        text = texts.get(image, "").strip()
        if text:
            sections.append(f"# {markdown_title(image, titles.get(image))}\n\n{text}\n")
    return "\n\n---\n\n".join(sections).strip() + "\n"


def load_body_text(image: Path, out_dir: Path) -> str:
    txt_path = (out_dir / f"{image.stem}_正文").with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")

    md_path = (out_dir / f"{image.stem}_正文").with_suffix(".md")
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")
        marker = "\n\n---\n\n"
        if marker in md_text:
            return md_text.split(marker, 1)[1].strip() + "\n"
        return md_text

    return ""


def load_markdown_title(image: Path, out_dir: Path) -> str:
    md_path = (out_dir / f"{image.stem}_正文").with_suffix(".md")
    if not md_path.exists():
        return markdown_title(image)

    first_line = md_path.read_text(encoding="utf-8").splitlines()[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return markdown_title(image)


def write_combined_files(images: list[Path], titles: dict[Path, str], texts: dict[Path, str], out_dir: Path, output_format: str, no_combined: bool) -> list[Path]:
    if len(images) <= 1 or no_combined:
        return []

    nonempty = [image for image in images if texts.get(image, "").strip()]
    if len(nonempty) <= 1:
        return []

    written: list[Path] = []
    if output_format in {"txt", "both"}:
        combined_txt_path = out_dir / "全部正文_合并.txt"
        combined_txt_path.write_text(combined_txt(nonempty, texts), encoding="utf-8")
        written.append(combined_txt_path)

    if output_format in {"md", "both"}:
        combined_md_path = out_dir / "全部正文_合并.md"
        combined_md_path.write_text(combined_md(nonempty, titles, texts), encoding="utf-8")
        written.append(combined_md_path)

    return written


def process_images(args: argparse.Namespace, images: list[Path], only_changed: bool = False) -> list[tuple[Path, str]]:
    processed: list[ExtractedArticle] = []

    for image in images:
        if only_changed and not needs_processing(image, args.out_dir, args.format):
            continue
        article = extract_one(image, args)
        processed.append(article)
        for path in article.output_paths:
            print(path, flush=True)
        if args.print:
            print(article.text)

    combined_titles: dict[Path, str] = {}
    combined_texts: dict[Path, str] = {}
    for image in images:
        existing_title = load_markdown_title(image, args.out_dir)
        if existing_title:
            combined_titles[image] = existing_title
        existing_text = load_body_text(image, args.out_dir)
        if existing_text:
            combined_texts[image] = existing_text
        else:
            for article in processed:
                if article.image == image:
                    combined_titles[image] = article.title
                    combined_texts[image] = article.text
                    break

    for path in write_combined_files(images, combined_titles, combined_texts, args.out_dir, args.format, args.no_combined):
        print(path, flush=True)

    return [(article.image, article.text) for article in processed]


def watch_folder(args: argparse.Namespace) -> int:
    if not args.folder:
        raise ValueError("--watch needs --folder")

    print(f"Watching {args.folder.expanduser()} every {args.interval}s. Press Ctrl-C to stop.", flush=True)
    while True:
        try:
            images = resolve_images(args)
            process_images(args, images, only_changed=True)
            time.sleep(max(5, args.interval))
        except KeyboardInterrupt:
            print("Stopped.", flush=True)
            return 0


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.watch:
        return watch_folder(args)

    images = resolve_images(args)
    if not images:
        scanned_dirs = []
        if args.folder:
            scanned_dirs.append(str(args.folder.expanduser()))
        scanned_dirs.extend(str(path.expanduser()) for path in args.images if path.expanduser().is_dir())
        if scanned_dirs:
            print(f"No images found in: {', '.join(scanned_dirs)}")
            return 0
        raise SystemExit("No images found. Pass image paths, or use --folder /path/to/screenshots.")

    process_images(args, images)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
