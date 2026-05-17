# CLAUDE.md — VidScope (repo Python)

> Instructions agent codebase-specific. Compagnon de `README.md` (user-facing) et de [[~/Documents/Atelier/projets/vidscope/CLAUDE.md]] (vault Atelier, voir aussi conventions méthodologiques).

## Project

**VidScope** : outil personnel d'intelligence vidéo Python — télécharge, transcrit, analyse et indexe des vidéos publiques Instagram / TikTok / YouTube **en local** depuis la CLI ou un MCP server.

- Local-first par design (pas de cloud, pas d'API paid par défaut)
- CLI Typer + MCP server (stdio local pour AI agents)
- Hexagonal architecture stricte enforcée par 11 import-linter contracts
- 1292 unit tests + 84 source files mypy strict-clean
- 11 milestones complétés (M001-M011), status Alpha

Vision projet + architecture cross-repo : `~/Documents/Atelier/projets/vidscope/vidscope.md`.

## Technology Stack

### Languages
- Python 3.12+ (3.13 supporté)

### Package manager
- **uv** (Astral) — lockfile `uv.lock`, sync via `uv sync`, run via `uv run <cmd>`. **NE PAS** utiliser `pip install` direct.

### Frameworks & libs core
- **Typer** — CLI declarative (`vidscope.cli.app`)
- **SQLAlchemy 2.x** — Core/ORM pour SQLite + FTS5
- **faster-whisper** ≥1.2 — transcription CPU int8 quantization
- **yt-dlp** ≥2026.3 — downloader Instagram/TikTok/YouTube
- **httpx** — HTTP client pour LLM adapters
- **mcp** ≥1.27 — Model Context Protocol SDK official Python
- **platformdirs** — paths cross-platform (cache, data, config)
- **pyyaml** — config parsing
- **rich** ≥14 — TUI output
- **instaloader** — fallback Instagram downloader

### Optional extras
- **vision** : rapidocr-onnxruntime + opencv-python-headless (OCR sur frames)
- **auth** : playwright (cookies extraction via browser automation)

### Dev tools
- **ruff** ≥0.15 — lint (style + bugs)
- **mypy** ≥1.20 — type check strict
- **pytest** ≥9.0 — test runner + hypothesis property-based
- **pytest-cov** — coverage
- **import-linter** ≥2.11 — 11 architecture contracts

### Runtime requirements
- Python 3.12+ sur PATH
- `ffmpeg` sur PATH (Windows: `winget install Gyan.FFmpeg`, macOS: `brew install ffmpeg`, Linux: `apt install ffmpeg`)
- Optional: cookies Instagram via `vidscope cookies set <path>` (requirement depuis 2026-04 pour Reels)

## Conventions

### Architecture hexagonal (CRITICAL)

11 import-linter contracts enforcés. Layers innermost-first :

```
domain         ← zero project imports, stdlib + typing only
ports          ← imports domain
adapters/*     ← concrete implementations, NEVER import each other
pipeline       ← imports domain + ports, NEVER imports concrete adapter
application    ← imports domain + ports + pipeline, NEVER touches I/O
cli + mcp      ← thin dispatch vers application
infrastructure ← composition root, wires adapters → ports, builds config
```

**Si tu touches au code** :
- Si tu ajoutes un adapter : 1 fichier `src/vidscope/adapters/<name>/__init__.py` + 1 factory dans `infrastructure/composition.py` + 1 test file `tests/unit/adapters/test_<name>.py`. **NE JAMAIS** importer un autre adapter depuis ton adapter.
- Si tu ajoutes un use case : `src/vidscope/application/<usecase>.py` qui dépend uniquement de `domain` + `ports` + `pipeline`. Aucun appel I/O direct.
- Si tu ajoutes un domain object : `src/vidscope/domain/<name>.py` avec stdlib + typing only. Pas d'`httpx`, pas de `sqlalchemy`, pas de `yt-dlp`.
- Si tu touches `pipeline/` : tu peux importer ports mais pas adapter concret. Le `PipelineRunner` reçoit les ports en constructor injection.

### Naming patterns

- **snake_case** pour modules, fonctions, variables (Python convention)
- **PascalCase** pour classes (entities, value objects, exceptions, adapters)
- **UPPER_CASE** pour constantes module-level (ex: `DEFAULT_ANALYZER = "heuristic"`)
- **Préfixes** : `_private_helper()` pour internal, `__double_underscore` jamais (Python name mangling rare cases only)
- **Tests** : `test_<feature>.py` dans `tests/unit/` ou `tests/integration/`. Functions `def test_<scenario>():`
- **Adapters dirs** : `src/vidscope/adapters/<name>/` (singular, kebab-case OR snake_case — dans VidScope c'est snake_case : `sqlite`, `ytdlp`, `ffmpeg`, `whisper`, `heuristic`, `llm`, `fs`, `export`, `text`, `vision`, `auth`, `config`, `instaloader`)

### Code style (ruff config dans pyproject)

- Line length **100**
- Target py312
- Select : `E/W/F/I/UP/B/SIM/RUF/TCH/PL`
- Ignore : `PLR0913/0912/0915` (too many args/branches/statements — on fait confiance au jugement), `PLR2004` (magic values OK dans tests/CLI), `TC001-003` (TYPE_CHECKING optionnel), `PLW0603` (global pour config singleton documenté), `S603` (slice IDs false-positive), `RUF001/002` (typographic apostrophes français)

### mypy strict (zéro tolérance)

```toml
strict = true
warn_unused_ignores = true
warn_return_any = true
warn_redundant_casts = true
no_implicit_optional = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_decorators = true
```

Si mypy fail → fix les types, n'ajoute PAS `# type: ignore` sans raison documentée.

Modules sans stubs : `yt_dlp`, `faster_whisper`, `mcp.*` — fall back à `ignore_missing_imports` dans `[[tool.mypy.overrides]]`. Si tu ajoutes un nouveau wrapper sans stubs, étends cette liste.

### Tests conventions

- **Sandbox via `tmp_path`** — chaque test reçoit son propre `tmp_path` fixture pytest, jamais polluer le filesystem global.
- **Markers** : `unit` / `integration` / `architecture` / `slow`. Default : exclude `integration` (pas de network real par défaut).
- **TDD when applicable** : write failing test, implement minimal, refactor.
- **Fixtures** : factor dans `conftest.py` per dir. Pas de globaux complexes.

### Cookies & secrets

- **Cookies** : traités comme credentials. `cookies.txt`, `*.cookies` gitignored. **NE JAMAIS** commit. **NE JAMAIS** logger le contenu.
- **API keys LLM** : env vars `VIDSCOPE_<PROVIDER>_API_KEY`. Pas d'hardcoded.
- **No telemetry** : zéro outbound call sauf opt-in user (download via yt-dlp, LLM analyzer si chosen). Si tu ajoutes une feature qui ferait un HTTP call sans opt-in → décision Atelier obligatoire.

## Quality gates (avant tout commit)

```bash
python -m uv run ruff check .                # lint
python -m uv run mypy src                    # type check strict
python -m uv run pytest -q                   # 1292 unit tests
python -m uv run lint-imports                # 11 architecture contracts
```

Plus per-milestone verify scripts (stub network) :

```bash
bash scripts/verify-m001.sh    # pipeline end-to-end (9 steps)
bash scripts/verify-m002.sh    # MCP + suggest_related (10 steps)
bash scripts/verify-m003.sh    # watchlist + refresh (9 steps)
bash scripts/verify-m004.sh    # 5 LLM analyzers stub HTTP (9 steps)
bash scripts/verify-m005.sh    # cookies UX stub yt_dlp (10 steps)
bash scripts/verify-m011.sh    # review, tags, collections, export (10 steps)
```

Tous exit 0 en mode stub. Live validation manuel documenté dans chaque milestone UAT (`.gsd/`).

## Anti-features (out of scope — NE PAS ajouter)

- ❌ **Republish / redistribute** ingested media (R030) — downloads stay local
- ❌ **Edit / re-encode video** beyond ffmpeg frame extraction (R031) — VidScope est reader, pas editor
- ❌ **Multi-tenant or web UI** (R032) — single-user local tool, MCP stdio only

Si tu vois une feature request qui touche un de ces 3 anti-features → décliner avec ref R0XX.

## Cross-projet (downstream consumers)

VidScope est consommé par 2 wrappers cross-repo :

1. **`Coeurdar/products/vidscope/`** (UI front React) — appelle backend Render, pas de re-impl moteur
2. **`Arkanes/render-ai-server/services/vidscope/`** (backend Express Render) — 11 fichiers TS wrap pipeline

**Impact breaking changes** :
- Changes dans `domain` / `ports` / `pipeline.runner` peuvent casser les 2 wrappers
- Nouvelle command CLI (`vidscope <new>`) ne propage pas auto vers wrappers
- Coordination via décision globale `~/Documents/Atelier/decisions-globales/2026-05-16-coeurdar-arkanes-vidscope-coupling.md`

**Périmètre éditable depuis ce repo** : tout `src/vidscope/`, `tests/`, `docs/`, `scripts/`, `pyproject.toml`, `.importlinter`. **NE PAS** toucher aux fichiers wrappers (côté Coeurdar/Arkanes) sans aller dans leur repo respectif.

## Atelier vault (méthodologie)

Vault : `~/Documents/Atelier/projets/vidscope/` (créé 2026-05-17 PM, baseline Karpathy complet).

- **`vidscope.md`** : vision projet (pitch, pipeline, architecture, audience)
- **`CLAUDE.md` vault** : conventions Python + hexagonal + cross-refs (= ce fichier mais perspective méthodologie)
- **`wiki/decisions/`** : décisions arch à créer au fur et à mesure
- **`wiki/concepts/`** : concepts (hexagonal-architecture, 5-stage-pipeline, etc.)
- **`wiki/audits/`** : audits VidScope
- **`wiki/entities/`** : adapters / ports / tables / commands / providers
- **`wiki/indexes/`** : 5 indexes Karpathy

## Cross-références importantes

- `~/.claude/CLAUDE.md` — méthode globale + checklist pré-push
- `~/Documents/Atelier/CLAUDE.md` — compilation rules globales vault
- `~/Documents/Atelier/decisions-globales/2026-05-17-cascade-docs-pattern.md` — pattern cascade docs (section « Architecture VidScope » décrit 3 surfaces)
- `~/Documents/Atelier/decisions-globales/2026-05-16-coeurdar-arkanes-vidscope-coupling.md` — coupling cross-projet
- `~/Documents/Atelier/projets/coeurdar/wiki/audits/2026-05-16-vidscope-audit-360-findings.md` — audit baseline 14 gaps
- `~/Documents/Atelier/projets/coeurdar/wiki/decisions/2026-05-16-vidscope-tier-critical-applied.md` — Tier Critical shippé
- `~/Documents/GitHub/Arkanes/render-ai-server/OWNERS.md` — périmètre fichiers Coeurdar vs Arkanes côté backend
- `~/.claude/projects/C--Users-joaud-Documents-GitHub-vidscope/memory/MEMORY.md` — memory Claude (auto-loaded)

## User context

- **joaudran@gmail.com** (Mighty John) — sole maintainer
- **Autonomy : MAXIMUM** — jamais demander confirmation
- Français pour conversations, English pour code/docs (codebase international)
- VidScope = side project veille + offering MCP pour AI agents

## Conventions session

- **Avant tout refactor** : run `python -m uv run lint-imports` pour comprendre les contracts actuels + `graphify query "..."` si index VidScope rebuilt
- **Décisions arch → vault `wiki/decisions/`** avec frontmatter `type: decision`. Si une décision touche les contracts import-linter, documente le diff.
- **Toute breaking change dans domain/ports/pipeline.runner** → tag dans le commit + alert dans le PR (impact cross-repo).
- **Tests new feature** : 1 unit test minimum + scenario integration si pipeline traversé.
- **Docs user-facing** (`docs/*.md`) : update si command CLI changes ou MCP tool added.
