#!/usr/bin/env python3
"""End-to-end smoke test against a running service.

Waits for /health/ready, then runs the checks in tests/e2e/smoke.yaml.
Used by `make e2e`, the e2e workflow, and every desktop and cloud lab.

Usage:
    python scripts/smoke_test.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent


def wait_ready(client: httpx.Client, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = "no response"
    while time.monotonic() < deadline:
        try:
            r = client.get("/health/ready")
            if r.status_code == 200:
                return
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            last = type(e).__name__
        time.sleep(1)
    raise SystemExit(f"service not ready after {timeout:.0f}s ({last})")


def run_check(client: httpx.Client, check: dict) -> str | None:
    """Return None on success or an error message."""
    method = check.get("method", "GET").upper()
    r = client.request(method, check["path"], json=check.get("json"),
                       params=check.get("params"))
    if r.status_code != check.get("expect_status", 200):
        expected = check.get("expect_status", 200)
        return f"expected HTTP {expected}, got {r.status_code}: {r.text[:200]}"
    if "expect_keys" in check:
        body = r.json()
        missing = [k for k in check["expect_keys"] if k not in body]
        if missing:
            return f"missing keys {missing} in {body}"
    if "expect_contains" in check and check["expect_contains"] not in r.text:
        return f"response does not contain {check['expect_contains']!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--checks", type=Path, default=ROOT / "tests" / "e2e" / "smoke.yaml")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--include-exercises", action="store_true",
                        help="in a starter repo, also run checks that depend on learner TODOs")
    args = parser.parse_args(argv)

    checks = yaml.safe_load(args.checks.read_text(encoding="utf-8"))["checks"]
    if (ROOT / ".starter").exists() and not args.include_exercises:
        skipped = [c["name"] for c in checks if c.get("exercise")]
        checks = [c for c in checks if not c.get("exercise")]
        if skipped:
            print(f"starter repo: skipping exercise checks {skipped} (use --include-exercises)")
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        wait_ready(client, args.timeout)
        failures = 0
        for check in checks:
            error = run_check(client, check)
            status = "PASS" if error is None else "FAIL"
            print(f"{status}  {check['name']}" + ("" if error is None else f"  -> {error}"))
            failures += error is not None
    print(f"smoke: {len(checks) - failures}/{len(checks)} passed against {args.base_url}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
