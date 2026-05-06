import os
import time
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY")
INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID")


def get_installation_token() -> str:
    private_key = PRIVATE_KEY
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": APP_ID,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    url = f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    return response.json()["token"]


def create_check_run(repo_full_name: str, head_sha: str, name: str = "AI PR Reviewer") -> str:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "name": name,
        "head_sha": head_sha,
        "status": "in_progress",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output": {
            "title": "AI Review in progress...",
            "summary": "Indexing repository and analyzing diff. This usually takes 30-60 seconds.",
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        check_run_id = response.json()["id"]
        print(f"[Checks] Created check run {check_run_id}")
        return check_run_id
    else:
        print(f"[Checks] Failed to create check run: {response.status_code} {response.text}")
        return None


def complete_check_run(repo_full_name: str, check_run_id: str, review: dict, intent: dict) -> None:
    token = get_installation_token()
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs/{check_run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    diff_findings = review.get("diff_findings", [])
    context_findings = review.get("context_findings", [])
    critical_or_major = [f for f in diff_findings if f.get("severity") in ("critical", "major")]
    conclusion = "failure" if critical_or_major else "success"

    summary_lines = []
    if intent:
        match_icon = "✅" if intent.get("matches") else "❌" if intent.get("matches") is False else "❓"
        summary_lines.append(f"**Intent Check {match_icon}:** {intent.get('summary', '')}")
        if intent.get("mismatches"):
            for m in intent["mismatches"]:
                summary_lines.append(f"- {m}")

    summary_lines.append(f"\n**Issues in this PR:** {len(diff_findings)}")
    if context_findings:
        summary_lines.append(f"**Related issues worth noting:** {len(context_findings)}")

    text_lines = []
    if diff_findings:
        text_lines.append("## Issues in this PR\n")
        for f in diff_findings:
            emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(f["severity"], "⚪")
            text_lines.append(
                f"{emoji} **[{f['category'].upper()}]** `{f['severity']}` — "
                f"`{f['file']}` line {f['line']} (confidence: {f['confidence']}%)\n\n"
                f"{f['comment']}\n"
            )

    if context_findings:
        text_lines.append("## Related Issues Worth Noting\n")
        for f in context_findings:
            emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(f["severity"], "⚪")
            text_lines.append(
                f"{emoji} **[{f['category'].upper()}]** `{f['severity']}` — "
                f"`{f['file']}` line {f['line']} (confidence: {f['confidence']}%)\n\n"
                f"{f['comment']}\n"
            )

    payload = {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output": {
            "title": f"AI Review — {len(diff_findings)} PR issue(s), {len(context_findings)} related",
            "summary": "\n".join(summary_lines),
            "text": "\n".join(text_lines) if text_lines else "No issues found.",
        }
    }

    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"[Checks] Updated check run to {conclusion}")
    else:
        print(f"[Checks] Failed to update check run: {response.status_code} {response.text}")