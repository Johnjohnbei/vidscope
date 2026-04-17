# M007 — Rich content metadata (descriptions, links, hashtags, mentions, music)

## Vision
The current schema captures title/duration/view_count and nothing else from the platform payload. yt-dlp returns a large `info_dict` with description, hashtags, mentions, music track/artist, location, language hint, and raw URLs — all discarded today. M007 promotes this payload to first-class side tables so the user can query *"all videos mentioning @X"*, *"all videos with a link in the caption"*, *"all videos using sound Y"*. Link extraction also runs on the transcript so spoken URLs surface too. This is **the biggest qualitative data win** per hour invested: zero new deps, zero new ML.

## Slice Overview

| ID | Slice | Risk | Depends | Done when |
|----|-------|------|---------|-----------|
| S01 | Domain + storage for captions, hashtags, mentions, music | low | M006/S01 | `VideoMetadata`, `Hashtag`, `Mention`, `MusicTrack` entities; ports; SQLite adapter; migration 004_metadata; `videos.description` captured verbatim; hashtags/mentions/music in side tables with FK. |
| S02 | LinkExtractor port + regex adapter + link persistence | medium | S01 | `Link` entity, `LinkExtractor` Protocol, `RegexLinkExtractor` adapter, `links` table with `(video_id, url, normalized_url, source, position_ms)`, HEAD-resolver for short URLs (optional flag). |
| S03 | Pipeline wiring + ingest/transcribe stages capture metadata & extract links | medium | S02 | `IngestStage` persists description+hashtags+mentions+music, new `MetadataExtractStage` runs link extraction on (description, transcript) after TranscribeStage, resume-safe via `is_satisfied`. |
| S04 | CLI facets + MCP tool | low | S03 | `vidscope search` accepts `--hashtag`, `--mention`, `--has-link`, `--music-track`; `vidscope links <id>` lists extracted URLs; `vidscope show <id>` displays description + hashtags + music; MCP tool `vidscope_list_links`. |

## Layer Architecture

| Slice | Layer | New/Changed files |
|-------|-------|-------------------|
| S01 | domain | `entities.py` (+VideoMetadata, Hashtag, Mention, MusicTrack), `values.py` (+Hashtag, Handle) |
| S01 | ports | `video_metadata_repository.py`, `hashtag_repository.py`, `mention_repository.py`, `music_track_repository.py` |
| S01 | adapters/sqlite | `*_repository.py`, `migrations/004_metadata.py`, `schema.py` (+4 tables) |
| S02 | domain | `entities.py` (+Link) |
| S02 | ports | `link_extractor.py` (Protocol), `link_repository.py` |
| S02 | adapters/text | **new submodule** `adapters/text/regex_link_extractor.py`, `adapters/text/url_normalizer.py` |
| S02 | adapters/sqlite | `link_repository.py`, `migrations/005_links.py` |
| S03 | ports | `downloader.py` (DownloadResult +description, +hashtags, +mentions, +music) |
| S03 | adapters/ytdlp | `ytdlp_downloader.py` (extract from info_dict) |
| S03 | pipeline | `ingest_stage.py` (persist metadata), `metadata_extract_stage.py` **new**, `runner.py` (+new stage in default graph) |
| S03 | application | `use_cases/add_video.py` (wire new stage) |
| S04 | application | `use_cases/list_links.py`, `use_cases/search_videos.py` (extend with facets) |
| S04 | cli | `main.py` (search facets), `links.py` **new**, `videos.py` (show enriched) |
| S04 | mcp | `tools/links.py`, `tools/search.py` (facets) |

## Test Strategy

| Test kind | Scope | Tooling |
|-----------|-------|---------|
| Domain unit | Entity invariants (Hashtag canonicalisation to lowercase, URL normalisation idempotence) | pytest |
| Regex extractor unit | 30+ fixture strings: plain URL, URL with tracking params, markdown URL, link-in-bio, t.co/bit.ly, IDN, trailing punctuation, false positives ("hello.world") | pytest |
| URL normalizer unit | strip fragments, sort query params, lowercase host, strip `utm_*`, preserve path case | pytest |
| Adapter unit | Each new SqlXxxRepository (CRUD, FK cascade, UNIQUE where applicable) | pytest + tmp SQLite |
| Pipeline integration | IngestStage + MetadataExtractStage with stubbed Downloader, verify end-to-end persistence of description+hashtags+links | pytest + in-memory container |
| Application unit | list_links, search_videos with facets | pytest + InMemory repos |
| CLI snapshot | `vidscope search --hashtag foo`, `vidscope links <id>`, `vidscope show <id>` enriched rendering | pytest + CliRunner |
| MCP subprocess | JSON-RPC call to `vidscope_list_links` returns expected shape | existing subprocess harness |
| Architecture | 9 contracts green + new contract `text-adapter-is-self-contained` | lint-imports |
| E2E live | `verify-m007.sh`: `vidscope add <TikTok with caption + music>` → assert hashtags/mentions/music/links persisted, `vidscope search --hashtag <tag>` returns the video | bash + real network |

### Regex corpus (to guarantee extractor quality)
S02 ships `tests/fixtures/link_corpus.json` with ≥ 100 strings (50 positive, 30 negative, 20 edge). Failing regression = broken build. This is the non-negotiable quality gate for link extraction.

## Requirements Mapping

- Closes R043 (caption+hashtags+mentions), R044 (link extraction), R045 (music track), R046 (search facets + `vidscope links`).
- Unblocks: M008 (OCR feeds same LinkExtractor), M011 (search facets).

## Out of Scope (explicit)

- No URL deduplication across videos (same link appearing in 50 videos remains 50 rows — a table of unique domains is cheap to derive later).
- No link-preview/metadata fetching (no HTML scraping, no OpenGraph) — a URL is stored raw + normalized only.
- No music-fingerprinting — we trust yt-dlp's `track`/`artist` fields; when they're null, we store null.
