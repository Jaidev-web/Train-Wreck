from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import subprocess
from ai_model import ask_gemma

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
        # This is the exact same as typing `git diff --name-only` in the terminal
        git_command = subprocess.run(
            ["git", "diff", "--name-only"], 
            cwd=repo_path, 
            capture_output=True, 
            text=True
        )
        # Split the text output into a list of file names
        changed_files = git_command.stdout.strip().split("\n")
    except Exception as e:
        return {"status": "error", "message": "Git is not initialized in this folder."}
        
    # 3. If no files were changed, stop here
    if changed_files == [""]:
        return {"status": "safe", "message": "No uncommitted files to scan."}

    results = []
    
    # 4. Loop through every changed file, read it, and send to AI
    for file_name in changed_files:
        full_file_path = os.path.join(repo_path, file_name)
        
        # Only read it if it's an actual file (not deleted)
        if os.path.exists(full_file_path):
            with open(full_file_path, "r", encoding="utf-8") as file:
                code_text = file.read()
                
            ai_response = ask_gemma(code_text)
            
            # Save the AI's report for this specific file
            results.append({
                "file": file_name,
                "ai_analysis": ai_response
            })
            
    # 5. Send the final report back to Flutter
    return {
        "status": "scan_complete", 
        "total_files_scanned": len(results),
        "report": results
    }