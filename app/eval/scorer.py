import re
from typing import List, Dict
from dataclasses import dataclass
from app.eval.manifest import PlantedBug

@dataclass
class ParsedFinding:
    severity: str
    file_ref: str
    line: int
    confidence: int
    comment: str


def parse_findings_from_comment(body: str) -> List[ParsedFinding]:
    """
    Parses Reviu's markdown review comment into structured findings.
    Handles the format produced by checks.py complete_check_run.
    """
    findings = []
    # Match lines like: 🔴 **[SECURITY]** `critical` — `handler.ts` line 47 (confidence: 94%)
    pattern = re.compile(
        r"`(critical|major|minor)`\s*[—-]\s*`([^`]+)`\s*line\s*(\d+)\s*\(confidence:\s*(\d+)%\)(.*?)(?=\n[🔴🟠🟡⚪]|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(body):
        sev, file_ref, line, conf, comment = match.groups()
        findings.append(ParsedFinding(
            severity=sev.lower(),
            file_ref=file_ref.strip(),
            line=int(line),
            confidence=int(conf),
            comment=comment.strip(),
        ))
    return findings


def score(planted_bugs: List[PlantedBug], findings: List[ParsedFinding], line_tolerance: int = 8) -> Dict:
    """
    Compares planted bugs to Reviu's findings.
    A finding is a true positive if it references within line_tolerance of a planted bug
    OR contains at least 2 of the bug's hint_keywords.
    """
    true_positives = []
    false_negatives = []
    matched_finding_indices = set()

    for bug in planted_bugs:
        matched = False
        for i, finding in enumerate(findings):
            if i in matched_finding_indices:
                continue

            line_match = abs(finding.line - bug.line) <= line_tolerance
            keyword_hits = sum(
                1 for kw in bug.hint_keywords
                if kw.lower() in finding.comment.lower() or kw.lower() in finding.file_ref.lower()
            )
            keyword_match = keyword_hits >= 2

            if line_match or keyword_match:
                true_positives.append({
                    "bug": bug,
                    "finding": finding,
                    "confidence": finding.confidence,
                    "line_match": line_match,
                    "keyword_hits": keyword_hits,
                })
                matched_finding_indices.add(i)
                matched = True
                break

        if not matched:
            false_negatives.append(bug)

    false_positives = [
        findings[i] for i in range(len(findings))
        if i not in matched_finding_indices
    ]

    total_bugs = len(planted_bugs)
    tp = len(true_positives)
    fn = len(false_negatives)
    fp = len(false_positives)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_conf  = sum(r["confidence"] for r in true_positives) / tp if tp > 0 else 0

    return {
        "total_bugs_planted": total_bugs,
        "true_positives":     tp,
        "false_negatives":    fn,
        "false_positives":    fp,
        "precision":          round(precision, 3),
        "recall":             round(recall, 3),
        "f1_score":           round(f1, 3),
        "avg_tp_confidence":  round(avg_conf, 1),
        "tp_details":         true_positives,
        "fn_details":         false_negatives,
        "fp_details":         false_positives,
    }
