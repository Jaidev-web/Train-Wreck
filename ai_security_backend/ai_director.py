import difflib
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
# 2. LOCAL DETECTION (line by line)
# --------------------------------

# keyword  [quote] (: or =)  [quote] value
SECRET_RE = re.compile(
    r"""(?i)(?<![A-Za-z0-9])(api[_-]?key|password|passwd|secret|access[_-]?token|auth[_-]?token|private[_-]?key)["']?\s*[:=]\s*(['"]?)([^\s'",#]+)"""
)
SK_KEY_RE = re.compile(r"(?i)\bsk-[a-z0-9]{10,}\b")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Indian mobile numbers, optionally with +91
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")

PLACEHOLDER_RE = re.compile(r"(?i)^(your|paste|change|example|xxx|<|\{|\$|%|none$|null$|true$|false$)")

SECRET_FIX = (
    "Remove the hardcoded value. Load it from an environment variable or a "
    ".env file, and add .env to .gitignore."
)


def _secret_type(keyword):
    k = keyword.lower()
    if "pass" in k:
        return "password"
    if "private" in k:
        return "private_key"
    if "token" in k:
        return "token"
    if "api" in k:
        return "api_key"
    return "secret"


def _is_real_secret_value(value, quoted):
    """False for code references like os.environ.get(...) and for placeholders."""
    if not value or PLACEHOLDER_RE.match(value):
        return False
    if quoted:
        return len(value) >= 4
    # Unquoted: skip function calls, attribute access to env, plain variable names
    if "(" in value or ")" in value:
        return False
    if re.match(r"^(os|env|settings|config|getenv)\b", value, re.I):
        return False
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value) and not re.search(r"\d", value):
        return False
    return len(value) >= 6


def mask_line(line, limit=120):
    """Hide secret values so the report itself never leaks them."""
    def _mask(m):
        return m.group(0).replace(m.group(3), "****")

    masked = SECRET_RE.sub(_mask, line)
    masked = SK_KEY_RE.sub("sk-****", masked)
    masked = masked.strip()
    return masked if len(masked) <= limit else masked[: limit - 3] + "..."


def make_finding(line_no, kind, severity, message, line_text, fix):
    return {
        "line": line_no,
        "type": kind,
        "severity": severity,
        "message": message,
        "snippet": mask_line(line_text) if line_text is not None else "",
        "fix": fix,
    }


def find_local_issues(text):
    """Deterministic, line-numbered findings (no AI needed)."""
    findings = []

    for n, line in enumerate(text.splitlines(), start=1):

        if PRIVATE_KEY_RE.search(line):
            findings.append(make_finding(
                n, "private_key", "high",
                "Private key found in file.", line, SECRET_FIX))

        found_secret = False
        for m in SECRET_RE.finditer(line):
            if _is_real_secret_value(m.group(3), bool(m.group(2))):
                kind = _secret_type(m.group(1))
                findings.append(make_finding(
                    n, kind, "high",
                    f"Hardcoded {kind.replace('_', ' ')} found.", line, SECRET_FIX))
                found_secret = True
                break

        if not found_secret and SK_KEY_RE.search(line):
            findings.append(make_finding(
                n, "api_key", "high", "API key found.", line, SECRET_FIX))

        if EMAIL_RE.search(line):
            findings.append(make_finding(
                n, "email", "medium", "Email address found.", line,
                "Remove it or replace it with a placeholder like [REDACTED]."))

        if PHONE_RE.search(line):
            findings.append(make_finding(
                n, "phone", "medium", "Phone number found.", line,
                "Remove it or replace it with a placeholder like [REDACTED]."))

    return findings


def check_secrets(text):
    return any(f["severity"] == "high" for f in find_local_issues(text))


def redact_emails(text):
    """Redacts emails and phone numbers locally (no AI needed)."""
    sanitized = EMAIL_RE.sub("[REDACTED]", text)
    sanitized = PHONE_RE.sub("[REDACTED]", sanitized)
    return sanitized


# --------------------------------
# 3. MAPPING AI RESULTS TO LINES
# --------------------------------

