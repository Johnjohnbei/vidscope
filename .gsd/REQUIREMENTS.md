# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

Guidelines:
- Keep requirements capability-oriented, not a giant feature wishlist.
- Requirements should be atomic, testable, and stated in plain language.
- Every **Active** requirement should be mapped to a slice, deferred, blocked with reason, or moved out of scope.
- Each requirement should have one accountable primary owner and may have supporting slices.
- Research may suggest requirements, but research does not silently make them binding.
- Validation means the requirement was actually proven by completed work and verification, not just discussed.

## Active

### R001 — Download videos from Instagram, TikTok and YouTube by URL
- Class: core-capability
- Status: active
- Description: Given a public video URL from Instagram (Reel or post), TikTok, or YouTube (video or Short), the tool downloads the media file to a local cache and records the canonical metadata (platform, author, title, duration, upload date, view count when available).
- Why it matters: Without reliable ingestion, no other capability works. This is the riskiest brick because yt-dlp occasionally breaks when platforms change, and Instagram is the most fragile of the three.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Cookies-based auth for private or story content is deferred to M005.

### R002 — Transcribe the audio track of downloaded videos into text
- Class: core-capability
- Status: active
- Description: For every ingested video, produce a full-text transcript and timestamped segments in the video's spoken language. Must handle at least French and English reliably on CPU.
- Why it matters: The transcript is what makes videos searchable and analyzable without watching them. It is the atomic unit the rest of the pipeline consumes.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: unmapped
- Notes: Model and backend are implementation details; faster-whisper on CPU is the baseline.

### R003 — Extract representative frames from downloaded videos
- Class: core-capability
- Status: active
- Description: Produce a small set of frames per video (keyframes plus a fixed-rate sample) stored as images on disk with their timestamps recorded in the DB, so a multimodal agent or a human can inspect the visual content without loading the full video.
- Why it matters: The transcript captures audio but not visuals. Frames are the cheap substitute for "watching" the video that keeps the system multimodal-ready.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: none
- Validation: unmapped
- Notes: Sampling strategy is a tunable parameter; the default is ~1 frame per 5 seconds plus all keyframes, capped at 30 frames per video.

### R004 — Produce a qualitative analysis of every ingested video
- Class: core-capability
- Status: active
- Description: For every video, produce a structured analysis record containing at least: detected language, top keywords, dominant topics, a relevance/quality score (0–100), and a short summary. The analysis must be producible with zero paid API calls using only local heuristics on the transcript.
- Why it matters: Raw transcripts don't scale — the user needs a digestible signal per video. Keeping the default analyzer heuristic-only guarantees the system stays usable at zero cost.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Richer LLM-backed analyzers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic) are a pluggable extension deferred to M004.

### R005 — Persist all pipeline output in a queryable local database
- Class: core-capability
- Status: active
- Description: Videos, metadata, transcripts, frames, analyses, and pipeline run records must live in a single SQLite database with a schema versioned by migrations. Every row must be addressable by a stable ID and linked to its parent video.
- Why it matters: A pipeline without persistent output is just a pile of temp files. The DB is the durable surface the CLI and the future MCP server both read from.
- Source: inferred
- Primary owning slice: M001/S01
- Supporting slices: M001/S02, M001/S03, M001/S04, M001/S05, M001/S06
- Validation: unmapped
- Notes: The data layer is accessed through a repository abstraction so a future move to Postgres + pgvector touches one module only.

### R006 — Full-text search across stored transcripts and analyses
- Class: core-capability
- Status: active
- Description: `vidscope search "<query>"` returns ranked matches from transcripts, titles, and analysis summaries using SQLite FTS5.
- Why it matters: Search is the primary retrieval surface before the MCP layer ships. Without it, the DB is write-only.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S01
- Validation: unmapped
- Notes: Semantic search via embeddings is deferred — FTS5 is sufficient for v1.

### R007 — Single-command end-to-end ingestion from a URL
- Class: primary-user-loop
- Status: active
- Description: `vidscope add <url>` performs ingest → transcribe → frames → analyze → index in one invocation and reports a structured summary on exit. Failures at any stage are surfaced with enough context to diagnose (which stage, what error, what was persisted before the failure).
- Why it matters: This is the single command that justifies the project's existence. Every other CLI command is a support surface around this one loop.
- Source: user
- Primary owning slice: M001/S06
- Supporting slices: M001/S02, M001/S03, M001/S04, M001/S05
- Validation: unmapped
- Notes: Partial success must leave the DB in a consistent state — no half-written rows.

