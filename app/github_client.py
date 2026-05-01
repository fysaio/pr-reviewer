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


def post_review_comments(repo_full_name: str, pr_number: int, findings: list[dict]) -> None:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    body_lines = ["## AI PR Review\n"]
    for f in findings:
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
        print(f"[GitHub] Posted review with {len(findings)} finding(s) successfully.")
    else:
        print(f"[GitHub] Failed to post review: {response.status_code} {response.text}")