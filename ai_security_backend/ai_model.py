def ask_gemma(code_text):
    # Person 2 will replace this with the real Gemini API code later.
    # For now, it just checks for the word "password".
    if "password" in code_text:
        return "VULNERABILITY FOUND: Hardcoded password detected. Fix: Use environment variables."
    else:
        return "SAFE: No issues found."