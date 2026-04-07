# Knowledge

Append-only register of project-specific rules, patterns, and lessons learned.

Read at the start of every unit. Append when you discover a recurring issue, a non-obvious pattern, or a rule that future agents should follow.

---

## Architecture rules — non-negotiable

See D019–D023. VidScope uses a strict hexagonal layered architecture. Import-linter enforces every rule mechanically via pytest.

**Layers (innermost → outermost):**

1. `vidscope.domain` — entities, value objects, typed errors. **Zero project imports. Zero third-party runtime deps** (stdlib + typing only). No SQLAlchemy, no Typer, no rich, no platformdirs.
2. `vidscope.ports` — Protocol interfaces only. Imports only `domain`.
3. `vidscope.adapters.*` — concrete implementations (sqlite, ytdlp, whisper, ffmpeg, heuristic, fs). Each adapter imports `domain` + `ports` only. **Adapters never import each other.**
4. `vidscope.pipeline` — stages and PipelineRunner. Imports `domain` + `ports`. **Never imports a concrete adapter.**
5. `vidscope.application` — use cases. Imports `domain` + `ports` + `pipeline`. Never touches I/O directly.
6. `vidscope.cli` (and future `vidscope.mcp`) — thin dispatch to use cases. Imports `application` + `domain` only.
7. `vidscope.infrastructure` — composition root. Builds the config, wires adapters to ports, instantiates use cases. **Only place allowed to import every layer.**

**Forbidden moves:**

- Importing `sqlalchemy`, `yt_dlp`, `faster_whisper`, `ffmpeg`, `typer`, `rich`, `pathlib.Path` inside `domain/` or `ports/`.
- Importing any `adapters.*` from `pipeline/`, `application/`, or `cli/`. Wiring happens exclusively in `infrastructure/container.py`.
- Catching bare `Exception` in a stage. Stages raise typed domain errors (`IngestError`, `TranscriptionError`, `FrameExtractionError`, `AnalysisError`, `IndexError`, `StorageError`).
- Writing to the filesystem directly from a stage. Use the `MediaStorage` port.
- Reading `os.environ` outside `infrastructure/config.py`. Config is injected, never sniffed ad-hoc.

**Idempotence contract:**

- Every stage implements `is_satisfied(context) -> bool` so re-running `vidscope add <url>` resumes from the last incomplete stage.
- `videos.platform_id` is `UNIQUE` — inserts use `INSERT ... ON CONFLICT DO NOTHING` semantics at the repository level.
- Every stage execution is bundled in a single transaction with its matching `pipeline_runs` row (same `Connection`, same `begin()`).

**Test layering:**

- `tests/unit/domain/` — no I/O, no SQLite, no filesystem. Pure-Python assertions. Target: < 100ms total.
- `tests/unit/adapters/<name>/` — targets one adapter against an in-memory or tmp_path fixture.
- `tests/integration/` — full pipeline with stub adapters wired in `infrastructure/container.py`.
- `tests/architecture/test_layering.py` — runs `import-linter` and fails the suite on any violation.

---

<!-- Append new entries below. -->

## LLM analyzer adapter pattern (M004)

When adding a new LLM provider:

