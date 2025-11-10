#!/usr/bin/env python3
"""
Docker-based isolated processing for PII documents.
Automatically creates and destroys containers for each processing job.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


def log_container_event(log_file: str, operation: str, **kwargs):
    """Log container operation to audit log."""
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "operation": operation,
        "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        **kwargs
    }
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Warning: Could not write to audit log: {e}", file=sys.stderr)


def process_in_container(
    input_file: str,
    output_dir: str,
    mode: str = "encrypt",
    entities: Optional[list] = None,
    audit_log: str = "audit.log"
) -> int:
    """
    Process document in isolated Docker container.
    
    Args:
        input_file: Input PDF/MD file
        output_dir: Output directory for results
        mode: 'encrypt' or 'anonymize'
        entities: List of PII entity types to detect
        audit_log: Audit log file path
    
    Returns:
        Exit code (0 for success)
    """
    try:
        import docker  # type: ignore
    except ImportError:
        print("Error: docker-py is not installed. Install it with:", file=sys.stderr)
        print("  pip install docker", file=sys.stderr)
        return 1
    
    if not os.path.isfile(input_file):
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        return 1
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get absolute paths
    input_abs = os.path.abspath(input_file)
    output_abs = os.path.abspath(output_dir)
    
    # Docker client
    try:
        client = docker.from_env()
    except Exception as e:
        print(f"Error: Could not connect to Docker: {e}", file=sys.stderr)
        print("Make sure Docker is running.", file=sys.stderr)
        return 1
    
    # Build command
    input_basename = os.path.basename(input_file)
    cmd = [
        "python", "pii_encrypt_md.py", "encrypt",
        f"/data/input/{input_basename}",
        "--outdir", "/data/output",
        "--mode", mode,
        "--print-key"
    ]
    
    if entities:
        cmd.extend(["--entities"] + entities)
    
    print(f"Processing {input_file} in isolated container...")
    print(f"Mode: {mode}")
    print(f"Output: {output_dir}")
    
    # Log container start
    log_container_event(
        audit_log,
        "container_start",
        input_file=input_basename,
        mode=mode
    )
    
    try:
        # Run container with volume mounts
        container = client.containers.run(
            "pii-processor:latest",
            command=cmd,
            volumes={
                os.path.dirname(input_abs): {'bind': '/data/input', 'mode': 'ro'},
                output_abs: {'bind': '/data/output', 'mode': 'rw'}
            },
            remove=True,  # Auto-remove after completion
            detach=False,
            stdout=True,
            stderr=True,
            user="piiuser"
        )
        
        # Print container output
        output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
        print(output)
        
        # Log success
        log_container_event(
            audit_log,
            "container_complete",
            input_file=input_basename,
            mode=mode,
            status="success"
        )
        
        print(f"\n✓ Processing complete. Container automatically destroyed.")
        return 0
    
    except docker.errors.ContainerError as e:
        print(f"Error: Container execution failed: {e}", file=sys.stderr)
        log_container_event(
            audit_log,
            "container_error",
            input_file=input_basename,
            error=str(e)
        )
        return 1
    
    except docker.errors.ImageNotFound:
        print("Error: Docker image 'pii-processor:latest' not found.", file=sys.stderr)
        print("Build it first with:", file=sys.stderr)
        print("  docker build -t pii-processor:latest .", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        log_container_event(
            audit_log,
            "container_error",
            input_file=input_basename,
            error=str(e)
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process PII documents in isolated Docker containers"
    )
    parser.add_argument(
        "input",
        help="Input PDF or Markdown file"
    )
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="Output directory (default: ./output)"
    )
    parser.add_argument(
        "--mode",
        choices=["encrypt", "anonymize"],
        default="encrypt",
        help="Processing mode (default: encrypt)"
    )
    parser.add_argument(
        "--entities",
        nargs="*",
        help="PII entity types to detect, e.g. EMAIL_ADDRESS PHONE_NUMBER"
    )
    parser.add_argument(
        "--audit-log",
        default="audit.log",
        help="Audit log file path (default: audit.log)"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build Docker image before processing"
    )
    
    args = parser.parse_args()
    
    # Build image if requested
    if args.build:
        print("Building Docker image...")
        try:
            import docker
            client = docker.from_env()
            image, logs = client.images.build(
                path=".",
                tag="pii-processor:latest",
                rm=True
            )
            for log in logs:
                if 'stream' in log:
                    print(log['stream'], end='')
            print("✓ Image built successfully")
        except Exception as e:
            print(f"Error building image: {e}", file=sys.stderr)
            return 1
    
    # Process document
    return process_in_container(
        input_file=args.input,
        output_dir=args.output,
        mode=args.mode,
        entities=args.entities,
        audit_log=args.audit_log
    )


if __name__ == "__main__":
    raise SystemExit(main())


