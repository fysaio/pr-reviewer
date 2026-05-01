import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))


def check_intent(diff: str, pr_description: str, pr_title: str) -> dict:
    if not pr_description or pr_description.strip() == "":
        return {
            "matches": None,
            "confidence": 0,
            "summary": "No PR description provided. Cannot verify intent.",
            "mismatches": [],
        }

    prompt = f"""You are a senior engineer reviewing whether a pull request does what it claims to do.

PR Title: {pr_title}

PR Description:
{pr_description}

Diff:
{diff[:6000]}

Analyze whether the diff actually implements what the PR title and description claim.

Return ONLY a JSON object with these fields:
- "matches": true if the diff matches the description, false if there are significant mismatches, null if description is too vague to tell
- "confidence": integer 0-100, how confident you are in your assessment
- "summary": 1-2 sentence summary of what the diff actually does
- "mismatches": array of strings describing anything in the description not reflected in the diff, or anything in the diff not mentioned in the description. Empty array if none.

Example:
{{
  "matches": false,
  "confidence": 87,
  "summary": "The diff only updates the README. No authentication logic was changed.",
  "mismatches": [
    "Description claims to fix login bug but no auth files were modified",
    "Diff includes unrelated style changes not mentioned in description"
  ]
}}
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
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[ERROR] Could not parse intent check response: {text}")
        return {
            "matches": None,
            "confidence": 0,
            "summary": "Intent check failed to parse.",
            "mismatches": [],
        }