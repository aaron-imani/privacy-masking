#!/usr/bin/env python3
"""
S3 encrypted storage integration for secure document upload.
Supports server-side encryption (AES256 or KMS).
"""
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional


def upload_to_s3(
    file_path: str,
    bucket: str,
    key: Optional[str] = None,
    encryption: str = "AES256",
    kms_key_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> str:
    """
    Upload file to S3 with server-side encryption.
    
    Args:
        file_path: Local file to upload
        bucket: S3 bucket name
        key: S3 object key (defaults to basename)
        encryption: 'AES256' or 'aws:kms'
        kms_key_id: KMS key ID (required if encryption='aws:kms')
        metadata: Optional metadata dict
    
    Returns:
        S3 URI (s3://bucket/key)
    """
    try:
        import boto3  # type: ignore
    except ImportError:
        raise RuntimeError(
            "boto3 is not installed. Install it with:\n"
            "  pip install boto3"
        )
    
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Default key is basename
    if key is None:
        key = os.path.basename(file_path)
    
    s3_client = boto3.client('s3')
    
    # Prepare upload args
    upload_args = {
        'Bucket': bucket,
        'Key': key,
        'ServerSideEncryption': encryption
    }
    
    if encryption == 'aws:kms' and kms_key_id:
        upload_args['SSEKMSKeyId'] = kms_key_id
    
    if metadata:
        upload_args['Metadata'] = metadata
    
    # Upload file
    with open(file_path, 'rb') as f:
        s3_client.put_object(Body=f.read(), **upload_args)
    
    s3_uri = f"s3://{bucket}/{key}"
    return s3_uri


def log_upload_event(log_file: str, file_path: str, s3_uri: str, encryption: str):
    """Log S3 upload event to audit log."""
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "operation": "s3_upload",
        "file": os.path.basename(file_path),
        "s3_uri": s3_uri,
        "encryption": encryption,
        "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    }
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Warning: Could not write to audit log: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload files to S3 with server-side encryption"
    )
    parser.add_argument(
        "file",
        help="File to upload"
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name"
    )
    parser.add_argument(
        "--key",
        help="S3 object key (defaults to file basename)"
    )
    parser.add_argument(
        "--encryption",
        choices=["AES256", "aws:kms"],
        default="AES256",
        help="Server-side encryption method (default: AES256)"
    )
    parser.add_argument(
        "--kms-key-id",
        help="KMS key ID (required if encryption=aws:kms)"
    )
    parser.add_argument(
        "--metadata",
        nargs="*",
        help="Metadata key=value pairs, e.g. --metadata type=pii-masked version=1"
    )
    parser.add_argument(
        "--audit-log",
        default="audit.log",
        help="Audit log file path (default: audit.log)"
    )
    
    args = parser.parse_args()
    
    if args.encryption == "aws:kms" and not args.kms_key_id:
        print("Error: --kms-key-id is required when encryption=aws:kms", file=sys.stderr)
        return 1
    
    # Parse metadata
    metadata = {}
    if args.metadata:
        for item in args.metadata:
            if "=" not in item:
                print(f"Warning: Invalid metadata format '{item}', expected key=value", file=sys.stderr)
                continue
            k, v = item.split("=", 1)
            metadata[k] = v
    
    try:
        print(f"Uploading {args.file} to s3://{args.bucket}/{args.key or os.path.basename(args.file)}...")
        print(f"Encryption: {args.encryption}")
        
        s3_uri = upload_to_s3(
            file_path=args.file,
            bucket=args.bucket,
            key=args.key,
            encryption=args.encryption,
            kms_key_id=args.kms_key_id,
            metadata=metadata or None
        )
        
        print(f"✓ Uploaded successfully: {s3_uri}")
        
        # Log to audit
        log_upload_event(args.audit_log, args.file, s3_uri, args.encryption)
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


