#!/usr/bin/env python3
"""
prebuild_check.py
=================
Pre-build safety gate for FrogPaper.

Runs BEFORE PyInstaller packs the EXE. Aborts the build (exit code 2) if any
of the secret fields in `config.json` (or `config.template.json`) contain a
non-empty value. This prevents the developer's real HuggingFace / Google /
Dropbox / OneDrive credentials from being baked into the binary even if
someone accidentally re-adds `config.json` to FrogPaper.spec in the future.

Usage:
    python prebuild_check.py

Exit codes:
    0  - OK to build (no secrets detected)
    2  - ABORT build (secrets detected)
    3  - ABORT build (config files unreadable / malformed)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Fields that must NEVER contain a real value at build time.
# Empty string is OK. Whitespace-only is OK. Anything else -> abort.
SECRET_FIELDS = (
    "huggingface_token",
    "google_client_id",
    "google_client_secret",
    "onedrive_client_id",
    "onedrive_client_secret",
    "dropbox_app_key",
    "dropbox_app_secret",
)

# oauth_tokens is a dict keyed by provider -> token. It must be empty.
SECRET_OBJECTS = ("oauth_tokens",)

# Patterns that look like real secrets (used as a second-line defense in case
# a new key is added to the schema and forgotten in SECRET_FIELDS).
SUSPICIOUS_PATTERNS = (
    "hf_",          # HuggingFace tokens start with hf_
    "GOCSPX-",      # Google OAuth client secrets
    "AIza",         # Google API keys
    "ya29.",        # Google OAuth access tokens
    "sl.",          # Dropbox long-lived tokens
    "xoxb-",        # Slack tokens (shouldn't be here, but just in case)
)


def _scan_config(path: Path) -> list[str]:
    """Return a list of human-readable problems with the given config file."""
    if not path.exists():
        return []  # Missing config is fine — runtime will seed from template.

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [f"{path.name}: unreadable/invalid JSON ({e}) — abort for safety"]

    if not isinstance(data, dict):
        return [f"{path.name}: top-level JSON is not an object"]

    problems: list[str] = []

    # 1. Check known secret fields.
    for field in SECRET_FIELDS:
        val = data.get(field, "")
        if isinstance(val, str):
            if val.strip():
                preview = val[:4] + "..." if len(val) > 4 else val
                problems.append(f"{path.name}: '{field}' is non-empty (starts with '{preview}')")

    # 2. Check secret object fields (must be empty dict).
    for field in SECRET_OBJECTS:
        val = data.get(field, {})
        if isinstance(val, dict) and val:
            problems.append(
                f"{path.name}: '{field}' contains {len(val)} non-empty entr"
                f"y{'ies' if len(val) != 1 else 'y'} "
                f"({', '.join(list(val.keys())[:5])})"
            )

    # 3. Pattern sweep across ALL string values (catches future schema additions).
    def _walk(obj, trail: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{trail}.{k}" if trail else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _walk(v, f"{trail}[{i}]")
        elif isinstance(obj, str):
            for pat in SUSPICIOUS_PATTERNS:
                if pat in obj and len(obj.strip()) >= 8:
                    problems.append(
                        f"{path.name}: suspicious value at '{trail}' "
                        f"matches pattern '{pat}*' (length={len(obj)})"
                    )

    _walk(data)
    return problems


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    candidates = [
        project_dir / "config.json",          # Developer's local config
        project_dir / "config.template.json", # The template that gets bundled
    ]

    all_problems: list[str] = []
    for cfg in candidates:
        all_problems.extend(_scan_config(cfg))

    if all_problems:
        print("=" * 72)
        print("FrogPaper pre-build check FAILED.")
        print("Refusing to package the EXE because real secrets would be")
        print("baked into the binary. Strip them first:")
        print()
        for p in all_problems:
            print(f"  - {p}")
        print()
        print("Fix:")
        print("  1. Empty the offending fields in config.json / config.template.json.")
        print("  2. Store your real keys in environment variables or the OS")
        print("     credential manager (keyring) instead of config.json.")
        print("  3. Re-run build_frogpaper_exe.bat")
        print("=" * 72)
        return 2

    print("Pre-build check OK: no secrets in config.json or config.template.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
