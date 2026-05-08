from dataclasses import dataclass, field
from typing import List, Optional
import json, os

@dataclass
class PlantedBug:
    id: str
    type: str
    severity: str       # critical | major | minor
    line: int
    description: str
    hint_keywords: List[str]

@dataclass
class EvalCase:
    case_id: str
    file_path: str      # path inside the repo where the file lives
    buggy_file: str     # local path to the buggy file content
    bugs: List[PlantedBug]

    @classmethod
    def load(cls, case_dir: str) -> "EvalCase":
        with open(os.path.join(case_dir, "manifest.json")) as f:
            data = json.load(f)
        bugs = [PlantedBug(**b) for b in data["bugs"]]
        buggy_path = os.path.join(case_dir, data["buggy_filename"])
        return cls(
            case_id=data["case_id"],
            file_path=data["file_path"],
            buggy_file=buggy_path,
            bugs=bugs,
        )
