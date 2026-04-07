# VidScope

> Veille vidéo multi-sources : télécharge, transcrit, analyse et indexe des vidéos Instagram / TikTok / YouTube en local.

VidScope est un outil personnel de veille vidéo qui combine `yt-dlp`, `faster-whisper` et `ffmpeg` pour produire une base locale searchable de transcripts, frames et analyses qualitatives. Il expose à la fois une CLI et un serveur MCP pour être utilisé en conversation avec un agent IA.

## Statut

🚧 En cours de développement — M001 : Pipeline ponctuel end-to-end.

## Vision

Trois modes d'usage :

1. **Ponctuel** — `vidscope add <url>` télécharge, transcrit et analyse une vidéo à la demande.
2. **Surveillance** — déclare des comptes d'influenceurs, scrape leurs nouvelles publications en batch.
3. **Découverte** — via le wrapper MCP, un agent IA peut proposer des vidéos connexes pour enrichir la recherche.

## Principes

- **100% local par défaut** : yt-dlp + faster-whisper + ffmpeg. Pas de dépendance API payante en phase initiale.
- **Providers pluggables pour l'analyse** : heuristiques locales par défaut, backends gratuits (NVIDIA, Groq, OpenRouter) ou payants (OpenAI, Anthropic) activables via variable d'environnement.
- **Scalable par construction** : SQLite + FTS5 pour la v1, abstraction data layer pour migration vers Postgres + pgvector plus tard.
- **Découplé** : chaque étape du pipeline (ingest, transcribe, frames, analyze) est une brique indépendante orchestrable en manuel, en cron ou en démon.

## Stack

- **Langage** : Python 3.12+
- **Package manager** : uv
- **CLI** : Typer
- **DB** : SQLite + FTS5 (via SQLAlchemy)
- **Téléchargement** : yt-dlp
- **Transcription** : faster-whisper
- **Extraction frames** : ffmpeg
- **MCP** : mcp SDK officiel Python

## Plateformes supportées (v1)

- Instagram (Reels, posts publics)
- TikTok
- YouTube (vidéos et Shorts)

## Installation

À venir.

## Licence

MIT — voir [LICENSE](LICENSE).
