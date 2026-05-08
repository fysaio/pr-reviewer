# Reviu (AI PR Reviewer)

An automated, context-aware code review agent that uses Google Gemini and Vector Search (Supabase pgvector) to provide deep, systemic reviews for GitHub Pull Requests.

Unlike traditional AI reviewers that only look at the PR diff, **Reviu indexes your entire repository** and retrieves the most contextually relevant files *before* analyzing the changes. This allows it to catch cross-file bugs, architectural inconsistencies, and silent omissions that diff-only systems structurally cannot see.

## Features
- **RAG-Powered Context**: Uses `gemini-embedding-001` to index the repo into Supabase. For every PR, the diff is embedded and used to query the top 5 most relevant files via cosine similarity.
- **Dual-Pass Review**: 
  - *Pass 1*: Verifies intent (Does the code do what the description claims?).
  - *Pass 2*: Deep code review with full context (diff + retrieved files) using Gemini 2.5 Flash.
- **Decoupled Architecture**: Fast HTTP webhook acknowledgment (to satisfy GitHub's timeouts) while a Celery/Redis worker processes the heavy lifting asynchronously.
- **Configurable Thresholds**: Every finding gets an AI-generated confidence score. Repositories can set a custom threshold to filter out noise.
- **Junior vs Senior Modes**: Configurable verbosity. Junior mode explains *why* something is an issue; Senior mode is concise and direct.

---

## How It Works

```text
GitHub PR opened → POST /webhook (200 immediately)
      ↓
Celery task queued in Redis
      ↓
Worker: check repo_settings → fetch diff → index repo (if needed)
      ↓
pgvector semantic search → top 5 relevant files retrieved
      ↓
Gemini call 1: intent verification
Gemini call 2: code review with context
      ↓
Post Check Run + PR comment → update repo_settings
```

---

## Setup Guide

### 1. GitHub App Configuration
1. Go to your GitHub [Developer Settings](https://github.com/settings/apps) and create a **New GitHub App**.
2. **Permissions**:
   - **Pull requests**: Read & Write (to post comments)
   - **Contents**: Read (to fetch code and diffs)
   - **Metadata**: Read-only
3. **Events**: Subscribe to **Pull request** events.
4. **Webhook**: Set your webhook URL to `https://your-domain.com/webhook`.
5. **Private Key**: Generate a private key and download the `.pem` file. Place it in the root directory.
6. **Installation**: Install the app on your repository and note the **Installation ID**.

### 2. Supabase (pgvector) Setup
1. Create a new project on [Supabase](https://supabase.com/).
2. Enable the **Vector** extension in the SQL Editor:
   ```sql
   create extension if not exists vector;
   ```
3. Create the `repo_files` table:
   ```sql
   create table repo_files (
     id bigint primary key generated always as identity,
     repo_full_name text not null,
     file_path text not null,
     content text,
     embedding vector(768) -- 768 for gemini-embedding-001
   );

   create index on repo_files using ivfflat (embedding vector_cosine_ops);
   ```
4. Create the search function (RPC):
   ```sql
   create or replace function search_repo_files(
     query_embedding vector(768),
     repo_name text,
     match_count int
   )
   returns table (
     id bigint,
     repo_full_name text,
     file_path text,
     content text,
     similarity float
   )
   language plpgsql
   as $$
   begin
     return query
     select
       repo_files.id,
       repo_files.repo_full_name,
       repo_files.file_path,
       repo_files.content,
       1 - (repo_files.embedding <=> query_embedding) as similarity
     from repo_files
     where repo_files.repo_full_name = repo_name
     order by repo_files.embedding <=> query_embedding
     limit match_count;
   end;
   $$;
   ```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
# GitHub App
GITHUB_APP_ID=your_app_id
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_PRIVATE_KEY_PATH=your-key.pem
# Alternatively, pass the key as an environment variable directly
# GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..." 

# AI Provider
GOOGLE_AI_API_KEY=your_gemini_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key

# Redis (Celery Broker/Backend)
REDIS_URL=redis://localhost:6379/0
```

### 4. Local Installation & Running
```bash
# Clone the repository
git clone https://github.com/fysaio/pr-reviewer.git
cd pr-reviewer

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# In Terminal 1: Start Redis (make sure redis-server is installed)
redis-server

# In Terminal 2: Start the Celery Worker
celery -A app.celery_app worker --loglevel=info

# In Terminal 3: Start the FastAPI webhook server
uvicorn app.main:app --reload
```

---

## Documentation & Performance Evals

For an in-depth look at Reviu's architecture, the specific flaws of diff-only AI reviewers, and an honest account of our evaluation results (Recall: 0.909, Precision: 0.405), please read the full writeup:

[**How Reviu works, architecture decisions, and eval results →**](./WRITEUP.md)

## License
MIT