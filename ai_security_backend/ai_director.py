import json
import os
import re

from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types


# --------------------------------
# 1. GEMMA API CONFIGURATION
# --------------------------------

# Loads GEMINI_API_KEY from the .env file that sits next to this script
load_dotenv(Path(__file__).resolve().parent / ".env")

# The string below is the NAME of the variable, never the key itself.
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found. Add this line to the .env file next to "
        "ai_director.py:  GEMINI_API_KEY=your_key"
    )

MODEL = "gemma-4-26b-a4b-it"

client = genai.Client(api_key=API_KEY)


# --------------------------------
# 2. LOCAL SECRET DETECTION
# --------------------------------

def check_secrets(text):

    patterns = [
        r"""(?i)\b(api[_-]?key|password|passwd|secret|access[_-]?token|auth[_-]?token|private[_-]?key)\b\s*[:=]\s*(['"]?)([^\s'"#]+)""",
        r"(?i)\bsk-[a-z0-9]{10,}\b",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ]

    for pattern in patterns:
        if re.search(pattern, text):
            return True

    return False


# --------------------------------
# 3. LOCAL EMAIL DETECTION
# --------------------------------

def redact_emails(text):
    """Redacts emails and phone numbers locally (no AI needed)."""

    email_pattern = (
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    )

    # Indian mobile numbers, optionally with +91
    phone_pattern = r'(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)'

    sanitized = re.sub(email_pattern, "[REDACTED]", text)
    sanitized = re.sub(phone_pattern, "[REDACTED]", sanitized)

    return sanitized


# --------------------------------
# 4. AI ANALYSIS
# --------------------------------

def analyze_text(text):

    if not isinstance(text, str):
        raise TypeError("Input must be a string")

    # Check secrets locally first.

    if check_secrets(text):
        return {
            "action": "block",
            "reason": "Possible hardcoded secret or credential detected.",
            "sanitized_text": ""
        }

    # Detect and redact emails locally.

    sanitized_text = redact_emails(text)
    locally_redacted = sanitized_text != text

    # From here on the AI sees the already-redacted text, so it can still
    # catch secrets or other personal data the regexes missed.
    text = sanitized_text

    # --------------------------------
    # 5. GEMMA PROMPT
    # --------------------------------

    prompt = f"""
You are a strict security scanner for Git commits.

Analyze the complete file content.

CLASSIFICATION RULES:

1. BLOCK:
   - Hardcoded passwords
   - API keys
   - Authentication tokens
   - Private keys

2. REDACT:
   - Phone numbers
   - Home addresses
   - Other personally identifiable information

3. SAFE:
   - Only when NO sensitive information is present.

IMPORTANT:
- Never classify personal information as SAFE.
- For REDACT, return the COMPLETE original file.
- Replace only sensitive values with [REDACTED].
- Preserve all unrelated code.
- Never invent code.

FILE CONTENT:
{text}
"""

    # --------------------------------
    # 6. GEMMA RESPONSE
    # --------------------------------

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "enum": ["safe", "block", "redact"]
                    },
                    "reason": {
                        "type": "STRING"
                    },
                    "sanitized_text": {
                        "type": "STRING"
                    }
                },
                "required": [
                    "action",
                    "reason",
                    "sanitized_text"
                ]
            }
        )
    )

    # --------------------------------
    # 7. VALIDATE RESPONSE
    # --------------------------------

    if not response.text:
        raise ValueError("Gemma returned an empty response")

    result = json.loads(response.text)

    if not isinstance(result, dict):
        raise ValueError("Invalid AI response")

    action = result.get("action")
    reason = result.get("reason")
    sanitized = result.get("sanitized_text")

    if action not in ["safe", "block", "redact"]:
        raise ValueError("Invalid AI action")

    if not isinstance(reason, str):
        raise ValueError("Invalid reason")

    if not isinstance(sanitized, str):
        raise ValueError("Invalid sanitized text")

    # --------------------------------
    # 8. STANDARDIZED OUTPUT
    # --------------------------------

    if action == "safe":

        # The AI found nothing more, but local regexes may have redacted
        # emails/phones, so the file still needs to be rewritten.
        if locally_redacted:
            return {
                "action": "redact",
                "reason": "",
                "sanitized_text": sanitized_text
            }

        return {
            "action": "safe",
            "reason": "",
            "sanitized_text": ""
        }

    elif action == "block":

        if not reason:
            raise ValueError("Missing block reason")

        return {
            "action": "block",
            "reason": reason,
            "sanitized_text": ""
        }

    elif action == "redact":

        if not sanitized:
            raise ValueError("Missing sanitized content")

        return {
            "action": "redact",
            "reason": "",
            "sanitized_text": sanitized
        }


# --------------------------------
# 9. TESTING USING dummy.txt
# --------------------------------

# --------------------------------
# 9. TESTING USING dummy_code.py
# --------------------------------

if __name__ == "__main__":

    file_path = Path(__file__).parent / "dummy_code.py"

    try:

        with open(file_path, "r", encoding="utf-8") as file:
            test_text = file.read()

        print("\nFILE CONTENT:")
        print(test_text)

        result = analyze_text(test_text)

        print("\nGEMMA DECISION:")
        print(result["action"].upper())

        print("\nRESULT:")
        print(json.dumps(result, indent=4))

    except FileNotFoundError:
        print("ERROR: dummy_code.py was not found.")

    except Exception as error:
        print("SCAN FAILED:", error)