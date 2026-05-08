# Reviu

Most AI code reviewers work the same way. They receive a diff, apply a set of heuristics trained into the model, and return findings. The diff is the entire universe of information available to the reviewer. This is a significant constraint.

A diff tells you what changed. It says nothing about the system the change is landing in. Whether the modified endpoint already has rate limiting elsewhere in the stack, whether the function being refactored has callers that depend on its current behavior, whether the error type being thrown is handled by a top-level boundary: none of that is visible from the diff alone. The result is reviews that are generic by necessity. Correct in the abstract, but weakly coupled to the actual codebase under review.

Reviu takes a different approach. Before the reviewer sees any diff, it indexes the entire repository into a vector database using semantic embeddings and retrieves the most contextually relevant files against the diff. The review happens with that context in scope. This changes what kinds of findings are possible. It also changes what the system is responsible for getting right.

This document covers the architecture, the tradeoffs, and an honest account of how Reviu performs in practice, including where it falls short.

---

## Architecture

The review pipeline is built around two constraints: webhook reliability and review quality. GitHub expects a 200 response from a webhook endpoint within a few seconds. A review that involves fetching diffs, querying a vector database, and making multiple LLM calls cannot complete within that window. Decoupling the HTTP response from the review work is not optional. It is a requirement.

```
GitHub PR opened -> POST /webhook (200 immediately)
      |
Celery task queued in Redis
      |
Worker: check repo_settings -> fetch diff -> index repo (if needed)
      |
pgvector semantic search -> top 5 relevant files retrieved
      |
Gemini call 1: intent verification
Gemini call 2: code review with context
      |
Post Check Run + PR comment -> update repo_settings
```

The FastAPI webhook handler acknowledges immediately and enqueues a Celery task to Redis Cloud. A separate Railway worker service picks up the task and runs the full pipeline. Webhook delivery reliability is completely decoupled from review latency. If the worker takes 45 seconds to index a large repo, that is a worker concern, not a webhook concern.

The worker begins by checking `repo_settings` to determine whether the repository has already been indexed and what configuration is active. If the repo has not been indexed, or if a re-index has been triggered, it fetches the repository tree, chunks the files, generates embeddings using `gemini-embedding-001` at 768 dimensions, and stores the vectors in Supabase via pgvector. Indexing is expensive in time and API cost, so it runs once and is invalidated only when explicitly triggered or when the settings record indicates the repo has changed materially.

Once the index is ready, the worker fetches the PR diff and runs a semantic search against pgvector to retrieve the five most relevant files. The diff itself is embedded and used as the query vector. The five files with the highest cosine similarity scores are returned and appended to the review context. This is the mechanism that makes cross-file reasoning possible.

The actual review involves two separate Gemini 2.5 Flash calls. The first is intent verification: does the code in the diff do what the PR description claims? This is a narrow, answerable question, and separating it from the review prevents the two concerns from contaminating each other. A combined prompt asking the model to simultaneously verify intent and find bugs produces worse signal than two focused prompts. The second call performs the code review with the diff and retrieved context both in scope.

Every finding ships with a confidence percentage. Teams configure a per-repo threshold and findings below it are suppressed before being posted. After both calls complete, Reviu posts a GitHub Check Run with a summary status and a PR comment with the full findings. The `repo_settings` record is updated with the indexing state and any threshold adjustments.

---

## Why RAG Changes the Review

Reviewing a diff in isolation produces findings about what is present in the diff. It cannot produce findings about what the diff is missing, what it breaks elsewhere, or what it assumes about the surrounding system. Those are often the most important findings.

Consider a concrete case: a new API route is added in a PR. The diff shows the route handler, the auth middleware applied to it, and the response schema. A reviewer working on the diff alone can verify that the handler is typed correctly, that the middleware is applied, and that the response shape matches the schema. What the diff does not show is whether the codebase has a `RateLimiter` class already in use on similar routes. If it does, the omission of rate limiting on the new route is a real bug. If it does not, suggesting it is speculation. A RAG-backed reviewer can make that distinction. A diff-only reviewer cannot.

This pattern generalizes. Whether a thrown error type is caught by an existing boundary, whether a new utility function duplicates one already present under a different name, whether a config key being written matches the schema being read elsewhere: all of these require cross-file visibility. The RAG retrieval step is what makes this possible, and it is the primary architectural difference between Reviu and tools that treat each PR as a closed system.

The tradeoffs are real. Indexing a repository takes time on first run and that time scales with repository size. Embedding every file costs money at the API level. The retrieval step introduces a quality dependency: if the five retrieved files are not actually the most relevant ones, the context provided to the reviewer is noisy rather than helpful. In practice, `gemini-embedding-001` retrieves well on semantic similarity within a codebase, but edge cases exist, particularly in repos with very flat structure or highly generic naming conventions where many files look similarly distant from the query.

