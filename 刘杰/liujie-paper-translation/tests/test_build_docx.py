"""Synthetic regression tests; generated DOCX files stay in temporary folders."""

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_docx.py"
SPEC = importlib.util.spec_from_file_location("translation_docx_builder", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def fixture():
    """All text and numerical values here are invented test material."""
    return {
        "schema_version": 1,
        "title_zh": "合成排版测试",
        "title_en": "Synthetic Layout Test",
        "sources": [{"id": f"s{i}"} for i in range(1, 6)],
        "front_matter_source_ids": {"title_zh": ["s1"], "title_en": ["s1"]},
        "blocks": [
            {"id": "intro", "kind": "heading", "level": 1, "number": "1", "source_ids": ["s2"], "zh": "测试目的"},
            {"id": "paragraph", "kind": "paragraph", "source_ids": ["s3"], "zh": "本文仅用于检查合成示例的段落与表格排版。"},
            {"id": "table", "kind": "table", "number": 1, "source_ids": ["s4"], "zh": "合成记录", "headers": ["记录", "数值"], "rows": [["用于验证较长描述文字对齐行为的虚构记录", "1.25"], ["记录乙", "2.50"]]},
            {"id": "ref", "kind": "reference", "source_ids": ["s5"], "text": "[1] A. Example. Synthetic reference. 2025."},
        ],
    }


def settings():
    return argparse.Namespace(page_size="letter", font_cjk="宋体", font_heading_cjk="黑体", font_latin="Times New Roman", mml2omml=None)


class BuildDocxTests(unittest.TestCase):
    def test_cli_writes_valid_document_and_report(self):
        with tempfile.TemporaryDirectory(prefix="translate-word-test-") as folder:
            base = Path(folder)
            source, output, report = base / "input.json", base / "output.docx", base / "report.json"
            data = fixture()
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, "-B", str(SCRIPT), str(source), "--output", str(output), "--report", str(report)]
            result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})
            self.assertEqual(result.returncode, 0, result.stderr)
            with ZipFile(output) as package:
                self.assertIsNone(package.testzip())
                document = etree.fromstring(package.read("word/document.xml"))
                footer = etree.fromstring(package.read("word/footer1.xml"))
                styles = etree.fromstring(package.read("word/styles.xml"))
            self.assertIn("合成排版测试", "".join(document.xpath("//w:t/text()", namespaces=NS)))
            title_styles = document.xpath("//w:pPr/w:pStyle[@w:val='Title']", namespaces=NS)
            self.assertEqual(len(title_styles), 1)
            starts = document.xpath("//w:bookmarkStart", namespaces=NS)
            ends = document.xpath("//w:bookmarkEnd", namespaces=NS)
            self.assertEqual(len(starts), len(data["blocks"]))
            self.assertEqual([x.get(builder.qn("w:id")) for x in starts], [x.get(builder.qn("w:id")) for x in ends])
            self.assertEqual(len({x.get(builder.qn("w:name")) for x in starts}), len(starts))
            self.assertEqual(len(document.xpath("//w:tbl", namespaces=NS)), 1)
            self.assertEqual(len(document.xpath("//w:tbl/w:tr[1]/w:trPr/w:tblHeader", namespaces=NS)), 1)
            self.assertEqual(len(document.xpath("//w:tbl/w:tr/w:trPr/w:cantSplit", namespaces=NS)), 3)
            left_alignment = document.xpath("//w:tbl/w:tr[2]/w:tc[1]/w:p/w:pPr/w:jc/@w:val", namespaces=NS)
            self.assertEqual(left_alignment, ["left"])
            self.assertEqual(footer.xpath("//w:fldSimple/@w:instr", namespaces=NS), ["PAGE"])
            self.assertEqual(footer.xpath("//w:fldSimple/w:r/w:rPr/w:sz/@w:val", namespaces=NS), ["18"])
            self.assertEqual(footer.xpath("//w:fldSimple/w:r/w:t/text()", namespaces=NS), ["1"])
            self.assertEqual(styles.xpath("//w:style[@w:styleId='Heading1']/w:rPr/w:rFonts/@w:eastAsia", namespaces=NS), ["黑体"])
            audit = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(audit["front_matter_source_ids"], data["front_matter_source_ids"])
            self.assertEqual(audit["visual_qa"], "NOT_RUN")
            original = output.read_bytes()
            refused = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("Refusing to overwrite", refused.stderr)
            self.assertEqual(output.read_bytes(), original)

    def test_optional_table_row_splitting_and_heading_font(self):
        with tempfile.TemporaryDirectory(prefix="translate-word-test-") as folder:
            data = fixture()
            data["blocks"][2]["allow_row_split"] = True
            args = settings()
            args.font_heading_cjk = "Noto Sans CJK SC"
            builder.validate(data)
            generated = builder.Builder(Path(folder) / "source.json", args)
            output = Path(folder) / "split.docx"
            generated.build(data).save(output)
            with ZipFile(output) as package:
                document = etree.fromstring(package.read("word/document.xml"))
                styles = etree.fromstring(package.read("word/styles.xml"))
            self.assertEqual(len(document.xpath("//w:tbl/w:tr/w:trPr/w:cantSplit", namespaces=NS)), 1)
            self.assertEqual(styles.xpath("//w:style[@w:styleId='Heading1']/w:rPr/w:rFonts/@w:eastAsia", namespaces=NS), ["Noto Sans CJK SC"])

    def test_front_matter_rejects_unknown_or_unrendered_mapping(self):
        data = fixture()
        data["front_matter_source_ids"]["title_zh"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "unknown source"):
            builder.validate(data)
        data = fixture()
        data["front_matter_source_ids"]["metadata_line"] = ["s1"]
        with self.assertRaisesRegex(ValueError, "absent or empty"):
            builder.validate(data)

    def test_math_json_control_characters_are_rejected_before_conversion(self):
        fake = builder.Builder.__new__(builder.Builder)
        for character in ("\t", "\f", "\b"):
            with self.subTest(codepoint=ord(character)):
                with self.assertRaisesRegex(ValueError, "JSON escaping"):
                    fake.add_math(None, character + "frac{1}{2}")

    def test_native_math_when_optional_dependencies_exist(self):
        if importlib.util.find_spec("latex2mathml") is None:
            self.skipTest("latex2mathml is not available")
        with tempfile.TemporaryDirectory(prefix="translate-word-test-") as folder:
            source = Path(folder) / "source.json"
            generated = builder.Builder(source, settings())
            try:
                generated.load_transform()
            except ValueError as exc:
                if "requires a local MML2OMML.XSL" in str(exc):
                    self.skipTest("A local MML2OMML.XSL is not available")
                raise
            data = fixture()
            data["blocks"][1]["zh"] = r"设 $x=2$，下式为合成数学示例。"
            data["sources"].append({"id": "s6"})
            data["blocks"].append({"id": "equation", "kind": "equation", "source_ids": ["s6"], "latex": r"\frac{x^2+1}{2}", "number": 1})
            builder.validate(data)
            output = Path(folder) / "math.docx"
            generated.build(data).save(output)
            with ZipFile(output) as package:
                document = etree.fromstring(package.read("word/document.xml"))
            self.assertEqual(len(document.xpath("//m:oMath", namespaces=NS)), 2)
            self.assertEqual(generated.math_count, 2)
            self.assertNotIn(r"\frac", "".join(document.xpath("//w:t/text()", namespaces=NS)))


if __name__ == "__main__":
    unittest.main()
