
from ai_director import analyze_text

def ask_gemma(code_text):

    result = analyze_text(code_text)

    if result["action"] == "safe":
        return "SAFE: No sensitive information found."

    elif result["action"] == "block":
        return "VULNERABILITY FOUND: " + result["reason"]

    elif result["action"] == "redact":
        return (
            "SENSITIVE INFORMATION FOUND.\n"
            "Fix: Replace sensitive information with the sanitized content.\n"
            + result["sanitized_text"]
        )
