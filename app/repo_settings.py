import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))


def get_or_create_settings(repo_full_name: str) -> dict:
    result = supabase.table("repo_settings")\
        .select("*")\
        .eq("repo_full_name", repo_full_name)\
        .limit(1)\
        .execute()

    if result.data:
        return result.data[0]

    # First time seeing this repo -- create default settings
    new = supabase.table("repo_settings").insert({
        "repo_full_name": repo_full_name,
        "review_mode": "junior",
        "confidence_threshold": 70,
        "enabled": True,
    }).execute()

    print(f"[Settings] Created default settings for {repo_full_name}")
    return new.data[0]


def update_after_review(repo_full_name: str) -> None:
    supabase.rpc("increment_review_count", {
        "repo_name": repo_full_name
    }).execute()


def is_enabled(repo_full_name: str) -> bool:
    settings = get_or_create_settings(repo_full_name)
    return settings.get("enabled", True)