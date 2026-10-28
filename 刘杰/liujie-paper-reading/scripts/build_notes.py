"""从保留的论文笔记模板及逐篇 JSON 创建新 DOCX；不用于重建已有文档。

只替换模板正文，并添加新图片和链接；样式、主题、页眉页脚、页面设置及
其他包部件保持原始字节。内容真实性、摘要完整翻译和版面仍须人工核验。
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import zipfile

from lxml import etree as E
from PIL import Image

REQUIRED = ["摘要", "贡献", "关键技术（实现方法）", "实验设计", "实验结果对比", "总结"]
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
EDITABLE = {"word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "assets/reading-note-template.docx"


def q(tag):
    prefix, name = tag.split(":")
    return "{" + NS[prefix] + "}" + name


def xml_bytes(element):
    return E.tostring(element, encoding="UTF-8", xml_declaration=True, standalone=True)


def text_of(element):
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def require_text(value, context):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} 必须是非空字符串")
    return value.strip()


def asset_path(value, note_file, context):
    path = Path(require_text(value, context))
    if not path.is_absolute():
        path = note_file.parent / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{context} 文件不存在：{path}")
    return path


def load_notes(directory, ids):
    if not directory.is_dir():
        raise ValueError(f"笔记目录不存在：{directory}")
    candidates = []
    seen = set()
    for path in sorted(directory.glob("*.json")):
        note = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(note, dict):
            raise ValueError(f"{path.name} 顶层必须为论文对象")
        pid = require_text(note.get("id"), f"{path.name}: id")
        if pid in seen:
            raise ValueError(f"重复论文 id：{pid}")
        seen.add(pid)
        if not ids or pid in ids:
            candidates.append((path, note))
    if ids and set(ids) - seen:
        raise ValueError(f"找不到指定论文 id：{', '.join(sorted(set(ids) - seen))}")
    if not candidates:
        raise ValueError("没有可构建的笔记 JSON")
    for path, note in candidates:
        context = f"{path.name} ({note['id']})"
        require_text(note.get("title"), context + ": title")
        pdf = asset_path(note.get("pdf_path"), path, context + ": pdf_path")
        with pdf.open("rb") as stream:
            if b"%PDF-" not in stream.read(1024):
                raise ValueError(f"{context} 的 PDF 无有效文件头：{pdf}")
        sections = note.get("sections")
        if not isinstance(sections, list) or any(not isinstance(s, dict) for s in sections):
            raise ValueError(f"{context}: sections 必须为六章列表")
        if [s.get("heading") for s in sections] != REQUIRED:
            raise ValueError(f"{context} 章节缺失或顺序错误；必须依次为：{'、'.join(REQUIRED)}")
        for section in sections:
            label = context + " / " + section["heading"]
            blocks = section.get("blocks")
            if not isinstance(blocks, list) or not blocks:
                raise ValueError(f"{label} 缺少非空 blocks")
            for index, block in enumerate(blocks, 1):
                loc = f"{label} / block {index}"
                if not isinstance(block, dict):
                    raise ValueError(f"{loc} 必须为对象")
                kind = block.get("type")
                if section["heading"] == "摘要" and kind != "p":
                    raise ValueError(f"{loc}：摘要只允许原文完整译文段落 p")
                if kind in ("p", "subheading"):
                    require_text(block.get("text"), loc + ": text")
                elif kind == "image":
                    for key in ("caption", "source", "interpretation"):
                        require_text(block.get(key), loc + ": " + key)
                    image_path = asset_path(block.get("path"), path, loc + ": path")
                    if image_path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                        raise ValueError(f"{loc}：图片仅支持 PNG/JPEG：{image_path}")
                    with Image.open(image_path) as image:
                        if image.format not in ("PNG", "JPEG"):
                            raise ValueError(f"{loc}：图片内容不是 PNG/JPEG：{image_path}")
                        image.verify()
                    for key in ("max_width_cm", "max_height_cm"):
                        if key in block and (not isinstance(block[key], (int, float)) or block[key] <= 0):
                            raise ValueError(f"{loc}: {key} 必须为正数")
                else:
                    raise ValueError(f"{loc} 未知块类型：{kind}")
                for key in ("source", "align", "interpretation_align"):
                    if key in block and not isinstance(block[key], str):
                        raise ValueError(f"{loc}: {key} 必须为字符串")
    return candidates


def source_summary(sources):
    """页码合并到章末，非页码来源去重保留；详细定位仍保留在 JSON 中。"""
    pages, other = set(), []
    for source in dict.fromkeys(s.strip() for s in sources if s.strip()):
        matches = list(re.finditer(r"(?:PDF\s*第?\s*|第\s*)([\d、，,–\-—～~至/ ]+)\s*页", source))
        if not matches:
            other.append(source)
        for match in matches:
            for piece in re.split(r"[、，,/]", match[1]):
                numbers = [int(n) for n in re.findall(r"\d+", piece)]
                if len(numbers) == 2 and 0 <= numbers[1] - numbers[0] < 1000:
                    pages.update(range(numbers[0], numbers[1] + 1))
                else:
                    pages.update(numbers)
    ranges = []
    values = sorted(pages)
    while values:
        first = last = values.pop(0)
        while values and values[0] == last + 1:
            last = values.pop(0)
        ranges.append(str(first) if first == last else f"{first}–{last}")
    parts = (["PDF 第 " + "、".join(ranges) + " 页"] if ranges else []) + other
    return "原文位置：" + "；".join(parts) + "。" if parts else ""


def build(template, notes, output, overwrite):
    report_path = output.with_suffix(".build.json")
    if output.resolve() == template.resolve():
        raise ValueError("输出不能与模板相同；本脚本仅创建新文档")
    if output.suffix.lower() != ".docx":
        raise ValueError("输出文件必须使用 .docx 扩展名")
    if not overwrite:
        for path in (output, report_path):
            if path.exists():
                raise ValueError(f"输出已存在：{path}；确认需替换时显式使用 --overwrite")
    with zipfile.ZipFile(template) as archive:
        infos = archive.infolist()
        package = {info.filename: archive.read(info.filename) for info in infos}
    root = E.fromstring(package["word/document.xml"])
    body = root.find("w:body", NS)
    paragraphs = body.findall("w:p", NS)
    abstract_index = next((i for i, p in enumerate(paragraphs) if text_of(p).strip() == "摘要"), None)
    if abstract_index is None or abstract_index < 1 or abstract_index + 1 >= len(paragraphs):
        raise ValueError("模板无法识别：应含论文标题、摘要标题和紧随其后的正文段落")
    if len(body.xpath(".//w:sectPr", namespaces=NS)) != 1 or body.find("w:sectPr", NS) is None:
        raise ValueError("仅支持单节模板；多节模板需人工适配，不能直接重建")
    samples = {
        "title": paragraphs[abstract_index - 1],
        "heading": paragraphs[abstract_index],
        "normal": paragraphs[abstract_index + 1],
    }
    picture = next((p for p in paragraphs if len(p.xpath(".//wp:inline", namespaces=NS)) == 1
                    and len(p.xpath(".//a:blip", namespaces=NS)) == 1 and not text_of(p).strip()), None)
    if picture is None:
        raise ValueError("模板缺少可复用的独立行内图片段落")
    source_section = body.find("w:sectPr", NS)
    section_bytes = E.tostring(source_section)
    section = deepcopy(source_section)
    page = section.find("w:pgSz", NS)
    margins = section.find("w:pgMar", NS)
    if page is None or margins is None:
        raise ValueError("模板缺少明确页面大小或页边距")
    width = (int(page.get(q("w:w"))) - int(margins.get(q("w:left"))) - int(margins.get(q("w:right")))) * 635
    height = (int(page.get(q("w:h"))) - int(margins.get(q("w:top"))) - int(margins.get(q("w:bottom")))) * 635
    template_width = int(picture.find(".//wp:extent", NS).get("cx"))
    relations = E.fromstring(package["word/_rels/document.xml.rels"])
    types = E.fromstring(package["[Content_Types].xml"])
    next_relation = max([int(r.get("Id")[3:]) for r in relations if re.fullmatch(r"rId\d+", r.get("Id", ""))] + [0])
    next_drawing = max([int(n.get("id")) for n in root.xpath(".//wp:docPr | .//pic:cNvPr", namespaces=NS)
                        if n.get("id", "").isdigit()] + [0])
    media = {}
    stats = []
    for child in list(body):
        body.remove(child)

    def set_property(properties, name, value=None):
        for child in properties.findall("w:" + name, NS):
            properties.remove(child)
        child = E.SubElement(properties, q("w:" + name))
        if value is not None:
            child.set(q("w:val"), str(value))

    def paragraph(text, role="normal", bold=False, keep=False, page_break=False, align=None):
        sample = samples.get(role, samples["normal"])
        p = deepcopy(sample)
        p.attrib.clear()
        run_properties = sample.find("w:r/w:rPr", NS)
        for child in list(p):
            if child.tag != q("w:pPr"):
                p.remove(child)
        pp = p.find("w:pPr", NS)
        if pp is None:
            pp = E.SubElement(p, q("w:pPr"))
        for name in ("keepNext", "keepLines", "pageBreakBefore", "sectPr"):
            for child in pp.findall("w:" + name, NS):
                pp.remove(child)
        if role in ("title", "heading") or keep:
            set_property(pp, "keepNext")
        if role in ("caption", "source"):
            set_property(pp, "keepLines")
        set_property(pp, "widowControl", "1")
        if page_break:
            set_property(pp, "pageBreakBefore")
        if align:
            if align not in ("left", "center", "right", "both"):
                raise ValueError(f"不支持的段落对齐：{align}")
            set_property(pp, "jc", align)
        run = E.SubElement(p, q("w:r"))
        rp = deepcopy(run_properties) if run_properties is not None else E.Element(q("w:rPr"))
        if bold:
            set_property(rp, "b", "1")
        if role == "source":
            set_property(rp, "sz", "20")
            set_property(rp, "szCs", "20")
        run.append(rp)
        t = E.SubElement(run, q("w:t"))
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = text
        return p

    def add_text(text, **kwargs):
        for part in re.split(r"\n\s*\n", text):
            if part.strip():
                body.append(paragraph(part.strip(), **kwargs))

    def relationship(kind, target, external=False):
        nonlocal next_relation
        next_relation += 1
        rid = f"rId{next_relation}"
        rel = E.SubElement(relations, q("rel:Relationship"), Id=rid, Type=NS["r"] + "/" + kind, Target=target)
        if external:
            rel.set("TargetMode", "External")
        return rid

    def add_image(block, note_file, pid, number):
        nonlocal next_drawing
        path = asset_path(block["path"], note_file, f"{pid} 图片")
        next_drawing += 1
        name = f"media/reading-note-{next_drawing}{path.suffix.lower()}"
        while "word/" + name in package or "word/" + name in media:
            next_drawing += 1
            name = f"media/reading-note-{next_drawing}{path.suffix.lower()}"
        media["word/" + name] = path.read_bytes()
        rid = relationship("image", name)
        caption = re.sub(r"^图\s*\d+[a-zA-Z]?\s*", "", block["caption"]).strip()
        caption = f"图{number} {caption}"
        p = deepcopy(picture)
        p.attrib.clear()
        pp = p.find("w:pPr", NS)
        if pp is None:
            pp = E.Element(q("w:pPr"))
            p.insert(0, pp)
        set_property(pp, "jc", "center")
        set_property(pp, "keepNext")
        set_property(pp, "keepLines")
        with Image.open(path) as image:
            iw, ih = image.size
        max_width = min(width, template_width, round(block.get("max_width_cm", width / 360000) * 360000))
        max_height = min(round(height * 0.70), round(block.get("max_height_cm", height / 360000) * 360000))
        cx = min(max_width, round(max_height * iw / ih))
        cy = round(cx * ih / iw)
        for extent in p.xpath(".//wp:extent | .//a:xfrm/a:ext", namespaces=NS):
            extent.set("cx", str(cx))
            extent.set("cy", str(cy))
        for blip in p.xpath(".//a:blip", namespaces=NS):
            blip.set(q("r:embed"), rid)
            blip.attrib.pop(q("r:link"), None)
        for properties in p.xpath(".//wp:docPr | .//pic:cNvPr", namespaces=NS):
            properties.set("id", str(next_drawing))
            properties.set("name", pid + " " + caption)
            properties.set("descr", block["interpretation"])
        body.append(p)
        add_text(caption + " [" + block["source"] + "]", role="caption", keep=True)
        add_text(block["interpretation"], align=block.get("interpretation_align"))

    for index, (note_file, paper) in enumerate(notes):
        pid = paper["id"]
        title = "-".join(str(paper[key]) for key in ("year", "venue", "rank", "title") if paper.get(key))
        add_text(title, role="title", page_break=index > 0)
        for key, label in (("authors", "作者"), ("status", "版本与发表状态"), ("category", "研究环节"), ("rank_note", "分级依据")):
            if paper.get(key):
                add_text(label + "：" + str(paper[key]))
        if paper.get("url"):
            p = paragraph("原文链接：")
            link = E.SubElement(p, q("w:hyperlink"))
            link.set(q("r:id"), relationship("hyperlink", paper["url"], external=True))
            run = E.SubElement(link, q("w:r"))
            normal_rp = samples["normal"].find("w:r/w:rPr", NS)
            rp = deepcopy(normal_rp) if normal_rp is not None else E.Element(q("w:rPr"))
            run.append(rp)
            set_property(rp, "color", "0563C1")
            E.SubElement(run, q("w:t")).text = "查看论文原文"
            body.append(p)
        image_count = 0
        for section_note in paper["sections"]:
            add_text(section_note["heading"], role="heading")
            sources = []
            for block in section_note["blocks"]:
                if block["type"] == "image":
                    image_count += 1
                    add_image(block, note_file, pid, image_count)
                elif block["type"] == "subheading":
                    add_text(block["text"], bold=True, keep=True)
                else:
                    add_text(block["text"], align=block.get("align"))
                if block.get("source"):
                    sources.append(block["source"])
            source = source_summary(sources)
            if source:
                previous_pp = body[-1].find("w:pPr", NS)
                if previous_pp is not None:
                    set_property(previous_pp, "keepNext")
                add_text(source, role="source")
        stats.append({"id": pid, "note_file": str(note_file.resolve()), "images": image_count})
    body.append(section)
    if E.tostring(body.find("w:sectPr", NS)) != section_bytes:
        raise RuntimeError("页面设置校验失败")
    if len(body.xpath(".//w:drawing", namespaces=NS)) != sum(p["images"] for p in stats):
        raise RuntimeError("正文图片数量与新笔记不一致")
    extensions = {el.get("Extension").lower() for el in types if el.tag == q("ct:Default")}
    for name in media:
        extension = Path(name).suffix[1:]
        if extension not in extensions:
            E.SubElement(types, q("ct:Default"), Extension=extension,
                         ContentType="image/png" if extension == "png" else "image/jpeg")
            extensions.add(extension)
    package["word/document.xml"] = xml_bytes(root)
    package["word/_rels/document.xml.rels"] = xml_bytes(relations)
    package["[Content_Types].xml"] = xml_bytes(types)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w" if overwrite else "x", zipfile.ZIP_DEFLATED) as archive:
        for info in infos:
            archive.writestr(info, package[info.filename])
        for name, data in media.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as final, zipfile.ZipFile(template) as original:
        for name in original.namelist():
            if name not in EDITABLE and final.read(name) != original.read(name):
                raise RuntimeError(f"模板部件保留校验失败：{name}")
    report = {
        "output": str(output.resolve()), "template": str(template.resolve()),
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "papers": stats, "paper_count": len(stats),
        "new_note_image_count": len(media),
        "retained_template_media_count": sum(name.startswith("word/media/") for name in package),
        "preserved_parts": sum(info.filename not in EDITABLE for info in infos),
        "visual_qa": "待渲染并逐页检查；结构校验不代表版面或内容已经通过审核",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="按个人论文笔记模板，从逐篇 JSON 创建新 Word 文档。现有 DOCX 修改须原位编辑，不能用此脚本重建。")
    parser.add_argument("--notes-dir", required=True, type=Path, help="逐篇 JSON 所在目录；相对 PDF/图片路径以各 JSON 的父目录解析")
    parser.add_argument("--output", required=True, type=Path, help="新建 DOCX 路径；旁边同时写入 .build.json 结构校验记录")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="保留的单节模板 DOCX，默认为 skill 的 assets/reading-note-template.docx")
    parser.add_argument("--ids", nargs="+", help="可选论文 id 列表；按 JSON 文件名排序构建")
    parser.add_argument("--overwrite", action="store_true", help="显式允许替换既有输出及构建记录；绝不覆盖模板")
    args = parser.parse_args()
    try:
        if not args.template.is_file():
            raise ValueError(f"模板不存在：{args.template}")
        notes = load_notes(args.notes_dir.resolve(), args.ids)
        build(args.template.resolve(), notes, args.output.resolve(), args.overwrite)
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, E.XMLSyntaxError) as error:
        parser.exit(2, f"构建失败：{error}\n")


if __name__ == "__main__":
    main()
