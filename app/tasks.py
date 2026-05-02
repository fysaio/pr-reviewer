import os
from app.celery_app import celery
from dotenv import load_dotenv

load_dotenv()

REVIEW_MODE = os.getenv("REVIEW_MODE", "junior")


@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def process_pr(self, repo: str, pr_number: int, pr_title: str, pr_desc: str, head_sha: str):
    try:
        from app.github_client import get_pr_diff, get_pr_details, post_review_comments, get_installation_token
        from app.reviewer import review_pr
        from app.indexer import index_repo, search_relevant_files, is_recently_indexed, has_any_index
        from app.intent_checker import check_intent
        from app.checks import create_check_run, complete_check_run

        print(f"[Task] Starting review for {repo} PR #{pr_number}")

        check_run_id = create_check_run(repo, head_sha)

        token = get_installation_token()
        diff = get_pr_diff(repo, pr_number)

        if not has_any_index(repo):
            print(f"[Task] No index found, indexing synchronously...")
            index_repo(repo, token)
        elif not is_recently_indexed(repo):
            print(f"[Task] Stale index, triggering background reindex...")
            reindex_repo.delay(repo, token)
        else:
            print(f"[Task] Index is fresh, skipping.")

        print(f"[Task] Searching for relevant context...")
        context_files = search_relevant_files(repo, diff[:3000])
        print(f"[Task] Found {len(context_files)} relevant file(s)")

        print(f"[Task] Checking PR intent...")
        intent = check_intent(diff, pr_desc, pr_title)
        print(f"[Task] Intent matches: {intent.get('matches')} (confidence: {intent.get('confidence')}%)")

        print(f"[Task] Running Gemini review in {REVIEW_MODE} mode...")
        review = review_pr(diff, pr_desc, context_files, mode=REVIEW_MODE)
        print(f"[Task] Found {len(review['diff_findings'])} PR issue(s), {len(review['context_findings'])} related issue(s)")

        post_review_comments(repo, pr_number, review, intent)

        if check_run_id:
            complete_check_run(repo, check_run_id, review, intent)

        print(f"[Task] Review complete for {repo} PR #{pr_number}")

    except Exception as exc:
        print(f"[Task] Error processing PR: {exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=2)
def reindex_repo(self, repo: str, token: str):
    try:
        from app.indexer import index_repo
        print(f"[Task] Reindexing {repo}...")
        index_repo(repo, token)
        print(f"[Task] Reindex complete for {repo}")
    except Exception as exc:
        print(f"[Task] Reindex failed: {exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=2)
def process_push(self, repo: str, changed_files: list[str], token: str):
    try:
        from app.indexer import update_changed_files
        print(f"[Task] Incremental index for {repo} — {len(changed_files)} file(s) changed")
        update_changed_files(repo, changed_files, token)
        print(f"[Task] Incremental index complete for {repo}")
    except Exception as exc:
        print(f"[Task] Incremental index failed: {exc}")
        raise self.retry(exc=exc)