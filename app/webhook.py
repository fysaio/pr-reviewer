from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def github_webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if WEBHOOK_SECRET and not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event == "pull_request":
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name")
        pr_number = pr.get("number")
        pr_title = pr.get("title", "")
        pr_desc = pr.get("body") or ""
        head_sha = pr.get("head", {}).get("sha")

        print(f"\n--- PR EVENT ---")
        print(f"Action: {action}")
        print(f"Repo: {repo}")
        print(f"PR #{pr_number}: {pr_title}")
        print(f"By: {pr.get('user', {}).get('login')}")
        print(f"----------------\n")

        if action in ("opened", "synchronize"):
            from app.tasks import process_pr
            process_pr.delay(repo, pr_number, pr_title, pr_desc, head_sha)
            print(f"[Webhook] Queued review job for {repo} PR #{pr_number}")

    elif event == "push":
        repo = payload.get("repository", {}).get("full_name")
        commits = payload.get("commits", [])
        ref = payload.get("ref", "")

        # Only process pushes to main/master
        if ref not in ("refs/heads/main", "refs/heads/master"):
            return {"ok": True}

        changed_files = []
        for commit in commits:
            changed_files.extend(commit.get("added", []))
            changed_files.extend(commit.get("modified", []))
            changed_files.extend(commit.get("removed", []))

        changed_files = list(set(changed_files))

        if changed_files:
            from app.tasks import process_push
            from app.github_client import get_installation_token
            from app.indexer import has_any_index

            if has_any_index(repo):
                token = get_installation_token()
                process_push.delay(repo, changed_files, token)
                print(f"[Webhook] Queued incremental index for {repo} — {len(changed_files)} file(s)")

    return {"ok": True}