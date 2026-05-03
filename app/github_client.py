import os
import time
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")
INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID")


def load_private_key() -> str:
    key_content = os.getenv("GITHUB_PRIVATE_KEY")
    if key_content:
        return key_content.replace("\\n", "\n")
    with open(PRIVATE_KEY_PATH, "r") as f:
        return f.read()


def generate_jwt() -> str:
    private_key = load_private_key()
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": APP_ID,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_token() -> str:
    token = generate_jwt()
    url = f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()["token"]


def get_pr_diff(repo_full_name: str, pr_number: int) -> str:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def get_pr_details(repo_full_name: str, pr_number: int) -> dict:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def post_review_comments(repo_full_name: str, pr_number: int, review: dict, intent: dict = None) -> None:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    diff_findings = review.get("diff_findings", [])
    context_findings = review.get("context_findings", [])

    body_lines = ["## AI PR Review\n"]

    if intent:
        match_icon = "✅" if intent.get("matches") else "❌" if intent.get("matches") is False else "❓"
        body_lines.append(f"### Intent Check {match_icon}")
        body_lines.append(f"> {intent.get('summary', 'N/A')}")
        if intent.get("mismatches"):
            body_lines.append("\n**Mismatches found:**")
            for m in intent["mismatches"]:
                body_lines.append(f"- {m}")
        body_lines.append(f"\n_Intent confidence: {intent.get('confidence', 0)}%_\n")

    body_lines.append("### Issues in this PR\n")
    if diff_findings:
        for f in diff_findings:
            emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(f["severity"], "⚪")
            body_lines.append(
                f"{emoji} **[{f['category'].upper()}]** `{f['severity']}` — "
                f"`{f['file']}` line {f['line']} (confidence: {f['confidence']}%)\n\n"
                f"> {f['comment']}\n"
            )
    else:
        body_lines.append("✅ No issues found in this PR.\n")

    if context_findings:
        body_lines.append("---\n### Related Issues Worth Noting\n")
        body_lines.append("_These are pre-existing issues in code this PR touches or depends on. Not blockers, but worth knowing._\n")
        for f in context_findings:
            emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(f["severity"], "⚪")
            body_lines.append(
                f"{emoji} **[{f['category'].upper()}]** `{f['severity']}` — "
                f"`{f['file']}` line {f['line']} (confidence: {f['confidence']}%)\n\n"
                f"> {f['comment']}\n"
            )

    payload = {
        "body": "\n".join(body_lines),
        "event": "COMMENT",
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"[GitHub] Posted review — {len(diff_findings)} PR issue(s), {len(context_findings)} related issue(s).")
    else:
        print(f"[GitHub] Failed to post review: {response.status_code} {response.text}")