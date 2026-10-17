#!/usr/bin/env python3
# starter: verbatim
"""Generate the learner starter repo from this reference repo.

Solution blocks are replaced by TODO stubs:

    Python (inside a function body only):
        # >>> SOLUTION: week-13 hybrid retrieval
        ...reference code...
        # <<< SOLUTION
      becomes
        raise NotImplementedError("TODO week-13 hybrid retrieval: see labs/")

    Markdown (results tables, worked answers):
        <!-- >>> SOLUTION: week-02 results -->  ...  <!-- <<< SOLUTION -->
      becomes
        > TODO week-02 results: complete this section (see labs/).

    Other '#'-comment files (YAML, Terraform, Makefile, Dockerfile, shell):
        # >>> SOLUTION: label  ...  # <<< SOLUTION
      becomes
        # TODO label: complete this block (see labs/).

Paths listed in .starterignore (glob patterns) are left out of the starter.
Files with `starter: verbatim` in their first five lines are copied unchanged
(used by this script and its tests, which contain example markers).
A `.starter` marker file is written so CI runs learner-friendly checks.

Usage:
    python scripts/make_starter.py --out ../fde-00-programming-starter
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALWAYS_SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
               "node_modules", "artifacts", "data", ".coverage", "htmlcov", "dist", "build"}
# Run artefacts at the repo root (git-ignored); package folders with these names are kept.
TOP_LEVEL_SKIP = {"index", "models", "checkpoints", "outputs"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".tf", ".sh", ".txt", ".json",
                 ".cfg", ".ini", ".mmd", ".env", ".example", ".tpl", ".sql"}
TEXT_NAMES = {"Makefile", "Dockerfile", "Containerfile", ".gitignore", ".dockerignore"}

PY_START = re.compile(r"^(?P<indent>[ \t]*)# >>> SOLUTION(?::\s*(?P<label>.*?))?\s*$")
PY_END = re.compile(r"^[ \t]*# <<< SOLUTION\s*$")
MD_START = re.compile(r"^(?P<indent>\s*)<!-- >>> SOLUTION(?::\s*(?P<label>.*?))?\s*-->\s*$")
MD_END = re.compile(r"^\s*<!-- <<< SOLUTION\s*-->\s*$")


class MarkerError(ValueError):
    pass


def load_ignore(root: Path) -> list[str]:
    path = root / ".starterignore"
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def is_ignored(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.rstrip("/") + "/*")
               for p in patterns)


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES


def strip_solutions(text: str, kind: str, where: str = "<text>") -> tuple[str, int]:
    """Replace solution blocks. kind is 'py', 'md' or 'hash'. Returns (text, blocks_replaced)."""
    start_re, end_re = (MD_START, MD_END) if kind == "md" else (PY_START, PY_END)
    out: list[str] = []
    inside = False
    count = 0
    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        if not inside:
            m = start_re.match(line.rstrip("\n"))
            if m:
                inside = True
                count += 1
                indent = m.group("indent") or ""
                label = (m.group("label") or "exercise").strip()
                if kind == "py":
                    if not indent:
                        raise MarkerError(
                            f"{where}:{lineno}: Python solution markers must sit inside a "
                            "function body (indented), so the starter still imports."
                        )
                    out.append(f'{indent}raise NotImplementedError("TODO {label}: see labs/")\n')
                elif kind == "md":
                    out.append(f"{indent}> TODO {label}: complete this section (see labs/).\n")
                else:
                    out.append(f"{indent}# TODO {label}: complete this block (see labs/).\n")
                continue
            if end_re.match(line.rstrip("\n")):
                raise MarkerError(f"{where}:{lineno}: end marker without a start marker")
            out.append(line)
        else:
            if start_re.match(line.rstrip("\n")):
                raise MarkerError(f"{where}:{lineno}: nested solution markers are not allowed")
            if end_re.match(line.rstrip("\n")):
                inside = False
    if inside:
        raise MarkerError(f"{where}: solution block is not closed")
    return "".join(out), count


def kind_for(path: Path) -> str:
    if path.suffix == ".py":
        return "py"
    if path.suffix == ".md":
        return "md"
    return "hash"


STARTER_BANNER = """> **Learner starter.** This repo is generated from the reference solution.
> Work through `labs/` week by week and replace each `TODO` until `make exercises` is green
> (`make test` stays green throughout).
> Do not open the reference repo until you have tried each exercise yourself.

"""


def build(src: Path, out: Path, force: bool = False) -> dict[str, int]:
    if out.exists():
        if not force:
            raise SystemExit(f"{out} exists; pass --force to overwrite")
        # Keep the starter repo's .git so the publish workflow can commit on top of it.
        for child in out.iterdir():
            if child.name == ".git":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)

    patterns = load_ignore(src)
    stats = {"files": 0, "blocks": 0, "skipped": 0}
    for path in sorted(src.rglob("*")):
        rel_parts = path.relative_to(src).parts
        if set(rel_parts) & ALWAYS_SKIP or rel_parts[0] in TOP_LEVEL_SKIP:
            continue
        rel = path.relative_to(src).as_posix()
        if is_ignored(rel, patterns):
            stats["skipped"] += 1
            continue
        target = out / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if is_text(path):
            text = path.read_text(encoding="utf-8")
            if "starter: verbatim" in "".join(text.splitlines(keepends=True)[:5]):
                new, n = text, 0
            else:
                new, n = strip_solutions(text, kind_for(path), where=rel)
            if rel == "README.md":
                new = STARTER_BANNER + new
            target.write_text(new, encoding="utf-8")
            stats["blocks"] += n
        else:
            shutil.copy2(path, target)
        stats["files"] += 1

    (out / ".starter").write_text("Generated by scripts/make_starter.py; do not edit by hand.\n",
                                  encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        stats = build(args.src.resolve(), args.out.resolve(), force=args.force)
    except MarkerError as e:
        print(f"make_starter: {e}", file=sys.stderr)
        return 1
    print(f"make_starter: {stats['files']} files, {stats['blocks']} solution blocks replaced, "
          f"{stats['skipped']} paths skipped -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
