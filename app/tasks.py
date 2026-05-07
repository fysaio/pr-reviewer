import os
from app.celery_app import celery
from dotenv import load_dotenv

load_dotenv()

REVIEW_MODE = os.getenv("REVIEW_MODE", "junior")

NETWORK_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def is_network_error(exc: Exception) -> bool:
    if isinstance(exc, NETWORK_ERRORS):
        return True
    msg = str(exc).lower()
    return any(phrase in msg for phrase in [
        "getaddrinfo failed",
        "connection refused",
        "timed out",
        "read timeout",
        "connection reset",
        "name resolution",
        "network is unreachable",
        "ssl",
        "10054",
        "10060",
        "10053",
    ])


@celery.task(bind=True, max_retries=5, default_retry_delay=30)
def process_pr(self, repo: str, pr_number: int, pr_title: str, pr_desc: str, head_sha: str):
    try:
        from app.github_client import get_pr_diff, get_pr_details, post_review_comments, get_installation_token
        from app.reviewer import review_pr
        from app.indexer import index_repo, search_relevant_files, is_recently_indexed, has_any_index
        from app.intent_checker import check_intent
        from app.checks import create_check_run, complete_check_run
        from app.repo_settings import get_or_create_settings, update_after_review, is_enabled, log_review

        print(f"[Task] Starting review for {repo} PR #{pr_number}")

        # Check if repo is enabled
        if not is_enabled(repo):
            print(f"[Task] Reviews disabled for {repo}, skipping.")
            return

        # Get per-repo settings
        settings = get_or_create_settings(repo)
        review_mode = settings.get("review_mode", REVIEW_MODE)
        confidence_threshold = settings.get("confidence_threshold", 70)
        print(f"[Task] Mode: {review_mode}, Confidence threshold: {confidence_threshold}%")

        check_run_id = create_check_run(repo, head_sha)

        token = get_installation_token()
        diff = get_pr_diff(repo, pr_number)
        pr_desc_fetched = get_pr_details(repo, pr_number).get("body") or pr_desc

        if not has_any_index(repo):
            print(f"[Task] No index found, indexing synchronously...")
            index_repo(repo, token)
        elif not is_recently_indexed(repo):
            print(f"[Task] Stale index, triggering background reindex...")
            reindex_repo.delay(repo)
        else:
            print(f"[Task] Index is fresh, skipping.")

        print(f"[Task] Searching for relevant context...")
        context_files = search_relevant_files(repo, diff[:3000])
        print(f"[Task] Found {len(context_files)} relevant file(s)")

        print(f"[Task] Checking PR intent...")
        intent = check_intent(diff, pr_desc_fetched, pr_title)
        print(f"[Task] Intent matches: {intent.get('matches')} (confidence: {intent.get('confidence')}%)")

        print(f"[Task] Running Gemini review in {review_mode} mode...")
        review = review_pr(diff, pr_desc_fetched, context_files, mode=review_mode, confidence_threshold=confidence_threshold)
        print(f"[Task] Found {len(review['diff_findings'])} PR issue(s), {len(review['context_findings'])} related issue(s)")

        post_review_comments(repo, pr_number, review, intent)

        if check_run_id:
            complete_check_run(repo, check_run_id, review, intent)

        verdict = "pass" if len(review["diff_findings"]) == 0 else "fail"
        log_review(
            repo_full_name=repo,
            pr_number=pr_number,
            pr_title=pr_title,
            diff_findings=len(review["diff_findings"]),
            context_findings=len(review["context_findings"]),
            verdict=verdict,
            review_mode=review_mode,
        )

        update_after_review(repo)
        print(f"[Task] Review complete for {repo} PR #{pr_number}")

    except Exception as exc:
        print(f"[Task] Error processing PR: {exc}")
        if is_network_error(exc):
            delay = min(30 * (2 ** self.request.retries), 300)
            print(f"[Task] Network error detected, retrying in {delay}s (attempt {self.request.retries + 1}/5)...")
            raise self.retry(exc=exc, countdown=delay)
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def reindex_repo(self, repo: str):
    try:
        from app.indexer import index_repo
        from app.github_client import get_installation_token
        token = get_installation_token()
        print(f"[Task] Reindexing {repo}...")
        index_repo(repo, token)
        print(f"[Task] Reindex complete for {repo}")
    except Exception as exc:
        print(f"[Task] Reindex failed: {exc}")
        if is_network_error(exc):
            delay = min(60 * (2 ** self.request.retries), 600)
            print(f"[Task] Network error, retrying reindex in {delay}s...")
            raise self.retry(exc=exc, countdown=delay)
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_push(self, repo: str, changed_files: list[str]):
    try:
        from app.indexer import update_changed_files
        from app.github_client import get_installation_token
        token = get_installation_token()
        print(f"[Task] Incremental index for {repo} — {len(changed_files)} file(s) changed")
        update_changed_files(repo, changed_files, token)
        print(f"[Task] Incremental index complete for {repo}")
    except Exception as exc:
        print(f"[Task] Incremental index failed: {exc}")
        if is_network_error(exc):
            delay = min(60 * (2 ** self.request.retries), 600)
            print(f"[Task] Network error, retrying in {delay}s...")
            raise self.retry(exc=exc, countdown=delay)
        raise self.retry(exc=exc)