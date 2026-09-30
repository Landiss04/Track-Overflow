#!/usr/bin/env python3
"""Move promoted proposals from truth/incoming/ to their canonical paths.

Each incoming file is a proposal in the _templates/fragment.md format: bold-label
header lines (**Target:**, **Action:**, ...), a line containing only ---, then the
complete entry. The entry is written to Target and the incoming file is removed with
git rm.

Every file is validated before anything is written. Any error fails the run and
leaves the tree untouched, so a bad file stays in incoming/ for a human to fix.

Run from the repository root.
"""

import re
import subprocess
import sys
from pathlib import Path

INCOMING = Path("truth/incoming")
TARGET_RE = re.compile(
    r"^truth/(conventions|decisions|modules|signals|arbitration|ui)/[A-Za-z0-9._/-]+\.md$"
)
HEADER_RE = re.compile(r"^\*\*(?P<key>[A-Za-z ]+):\*\*\s*(?P<value>.*?)\s*$")
PROVENANCE_RE = re.compile(r"^\*\*Provenance:\*\*\s*\S", re.MULTILINE)


def parse(path):
    """Return (headers, body) for a fragment file, or raise ValueError."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "---":
            break
    else:
        raise ValueError("no --- line separating the header from the entry")

    headers = {}
    for line in lines[:i]:
        match = HEADER_RE.match(line)
        if match:
            headers[match["key"].strip().lower()] = match["value"]

    body = "".join(lines[i + 1 :]).lstrip("\n")
    if body and not body.endswith("\n"):
        body += "\n"
    return headers, body


def validate(path, seen):
    """Return (target, body) for a valid fragment, or raise ValueError."""
    headers, body = parse(path)

    action = headers.get("action", "")
    if action not in ("create", "replace"):
        raise ValueError(f"**Action:** must be create or replace, got {action!r}")

    target = headers.get("target", "").strip("`")
    if not TARGET_RE.match(target) or ".." in target.split("/"):
        raise ValueError(f"**Target:** is not a valid entry path: {target!r}")
    if target in seen:
        raise ValueError(f"**Target:** {target} is also targeted by {seen[target]}")

    exists = Path(target).exists()
    if action == "create" and exists:
        raise ValueError(f"create onto {target}, which already exists; use replace")
    if action == "replace" and not exists:
        raise ValueError(f"replace of {target}, which does not exist; use create")

    if not body.startswith("# "):
        raise ValueError("entry below --- must start with a '# <entry-key>' heading")
    if not PROVENANCE_RE.search(body):
        raise ValueError("entry has no **Provenance:** line; it cannot go in")

    return target, body


def main():
    files = sorted(p for p in INCOMING.rglob("*.md") if p.is_file())
    if not files:
        print("truth/incoming/ holds no proposals; nothing to move.")
        return 0

    moves, errors, seen = [], [], {}
    for path in files:
        try:
            target, body = validate(path, seen)
        except ValueError as err:
            errors.append(f"{path}: {err}")
            continue
        seen[target] = path
        moves.append((path, target, body))

    if errors:
        print("Nothing moved. Fix these files in truth/incoming/:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    for path, target, body in moves:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "--", target], check=True)
        subprocess.run(["git", "rm", "--quiet", "--", str(path)], check=True)
        print(f"{path} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
