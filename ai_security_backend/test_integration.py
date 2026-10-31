"""End-to-end integration test for the Git Plumber + AI Director project.

Usage (from the folder containing the project files):
    python test_integration.py          # offline: uses a stand-in for the Gemini API
    python test_integration.py --live   # uses your real GEMINI_API_KEY from .env
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LIVE = "--live" in sys.argv
PROJECT = Path(__file__).resolve().parent
PY = sys.executable
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"   -> {detail}" if detail and not ok else ""))


# ---------- offline stand-in for google.genai ----------
fake_dir = None
env = os.environ.copy()
if not LIVE:
    fake_dir = Path(tempfile.mkdtemp())
    pkg = fake_dir / "google" / "genai"
    pkg.mkdir(parents=True)
    (fake_dir / "google" / "__init__.py").write_text("")
    (pkg / "types.py").write_text(
        "class GenerateContentConfig:\n"
        "    def __init__(self, **kw): pass\n"
    )
    (pkg / "__init__.py").write_text(
        "import json\n"
        "from . import types\n"
        "class _R:\n"
        "    def __init__(self, t): self.text = t\n"
        "class _M:\n"
        "    def generate_content(self, model, contents, config=None):\n"
        "        body = contents.split('FILE CONTENT:')[-1]\n"
        "        if 'MG Road' in body:\n"
        "            return _R(json.dumps({'action': 'redact', 'reason': '',\n"
        "                'sanitized_text': body.replace('12 MG Road, Pune', '[REDACTED]').strip()}))\n"
        "        return _R(json.dumps({'action': 'safe', 'reason': '', 'sanitized_text': ''}))\n"
        "class Client:\n"
        "    def __init__(self, api_key=None): self.models = _M()\n"
    )
    env["PYTHONPATH"] = str(fake_dir) + os.pathsep + env.get("PYTHONPATH", "")
    env["GEMINI_API_KEY"] = "offline-test-key"
    os.environ.update({"PYTHONPATH": env["PYTHONPATH"], "GEMINI_API_KEY": "offline-test-key"})
    sys.path.insert(0, str(fake_dir))

sys.path.insert(0, str(PROJECT))

# ---------- 1. AI Director ----------
import ai_director  # noqa: E402

dummy = (PROJECT / "dummy_code.py").read_text(encoding="utf-8")
check("Director blocks dummy_code.py (secrets)", ai_director.analyze_text(dummy)["action"] == "block")

r = ai_director.analyze_text("Contact 9876543210 or a@b.com\nprint('hi')\n")
check("Director redacts phone + email locally",
      r["action"] == "redact" and "9876543210" not in r["sanitized_text"]
      and "a@b.com" not in r["sanitized_text"] and "print('hi')" in r["sanitized_text"])

check("Director returns safe for clean code",
      ai_director.analyze_text("print('hello')\n")["action"] == "safe")

if not LIVE:
    r = ai_director.analyze_text("addr = '12 MG Road, Pune'\n")
    check("Director passes AI redaction through", r["action"] == "redact" and "MG Road" not in r["sanitized_text"])

# ---------- 2. Git hook ----------
repo = Path(tempfile.mkdtemp())


def git(*a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, env=env)


git("init")
git("config", "user.email", "t@t.t")
git("config", "user.name", "tester")
inst = subprocess.run([PY, str(PROJECT / "install_hook.py"), str(repo)], capture_output=True, text=True)
check("install_hook.py installs hook", inst.returncode == 0 and (repo / ".git/hooks/pre-commit").exists(), inst.stderr)

shutil.copy(PROJECT / "dummy_code.py", repo / "dummy_code.py")
git("add", ".")
c = git("commit", "-m", "block")
check("Hook blocks commit with secrets", c.returncode != 0 and "COMMIT BLOCKED" in (c.stdout + c.stderr), c.stdout + c.stderr)
git("rm", "-f", "--cached", "dummy_code.py")
(repo / "dummy_code.py").unlink()

(repo / "notes.txt").write_text("Call me on 9876543210\n")
git("add", "notes.txt")
c = git("commit", "-m", "redact")
committed = git("show", "HEAD:notes.txt").stdout
check("Hook redacts and lets commit through",
      c.returncode == 0 and "[REDACTED]" in committed and "9876543210" not in committed, c.stdout + c.stderr)
check("Redacted text also written to working file", "9876543210" not in (repo / "notes.txt").read_text())

(repo / "hello.py").write_text("print('hello')\n")
git("add", "hello.py")
c = git("commit", "-m", "safe")
check("Hook allows clean file", c.returncode == 0 and "Scan passed" in (c.stdout + c.stderr), c.stdout + c.stderr)

# ---------- 3. FastAPI endpoint (what Flutter calls) ----------
try:
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    (repo / "api_test.txt").write_text("Reach me on 9123456780\n")
    git("add", "api_test.txt")

    resp = client.post("/scan-repo", json={"repo_folder_path": str(repo)})
    body = resp.json()
    check("API /scan-repo returns scan_complete",
          resp.status_code == 200 and body.get("status") == "scan_complete" and body["total_files_scanned"] >= 1,
          json.dumps(body))
    check("API report has file + ai_analysis keys",
          all({"file", "ai_analysis"} <= set(x) for x in body.get("report", [])))

    resp = client.post("/scan-repo", json={"repo_folder_path": "/no/such/folder"})
    check("API handles missing folder", resp.json().get("status") == "error")

    resp = client.post("/scan-repo", json={"repo_folder_path": tempfile.mkdtemp()})
    check("API handles non-git folder gracefully", resp.json().get("status") in ("error", "safe"))

    cors = client.options("/scan-repo", headers={
        "Origin": "http://localhost:5000", "Access-Control-Request-Method": "POST"})
    check("API CORS preflight allowed", cors.status_code == 200 and "access-control-allow-origin" in cors.headers)
except ImportError as e:
    check("API tests (install fastapi httpx)", False, str(e))

shutil.rmtree(repo, ignore_errors=True)
if fake_dir:
    shutil.rmtree(fake_dir, ignore_errors=True)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
