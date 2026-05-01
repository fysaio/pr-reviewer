import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))


def review_pr(diff: str, pr_description: str, context_files: list[dict] = None) -> list[dict]:
    context_section = ""
    if context_files:
        context_section = "## Relevant Codebase Context\n\n"
        for f in context_files:
            context_section += f"### `{f['file_path']}`\n```\n{f['content'][:2000]}\n```\n\n"

    prompt = f"""You are an expert code reviewer with full context of the codebase. Analyze this pull request diff and return a JSON array of findings.

PR Description: {pr_description or "No description provided"}

{context_section}

## Diff to Review
{diff}

Return ONLY a JSON array. No markdown, no explanation. Each item must have:
- "file": the filename
- "line": line number in the diff (integer)
- "category": one of "bug", "style", "security", "performance", "missing_test"
- "severity": one of "critical", "major", "minor"
- "comment": your review comment, explain clearly for a junior developer. If you spotted something using the codebase context, mention it specifically.
- "confidence": integer 0-100, how confident you are this is a real issue

Example:
[
  {{
    "file": "app/main.py",
    "line": 12,
    "category": "bug",
    "severity": "critical",
    "comment": "This will throw a KeyError if 'user' is not in the dict. Use .get('user') instead.",
    "confidence": 92
  }}
]

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
        return findings
    except json.JSONDecodeError:
        print(f"[ERROR] Could not parse Gemini response: {text}")
        return []