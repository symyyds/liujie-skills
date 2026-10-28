#!/usr/bin/env python3
"""Read-only DOCX -> PNG rendering through an isolated Microsoft Word instance.

Windows + Microsoft Word + pywin32 are required. Without --renderer, PyMuPDF
performs rasterization. --renderer may point to an available, trusted Documents
render_docx.py; its PDF conversion hook is replaced with Word. This does not
inspect images or establish visual/semantic correctness.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


def word_to_pdf(source: Path, target: Path):
    if sys.platform != "win32":
        raise RuntimeError("This renderer requires Windows and Microsoft Word")
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("pywin32 is missing from the selected Python runtime") from exc
    pythoncom.CoInitialize()
    application = document = None
    try:
        application = win32com.client.DispatchEx("Word.Application")
        application.Visible = False
        application.DisplayAlerts = 0
        application.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        document = application.Documents.Open(
            str(source.resolve()), ReadOnly=True, AddToRecentFiles=False,
            Visible=False, ConfirmConversions=False,
        )
        document.Repaginate()
        document.ExportAsFixedFormat(
            OutputFileName=str(target.resolve()), ExportFormat=17,
            OpenAfterExport=False, OptimizeFor=0, Range=0, Item=0,
            IncludeDocProps=False, KeepIRM=False, CreateBookmarks=1,
            DocStructureTags=True, BitmapMissingFonts=True,
            UseISO19005_1=False,
        )
    finally:
        try:
            if document is not None:
                document.Close(SaveChanges=0)
        finally:
            try:
                if application is not None:
                    application.Quit(SaveChanges=0)
            finally:
                pythoncom.CoUninitialize()
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("Word did not produce a nonempty PDF")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--emit-pdf", action="store_true")
    parser.add_argument("--renderer", type=Path, help="Trusted existing Documents render_docx.py")
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output_dir.resolve()
    if source.suffix.lower() != ".docx" or not source.is_file():
        parser.error("Input must be an existing .docx file")
    if not 72 <= args.dpi <= 600:
        parser.error("--dpi must be between 72 and 600")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("Use a new or empty output directory to avoid mixing stale pages")
    if args.renderer and not args.renderer.is_file():
        parser.error("--renderer must be an existing trusted Python renderer")
    output.mkdir(parents=True, exist_ok=True)
    try:
        if args.renderer:
            spec = importlib.util.spec_from_file_location("documents_renderer", args.renderer.resolve())
            if spec is None or spec.loader is None:
                raise RuntimeError("Cannot load Documents renderer")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not callable(getattr(module, "convert_to_pdf", None)) or not callable(getattr(module, "main", None)):
                raise RuntimeError("Unsupported renderer API; use standalone mode or inspect renderer compatibility")

            def convert_to_pdf(doc_path, user_profile, convert_tmp_dir, stem, verbose):
                target = Path(convert_tmp_dir) / f"{stem}.pdf"
                word_to_pdf(Path(doc_path), target)
                return str(target), "Read-only Microsoft Word export using an isolated instance"

            module.convert_to_pdf = convert_to_pdf
            previous_argv = sys.argv
            sys.argv = [str(args.renderer), str(source), "--output_dir", str(output), "--dpi", str(args.dpi)]
            if args.emit_pdf:
                sys.argv.append("--emit_pdf")
            try:
                module.main()
            finally:
                sys.argv = previous_argv
        else:
            try:
                import fitz
            except ImportError as exc:
                raise RuntimeError("Standalone rasterization requires PyMuPDF in the selected runtime") from exc
            with tempfile.TemporaryDirectory(prefix="paper-translate-render-") as temporary:
                pdf = output / f"{source.stem}.pdf" if args.emit_pdf else Path(temporary) / "render.pdf"
                word_to_pdf(source, pdf)
                with fitz.open(pdf) as document:
                    for index, page in enumerate(document, 1):
                        page.get_pixmap(matrix=fitz.Matrix(args.dpi / 72, args.dpi / 72), alpha=False).save(output / f"page-{index}.png")
        pages = list(output.glob("page-*.png"))
        if not pages:
            raise RuntimeError("Rendering produced no page PNGs")
        print(json.dumps({"page_count": len(pages), "output_dir": str(output), "visual_review": "NOT_RUN"}, ensure_ascii=False))
    except Exception as exc:
        parser.exit(1, f"Render failed: {exc}\n")


if __name__ == "__main__":
    main()
