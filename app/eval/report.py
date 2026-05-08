from typing import Dict, List


def print_report(case_id: str, result: Dict):
    sep = "─" * 56
    print(f"\n{sep}")
    print(f"  EVAL REPORT — {case_id}")
    print(sep)
    print(f"  Bugs planted      {result['total_bugs_planted']}")
    print(f"  True positives    {result['true_positives']}  (Reviu correctly flagged)")
    print(f"  False negatives   {result['false_negatives']}  (Reviu missed)")
    print(f"  False positives   {result['false_positives']}  (Reviu incorrectly flagged)")
    print(f"  Precision         {result['precision']}")
    print(f"  Recall            {result['recall']}")
    print(f"  F1 score          {result['f1_score']}")
    print(f"  Avg TP confidence {result['avg_tp_confidence']}%")

    if result["fn_details"]:
        print(f"\n  MISSED BUGS:")
        for bug in result["fn_details"]:
            print(f"    [{bug.severity.upper()}] {bug.description} (line {bug.line})")

    if result["fp_details"]:
        print(f"\n  FALSE ALARMS:")
        for f in result["fp_details"]:
            print(f"    [{f.severity.upper()}] {f.file_ref}:{f.line} — {f.comment[:80]}...")

    if result["tp_details"]:
        print(f"\n  CORRECTLY CAUGHT:")
        for r in result["tp_details"]:
            print(f"    [{r['bug'].severity.upper()}] {r['bug'].description}")
            print(f"      -> Reviu: line {r['finding'].line}, {r['finding'].confidence}% confidence")

    print(sep)


def save_report(case_id: str, result: Dict, path: str):
    import json
    with open(path, "w") as f:
        data = {
            "case_id": case_id,
            "scores": {k: v for k, v in result.items() if k not in ("tp_details", "fn_details", "fp_details")},
            "missed": [{"id": b.id, "severity": b.severity, "description": b.description, "line": b.line} for b in result["fn_details"]],
            "false_alarms": [{"severity": f.severity, "file": f.file_ref, "line": f.line, "comment": f.comment} for f in result["fp_details"]],
        }
        json.dump(data, f, indent=2)
    print(f"\n  Report saved to {path}")
