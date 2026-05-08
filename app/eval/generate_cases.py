import os
import re
import json
import random
import time
import requests
import base64
from dotenv import load_dotenv
from google import genai

from app.github_client import get_installation_token

load_dotenv()

# Setup Gemini Client
client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))

EVAL_REPO = os.getenv("EVAL_REPO", "fysaio/PrometheAI")
GITHUB_API = "https://api.github.com"
NUM_CASES = int(os.getenv("NUM_CASES", "5"))

SKIP = [
    'test', 'spec', 'migration', '.min.', '.d.ts', '__tests__', '__mocks__',
    'node_modules', '/dist/', '/build/', '/types/', 'fixture', 'mock',
    'seed', 'schema.ts', 'schema.js', 'index.ts', 'index.js', 'index.tsx'
]

BUG_PLANT_PROMPT = """You are building an eval dataset for an AI code reviewer called Reviu.

Given the working code below, plant exactly 3 bugs. Requirements:
- Each bug must be syntactically valid
- Each bug must look like plausible, reasonable code
- Do not add any comments or markers indicating where bugs are
- Do not rename variables or restructure the code beyond the bug itself
- One bug must be critical severity, two must be major severity
- Use different bug types: choose from state_mutation, logic_error, incorrect_guard,
  off_by_one, silent_data_loss, wrong_variable, incorrect_operator,
  error_swallowing, race_condition, null_reference

Return ONLY these two things in order, with no other text:

BUGGY_FILE_START
<complete modified file with bugs planted>
BUGGY_FILE_END

MANIFEST_START
{
  "case_id": "<snake_case_descriptive_name_based_on_filename>",
  "buggy_filename": "buggy.<ext>",
  "file_path": "<exact path of this file in the repo>",
  "bugs": [
    {
      "id": "bug_001",
      "type": "<bug_type>",
      "severity": "critical",
      "line": <exact_line_number_in_buggy_file>,
      "description": "<one sentence: what the bug is and why it breaks things>",
      "hint_keywords": ["word1","word2","word3","word4","word5"]
    },
    {
      "id": "bug_002",
      "type": "<bug_type>",
      "severity": "major",
      "line": <exact_line_number_in_buggy_file>,
      "description": "<one sentence>",
      "hint_keywords": ["word1","word2","word3","word4","word5"]
    },
    {
      "id": "bug_003",
      "type": "<bug_type>",
      "severity": "major",
      "line": <exact_line_number_in_buggy_file>,
      "description": "<one sentence>",
      "hint_keywords": ["word1","word2","word3","word4","word5"]
    }
  ]
}
MANIFEST_END

hint_keywords must be words a code reviewer would naturally write when describing this problem.
line numbers must be exact — count from line 1 of the buggy file you return.

Working code:
"""

def _headers():
    token = os.getenv("GITHUB_TOKEN") or get_installation_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def fetch_file_tree(repo):
    for ref in ['HEAD', 'main', 'master']:
        url = f"{GITHUB_API}/repos/{repo}/git/trees/{ref}?recursive=1"
        res = requests.get(url, headers=_headers())
        if res.status_code == 200:
            tree = res.json().get("tree", [])
            valid_files = []
            for f in tree:
                if f.get("type") != "blob":
                    continue
                path = f.get("path", "")
                ext = path.split('.')[-1].lower()
                if ext not in ['ts', 'tsx', 'js', 'jsx', 'py']:
                    continue
                lower_path = path.lower()
                if any(s in lower_path for s in SKIP):
                    continue
                valid_files.append(f)
            return valid_files
    raise Exception("Could not fetch file tree. Make sure the app has repo access.")

def fetch_file_content(repo, path):
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    res = requests.get(url, headers=_headers())
    res.raise_for_status()
    content = res.json().get("content", "")
    return base64.b64decode(content).decode('utf-8')

