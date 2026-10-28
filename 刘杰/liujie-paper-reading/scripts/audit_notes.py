"""Check reading-note evidence and abstract alignment; not semantic correctness."""
import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


HEADINGS = ["摘要", "贡献", "关键技术（实现方法）", "实验设计", "实验结果对比", "总结"]


def compact(value):
    return re.sub(r"\s+", "", value)


def resolve_file(value, parent):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(notes_dir, alignment_dir, expected_ids=None):
    errors, warnings, records = [], [], []
    found_ids = set()
    paths = sorted(notes_dir.glob("*.json"))
    if not paths:
        errors.append("未发现笔记 JSON")
    for note_path in paths:
        label = note_path.name
        try:
            note = read_json(note_path)
            paper_id = note["id"]
            if not isinstance(paper_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", paper_id):
                raise ValueError("id 须为字母、数字、下划线或连字符")
            label = paper_id
            if paper_id in found_ids:
                raise ValueError("重复的论文 ID")
            found_ids.add(paper_id)
            if note_path.stem != paper_id:
                raise ValueError("笔记文件名须与 id 相同")
            if not isinstance(note.get("title"), str) or not note["title"].strip():
                raise ValueError("缺少论文题名")
            pdf_path = resolve_file(note["pdf_path"], note_path.parent)
            with pdf_path.open("rb") as stream:
                if b"%PDF-" not in stream.read(1024):
                    raise ValueError("全文文件缺少 PDF 文件头")
            pdf = PdfReader(str(pdf_path))
            page_count = len(pdf.pages)
            if page_count == 0:
                raise ValueError("PDF 无页面")
            sections = note["sections"]
            if [s.get("heading") for s in sections] != HEADINGS:
                raise ValueError("六章缺失、重复或顺序错误")
            images = 0
            for section in sections:
                blocks = section.get("blocks", [])
                if not blocks or not any(b.get("type") in ("p", "image") for b in blocks):
                    raise ValueError(section["heading"] + "没有实质内容")
                for block in blocks:
                    kind = block.get("type")
                    if kind not in ("p", "image", "subheading"):
                        raise ValueError("未知块类型 " + str(kind))
                    if section["heading"] == "摘要" and kind != "p":
                        raise ValueError("摘要只能包含译文段落")
                    if kind != "subheading" and not str(block.get("source", "")).strip():
                        raise ValueError(section["heading"] + "有块缺少 source")
                    if kind in ("p", "subheading"):
                        if not isinstance(block.get("text"), str) or not block["text"].strip():
                            raise ValueError("空文字块")
                    else:
                        for key in ("path", "caption", "interpretation"):
                            if not isinstance(block.get(key), str) or not block[key].strip():
                                raise ValueError("图片缺少 " + key)
                        image_path = resolve_file(block["path"], note_path.parent)
                        with Image.open(image_path) as picture:
                            if picture.format not in ("PNG", "JPEG"):
                                raise ValueError("图片须为 PNG 或 JPEG")
                            picture.verify()
                        images += 1
            alignment_path = alignment_dir / (paper_id + ".json")
            alignment = read_json(alignment_path)
            if alignment.get("id") != paper_id:
                raise ValueError("摘要对齐文件 id 不一致")
            alignment_pdf = resolve_file(alignment["source_pdf"], alignment_path.parent)
            if alignment_pdf != pdf_path:
                raise ValueError("笔记和摘要对齐引用了不同 PDF")
            pages = alignment.get("source_pages", [])
            if not isinstance(pages, list) or not pages or any(
                type(p) is not int or p < 1 or p > page_count for p in pages
            ):
                raise ValueError("摘要来源物理页码超范围或缺失")
            original = alignment.get("english_abstract")
            pairs = alignment.get("sentences", [])
            if not isinstance(original, str) or not original.strip() or not isinstance(pairs, list) or not pairs:
                raise ValueError("缺少完整英文摘要或句对")
            for pair in pairs:
                if any(not isinstance(pair.get(key), str) or not pair[key].strip() for key in ("en", "zh")):
                    raise ValueError("摘要中存在空句对")
            if compact("".join(p["en"] for p in pairs)) != compact(original):
                raise ValueError("英文句对未完整覆盖所存英文摘要或顺序不一致")
            translated = "".join(b["text"] for b in sections[0]["blocks"])
            if compact("".join(p["zh"] for p in pairs)) != compact(translated):
                raise ValueError("笔记摘要与逐句译文不一致")
            if images == 0:
                warnings.append(f"{paper_id}: 无图片，请确认原文没有需配图讲解的内容")
            records.append({"id": paper_id, "pdf_pages": page_count, "abstract_sentences": len(pairs), "images": images})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
            errors.append(f"{label}: {error}")
        except Exception as error:
            errors.append(f"{label}: 解析失败 {type(error).__name__}: {error}")
    if expected_ids is not None:
        expected = set(expected_ids)
        if len(expected_ids) != len(expected):
            errors.append("预期 ID 清单存在重复项")
        missing, extra = expected - found_ids, found_ids - expected
        if missing:
            errors.append("缺少笔记: " + ", ".join(sorted(missing)))
        if extra:
            errors.append("清单外笔记: " + ", ".join(sorted(extra)))
    return {
        "ok": not errors,
        "coverage_checked": expected_ids is not None,
        "papers": records,
        "errors": errors,
        "warnings": warnings,
        "scope": "仅检查数据一致性；原文摘要完整性、翻译语义、图表和事实须人工式核对。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes-dir", type=Path, required=True)
    parser.add_argument("--alignment-dir", type=Path, required=True)
    parser.add_argument("--expected-ids", type=Path, help="Whitespace-separated IDs or JSON string array")
    parser.add_argument("--output", type=Path, help="Internal audit JSON, separate from inputs")
    args = parser.parse_args()
    expected = None
    if args.expected_ids:
        content = args.expected_ids.read_text(encoding="utf-8-sig").strip()
        expected = json.loads(content) if content.startswith("[") else content.split()
        if not isinstance(expected, list) or any(not isinstance(item, str) for item in expected):
            parser.error("--expected-ids must contain a list of strings")
    report = audit(args.notes_dir.resolve(), args.alignment_dir.resolve(), expected)
    if args.output:
        output = args.output.resolve()
        inputs = list(args.notes_dir.glob("*.json")) + list(args.alignment_dir.glob("*.json"))
        if args.expected_ids:
            inputs.append(args.expected_ids)
        if output in {path.resolve() for path in inputs}:
            parser.error("Audit output must not overwrite any input")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
