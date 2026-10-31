#!/usr/bin/env python
"""Git Plumber: scans staged files before a commit using the AI Director."""

import subprocess
import sys
from pathlib import Path

# Make sure we can import ai_director.py (it lives next to this file)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_director import analyze_text  # noqa: E402

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe",
    ".dll", ".pyc", ".ico", ".woff", ".woff2", ".mp4", ".mp3",
}


def git(*args, text=True):
    return subprocess.run(["git", *args], capture_output=True, text=text)


def main():
    repo_root = Path(git("rev-parse", "--show-toplevel").stdout.strip())

    # Only files that are staged (Added / Copied / Modified)
    staged = git("diff", "--cached", "--name-only", "--diff-filter=ACM").stdout.splitlines()

    blocked = []
    redacted = []

    for rel_path in staged:
        if Path(rel_path).suffix.lower() in SKIP_EXTENSIONS:
            continue

        # Read the STAGED version of the file (what would actually be committed)
        raw = git("show", f":{rel_path}", text=False).stdout
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue  # binary file, skip

        if not content.strip():
            continue

        try:
            result = analyze_text(content)
        except Exception as err:
            # Fail closed: if the scanner breaks, don't let unscanned code through
            print(f"[Git Plumber] Scan failed for {rel_path}: {err}")
            print("Fix the problem, or bypass once with: git commit --no-verify")
            sys.exit(1)

        action = result["action"]

        if action == "block":
            blocked.append((rel_path, result["reason"], result.get("findings", [])))

        elif action == "redact":
            # Overwrite the file with the safe text and re-stage it
            (repo_root / rel_path).write_text(result["sanitized_text"], encoding="utf-8")
            git("add", rel_path)
            redacted.append((rel_path, result.get("findings", [])))

    if redacted:
        print("[Git Plumber] Sensitive data was redacted and re-staged in:")
        for f, findings in redacted:
            print(f"   - {f}")
            for item in findings:
                print(f"       line {item['line']}: {item['message']}")

    if blocked:
        print("\n[Git Plumber] COMMIT BLOCKED. Secrets found:")
        for f, reason, findings in blocked:
            print(f"   - {f}: {reason}")
            for item in findings:
                print(f"       line {item['line']} [{item['type']}]: {item['snippet']}")
        print("\nRemove the secrets (use environment variables) and commit again.")
        sys.exit(1)

    print("[Git Plumber] Scan passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()