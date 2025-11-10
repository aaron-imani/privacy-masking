import argparse
import base64
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple


# ---- Audit logging setup ----
def setup_audit_logger(log_file: str = "audit.log") -> logging.Logger:
    """Setup structured audit logger that outputs JSON format."""
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if not audit_logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit_logger.addHandler(handler)
    
    return audit_logger


def log_audit_event(operation: str, file_path: str, **kwargs):
    """Log an audit event with metadata only (no actual content)."""
    audit_logger = logging.getLogger("audit")
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "operation": operation,
        "file": os.path.basename(file_path),
        "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        **kwargs
    }
    audit_logger.info(json.dumps(event, ensure_ascii=False))


# ---- Crypto helpers (Fernet) ----
def ensure_fernet_key(key_b64: Optional[str]) -> bytes:
    if key_b64:
        try:
            key = base64.urlsafe_b64decode(key_b64)
            # Re-encode to Fernet format if needed
            key_b64_checked = base64.urlsafe_b64encode(key)
            return key_b64_checked
        except Exception as exc:
            raise ValueError(f"Invalid key: {exc}")
    else:
        from cryptography.fernet import Fernet  # type: ignore

        return Fernet.generate_key()


def encrypt_text(plaintext: str, key_b64: bytes) -> str:
    from cryptography.fernet import Fernet  # type: ignore

    f = Fernet(key_b64)
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str, key_b64: bytes) -> str:
    from cryptography.fernet import Fernet  # type: ignore

    f = Fernet(key_b64)
    return f.decrypt(token.encode("utf-8")).decode("utf-8")


# ---- Presidio analyzer setup ----
def build_analyzer():
    from presidio_analyzer import AnalyzerEngine  # type: ignore
    from presidio_analyzer.nlp_engine import NlpEngineProvider  # type: ignore

    # Prefer en_core_web_lg, fallback to en_core_web_sm
    for model in ("en_core_web_lg", "en_core_web_sm"):
        try:
            provider = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": model}],
            })
            nlp_engine = provider.create_engine()
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"]) 
            # Quick warm-up to validate
            analyzer.analyze(text="warm up", language="en")
            return analyzer
        except Exception:
            continue

    # Finally try default engine (works if env already has a default model)
    try:
        analyzer = AnalyzerEngine()
        analyzer.analyze(text="warm up", language="en")
        return analyzer
    except Exception as exc:
        raise RuntimeError(
            "No usable spaCy English model found. Install one and retry:\n"
            "  - en_core_web_sm: python -m spacy download en_core_web_sm\n"
            "  - en_core_web_lg: python -m spacy download en_core_web_lg\n"
            f"Original error: {exc}"
        )


@dataclass
class PiiMatch:
    start: int
    end: int
    entity_type: str
    score: float
    text: str
    line: int
    column: int


def calculate_line_col_map(text: str) -> List[int]:
    # Return the start offset of each line
    line_starts = [0]
    for match in re.finditer("\n", text):
        line_starts.append(match.end())
    return line_starts


def offset_to_line_col(offset: int, line_starts: List[int]) -> Tuple[int, int]:
    # Linear scan is fine for small docs; binary search could optimize
    line_index = 0
    for i, start in enumerate(line_starts):
        if start <= offset:
            line_index = i
        else:
            break
    line_start = line_starts[line_index]
    line_no = line_index + 1
    col_no = offset - line_start + 1
    return line_no, col_no


def analyze_pii(md_text: str, entities: Optional[List[str]] = None) -> List[PiiMatch]:
    from presidio_analyzer import RecognizerResult  # type: ignore

    analyzer = build_analyzer()
    results: List[RecognizerResult] = analyzer.analyze(
        text=md_text,
        language="en",
        entities=entities,
        return_decision_process=False,
    )

    line_starts = calculate_line_col_map(md_text)
    matches: List[PiiMatch] = []
    for r in results:
        start, end = r.start, r.end
        snippet = md_text[start:end]
        line, column = offset_to_line_col(start, line_starts)
        matches.append(PiiMatch(
            start=start,
            end=end,
            entity_type=r.entity_type,
            score=r.score or 0.0,
            text=snippet,
            line=line,
            column=column,
        ))
    return matches