The signal quality difference is significant enough to justify these costs. Reviews grounded in codebase context produce findings that are harder to dismiss as generic, and they surface the class of bugs that diff-only systems structurally cannot catch.

---

## Eval Results

Reviu was evaluated across 11 cases covering 33 planted bugs in TypeScript and TSX files, spanning React components, Next.js pages, API libraries, and Genkit AI flows.

Recall was 0.909: 30 of 33 bugs were caught. Precision was 0.405: 30 true positives against 44 false positives, for a total of 74 findings. The average F1 across cases was 0.564. The average confidence on true positives was 97.8%.

The recall number is strong. The three misses were all from categories that are structurally difficult: a boolean guard operator swap (`&&` vs `||` in a null-check early-return), a wrong delete-count argument to `.splice()`, and a semantic omission in an AI prompt template string. None of these have syntactic fingerprints that stand out in a diff. The guard condition inversion looks like valid code and requires reasoning about the intent of the condition to catch. The `.splice()` argument error requires knowing the API contract precisely enough to flag an off-by-one in the delete count. The prompt omission requires treating the content of a string literal as functional code, then reasoning about what the downstream model will fail to return as a result.

The precision number is not acceptable in production. At 44 false positives against 30 true positives, the noise level would quickly erode engineer trust in the findings. A reviewer that requires triage to determine which comments are real defeats its own purpose.

The false positives break into four categories. The largest, roughly 15 to 18 findings, was Reviu flagging issues in context files retrieved for reference but not changed by the PR. The retrieval mechanism provides files as context, not as review targets, but the current prompt does not enforce that boundary. The second category was repeated trailing newline complaints across nearly every case, which inflated the false positive count by 7 to 8 findings and is purely a prompt-scoping problem. The third was style and architecture suggestions: DRY violations, abstraction layer recommendations, type centralization. Those are code quality opinions, not defect findings. The fourth was hallucinated incomplete or syntax-broken code in truncated retrieved files, where the model interpreted retrieval truncation as actual incompleteness.

The confidence score did not distinguish true positives from false positives. All 44 false positives were generated at high confidence. The signal is reliable at the top end for true positives, but confidence scoring alone will not fix precision. This is a category problem: the model is flagging the wrong things with high certainty, not hedging on the right things. Raising the threshold from 70% to 85% would capture all confirmed true positives (minimum TP confidence was 90%) while suppressing some marginal false alarms, but the primary fix is prompt scoping: restrict findings to the diff, suppress linting concerns, and require that every finding describe a concrete defect with verifiable runtime impact.

What would improve the numbers further: a structured output schema that forces the model to tag each finding by type (defect, style, out-of-diff) before the threshold filter is applied; a fine-tuning pass on the eval dataset to directly reward correct scoping; and expanding the eval suite to cover more repositories with different structural characteristics.

---

## Dashboard and Configuration

The self-serve dashboard is built in Next.js 15 with NextAuth v5 handling GitHub OAuth. It surfaces per-repository configuration: enable or disable the reviewer, select Junior or Senior mode, and set the confidence threshold.

Junior mode includes reasoning in each finding. Senior mode is concise and direct, without explanation. This is not a cosmetic distinction. A team onboarding a junior engineer benefits from findings that explain why something is a problem. A senior team shipping fast does not want to read justifications they already understand.

The confidence threshold matters differently at different team sizes. A small team with a high-trust review culture might set it at 80% and accept some noise in exchange for broader coverage. A larger team running Reviu across dozens of repositories needs higher precision per finding because the volume of comments scales with the number of active PRs. The threshold makes that tradeoff explicit and team-configurable rather than baked in.

---

## What's Next

Four concrete items in priority order.

First: fix the false positive rate through prompt changes before any other feature work. The eval analysis is specific about what to change and why. This is the highest-leverage single intervention available.

Second: review history and analytics. Every finding Reviu generates should be stored and queryable. Over time, patterns emerge: which engineers generate the most flagged bug types, which areas of a codebase accumulate recurring findings, whether the recall and precision numbers shift as the prompt improves. This data makes the tool worth running continuously, not just reviewing.

Third: monorepo support with subdirectory-level indexing. The current architecture indexes at the repository level. A monorepo with a frontend, backend, and shared utilities package benefits from indexes scoped to each subdirectory, with retrieval weighted by which subdirectory the diff touches. This is an architectural extension, not a redesign.

Fourth: fine-tuning on eval results. The labeled dataset from the eval run is a training signal. A fine-tuned model trained to correctly scope findings to the diff and flag the hard categories, guard inversions, silent omissions, would directly improve both recall and precision on the cases where the base model currently falls short.

---

## Built By

Oluwafisayo (fysaio), Lagos, Nigeria, building at 0xPermission Labs -- [github.com/fysaio](https://github.com/fysaio).