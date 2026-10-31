"""Installs the pre-commit hook into a target git repo.

Usage:  python install_hook.py /path/to/target/repo
"""

import os
import stat
import sys
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit("Usage: python install_hook.py /path/to/target/repo")

repo = Path(sys.argv[1]).resolve()
hooks_dir = repo / ".git" / "hooks"

if not hooks_dir.is_dir():
    sys.exit(f"{repo} is not a git repository (no .git/hooks).")

scanner = Path(__file__).resolve().parent / "pre_commit_scan.py"

# Git runs this tiny file; it simply calls our Python scanner.
hook = hooks_dir / "pre-commit"
hook.write_text(
    "#!/bin/sh\n"
    f'exec "{sys.executable}" "{scanner.as_posix()}"\n',
    encoding="utf-8",
)
hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

print(f"Installed pre-commit hook at {hook}")
