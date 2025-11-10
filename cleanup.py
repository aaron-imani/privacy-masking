#!/usr/bin/env python3
"""
Automatic data retention and cleanup script.
Deletes files older than specified retention period.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


def find_old_files(directory: str, max_age_days: int, patterns: List[str]) -> List[Tuple[str, float]]:
    """Find files older than max_age_days matching patterns."""
    now = time.time()
    cutoff = now - (max_age_days * 86400)
    old_files = []
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # Check if file matches any pattern
            if patterns and not any(filename.endswith(p) or p in filename for p in patterns):
                continue
            
            filepath = os.path.join(root, filename)
            try:
                mtime = os.path.getmtime(filepath)
                if mtime < cutoff:
                    age_days = (now - mtime) / 86400
                    old_files.append((filepath, age_days))
            except OSError:
                continue
    
    return old_files


def delete_files(files: List[Tuple[str, float]], dry_run: bool = False) -> Tuple[int, int]:
    """Delete files and return (success_count, error_count)."""
    success = 0
    errors = 0
    
    for filepath, age_days in files:
        try:
            if dry_run:
                print(f"[DRY RUN] Would delete: {filepath} (age: {age_days:.1f} days)")
            else:
                os.remove(filepath)
                print(f"Deleted: {filepath} (age: {age_days:.1f} days)")
            success += 1
        except OSError as e:
            print(f"Error deleting {filepath}: {e}", file=sys.stderr)
            errors += 1
    
    return success, errors


def cleanup_empty_dirs(directory: str, dry_run: bool = False) -> int:
    """Remove empty directories and return count."""
    removed = 0
    
    for root, dirs, files in os.walk(directory, topdown=False):
        for dirname in dirs:
            dirpath = os.path.join(root, dirname)
            try:
                if not os.listdir(dirpath):  # Empty directory
                    if dry_run:
                        print(f"[DRY RUN] Would remove empty dir: {dirpath}")
                    else:
                        os.rmdir(dirpath)
                        print(f"Removed empty directory: {dirpath}")
                    removed += 1
            except OSError:
                continue
    
    return removed


def log_cleanup_event(log_file: str, directory: str, retention_days: int, 
                      files_deleted: int, errors: int, dry_run: bool):
    """Log cleanup event to audit log."""
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "operation": "cleanup",
        "directory": directory,
        "retention_days": retention_days,
        "files_deleted": files_deleted,
        "errors": errors,
        "dry_run": dry_run,
        "user": os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    }
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Warning: Could not write to audit log: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automatic cleanup of old files based on retention policy"
    )
    parser.add_argument(
        "directory",
        help="Directory to clean up"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=7,
        help="Delete files older than this many days (default: 7)"
    )
    parser.add_argument(
        "--patterns",
        nargs="*",
        help="File patterns to match (e.g., .md .json .pdf). If omitted, matches all files."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--remove-empty-dirs",
        action="store_true",
        help="Also remove empty directories after cleanup"
    )
    parser.add_argument(
        "--audit-log",
        default="audit.log",
        help="Audit log file path (default: audit.log)"
    )
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: Directory not found: {args.directory}", file=sys.stderr)
        return 1
    
    print(f"Scanning {args.directory} for files older than {args.retention_days} days...")
    if args.patterns:
        print(f"Matching patterns: {', '.join(args.patterns)}")
    
    old_files = find_old_files(args.directory, args.retention_days, args.patterns or [])
    
    if not old_files:
        print("No files to delete.")
        log_cleanup_event(args.audit_log, args.directory, args.retention_days, 0, 0, args.dry_run)
        return 0
    
    print(f"\nFound {len(old_files)} file(s) to delete:")
    for filepath, age_days in old_files:
        print(f"  - {filepath} ({age_days:.1f} days old)")
    
    if args.dry_run:
        print("\n[DRY RUN MODE] No files will be deleted.")
    else:
        confirm = input("\nProceed with deletion? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return 0
    
    print("\nDeleting files...")
    success, errors = delete_files(old_files, args.dry_run)
    
    if args.remove_empty_dirs and not args.dry_run:
        print("\nRemoving empty directories...")
        removed_dirs = cleanup_empty_dirs(args.directory, args.dry_run)
        print(f"Removed {removed_dirs} empty director(ies).")
    
    print(f"\nSummary:")
    print(f"  Files deleted: {success}")
    print(f"  Errors: {errors}")
    
    # Log to audit
    log_cleanup_event(args.audit_log, args.directory, args.retention_days, success, errors, args.dry_run)
    
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


