"""Architecture tests — import-linter layering contracts.

This test runs the full suite of contracts declared in ``.importlinter``
and fails the pytest run on any violation. It is the mechanical
enforcement of D019–D023: nobody can accidentally break the hexagonal
layering without getting a loud red test.

Two redundant paths are exercised so a regression in either one fails
loudly:

1. **CLI invocation.** Runs ``lint-imports`` as a subprocess and
   asserts exit code 0. This is the path a human runs on the command
   line, so it's the authoritative signal.

2. **Programmatic contract count.** Parses the CLI output to confirm
   every expected contract ran and was kept. This catches the case
   where import-linter silently skips a contract (e.g. a typo in the
   ``.importlinter`` file means the contract doesn't get registered).

The test is marked with the `architecture` marker so it can be run
in isolation via ``pytest -m architecture``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_CONTRACTS = (
    "Hexagonal layering - inward-only",
    "sqlite adapter does not import fs adapter",
    "fs adapter does not import sqlite adapter",
    "Domain is pure Python - no third-party runtime deps",
    "Ports are pure Python - no third-party runtime deps",
    "Pipeline layer depends only on ports and domain",
    "Application layer depends only on ports and domain",
    "MCP interface layer depends only on application and infrastructure",
    "config adapter does not import other adapters",
)


@pytest.mark.architecture
class TestLayering:
    def test_importlinter_file_exists(self) -> None:
        importlinter_file = REPO_ROOT / ".importlinter"
        assert importlinter_file.is_file(), (
            f".importlinter not found at {importlinter_file}. "
            "Every architecture contract depends on this file."
        )

    def test_lint_imports_exits_zero(self) -> None:
        """Run the ``lint-imports`` command and expect exit code 0.

        Uses ``shutil.which`` to locate the binary so this works inside
        both a uv-managed venv and a bare `pip install import-linter`.
        """
        binary = shutil.which("lint-imports")
        if binary is None:
            pytest.skip("lint-imports binary not on PATH")

        result = subprocess.run(
            [binary],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, (
            f"import-linter failed with exit {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_every_expected_contract_is_kept(self) -> None:
        """Parse the lint-imports output and assert every expected
        contract name appears with a KEPT verdict."""
        binary = shutil.which("lint-imports")
        if binary is None:
            pytest.skip("lint-imports binary not on PATH")

        result = subprocess.run(
            [binary],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0

        for contract in EXPECTED_CONTRACTS:
            assert contract in result.stdout, (
                f"Expected contract not found in import-linter output: "
                f"{contract!r}"
            )
            # The line format is: "<name> KEPT" or "<name> BROKEN".
            lines_mentioning = [
                line for line in result.stdout.splitlines() if contract in line
            ]
            assert any("KEPT" in line for line in lines_mentioning), (
                f"Contract {contract!r} is not KEPT. "
                f"Matching lines: {lines_mentioning}"
            )
