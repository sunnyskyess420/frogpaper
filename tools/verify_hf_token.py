"""Is the stored Hugging Face token actually usable?

    python tools/verify_hf_token.py
    python tools/verify_hf_token.py --token hf_xxx     (does not save it)

Two checks, both free and neither generating an image:
  1. whoami-v2 - is the token real, and whose is it?
  2. a POST to a model id that cannot exist - Hugging Face checks permissions
     before it looks for a model, so this says whether the token may call
     Inference Providers at all (a fine-grained read-only token may not).

The token itself is never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WHOAMI = "https://huggingface.co/api/whoami-v2"
#: Cannot exist on purpose: permissions are checked before model lookup.
PROBE_URL = "https://router.huggingface.co/hf-inference/models/frogpaper/probe-none"


def stored_token() -> str:
    from utils import get_huggingface_token
    return (get_huggingface_token() or "").strip()


def whoami(token: str) -> tuple[int | str, dict | str]:
    request = urllib.request.Request(WHOAMI, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:200]
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw
    except Exception as exc:  # network, DNS, ...
        return "ERR", str(exc)[:200]


def probe_inference(token: str) -> tuple[int | str, str]:
    """Can this token call Inference Providers at all? Nothing is generated."""
    request = urllib.request.Request(
        PROBE_URL, data=b'{"inputs": "x"}', method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read(200).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(300).decode("utf-8", "replace")
    except Exception as exc:
        return "ERR", str(exc)[:200]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", default=None, help="check this token instead of the stored one")
    args = parser.parse_args(argv)

    source = "--token argument" if args.token else "app settings"
    token = (args.token or stored_token()).strip()
    if not token:
        print("No Hugging Face token found. Add one in Settings > AI Provider.")
        return 2

    print(f"checking token from {source} (prefix {token[:4]}…, {len(token)} chars)")
    status, body = whoami(token)

    if status != 200 or not isinstance(body, dict):
        print(f"REJECTED - HTTP {status}")
        detail = body.get("error") if isinstance(body, dict) else body
        if detail:
            print(f"  Hugging Face says: {detail}")
        if status == 401:
            print("  The token is revoked, expired or mistyped.")
            print("  Create a new one at huggingface.co/settings/tokens, paste it into")
            print("  Settings > AI Provider, then restart FrogPaper.")
        elif status == "ERR":
            print("  Could not reach huggingface.co - check your connection.")
        return 1

    name = body.get("name") or "?"
    kind = body.get("type") or "?"
    role = ((body.get("auth") or {}).get("accessToken") or {}).get("role") or "?"
    print(f"signs in as {name!r} ({kind}), token role {role}")

    probe_status, probe_body = probe_inference(token)
    lowered = (probe_body or "").lower()
    if probe_status == 403 or "sufficient permissions" in lowered:
        print("CANNOT GENERATE - the token may not call Inference Providers")
        print("  huggingface.co/settings/tokens -> edit this token -> enable")
        print("  'Make calls to Inference Providers' (or use a classic Read token),")
        print("  then paste it into Settings > AI Provider and restart FrogPaper.")
        return 1
    if probe_status == "ERR":
        print(f"could not probe inference: {probe_body[:120]}")
        return 1

    print(f"OK - inference allowed (HTTP {probe_status} on a dummy model, as expected)")
    print("Pick a model in Settings > AI Provider: FLUX needs credits, SD3 Medium is free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
