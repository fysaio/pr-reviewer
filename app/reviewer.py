import os
import json
import re
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


def review_pr(diff: str, pr_description: str, context_files: list[dict] = None, mode: str = "junior", confidence_threshold: int = 70) -> dict:
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

Analyze the diff and the context files separately.

Return ONLY a JSON object with two arrays. No markdown, no explanation.

{{
  "diff_findings": [...],
  "context_findings": [...]
}}

**diff_findings**: Issues found directly in the diff above. These are problems introduced or visible in this PR.

**context_findings**: Issues found in the context files that are relevant to this PR. These are pre-existing problems in code this PR touches or depends on. Only include these if they are genuinely relevant to understanding or safely merging this PR.

Each finding in both arrays must have:
- "file": the filename
- "line": line number (integer)
- "category": one of "bug", "style", "security", "performance", "missing_test"
- "severity": one of "critical", "major", "minor"
- "comment": your review comment based on the mode instructions. Keep under 400 characters.
- "confidence": integer 0-100

Only flag real issues. Return empty arrays if nothing found.
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

    def extract_findings(raw: dict) -> dict:
        diff_findings = [f for f in raw.get("diff_findings", []) if f.get("confidence", 0) >= confidence_threshold]
        context_findings = [f for f in raw.get("context_findings", []) if f.get("confidence", 0) >= confidence_threshold]
        return {"diff_findings": diff_findings, "context_findings": context_findings}

    # Attempt 1: direct parse
    try:
        result = json.loads(text)
        return extract_findings(result)
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip extra trailing braces
    try:
        cleaned = text.rstrip("} \n") + "}"
        result = json.loads(cleaned)
        return extract_findings(result)
    except json.JSONDecodeError:
        pass

    # Attempt 3: regex extract each array independently
    try:
        diff_match = re.search(r'"diff_findings"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
        context_match = re.search(r'"context_findings"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
        diff_findings = json.loads(diff_match.group(1)) if diff_match else []
        context_findings = json.loads(context_match.group(1)) if context_match else []
        return extract_findings({"diff_findings": diff_findings, "context_findings": context_findings})
    except Exception:
        pass

    print(f"[ERROR] Could not parse Gemini response: {text[:200]}")
    return {"diff_findings": [], "context_findings": []}