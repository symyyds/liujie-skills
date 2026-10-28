#!/usr/bin/env python3
"""Audit a supplied source inventory and its translation blocks.

This is a structural and numeric-candidate checker, not a translator, a PDF
extractor, or a semantic/visual verification service. Standard library only.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re
import sys
import unicodedata


BLOCK_KINDS = {
    "heading", "paragraph", "figure", "table", "equation", "reference",
    "list_item", "note",
}
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|TBD|FIXME)\b|待补(?:充)?|待翻译|占位符", re.I)
LEAK_RE = re.compile(
    r"\{\s*['\"](?:en|zh|text)['\"]\s*:|"
    r"(?:\ue200|\ue202|:codex-file-citation\{|::code-comment\{|turn\d+(?:search|view)\d+)"
)
SCIENTIFIC_RE = re.compile(
    r"(?<![A-Za-z0-9_.])([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*[×·*]\s*10\s*"
    r"(?:\^\s*\{?\s*([+-]?\d+)\s*\}?|\*\*\s*([+-]?\d+))"
)
TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_.])(?:0[xX][0-9A-Fa-f]+|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:\s*%)?|<=|>=|!=|<|>|\bRANGE\b|\^|/"
)


def _issue(code: str, location: str, message: str) -> dict:
    return {"code": code, "location": location, "message": message}


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _translated_text(block: dict) -> str:
    return _text(block.get("text")) if block.get("kind") == "reference" else _text(block.get("zh"))


def _valid_id(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _decimal(value: str) -> str:
    try:
        number = Decimal(value)
        if not number.is_finite():
            return value
        return "0" if number == 0 else str(number.normalize())
    except InvalidOperation:
        return value


def numeric_tokens(text: str) -> Counter:
    """Return normalized numeric atoms and notation that need human review.

    Values normalize 1.00 to 1 and 1 x 10^-3 (with a multiplication glyph) to
    1e-3. Precision, units, textual number words and scientific meaning still
    require human checking. Slashes/carets are retained only between numbers.
    """
    value = unicodedata.normalize("NFKC", text)
    value = value.replace("−", "-").replace("﹣", "-")
    value = value.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    value = re.sub(r"\\leq?\b", "<=", value)
    value = re.sub(r"\\geq?\b", ">=", value)
    value = re.sub(r"\\neq?\b", "!=", value)
    value = re.sub(r"\\times\b", "×", value)
    value = value.replace(r"\%", "%")
    value = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", value)
    value = SCIENTIFIC_RE.sub(lambda m: f"{m[1]}e{m[2] or m[3]}", value)
    # A hyphen between numeric endpoints is a range, not the second sign.
    value = re.sub(r"(?<=\d)\s*[-–—]\s*(?=[+-]?\d)", " RANGE ", value)
    value = re.sub(r"(?<=\d)\s*(?:to|至|到)\s*(?=[+-]?\d)", " RANGE ", value)
    tokens = Counter()
    for match in TOKEN_RE.finditer(value):
        token = match[0].replace(" ", "")
        if token in {"/", "^"}:
            before = value[:match.start()].rstrip()
            after = value[match.end():].lstrip(" {+")
            if not before or not before[-1].isdigit() or not re.match(r"-?\d", after):
                continue
        if token in {"<=", ">=", "!=", "<", ">", "RANGE", "/", "^"}:
            tokens[token] += 1
        elif token.lower().startswith("0x"):
            tokens[token.lower()] += 1
        else:
            percent = token.endswith("%")
            tokens[_decimal(token[:-1] if percent else token) + ("%" if percent else "")] += 1
    return tokens


def _strip_label(text: str, kind: str, number=None) -> str:
    if kind == "heading":
        if number is None:
            return text
        label = re.escape(str(number))
        return re.sub(r"^\s*(?:(?:Section|第)\s*)?" + label + r"(?!\d|\.\d)\s*(?:节|[.)、:：])?\s*", "", text, count=1, flags=re.I)
    if kind in {"figure", "table"}:
        label = r"(?:Figure|Fig\.?|图)" if kind == "figure" else r"(?:Table|表)"
        ordinal = re.escape(str(number)) if number is not None else r"\d+(?:\.\d+)*"
        return re.sub(r"^\s*" + label + r"\s*" + ordinal + r"(?!\d|\.\d)\s*[:：.)、]?\s*", "", text, count=1, flags=re.I)
    if kind == "equation" and number is not None:
        escaped = re.escape(str(number))
        text = re.sub(r"\\tag\s*\{" + escaped + r"\}", "", text)
        return re.sub(r"\s*\(" + escaped + r"\)\s*$", "", text)
    return text


def _counter_dict(counter: Counter) -> dict:
    return dict(sorted(counter.items()))


def _matrix_errors(item: dict, location: str) -> list:
    errors = []
    headers, rows = item.get("headers"), item.get("rows")
    if not isinstance(headers, list) or not headers:
        errors.append(_issue("table_headers", location, "Table headers must be a nonempty list."))
        return errors
    if not isinstance(rows, list):
        errors.append(_issue("table_rows", location, "Table rows must be a list (an empty data body is allowed)."))
        return errors
    for row_index, row in enumerate([headers, *rows]):
        suffix = ".headers" if row_index == 0 else f".rows[{row_index - 1}]"
        if not isinstance(row, list) or len(row) != len(headers):
            errors.append(_issue("table_rectangular", location + suffix, "Every row must have the header column count."))
            continue
        if any(not isinstance(cell, (str, int, float)) or isinstance(cell, bool) for cell in row):
            errors.append(_issue("table_cell", location + suffix, "Cells must be strings or numbers; use an empty string for a blank cell."))
        if any(isinstance(cell, float) and not math.isfinite(cell) for cell in row):
            errors.append(_issue("table_finite", location + suffix, "Numeric table cells must be finite; preserve intentional missing-value labels as strings."))
    return errors


def audit_document(data, base_dir: Path | str = ".") -> dict:
    errors, warnings, candidates = [], [], []
    result = {
        "schema_version": 1,
        "verification_scope": "Checks the supplied source inventory only; it cannot establish whether PDF extraction was complete.",
        "structural_pass": False,
        "numeric_review_required": False,
        "review_required": False,
        "semantic_verified": False,
        "visually_verified": False,
        "structural_errors": errors,
        "review_warnings": warnings,
        "numeric_candidates": candidates,
    }
    if not isinstance(data, dict):
        errors.append(_issue("root_type", "$", "The input must be a JSON object."))
        return result
    if data.get("schema_version") != 1:
        errors.append(_issue("schema_version", "$", "Expected schema_version 1."))
    if not _text(data.get("title_zh")).strip():
        errors.append(_issue("missing_title", "title_zh", "A nonempty string is required."))
    if not isinstance(data.get("title_en"), str):
        errors.append(_issue("missing_title", "title_en", "title_en must be a string; it may be empty when no English title is supplied or mapped."))
    if "metadata_line" in data and not isinstance(data["metadata_line"], str):
        errors.append(_issue("metadata_type", "metadata_line", "metadata_line must be a string."))
    for field in ("title_zh", "title_en", "metadata_line"):
        value = _text(data.get(field))
        if PLACEHOLDER_RE.search(value):
            warnings.append(_issue("placeholder", field, "Possible unfinished placeholder in rendered front matter; review in context."))
        if LEAK_RE.search(value):
            warnings.append(_issue("serialization_leak", field, "Possible serialized dictionary or tool citation token in rendered front matter."))
    sources, blocks = data.get("sources"), data.get("blocks")
    if not isinstance(sources, list) or not sources:
        errors.append(_issue("source_inventory", "sources", "A nonempty source inventory is required."))
        sources = []
    if not isinstance(blocks, list) or not blocks:
        errors.append(_issue("translation_inventory", "blocks", "A nonempty translation block list is required."))
        blocks = []
    by_source, coverage = {}, defaultdict(list)
    for index, source in enumerate(sources):
        loc = f"sources[{index}]"
        if not isinstance(source, dict) or not _valid_id(source.get("id")):
            errors.append(_issue("source_id", loc, "Each source requires a nonempty string id."))
            continue
        sid = source["id"]
        if sid in by_source:
            errors.append(_issue("duplicate_source_id", loc, f"Duplicate source id: {sid}"))
            continue
        by_source[sid] = source
        if not _text(source.get("kind")).strip():
            errors.append(_issue("source_kind", loc, "Each source requires a kind."))
        if not isinstance(source.get("text"), str):
            errors.append(_issue("source_text", loc, "Each source requires text; use an empty string only for an image-only object."))
        elif not source["text"].strip() and _text(source.get("kind")) not in {"figure", "table", "equation"}:
            errors.append(_issue("empty_source_text", loc, "Textual source blocks cannot be blank."))
        if source.get("kind") == "table":
            errors.extend(_matrix_errors(source, loc))
    shared = data.get("shared_source_ids", [])
    if not isinstance(shared, list) or any(not _valid_id(s) for s in shared):
        errors.append(_issue("shared_sources", "shared_source_ids", "Use an explicit list of source IDs."))
        shared = []
    if len(shared) != len(set(shared)):
        errors.append(_issue("shared_duplicate", "shared_source_ids", "Shared source IDs must be unique."))
    for sid in shared:
        if sid not in by_source:
            errors.append(_issue("unknown_shared_source", "shared_source_ids", f"Unknown source id: {sid}"))
    seen_blocks = set()

    def compare(original: str, translated: str, location: str, source_ids: list):
        source_numbers, translated_numbers = numeric_tokens(original), numeric_tokens(translated)
        missing, added = source_numbers - translated_numbers, translated_numbers - source_numbers
        if missing or added:
            candidates.append({"location": location, "source_ids": source_ids,
                               "missing_tokens": _counter_dict(missing), "added_tokens": _counter_dict(added)})

    front_matter = data.get("front_matter_source_ids", {})
    front_matter_ids = set()
    if not isinstance(front_matter, dict):
        errors.append(_issue("front_matter_type", "front_matter_source_ids", "Use an object mapping title_zh, title_en or metadata_line to explicit source-ID lists."))
        front_matter = {}
    for field, ids in front_matter.items():
        loc = "front_matter_source_ids." + field
        if field not in {"title_zh", "title_en", "metadata_line"}:
            errors.append(_issue("front_matter_field", loc, "Only title_zh, title_en and metadata_line can map front-matter sources."))
            continue
        if not isinstance(ids, list) or not ids or any(not _valid_id(s) for s in ids):
            errors.append(_issue("front_matter_ids", loc, "Use a nonempty explicit list of source IDs."))
            continue
        if len(ids) != len(set(ids)):
            errors.append(_issue("front_matter_duplicate", loc, "A field must not list the same source id twice."))
        for sid in set(ids):
            if sid not in by_source:
                errors.append(_issue("unknown_front_matter_source", loc, f"Unknown source id: {sid}"))
            else:
                front_matter_ids.add(sid)
        if not _text(data.get(field)).strip():
            errors.append(_issue("front_matter_content", field, "A mapped front-matter field needs nonempty text."))
        else:
            original = "\n".join(_text(by_source[s].get("text")) for s in ids if s in by_source)
            compare(original, data[field], field, ids)
    for sid in front_matter_ids:
        coverage[sid].append("front_matter")

    for index, block in enumerate(blocks):
        loc = f"blocks[{index}]"
        if not isinstance(block, dict):
            errors.append(_issue("block_type", loc, "Each translation block must be an object."))
            continue
        bid, kind = block.get("id"), block.get("kind")
        if not _valid_id(bid):
            errors.append(_issue("block_id", loc, "Each translation block requires a nonempty string id."))
        elif bid in seen_blocks:
            errors.append(_issue("duplicate_block_id", loc, f"Duplicate translation id: {bid}"))
        else:
            seen_blocks.add(bid)
        if not isinstance(kind, str) or kind not in BLOCK_KINDS:
            errors.append(_issue("block_kind", loc, f"Unsupported block kind: {kind!r}"))
            kind = "unsupported"
        ids = block.get("source_ids")
        if not isinstance(ids, list) or not ids or any(not _valid_id(s) for s in ids):
            errors.append(_issue("source_ids", loc, "source_ids must be a nonempty explicit list; ranges are not expanded."))
            ids = []
        if len(ids) != len(set(ids)):
            errors.append(_issue("duplicate_block_source", loc, "A block lists the same source id more than once."))
        for sid in set(ids):
            if sid not in by_source:
                errors.append(_issue("unknown_source_id", loc, f"Unknown source id: {sid}"))
            else:
                coverage[sid].append(bid or loc)
        translated = _translated_text(block)
        if kind != "equation" and not translated.strip():
            field = "text" if kind == "reference" else "zh"
            errors.append(_issue("missing_translation", loc, f"A nonempty {field} string is required for this block kind."))
        for key in ("zh", "text", "latex", "image", "notes"):
            if key in block and not isinstance(block[key], str):
                errors.append(_issue("field_type", loc + "." + key, "This field must be a string."))
        if "number" in block and (not isinstance(block["number"], (str, int)) or isinstance(block["number"], bool) or not str(block["number"]).strip()):
            errors.append(_issue("number_type", loc + ".number", "A label number must be a nonempty string or integer."))
        if kind in {"figure", "table"} and "number" not in block:
            errors.append(_issue("missing_number", loc + ".number", "A figure or table requires its source label number."))
        if kind == "heading" and (type(block.get("level", 1)) is not int or block.get("level", 1) not in (1, 2, 3)):
            errors.append(_issue("heading_level", loc + ".level", "Heading level must be an integer from 1 to 3."))
        if kind == "equation":
            if bool(_text(block.get("latex")).strip()) == bool(_text(block.get("image")).strip()):
                errors.append(_issue("equation_content", loc, "An equation needs exactly one nonempty representation: latex or image."))
            if any(char in _text(block.get("latex")) for char in ("\t", "\f", "\b")):
                errors.append(_issue("latex_escape", loc + ".latex", "LaTeX contains a tab, formfeed or backspace; check JSON backslash escaping."))
        if kind == "figure" and not _text(block.get("image")).strip():
            errors.append(_issue("figure_image", loc, "A figure requires an image path."))
        if _text(block.get("image")).strip():
            image = Path(block["image"])
            if image.is_absolute() or image.drive:
                errors.append(_issue("absolute_image", loc + ".image", "Image paths must be relative to the translation JSON file."))
            elif not (Path(base_dir) / image).is_file():
                errors.append(_issue("missing_image", loc + ".image", "The relative image path does not identify a local file."))
            if kind == "equation":
                warnings.append(_issue("image_equation_review", loc, "Inspect the equation image against the source; numerical text cannot be checked from pixels."))
        display_values = [translated, _text(block.get("notes"))]
        if kind == "figure" and "labels_zh" in block:
            labels = block["labels_zh"]
            if not isinstance(labels, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items()):
                errors.append(_issue("figure_labels", loc, "labels_zh must map original-label strings to translated-label strings."))
            else:
                display_values.extend(labels.values())
        if kind == "table":
            matrix_errors = _matrix_errors(block, loc)
            errors.extend(matrix_errors)
            if not matrix_errors:
                display_values += [str(cell) for row in [block["headers"], *block["rows"]] for cell in row]
            source_tables = [by_source[s] for s in ids if s in by_source and by_source[s].get("kind") == "table"]
            if len(ids) == 1 and len(source_tables) == 1 and not matrix_errors and not _matrix_errors(source_tables[0], loc):
                source_table = source_tables[0]
                if len(block["headers"]) != len(source_table["headers"]) or len(block["rows"]) != len(source_table["rows"]):
                    errors.append(_issue("table_dimensions", loc, "Source and translated table dimensions differ; do not silently drop or merge rows/columns."))
                else:
                    for row_index, (original_row, target_row) in enumerate(zip([source_table["headers"], *source_table["rows"]], [block["headers"], *block["rows"]])):
                        for column, (original_cell, target_cell) in enumerate(zip(original_row, target_row)):
                            row_loc = ".headers" if row_index == 0 else f".rows[{row_index - 1}]"
                            compare(str(original_cell), str(target_cell), loc + row_loc + f"[{column}]", ids)
            else:
                warnings.append(_issue("table_mapping_review", loc, "Per-cell numeric comparison needs one source table with a valid rectangular matrix."))
        for value in display_values:
            if PLACEHOLDER_RE.search(value):
                warnings.append(_issue("placeholder", loc, "Possible unfinished placeholder in rendered text; review in context."))
            if LEAK_RE.search(value):
                warnings.append(_issue("serialization_leak", loc, "Possible serialized dictionary or tool citation token in rendered text."))
        original = "\n".join(_text(by_source[s].get("text")) for s in ids if s in by_source)
        if kind == "equation":
            translated = _text(block.get("latex"))
        if translated:
            compare(_strip_label(original, kind, block.get("number")),
                    _strip_label(translated, kind, block.get("number")), loc, ids)

    omissions = data.get("omissions", [])
    if not isinstance(omissions, list):
        errors.append(_issue("omissions_type", "omissions", "omissions must be a list."))
        omissions = []
    omitted = set()
    for index, omission in enumerate(omissions):
        loc = f"omissions[{index}]"
        if not isinstance(omission, dict) or not _valid_id(omission.get("source_id")):
            errors.append(_issue("omission_id", loc, "An omission requires source_id and a nonempty reason."))
            continue
        sid = omission["source_id"]
        if not _text(omission.get("reason")).strip():
            errors.append(_issue("omission_reason", loc, "Explain the exclusion; coverage alone does not approve its reason."))
        if sid not in by_source:
            errors.append(_issue("unknown_omission", loc, f"Unknown source id: {sid}"))
        if sid in omitted:
            errors.append(_issue("duplicate_omission", loc, f"Duplicate omission: {sid}"))
        if sid in coverage:
            errors.append(_issue("covered_and_omitted", loc, f"The same source is translated and omitted: {sid}"))
        omitted.add(sid)
    uncovered = sorted(set(by_source) - set(coverage) - omitted)
    for sid in uncovered:
        errors.append(_issue("uncovered_source", "sources", f"Source is neither translated nor explicitly omitted: {sid}"))
    for sid, owners in coverage.items():
        if len(owners) > 1 and sid not in shared:
            errors.append(_issue("double_coverage", "blocks", f"Source {sid} belongs to multiple blocks; declare intentional sharing in shared_source_ids."))
    result["coverage"] = {"source_count": len(by_source), "translation_block_count": len(blocks),
                          "covered_count": len(coverage), "omitted_count": len(omitted & set(by_source)),
                          "front_matter_source_count": len(front_matter_ids),
                          "uncovered_source_ids": uncovered}
    result["structural_pass"] = not errors
    result["numeric_review_required"] = bool(candidates)
    result["review_required"] = bool(candidates or warnings or omissions)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Translation JSON to inspect")
    parser.add_argument("--output", type=Path, help="Write the JSON report (otherwise stdout)")
    parser.add_argument("--strict-numbers", action="store_true", help="Exit 2 when numeric candidates need review")
    args = parser.parse_args(argv)
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("The output report must not overwrite the input translation JSON.")
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        report = audit_document(data, args.input.resolve().parent)
    except (OSError, ValueError) as exc:
        print(f"Cannot audit input: {exc}", file=sys.stderr)
        return 1
    if args.output and isinstance(data, dict) and isinstance(data.get("blocks"), list):
        for block in data["blocks"]:
            if isinstance(block, dict) and _text(block.get("image")).strip():
                image_path = (args.input.resolve().parent / block["image"]).resolve()
                if args.output.resolve() == image_path:
                    parser.error("The output report must not overwrite a referenced image asset.")
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({"structural_pass": report["structural_pass"],
                          "numeric_review_required": report["numeric_review_required"],
                          "review_required": report["review_required"]}, ensure_ascii=False))
    else:
        print(payload)
    if not report["structural_pass"]:
        return 1
    return 2 if args.strict_numbers and report["numeric_review_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
