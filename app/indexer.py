import os
import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".lock", ".pdf", ".zip", ".exe", ".bin",
    ".woff", ".woff2", ".ttf", ".eot", ".docx", ".doc",
    ".log",
}

IGNORED_PATHS = {
    "node_modules", ".git", "venv", "__pycache__",
    ".next", "dist", "build", ".env",
}


def is_recently_indexed(repo_full_name: str, max_age_hours: int = 24) -> bool:
    result = supabase.table("repo_files")\
        .select("indexed_at")\
        .eq("repo_full_name", repo_full_name)\
        .order("indexed_at", desc=True)\
        .limit(1)\
        .execute()
    if not result.data:
        return False
    from datetime import datetime, timezone, timedelta
    last_indexed = datetime.fromisoformat(result.data[0]["indexed_at"].replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - last_indexed < timedelta(hours=max_age_hours)


def should_index(file_path: str) -> bool:
    parts = set(file_path.split("/"))
    if parts & IGNORED_PATHS:
        return False
    ext = os.path.splitext(file_path)[1].lower()
    if ext in IGNORED_EXTENSIONS:
        return False
    return True


def get_embedding(text: str) -> list[float]:
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
    payload = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": 768
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        raise Exception(f"Embedding API error: {response.status_code} {response.text}")
    return response.json()["embedding"]["values"]


def fetch_repo_files(repo_full_name: str, token: str) -> list[dict]:
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/HEAD?recursive=1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tree = response.json().get("tree", [])
    return [f for f in tree if f["type"] == "blob" and should_index(f["path"])]


def fetch_file_content(repo_full_name: str, file_path: str, token: str) -> str | None:
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    try:
        return response.text
    except Exception:
        return None


def index_repo(repo_full_name: str, token: str) -> None:
    print(f"[Indexer] Starting index for {repo_full_name}")

    supabase.table("repo_files").delete().eq("repo_full_name", repo_full_name).execute()

    files = fetch_repo_files(repo_full_name, token)
    print(f"[Indexer] Found {len(files)} files to index")

    indexed = 0
    for file in files:
        path = file["path"]
        content = fetch_file_content(repo_full_name, path, token)
        if not content or len(content.strip()) == 0:
            continue
        content_truncated = content[:8000]
        try:
            embedding = get_embedding(f"{path}\n\n{content_truncated}")
            supabase.table("repo_files").insert({
                "repo_full_name": repo_full_name,
                "file_path": path,
                "content": content_truncated,
                "embedding": embedding,
            }).execute()
            indexed += 1
            print(f"[Indexer] Indexed {path}")
        except Exception as e:
            print(f"[Indexer] Failed to index {path}: {e}")

    print(f"[Indexer] Done. {indexed}/{len(files)} files indexed for {repo_full_name}")


def search_relevant_files(repo_full_name: str, query: str, limit: int = 5) -> list[dict]:
    embedding = get_embedding(query)
    result = supabase.rpc("search_repo_files", {
        "query_embedding": embedding,
        "repo_name": repo_full_name,
        "match_count": limit,
    }).execute()
    return result.data