### R008 — Inspect the state and history of pipeline runs
- Class: failure-visibility
- Status: active
- Description: `vidscope status` and `vidscope show <id>` surface the current state of the pipeline: last N runs, their stage outcomes, any persistent errors, and the full record of a given video including transcript, frames list, and analysis. Errors are recoverable — re-running `add` on a video that previously failed resumes from the last successful stage.
- Why it matters: When something breaks at 3am or after a yt-dlp upstream change, the tool must tell the operator what it did, where it stopped, and why — without requiring a log dive or a manual DB inspection.
- Source: inferred
- Primary owning slice: M001/S06
- Supporting slices: M001/S01
- Validation: unmapped
- Notes: Structured run records are written by every stage from S01 onwards.

### R009 — Cross-platform local installation and execution
- Class: operability
- Status: active
- Description: The tool installs and runs on Windows (current dev machine), macOS, and Linux with a single command (`uv tool install` or `pipx install`). System dependencies (`ffmpeg`, `yt-dlp` binary when not bundled) are documented and checked at startup with an actionable error when missing.
- Why it matters: This is a personal tool but cross-platform discipline prevents Windows-specific shortcuts that would bite later.
- Source: inferred
- Primary owning slice: M001/S01
- Supporting slices: M001/S02
- Validation: unmapped
- Notes: Python 3.12+ is the minimum because of typing features and stdlib improvements used throughout.

### R010 — Pluggable analyzer providers for qualitative analysis
- Class: quality-attribute
- Status: active
- Description: The analyzer is a provider interface with at least two implementations wired in M001 (heuristics, and a stub for a future LLM backend) so that adding NVIDIA, Groq, OpenRouter, OpenAI, or Anthropic later requires only implementing the interface and registering the provider — not changing any caller.
- Why it matters: The user explicitly wants to stay cost-free by default but keep the door open for richer analysis via free-tier LLM APIs (NVIDIA Build, Groq, Cerebras) or paid APIs on demand. This requirement is about the seam, not the implementations.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: none
- Validation: unmapped
- Notes: Concrete non-heuristic providers ship in M004.

## Validated

<!-- Requirements move here as slices complete and prove them. -->

## Deferred

### R020 — MCP server exposing ingestion, search and suggestions to an AI agent
- Class: integration
- Status: deferred
- Description: A Python MCP server exposes at least `vidscope_ingest`, `vidscope_search`, `vidscope_get_video`, `vidscope_suggest_related`, and `vidscope_watch_list` so an AI agent can drive the library in conversation and propose related videos to enrich a topic.
- Why it matters: This is the other half of the user-facing value: being able to hand an agent a URL and have it both ingest and suggest adjacent content. It's deferred only to keep M001 focused on the pipeline itself.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M002, immediately after M001 lands.

### R021 — Public-account monitoring for influencer watchlists
- Class: primary-user-loop
- Status: deferred
- Description: Declare a public Instagram / TikTok / YouTube account as "watched"; on demand (`vidscope watch refresh`) or via cron, the tool detects new videos from watched accounts and pushes them through the ingestion pipeline automatically.
- Why it matters: The user wants a veille loop that keeps a library fresh without manual URL-by-URL work. Deferred to keep M001 scoped to single-URL ingestion.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M003. Requires a stable ingestion loop from M001 and a job-queue pattern in SQLite.

### R022 — Scheduled/daemon execution for autonomous refresh
- Class: operability
- Status: deferred
- Description: Provide a documented way to run the refresh loop on a schedule (cron on Linux/macOS, Task Scheduler on Windows) and a long-lived daemon mode with health surface.
- Why it matters: Turns VidScope from "a tool I invoke" into "a service that keeps my library fresh". Deferred until monitoring itself works.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M003 or later. Manual refresh is the baseline; scheduled refresh must reuse the same code path.

### R023 — Related-video suggestion from existing library
- Class: differentiator
- Status: deferred
- Description: Given a video ID or a freshly ingested URL, propose N related videos already in the library and optionally N external URLs worth ingesting, using topic overlap, creator overlap, and transcript similarity.
- Why it matters: This is what turns a passive archive into an active research tool. It's only useful once the library has enough content, so it ships after M001.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M002. First version uses keyword overlap from the heuristic analyzer; semantic embeddings come later.

