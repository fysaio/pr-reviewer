import os, sys, time
from app.eval.manifest import EvalCase
from app.eval.runner import (
    get_default_branch_sha, create_branch, commit_file,
    open_pr, wait_for_review_comment, close_pr_and_delete_branch,
)
from app.eval.scorer import parse_findings_from_comment, score
from app.eval.report import print_report, save_report


def run_case(case_dir: str, eval_repo: str, cleanup: bool = True):
    case = EvalCase.load(case_dir)
    print(f"\n[Eval] Running case: {case.case_id}")
    print(f"       File: {case.file_path}")
    print(f"       Bugs planted: {len(case.bugs)}")

    with open(case.buggy_file) as f:
        buggy_content = f.read()

    branch = f"eval/{case.case_id}-{int(time.time())}"
    sha = get_default_branch_sha(eval_repo)

    print(f"  Creating branch {branch}...")
    create_branch(eval_repo, branch, sha)

    print(f"  Committing buggy file...")
    commit_file(
        repo=eval_repo,
        file_path=case.file_path,
        content=buggy_content,
        branch=branch,
        message=f"eval: {case.case_id} — plant test bugs",
    )

    print(f"  Opening PR...")
    pr_number = open_pr(
        repo=eval_repo,
        branch=branch,
        title=f"[eval] {case.case_id}",
        body=f"Automated eval case. Contains {len(case.bugs)} planted bugs.",
    )
    print(f"  PR #{pr_number} opened.")

    comment_body = wait_for_review_comment(eval_repo, pr_number)

    if not comment_body:
        print(f"  Timed out waiting for Reviu. PR #{pr_number} left open for inspection.")
        return None

    print(f"  Reviu responded. Scoring...")
    findings = parse_findings_from_comment(comment_body)
    result = score(case.bugs, findings)

    print_report(case.case_id, result)

    os.makedirs("eval_results", exist_ok=True)
    save_report(case.case_id, result, f"eval_results/{case.case_id}.json")

    if cleanup:
        print(f"  Cleaning up PR and branch...")
        close_pr_and_delete_branch(eval_repo, pr_number, branch)

    return result


def run_all(cases_dir: str = "eval_cases", eval_repo: str = None):
    repo = eval_repo or os.getenv("EVAL_REPO", "fysaio/PrometheAI")
    results = []
    for case_name in sorted(os.listdir(cases_dir)):
        case_dir = os.path.join(cases_dir, case_name)
        if not os.path.isdir(case_dir):
            continue
        result = run_case(case_dir, repo)
        if result:
            results.append((case_name, result))

    if results:
        print("\n" + "═" * 56)
        print("  AGGREGATE RESULTS")
        print("═" * 56)
        avg_f1 = sum(r["f1_score"] for _, r in results) / len(results)
        avg_recall = sum(r["recall"] for _, r in results) / len(results)
        total_tp = sum(r["true_positives"] for _, r in results)
        total_fn = sum(r["false_negatives"] for _, r in results)
        total_fp = sum(r["false_positives"] for _, r in results)
        print(f"  Cases run         {len(results)}")
        print(f"  Total TP          {total_tp}")
        print(f"  Total FN          {total_fn}")
        print(f"  Total FP          {total_fp}")
        print(f"  Avg recall        {round(avg_recall, 3)}")
        print(f"  Avg F1            {round(avg_f1, 3)}")
        print("═" * 56)
