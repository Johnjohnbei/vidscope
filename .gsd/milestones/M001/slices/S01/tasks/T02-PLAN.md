---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: Created the src/vidscope/ package and a frozen-dataclass Config module with platformdirs-based path resolution and an env override.

Create the src/vidscope/ package with __init__.py (exports __version__), a config.py module that resolves: data_dir (default: platform-appropriate app data — %LOCALAPPDATA%/vidscope on Windows, ~/.local/share/vidscope on Linux/macOS via platformdirs), cache_dir (default: data_dir/cache), db_path (default: data_dir/vidscope.db), whisper model cache dir, downloads dir, frames dir. All paths overridable via VIDSCOPE_DATA_DIR env var. Config is a frozen dataclass with a module-level `get_config()` that memoizes. Create the directory tree on first access. Add platformdirs to runtime deps if not already there.

## Inputs

- ``pyproject.toml` — updated with platformdirs dep`

## Expected Output

- ``src/vidscope/__init__.py` — exports __version__`
- ``src/vidscope/config.py` — frozen dataclass Config + get_config() with env override and path creation`
- ``pyproject.toml` — platformdirs added to [project.dependencies]`

## Verification

uv run python -c "from vidscope.config import get_config; c = get_config(); assert c.db_path.parent.exists(); print(c.data_dir)"