### R024 — Richer LLM-backed analyzer providers (NVIDIA, Groq, OpenRouter, OpenAI, Anthropic)
- Class: quality-attribute
- Status: deferred
- Description: Concrete implementations of the analyzer provider interface for NVIDIA Build, Groq, OpenRouter, OpenAI, and Anthropic, with rate-limit handling, retry, and cost-aware invocation (never run automatically unless explicitly enabled).
- Why it matters: Heuristics cover the baseline; LLM providers are the upgrade path for videos the user specifically flags. Deferred so the default stays zero-cost.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M004. The interface itself (R010) ships in M001.

### R025 — Cookie-based ingestion for private or gated content
- Class: core-capability
- Status: deferred
- Description: Support an exported browser cookie file (cookies.txt) so yt-dlp can fetch Instagram stories, age-gated YouTube videos, and private posts the user has access to.
- Why it matters: Expands coverage beyond public content. Deferred because public content is the 80% case and cookie handling has its own friction.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Target milestone is M005.

### R026 — Semantic search via local embeddings
- Class: quality-attribute
- Status: deferred
- Description: In addition to FTS5, store embeddings per transcript and offer `vidscope search --semantic` that uses cosine similarity over a local embedding model (sentence-transformers or equivalent).
- Why it matters: Makes "find videos about X" work even when X is not a literal keyword in the transcript. Deferred because FTS5 is enough for v1.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Implied by user's note on scalability. Lands alongside a potential Postgres + pgvector migration.

## Out of Scope

### R030 — Re-uploading or re-publishing downloaded content
- Class: anti-feature
- Status: out-of-scope
- Description: VidScope does not republish, repost, or redistribute any ingested media. Downloaded files stay on the local machine for personal analysis only.
- Why it matters: Prevents scope creep into content-generation territory and keeps the tool aligned with its veille purpose.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The `data/` folder is gitignored and the tool never uploads anywhere.

### R031 — Video editing, cutting, or post-production
- Class: anti-feature
- Status: out-of-scope
- Description: VidScope does not cut, edit, re-encode beyond what is needed for frame extraction, or produce new video files from ingested content.
- Why it matters: ffmpeg can do all of this but it's a different product. VidScope is a reader, not an editor.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Frame extraction is the only ffmpeg operation in scope.

### R032 — Hosting a web UI or multi-user service
- Class: constraint
- Status: out-of-scope
- Description: VidScope is a single-user local tool. No web UI, no authentication layer, no multi-tenant considerations, no cloud deployment target.
- Why it matters: Keeps the surface small and the architecture honest — no spurious HTTP layers, no accidentally-public data.
- Source: inferred
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: The MCP server in M002 is a local stdio integration, not an HTTP service.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M001/S02 | none | unmapped |
| R002 | core-capability | active | M001/S03 | none | unmapped |
| R003 | core-capability | active | M001/S04 | none | unmapped |
| R004 | core-capability | active | M001/S05 | none | unmapped |
| R005 | core-capability | active | M001/S01 | M001/S02, S03, S04, S05, S06 | unmapped |
| R006 | core-capability | active | M001/S06 | M001/S01 | unmapped |
| R007 | primary-user-loop | active | M001/S06 | M001/S02, S03, S04, S05 | unmapped |
| R008 | failure-visibility | active | M001/S06 | M001/S01 | unmapped |
| R009 | operability | active | M001/S01 | M001/S02 | unmapped |
| R010 | quality-attribute | active | M001/S05 | none | unmapped |
| R020 | integration | deferred | none | none | unmapped |
| R021 | primary-user-loop | deferred | none | none | unmapped |
| R022 | operability | deferred | none | none | unmapped |
| R023 | differentiator | deferred | none | none | unmapped |
| R024 | quality-attribute | deferred | none | none | unmapped |
| R025 | core-capability | deferred | none | none | unmapped |
| R026 | quality-attribute | deferred | none | none | unmapped |
| R030 | anti-feature | out-of-scope | none | none | n/a |
| R031 | anti-feature | out-of-scope | none | none | n/a |
| R032 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 10
- Mapped to slices: 10
- Validated: 0
- Unmapped active requirements: 0