def parse_planting(response_text, file_path, ext):
    cleaned = re.sub(r'^```[\w]*\r?\n', '', response_text, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\s*$', '', cleaned, flags=re.MULTILINE)

    file_match = re.search(r'BUGGY_FILE_START\r?\n([\s\S]*?)BUGGY_FILE_END', cleaned)
    manifest_match = re.search(r'MANIFEST_START\r?\n([\s\S]*?)MANIFEST_END', cleaned)

    if not file_match:
        raise Exception("Missing BUGGY_FILE_START/END delimiters")
    if not manifest_match:
        raise Exception("Missing MANIFEST_START/END delimiters")

    buggy_file = file_match.group(1).rstrip()
    raw_json = manifest_match.group(1).strip()
    raw_json = re.sub(r'^```json\r?\n?', '', raw_json)
    raw_json = re.sub(r'```\s*$', '', raw_json).strip()

    manifest = json.loads(raw_json)
    
    if not isinstance(manifest.get("bugs"), list):
        raise Exception("manifest.bugs is not an array")
    if len(manifest["bugs"]) != 3:
        raise Exception(f"Expected 3 bugs, got {len(manifest['bugs'])}")

    line_count = len(buggy_file.split('\n'))
    for bug in manifest["bugs"]:
        if not isinstance(bug.get("line"), int):
            raise Exception(f"bug.line is not an integer: {bug.get('line')}")
        if bug["line"] < 1 or bug["line"] > line_count:
            raise Exception(f"Bug line {bug['line']} out of range (file has {line_count} lines)")

    manifest["file_path"] = file_path
    manifest["buggy_filename"] = f"buggy.{ext}"

    return buggy_file, manifest

def generate_cases():
    print(f"Scanning repository: {EVAL_REPO}...")
    all_files = fetch_file_tree(EVAL_REPO)
    print(f"Found {len(all_files)} candidate files.")
    
    random.shuffle(all_files)
    selected_files = []
    
    for f in all_files:
        if len(selected_files) >= NUM_CASES:
            break
        try:
            content = fetch_file_content(EVAL_REPO, f["path"])
            lines = len(content.split('\n'))
            if 50 <= lines <= 400:
                ext = f["path"].split('.')[-1].lower()
                selected_files.append({"path": f["path"], "content": content, "ext": ext, "lines": lines})
                print(f"  ok {f['path']} ({lines} lines)")
            time.sleep(0.5) # Prevent rate limiting
        except Exception as e:
            pass

    if not selected_files:
        print("No suitable files found.")
        return

    print(f"\nStarting bug planting phase for {len(selected_files)} files...")
    
    os.makedirs("eval_cases", exist_ok=True)
    
    for idx, f in enumerate(selected_files):
        print(f"\n[{idx+1}/{len(selected_files)}] {f['path']}")
        
        success = False
        for attempt in range(1, 3):
            print(f"  Calling Gemini (attempt {attempt})...")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=BUG_PLANT_PROMPT + f["content"],
                )
                
                if not response.text:
                    raise Exception("Empty response")
                
                buggy_file, manifest = parse_planting(response.text, f["path"], f["ext"])
                
                case_id = manifest.get("case_id", f"case_{int(time.time())}")
                case_dir = os.path.join("eval_cases", case_id)
                os.makedirs(case_dir, exist_ok=True)
                
                manifest_path = os.path.join(case_dir, "manifest.json")
                with open(manifest_path, "w") as jf:
                    json.dump(manifest, jf, indent=2)
                
                buggy_path = os.path.join(case_dir, manifest["buggy_filename"])
                with open(buggy_path, "w") as bf:
                    bf.write(buggy_file)
                
                bug_lines = ", ".join(str(b["line"]) for b in manifest["bugs"])
                print(f"  ok {case_id}")
                print(f"     lines: {bug_lines}")
                success = True
                break
            except Exception as e:
                print(f"  fail attempt {attempt}: {e}")
                time.sleep(2)
        
        if not success:
            print("  Skipping file after 2 failed attempts.")
            
    print("\nBug planting complete! Eval cases saved to eval_cases/ directory.")
    print("Next step: Run `python run_eval.py` to evaluate them.")

if __name__ == "__main__":
    generate_cases()
