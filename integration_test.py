
from ai_director import analyze_text

file_content = """
email = "john@gmail.com"
print("Hello World")
"""

result = analyze_text(file_content)

print("AI DECISION:", result["action"])

if result["action"] == "safe":
    print("File is safe.")

elif result["action"] == "block":
    print("Commit blocked:", result["reason"])

elif result["action"] == "redact":
    print("Sanitized file:")
    print(result["sanitized_text"])
