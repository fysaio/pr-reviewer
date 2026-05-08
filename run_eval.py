#!/usr/bin/env python3
"""
Run the Reviu eval suite.

Usage:
  python run_eval.py                        # run all cases
  python run_eval.py eval_cases/case_001    # run single case
  python run_eval.py --repo fysaio/SabiOS   # run against different repo
  python run_eval.py --generate             # generate new eval cases using Gemini
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.eval.cli import run_case, run_all

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--generate" in args:
        from app.eval.generate_cases import generate_cases
        generate_cases()
        sys.exit(0)
        
    repo = None
    dirs = []

    for arg in args:
        if arg.startswith("--repo="):
            repo = arg.split("=", 1)[1]
        elif os.path.isdir(arg) and not arg.startswith("--"):
            dirs.append(arg)

    if dirs:
        for d in dirs:
            run_case(d, repo or os.getenv("EVAL_REPO", "fysaio/PrometheAI"))
    else:
        run_all(eval_repo=repo)
