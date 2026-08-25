#!/usr/bin/env python3
"""
Counts the number of writeup subfolders in each category directory and
updates the Count column in README.md's Categories table.

A "writeup" is any immediate subdirectory of a category folder
(matches the repo convention: category/event-name_challenge-name/).
A category folder containing only a placeholder README.md (no
subdirectories yet) counts as 0.

Run from the repo root:
    python3 scripts/update_counts.py
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

# Maps the folder slug (used in the README's markdown links, e.g. "./web")
# to the category's display name as it must appear in the table row.
CATEGORY_SLUGS = [
    "web",
    "crypto",
    "reverse-engineering",
    "pwn",
    "network",
    "osint",
    "forensics-dfir",
    "steganography",
    "misc",
    "ai",
    "hardware",
]


def count_writeups(slug: str) -> int:
    folder = REPO_ROOT / slug
    if not folder.is_dir():
        return 0
    return sum(1 for child in folder.iterdir() if child.is_dir())


def update_readme_counts(counts: dict[str, int]) -> bool:
    """Rewrites the Count cell on each category's table row.
    Returns True if the file content changed."""
    text = README_PATH.read_text(encoding="utf-8")
    original = text

    for slug, count in counts.items():
        # Matches a table row like:
        # | [Web](./web) | SQLi, XSS, ... | - |
        # and replaces only the final cell's value.
        pattern = re.compile(
            r"(\|\s*\[[^\]]*\]\(\./" + re.escape(slug) + r"\)\s*\|[^\n|]*\|)"
            r"[^\n|]*"
            r"(\|)"
        )
        text = pattern.sub(lambda m, c=count: f"{m.group(1)} {c} {m.group(2)}", text, count=1)

    if text != original:
        README_PATH.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    counts = {slug: count_writeups(slug) for slug in CATEGORY_SLUGS}

    total = sum(counts.values())
    print("Writeup counts per category:")
    for slug, count in counts.items():
        print(f"  {slug:22s} {count}")
    print(f"  {'TOTAL':22s} {total}")

    changed = update_readme_counts(counts)
    if changed:
        print("\nREADME.md updated.")
    else:
        print("\nREADME.md already up to date.")


if __name__ == "__main__":
    main()
