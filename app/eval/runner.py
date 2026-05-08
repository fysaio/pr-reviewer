import os, time, base64, requests
from typing import Optional
from app.github_client import get_installation_token

EVAL_REPO = os.getenv("EVAL_REPO", "fysaio/PrometheAI")
GITHUB_API = "https://api.github.com"


def _headers():
    token = os.getenv("GITHUB_TOKEN") or get_installation_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def get_default_branch_sha(repo: str) -> str:
    r = requests.get(f"{GITHUB_API}/repos/{repo}", headers=_headers())
    r.raise_for_status()
    branch = r.json()["default_branch"]
    r2 = requests.get(f"{GITHUB_API}/repos/{repo}/git/ref/heads/{branch}", headers=_headers())
    r2.raise_for_status()
    return r2.json()["object"]["sha"]


def create_branch(repo: str, branch_name: str, sha: str):
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/refs",
        headers=_headers(),
        json={"ref": f"refs/heads/{branch_name}", "sha": sha},
    )
    if r.status_code not in (201, 422):
        r.raise_for_status()


def get_file_sha(repo: str, file_path: str, branch: str) -> Optional[str]:
    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/contents/{file_path}",
        headers=_headers(),
        params={"ref": branch},
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get("sha")


def commit_file(repo: str, file_path: str, content: str, branch: str, message: str):
    encoded = base64.b64encode(content.encode()).decode()
    existing_sha = get_file_sha(repo, file_path, branch)
    payload = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha
    r = requests.put(
        f"{GITHUB_API}/repos/{repo}/contents/{file_path}",
        headers=_headers(),
        json=payload,
    )
    r.raise_for_status()


def open_pr(repo: str, branch: str, title: str, body: str) -> int:
    default = requests.get(f"{GITHUB_API}/repos/{repo}", headers=_headers()).json()["default_branch"]
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/pulls",
        headers=_headers(),
        json={"title": title, "head": branch, "base": default, "body": body},
    )
    r.raise_for_status()
    return r.json()["number"]


def wait_for_review_comment(repo: str, pr_number: int, timeout: int = 360) -> Optional[str]:
    """Polls every 15s for a Reviu review comment. Returns comment body or None."""
    deadline = time.time() + timeout
    print(f"    Waiting for Reviu to review PR #{pr_number}...")
    while time.time() < deadline:
        for endpoint in [f"issues/{pr_number}/comments", f"pulls/{pr_number}/reviews"]:
            r = requests.get(
                f"{GITHUB_API}/repos/{repo}/{endpoint}",
                headers=_headers(),
            )
            r.raise_for_status()
            for comment in r.json():
                if "AI Review" in comment.get("body", "") or "diff_findings" in comment.get("body", "").lower() or "## Issues in this PR" in comment.get("body", ""):
                    return comment["body"]
        time.sleep(15)
    return None


def close_pr_and_delete_branch(repo: str, pr_number: int, branch: str):
    requests.patch(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}",
        headers=_headers(),
        json={"state": "closed"},
    )
    requests.delete(
        f"{GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
        headers=_headers(),
    )