def write_report(md_path: str, matches: List[PiiMatch], report_path: Optional[str] = None) -> str:
    if report_path is None:
        report_path = md_path + ".pii.json"

    data = {
        "file": os.path.basename(md_path),
        "total": len(matches),
        "matches": [
            {
                "start": m.start,
                "end": m.end,
                "entity_type": m.entity_type,
                "score": m.score,
                "text": m.text,
                "line": m.line,
                "column": m.column,
            }
            for m in matches
        ],
    }

    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return report_path


ENCODED_PATTERN = re.compile(r"\{\{ENC:([A-Z_]+):([A-Za-z0-9_\-]+=*)\}\}")


def apply_encryption_replacements(md_text: str, matches: List[PiiMatch], key_b64: bytes) -> str:
    # Replace from back to front to avoid offset drift
    matches_sorted = sorted(matches, key=lambda m: m.start, reverse=True)
    buf = md_text
    for m in matches_sorted:
        ciphertext = encrypt_text(m.text, key_b64)
        safe_token = f"{{{{ENC:{m.entity_type}:{ciphertext}}}}}"
        buf = buf[: m.start] + safe_token + buf[m.end :]
    return buf


def apply_anonymization_replacements(md_text: str, matches: List[PiiMatch]) -> str:
    """Apply irreversible anonymization by replacing PII with placeholders."""
    matches_sorted = sorted(matches, key=lambda m: m.start, reverse=True)
    buf = md_text
    for m in matches_sorted:
        # Use hash to create consistent but non-reversible placeholder
        hash_suffix = abs(hash(m.text)) % 10000
        placeholder = f"[{m.entity_type}_{hash_suffix}]"
        buf = buf[: m.start] + placeholder + buf[m.end :]
    return buf


def decrypt_markers(md_text: str, key_b64: bytes) -> str:
    def _replace(match: re.Match) -> str:
        entity = match.group(1)
        token = match.group(2)
        try:
            plain = decrypt_text(token, key_b64)
            return plain
        except Exception:
            # If decryption fails, keep marker as-is to avoid data loss
            return match.group(0)

    return ENCODED_PATTERN.sub(_replace, md_text)