def diff_findings(original, sanitized):
    """Lines the AI changed = personal data the AI found (with real line numbers)."""
    a = original.splitlines()
    b = sanitized.splitlines()
    out = []

    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            for i in range(i1, i2):
                out.append(make_finding(
                    i + 1, "personal_info", "medium",
                    "Personal or sensitive information found by AI.", a[i],
                    "Remove it or replace it with a placeholder like [REDACTED]."))
    return out


def flagged_lines_to_findings(flagged, reason, text):
    """Map the exact lines the AI quoted back to line numbers."""
    lines = text.splitlines()
    out = []

    for quoted in flagged:
        q = quoted.strip()
        if not q:
            continue
        for n, line in enumerate(lines, start=1):
            if line.strip() == q or q in line:
                out.append(make_finding(
                    n, "secret", "high", reason or "Sensitive credential found by AI.",
                    line, SECRET_FIX))
                break

    if not out:
        out.append(make_finding(
            None, "secret", "high", reason or "Sensitive credential found by AI.",
            None, SECRET_FIX))
    return out


def _sorted(findings):
    return sorted(findings, key=lambda f: (f["line"] is None, f["line"] or 0, f["type"]))


def _result(action, reason, sanitized, findings):
    return {
        "action": action,
        "reason": reason,
        "sanitized_text": sanitized,
        "findings": _sorted(findings),
    }


def _block_reason(findings):
    lines = sorted({f["line"] for f in findings if f["severity"] == "high" and f["line"]})
    if lines:
        return "Hardcoded secret(s) found on line(s): " + ", ".join(str(n) for n in lines)
    return "Possible hardcoded secret or credential detected."


# --------------------------------
# 4. AI ANALYSIS
# --------------------------------

def analyze_text(text):

    if not isinstance(text, str):
        raise TypeError("Input must be a string")

    local_findings = find_local_issues(text)

    # Secrets are found locally first: no AI call needed.

    if any(f["severity"] == "high" for f in local_findings):
        return _result("block", _block_reason(local_findings), "", local_findings)

    # Redact emails and phone numbers locally.

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
- Preserve all unrelated code and keep the same number of lines.
- Never invent code.
- For BLOCK, put a short explanation in "reason" and put an exact copy of
  each offending line in "flagged_lines". For SAFE and REDACT, use [].

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
                    },
                    "flagged_lines": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
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
    flagged = result.get("flagged_lines", [])

    if action not in ["safe", "block", "redact"]:
        raise ValueError("Invalid AI action")

    if not isinstance(reason, str):
        raise ValueError("Invalid reason")

    if not isinstance(sanitized, str):
        raise ValueError("Invalid sanitized text")

    if not isinstance(flagged, list):
        flagged = []
    flagged = [x for x in flagged if isinstance(x, str)]

    # --------------------------------
    # 8. STANDARDIZED OUTPUT
    # --------------------------------

    if action == "safe":

        # The AI found nothing more, but local regexes may have redacted
        # emails/phones, so the file still needs to be rewritten.
        if locally_redacted:
            return _result("redact", "", sanitized_text, local_findings)

        return _result("safe", "", "", local_findings)

    elif action == "block":

        if not reason:
            raise ValueError("Missing block reason")

        findings = local_findings + flagged_lines_to_findings(flagged, reason, text)
        return _result("block", reason, "", findings)

    elif action == "redact":

        if not sanitized:
            raise ValueError("Missing sanitized content")

        findings = local_findings + diff_findings(text, sanitized)
        return _result("redact", "", sanitized, findings)


# --------------------------------
# 9. TESTING USING dummy_code.py
# --------------------------------

if __name__ == "__main__":

    file_path = Path(__file__).parent / "dummy_code.py"

    try:

        with open(file_path, "r", encoding="utf-8") as file:
            test_text = file.read()

        result = analyze_text(test_text)

        print("\nGEMMA DECISION:")
        print(result["action"].upper())

        print("\nFINDINGS:")
        for f in result["findings"]:
            print(f"  line {f['line']}: [{f['type']}] {f['snippet']}")

        print("\nRESULT:")
        print(json.dumps(result, indent=4))

    except FileNotFoundError:
        print("ERROR: dummy_code.py was not found.")

    except Exception as error:
        print("SCAN FAILED:", error)