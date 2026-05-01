import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))

JUNIOR_MODE_PROMPT = """
You are a patient senior engineer reviewing code written by a junior developer.
For each finding, explain WHY it is a problem, WHAT could go wrong, and HOW to fix it with a concrete example.
Be encouraging but honest. Teach, don't just flag.
"""

SENIOR_MODE_PROMPT = """
You are a senior engineer reviewing code written by another senior engineer.
Be concise and direct. Flag issues with minimal explanation.
Assume the reviewer understands the implications.
"""


def review_pr(diff: str, pr_description: str, context_files: list[dict] = None, mode: str = "junior") -> list[dict]:
    context_section = ""
    if context_files:
        context_section = "## Relevant Codebase Context\n\n"
        for f in context_files:
            context_section += f"### `{f['file_path']}`\n```\n{f['content'][:2000]}\n```\n\n"

    mode_instruction = JUNIOR_MODE_PROMPT if mode == "junior" else SENIOR_MODE_PROMPT

    prompt = f"""{mode_instruction}

PR Description: {pr_description or "No description provided"}

{context_section}

## Diff to Review
{diff}

Return ONLY a JSON array. No markdown, no explanation. Each item must have:
- "file": the filename
- "line": line number in the diff (integer)
- "category": one of "bug", "style", "security", "performance", "missing_test"
- "severity": one of "critical", "major", "minor"
- "comment": your review comment based on the mode instructions above. Keep each comment under 400 characters.
- "confidence": integer 0-100, how confident you are this is a real issue

Only flag real issues. If the diff is clean, return an empty array [].
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        findings = json.loads(text)
        findings = [f for f in findings if f.get("confidence", 0) >= 70]
        return findings
    except json.JSONDecodeError:
        try:
            text = text[:text.rfind("}") + 1] + "]"
            findings = json.loads(text)
            findings = [f for f in findings if f.get("confidence", 0) >= 70]
            return findings
        except Exception:
            print(f"[ERROR] Could not parse Gemini response: {text}")
            return []