def _derive_outdir_from_input(input_path: str, explicit_outdir: Optional[str]) -> str:
    if explicit_outdir:
        os.makedirs(explicit_outdir, exist_ok=True)
        return explicit_outdir
    base = os.path.splitext(os.path.basename(input_path))[0]
    parent = os.path.dirname(input_path)
    outdir = os.path.join(parent, base)
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _convert_pdf_if_needed(input_path: str, outdir: str) -> str:
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        # Lazy import to avoid circular deps
        from pdf_to_md import convert_pdf_to_md  # type: ignore

        md_path = convert_pdf_to_md(input_path, output_md_path=None, output_dir=outdir)
        return md_path
    return input_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and encrypt/decrypt PII in Markdown/PDF")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # encrypt subcommand
    p_enc = sub.add_parser("encrypt", help="Detect and encrypt PII in the document")
    p_enc.add_argument("input", help="Input Markdown or PDF file")
    p_enc.add_argument("-o", "--output", help="Output file path (defaults to same-name file under same-name folder)")
    p_enc.add_argument("--outdir", help="Output directory (defaults to folder named after the input file)")
    p_enc.add_argument("--mode", choices=["encrypt", "anonymize"], default="encrypt", 
                       help="Processing mode: 'encrypt' (reversible) or 'anonymize' (irreversible)")
    p_enc.add_argument("--key", help="Base64(urlsafe) Fernet key. If omitted, a new key is generated (only for encrypt mode)")
    p_enc.add_argument("--entities", nargs="*", help="Restrict PII types, e.g. EMAIL_ADDRESS PHONE_NUMBER")
    p_enc.add_argument("--report", help="PII report JSON path (defaults to <md>.pii.json in the output directory)")
    p_enc.add_argument("--print-key", action="store_true", help="Print the generated key (only for encrypt mode)")
    p_enc.add_argument("--audit-log", default="audit.log", help="Audit log file path (default: audit.log)")

    # decrypt subcommand
    p_dec = sub.add_parser("decrypt", help="Decrypt PII markers in the document")
    p_dec.add_argument("input", help="Input Markdown file containing {{ENC:..}} markers")
    p_dec.add_argument("-o", "--output", help="Output file path (defaults to same-name file under same-name folder)")
    p_dec.add_argument("--outdir", help="Output directory (defaults to folder named after the input file)")
    p_dec.add_argument("--key", required=True, help="Base64(urlsafe) Fernet key")
    p_dec.add_argument("--audit-log", default="audit.log", help="Audit log file path (default: audit.log)")

    args = parser.parse_args()

    if args.cmd == "encrypt":
        # Setup audit logging
        setup_audit_logger(args.audit_log)
        
        if args.output and args.outdir:
            print("--output and --outdir cannot be used together", file=sys.stderr)
            return 1
        if not os.path.isfile(args.input):
            print(f"File not found: {args.input}", file=sys.stderr)
            return 1

        outdir = _derive_outdir_from_input(args.input, args.outdir)

        # If input is PDF, convert to Markdown first
        work_input = _convert_pdf_if_needed(args.input, outdir)

        # For anonymize mode, key is not needed
        if args.mode == "encrypt":
            key_b64 = ensure_fernet_key(args.key)
            key_b64_str = key_b64.decode("utf-8")
        else:
            key_b64 = None
            key_b64_str = None

        with open(work_input, "r", encoding="utf-8") as f:
            md_text = f.read()

        matches = analyze_pii(md_text, args.entities)

        # Target Markdown output path
        if args.output:
            out_md_path = args.output
            os.makedirs(os.path.dirname(out_md_path) or ".", exist_ok=True)
        else:
            base = os.path.splitext(os.path.basename(work_input))[0]
            out_md_path = os.path.join(outdir, base + ".md")

        # Report path
        report_path = args.report or (out_md_path + ".pii.json")

        # Write outputs based on mode
        if args.mode == "encrypt":
            processed_text = apply_encryption_replacements(md_text, matches, key_b64)
        else:  # anonymize
            processed_text = apply_anonymization_replacements(md_text, matches)
        
        with open(out_md_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(processed_text)
        write_report(out_md_path, matches, report_path)

        # Log audit event
        entity_counts = {}
        for m in matches:
            entity_counts[m.entity_type] = entity_counts.get(m.entity_type, 0) + 1
        
        log_audit_event(
            operation=f"pii_{args.mode}",
            file_path=args.input,
            mode=args.mode,
            pii_total=len(matches),
            entity_counts=entity_counts,
            output_file=os.path.basename(out_md_path),
            report_file=os.path.basename(report_path)
        )

        print(f"Written: {out_md_path}")
        print(f"PII report: {report_path}")
        if args.mode == "encrypt" and not args.key and args.print_key:
            print(f"Generated key (keep it safe): {key_b64_str}")
        return 0

    if args.cmd == "decrypt":
        # Setup audit logging
        setup_audit_logger(args.audit_log)
        
        if args.output and args.outdir:
            print("--output and --outdir cannot be used together", file=sys.stderr)
            return 1
        if not os.path.isfile(args.input):
            print(f"File not found: {args.input}", file=sys.stderr)
            return 1

        # Normalize key
        try:
            key_bytes = ensure_fernet_key(args.key)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1

        with open(args.input, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Count encrypted markers before decryption
        encrypted_markers = len(ENCODED_PATTERN.findall(md_text))
        
        decrypted_text = decrypt_markers(md_text, key_bytes)

        if args.output:
            out_path = args.output
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        elif args.outdir:
            os.makedirs(args.outdir, exist_ok=True)
            base = os.path.splitext(os.path.basename(args.input))[0]
            out_path = os.path.join(args.outdir, base + ".decrypted.md")
        else:
            # Default: output to same directory as input file
            input_dir = os.path.dirname(args.input) or "."
            base = os.path.splitext(os.path.basename(args.input))[0]
            out_path = os.path.join(input_dir, base + ".decrypted.md")

        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(decrypted_text)
        
        # Log audit event
        log_audit_event(
            operation="pii_decrypt",
            file_path=args.input,
            markers_decrypted=encrypted_markers,
            output_file=os.path.basename(out_path)
        )
        
        print(f"Written: {out_path}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


