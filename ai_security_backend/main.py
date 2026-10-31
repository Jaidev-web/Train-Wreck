from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import subprocess
from ai_director import analyze_text

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    # Development only: replace with your Flutter app's real origin(s) before deploying
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This tells the server to expect a Git folder path from Flutter
class RepoRequest(BaseModel):
    repo_folder_path: str

@app.post("/scan-repo")
def scan_git_repo(request: RepoRequest):
    repo_path = request.repo_folder_path
    
    # 1. Check if the folder actually exists
    if not os.path.exists(repo_path):
        return {"status": "error", "message": "Folder not found!"}
        
    # 2. Ask Git for a list of modified files using subprocess
    try:
        # Same as `git diff --cached --name-only` in the terminal: files staged
        # for the next commit (the same files the pre-commit hook scans).
        git_command = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if git_command.returncode != 0:
            return {"status": "error", "message": "Git is not initialized in this folder."}
        # Split the text output into a list of file names
        changed_files = [f for f in git_command.stdout.splitlines() if f.strip()]
    except Exception as e:
        return {"status": "error", "message": "Git is not initialized in this folder."}

    # 3. If no files were staged, stop here
    if not changed_files:
        return {"status": "safe", "message": "No staged files to scan. Run `git add` first."}

    results = []
    
    # 4. Loop through every changed file, read it, and send to AI
    for file_name in changed_files:
        full_file_path = os.path.join(repo_path, file_name)
        
        # Only read it if it's an actual file (not deleted)
        if os.path.isfile(full_file_path):
            try:
                with open(full_file_path, "r", encoding="utf-8") as file:
                    code_text = file.read()
            except UnicodeDecodeError:
                continue  # binary file (image, pdf, ...), skip it

            try:
                result = analyze_text(code_text)
                action = result["action"]
                findings = result["findings"]
                reason = result["reason"]
            except Exception as e:
                action, findings, reason = "error", [], f"SCAN FAILED: {e}"

            # Save the report for this specific file
            results.append({
                "file": file_name,
                "action": action,          # safe | redact | block | error
                "reason": reason,
                "findings": findings,      # [{line, type, severity, message, snippet, fix}]
                "ai_analysis": _summary(action, reason, findings),
            })

    # 5. Send the final report back to Flutter
    actions = {r["action"] for r in results}
    if "block" in actions:
        overall = "block"
    elif "error" in actions:
        overall = "error"
    elif "redact" in actions:
        overall = "redact"
    else:
        overall = "safe"

    return {
        "status": "scan_complete",
        "overall_action": overall,
        "total_files_scanned": len(results),
        "total_findings": sum(len(r["findings"]) for r in results),
        "report": results
    }


def _summary(action, reason, findings):
    """One readable sentence per file (kept for simple displays)."""
    if action == "safe":
        return "SAFE: No sensitive information found."
    if action == "error":
        return reason
    lines = sorted({f["line"] for f in findings if f["line"]})
    where = " on line(s) " + ", ".join(str(n) for n in lines) if lines else ""
    if action == "block":
        return "VULNERABILITY FOUND" + where + ". " + reason
    return "SENSITIVE INFORMATION FOUND" + where + "."