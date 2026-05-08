# AI PR Reviewer

An automated code review agent that uses Google Gemini and Vector Search (Supabase) to provide context-aware reviews for GitHub Pull Requests.

## Features
- **Context-Aware Reviews**: Uses RAG (Retrieval-Augmented Generation) to search your codebase for relevant files before reviewing a PR.
- **Dual AI Support**: Compatible with Google AI Studio (Gemini API) and Vertex AI.
- **Automated Comments**: Posts review findings directly onto the GitHub PR as line-by-line comments.
- **FastAPI Backend**: Lightweight and ready for deployment.

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

### 2. Supabase (Vector Database) Setup
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
Create a `.env` file in the root directory (use `.env.example` if provided):
```env
# GitHub App
GITHUB_APP_ID=your_app_id
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_PRIVATE_KEY_PATH=your-key.pem
GITHUB_INSTALLATION_ID=your_installation_id

# AI Provider
GOOGLE_AI_API_KEY=your_gemini_api_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
```

### 4. Local Installation
```bash
# Clone the repository
git clone https://github.com/fysaio/pr-reviewer.git
cd pr-reviewer

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

---

## How it Works
1. **Webhook**: When a PR is opened or updated, GitHub sends a webhook to this app.
2. **Indexing**: On the first PR, the app crawls the repository, generates embeddings for every file, and stores them in Supabase.
3. **Context Retrieval**: For every PR change, the app searches Supabase for files most relevant to the modified code.
4. **AI Review**: The PR diff + retrieved context are sent to Gemini for analysis.
5. **Feedback**: Review comments are posted back to the GitHub PR automatically.

## Writeup

[How Reviu works, architecture decisions, and eval results →](./WRITEUP.md)

## License
MIT
