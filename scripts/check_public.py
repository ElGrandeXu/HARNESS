#!/usr/bin/env python3
"""Audit selected public files; pattern checks are not a secret-detection guarantee."""
from pathlib import Path
import argparse
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".agent-state", ".delivery", "__pycache__"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "API key": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "personal Linux path": re.compile(r"/(?:home)/[^/\s\"'<>]+/"),
    "personal macOS path": re.compile(r"/(?:Users)/[^/\s\"'<>]+/"),
    "personal Windows path": re.compile(r"[A-Z]:\\Users\\[^\\\s]+\\", re.I),
}


def files():
    if (ROOT / ".git").exists():
        proc = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
        return [ROOT / p.decode("utf-8") for p in proc.stdout.split(b"\0") if p]
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(x in SKIP for x in p.relative_to(ROOT).parts)
            and not (p.relative_to(ROOT).parts[0] in ("inbox", "memory", "tasks", "handoffs") and p.name != "README.md")
            and p.name not in ("project.local.json", "AGENTS.local.md", "CLAUDE.local.md")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", action="store_true", help="Exiger en plus un dépôt vierge de données projet")
    args = parser.parse_args()
    failures = []
    selected = files()
    for p in selected:
        relative = p.relative_to(ROOT).as_posix()
        if p.is_symlink():
            failures.append(f"{relative}: symlink not allowed in template")
            continue
        if any(x in SKIP for x in p.relative_to(ROOT).parts):
            failures.append(f"{relative}: private runtime/build directory selected")
        if (args.template and relative.startswith(("inbox/", "memory/", "tasks/", "handoffs/")) and p.name != "README.md") or p.name in (
                "project.local.json", "AGENTS.local.md", "CLAUDE.local.md", ".env"):
            failures.append(f"{relative}: project/private data selected in template")
        if p.stat().st_size > 262144:
            failures.append(f"{relative}: unexpected large file")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeError:
            failures.append(f"{relative}: binary file requires manual review")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{relative}: {label}")
    for message in failures:
        print(message, file=sys.stderr)
    if failures:
        return 1
    print(f"Public audit OK: {len(selected)} files; no detected secret/private path or forbidden local data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
