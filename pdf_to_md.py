import argparse
import os
import re
import sys
from typing import Optional


def _normalize_text(text: str) -> str:
    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Trim trailing spaces on each line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse 3+ blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_text_with_pypdf(pdf_path: str) -> Optional[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    try:
        reader = PdfReader(pdf_path)
        pages_text = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)
        return "\n\n".join(pages_text)
    except Exception:
        return None


def extract_text_with_pdfminer(pdf_path: str) -> Optional[str]:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        return None

    try:
        return extract_text(pdf_path) or ""
    except Exception:
        return None


def extract_text_with_pymupdf(pdf_path: str) -> Optional[str]:
    try:
        import fitz  # PyMuPDF  # type: ignore
    except Exception:
        return None

    try:
        doc = fitz.open(pdf_path)
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
        return "\n\n".join(pages_text)
    except Exception:
        return None


def extract_pdf_text(pdf_path: str) -> str:
    # Try PyMuPDF (best layout), then pdfminer.six, then pypdf
    for extractor in (extract_text_with_pymupdf, extract_text_with_pdfminer, extract_text_with_pypdf):
        text = extractor(pdf_path)
        if text:
            return text

    raise RuntimeError(
        "No available PDF parsing backend found. Please install one of:\n"
        "  - PyMuPDF: pip install pymupdf\n"
        "  - pdfminer.six: pip install pdfminer.six\n"
        "  - pypdf: pip install pypdf\n"
    )


def convert_pdf_to_md(pdf_path: str, output_md_path: Optional[str] = None, output_dir: Optional[str] = None) -> str:
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if output_md_path is None:
        base, _ = os.path.splitext(os.path.basename(pdf_path))
        parent_dir = os.path.dirname(pdf_path)
        out_dir = output_dir or os.path.join(parent_dir, base)
        os.makedirs(out_dir, exist_ok=True)
        output_md_path = os.path.join(out_dir, base + ".md")

    text = extract_pdf_text(pdf_path)
    text = _normalize_text(text)

    # Write Markdown (plain text, no extra markup conversion)
    with open(output_md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    return output_md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown plain text file")
    parser.add_argument("pdf", help="Input PDF file path, e.g. leasing_agreement.pdf")
    parser.add_argument("-o", "--output", help="Output .md path; if omitted, writes to <same-name-folder>/<same-name>.md")
    parser.add_argument("--outdir", help="Output directory; mutually exclusive with --output. Defaults to a folder named after the PDF.")

    args = parser.parse_args()

    try:
        if args.output and args.outdir:
            print("--output and --outdir cannot be used together", file=sys.stderr)
            return 1
        out_path = convert_pdf_to_md(args.pdf, args.output, args.outdir)
        print(f"Generated: {out_path}")
        return 0
    except Exception as e:
        print(f"转换失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


