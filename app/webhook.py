from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib
import os
import threading
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
REVIEW_MODE = os.getenv("REVIEW_MODE", "junior")


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
        head_sha = pr.get("head", {}).get("sha")

        print(f"\n--- PR EVENT ---")
        print(f"Action: {action}")
        print(f"Repo: {repo}")
        print(f"PR #{pr_number}: {pr_title}")
        print(f"By: {pr.get('user', {}).get('login')}")
        print(f"Mode: {REVIEW_MODE}")
        print(f"----------------\n")

        if action in ("opened", "synchronize"):
            from app.github_client import get_pr_diff, get_pr_details, post_review_comments, get_installation_token
            from app.reviewer import review_pr
            from app.indexer import index_repo, search_relevant_files, is_recently_indexed
            from app.intent_checker import check_intent
            from app.checks import create_check_run, complete_check_run

            # Post check run immediately so user sees feedback on GitHub
            check_run_id = create_check_run(repo, head_sha)

            token = get_installation_token()
            details = get_pr_details(repo, pr_number)
            diff = get_pr_diff(repo, pr_number)
            pr_desc = details.get("body")

            # Index in background only if not recently indexed
            if not is_recently_indexed(repo):
                print(f"[Indexer] Repo not indexed recently, indexing in background...")
                threading.Thread(target=index_repo, args=(repo, token), daemon=True).start()
            else:
                print(f"[Indexer] Repo already indexed recently, skipping.")

            print(f"[Indexer] Searching for relevant context...")
            context_files = search_relevant_files(repo, diff[:3000])
            print(f"[Indexer] Found {len(context_files)} relevant file(s) for context")

            print(f"[Intent] Checking PR intent...")
            intent = check_intent(diff, pr_desc, pr_title)
            print(f"[Intent] Matches: {intent.get('matches')} (confidence: {intent.get('confidence')}%)")
            print(f"[Intent] Summary: {intent.get('summary')}")
            if intent.get("mismatches"):
                print(f"[Intent] Mismatches: {intent.get('mismatches')}")

            print(f"[Reviewer] Running Gemini review in {REVIEW_MODE} mode...")
            findings = review_pr(diff, pr_desc, context_files, mode=REVIEW_MODE)
            print(f"\n--- FINDINGS ({len(findings)}) ---")
            for f in findings:
                print(f)
            print(f"--------------------------------\n")

            post_review_comments(repo, pr_number, findings, intent)

            if check_run_id:
                complete_check_run(repo, check_run_id, findings, intent)

    return {"ok": True}