1. **One file per provider** under `src/vidscope/adapters/llm/<name>.py`. Never put two providers in one file even if they share a vendor (e.g. don't put `openai` and `azure_openai` in the same file).
2. **Reuse the shared toolkit in `_base.py`**:
   - For OpenAI-compatible endpoints (anything that exposes `POST /chat/completions` with the OpenAI request schema), call `run_openai_compatible(client, base_url, api_key, model, transcript, provider_name, ...)` and return its result. Your file is ~50 lines: docstring + constructor + delegate.
   - For non-compatible providers (Anthropic native, Cohere, Bedrock), reuse `parse_llm_json`, `make_analysis`, `call_with_retry`, `LlmCallContext`, `build_messages` individually and write the request/response shape yourself.
3. **Constructor must validate `api_key` immediately** — empty/whitespace raises `AnalysisError(retryable=False)`. Misconfiguration must be caught at container build time, not at first call.
4. **Inject `httpx.Client | None` via constructor** so tests can pass `httpx.MockTransport`. Track ownership: when the caller injects, never close. When the adapter creates its own, close in `try/finally`.
5. **Registry factory** in `vidscope.infrastructure.analyzer_registry` reads env at invocation time (not module import time), wraps construction errors in `ConfigError` with an actionable signup URL, and is registered in `_FACTORIES` under the canonical provider name.
6. **Tests** under `tests/unit/adapters/llm/test_<name>.py` using `httpx.MockTransport`. Always cover: empty key, valid construction, happy path, 401 fail-fast, 429 retry, malformed response. The `_no_sleep` autouse fixture should monkeypatch `_base.time.sleep` so retry tests run in microseconds.
7. **Import-linter contract `llm-never-imports-other-adapters` is structural** — your new file is automatically subject to it. No changes needed to `.importlinter`.

The whole point of the architecture: adding a provider is `<name>.py` + factory + tests. Never touches the pipeline, the use cases, the CLI, or the MCP server.

## httpx + mcp are forbidden in domain/ports (M004)

The `domain-is-pure` and `ports-are-pure` import-linter contracts forbid `httpx` and `mcp` (in addition to the existing `sqlalchemy`, `typer`, `rich`, `platformdirs`, `yt_dlp`, `faster_whisper`). The innermost layers stay 100% stdlib + typing.

## Application layer cannot import infrastructure (M005)

The `application-has-no-adapters` import-linter contract forbids `vidscope.adapters.*`, `vidscope.cli`, AND `vidscope.infrastructure`. Application use cases must take simple primitives (Path, str, int) as constructor arguments, never `Config` or other infrastructure types. The composition root in `vidscope.infrastructure.container` is the only place that builds use cases with the resolved dependencies.

This was a pre-existing architectural hole closed during M005/S01 — every other application file happened to be clean by convention but the rule wasn't structurally enforced. The cookies use cases triggered the discovery and the contract is now permanent.

If you need to share a helper between application use cases (like the cookies validator), place it in `vidscope.application.<helper>` as a pure-Python module — never in `vidscope.infrastructure`.

## CLI sub-application pattern (M002, M003, M005)

VidScope has 3 Typer sub-applications: `mcp` (M002), `watch` (M003), `cookies` (M005). Each lives in `src/vidscope/cli/commands/<name>.py` and is registered via `app.add_typer(<name>_app, name="<name>")` in `src/vidscope/cli/app.py`. Each sub-application is its own `typer.Typer(...)` instance with `no_args_is_help=True` so users see the subcommand list when they forget the verb.

When adding a new sub-application:
1. Create the file with `<name>_app = typer.Typer(name="<name>", help="...", no_args_is_help=True)`
2. Decorate each subcommand with `@<name>_app.command("<verb>")`
3. Wrap CLI bodies in `with handle_domain_errors():` from `_support.py`
4. Use `acquire_container()` to get the wired container
5. Export from `commands/__init__.py`
6. Register in `app.py` via `add_typer`
7. Add a smoke test in `tests/unit/cli/test_app.py::test_help_lists_every_command`
8. Write CLI tests via `CliRunner` in `tests/unit/cli/test_<name>.py`

## Use Annotated[T, typer.Argument(...)] for non-str CLI defaults (M005)

Ruff's `B008` (function call in argument default) flags `def cmd(p: Path = typer.Argument(...))` because `Path` is the type annotation but `typer.Argument(...)` is a function call as the default value. The fix is the modern typer-recommended `Annotated` style:

```python
def cmd(
    p: Annotated[Path, typer.Argument(help="...")],
) -> None: ...
```

This works for both `Argument` and `Option`. The older `T = typer.X(...)` style is fine for `str` defaults (B008 doesn't flag it for some reason) but break for `Path`, `int`, `bool` defaults. Default to `Annotated` for any new CLI parameter.

## Don't use unicode glyphs in CLI output that goes to stdout (M005)

Rich's `console.print("[green]✓[/green]")` crashes on Windows with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'` when stdout is a pipe (not a TTY) because Windows defaults to cp1252 for non-TTY output. The verify scripts capture stdout via subprocess, so any unicode glyph in CLI output crashes the verify script on Windows.

**Rule**: use plain ASCII tags in CLI output: `[green]OK[/green]`, `[red]FAIL[/red]`. Save unicode glyphs (✓ ✗ → ←) for verify-mNNN.sh scripts that print directly to the terminal, not for source files in `src/vidscope/cli/`.

## Probe pattern for diagnostic operations (M005)

When you need a diagnostic operation that verifies an external service works without performing the full operation (e.g. "do my cookies authenticate?" vs "ingest a video"), follow the probe pattern:

1. Add a `probe(...)` method to the relevant port Protocol that **never raises** — every failure encoded in the returned result type
2. The result type is a frozen dataclass with a status enum + url + detail + optional payload
3. The status enum distinguishes the kinds of failures the caller cares about (`OK`, `AUTH_REQUIRED`, `NOT_FOUND`, `NETWORK_ERROR`, `UNSUPPORTED`, `ERROR`)
4. The application use case wraps the probe with context-aware interpretation (e.g. `cookies_configured × ProbeStatus → actionable message`)
5. The CLI command exits 0 only on `OK`, exits 1 on every other status so scripts can detect failures
6. Tests stub the port at the adapter level (e.g. `monkeypatch.setattr(YtdlpDownloader, "probe", fake_probe)`)

This pattern is used by `vidscope cookies test` (M005). It's reusable for any future diagnostic operation that needs a "dry run" against an external service.

