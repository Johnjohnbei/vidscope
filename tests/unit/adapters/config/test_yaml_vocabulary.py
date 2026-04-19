"""Tests for YamlVocabularySource.load_corrections()."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vidscope.adapters.config.yaml_vocabulary import YamlVocabularySource


class TestLoadCorrections:
    def test_returns_empty_when_file_absent(self, tmp_path: Path) -> None:
        src = YamlVocabularySource(tmp_path / "nope.yaml")
        assert src.load_corrections() == []

    def test_returns_corrections_from_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "vocabulary.yaml"
        f.write_text(
            yaml.dump({
                "corrections": [
                    {"wrong": "Cloud Code", "right": "Claude Code"},
                    {"wrong": "CloudCode", "right": "Claude Code"},
                ]
            }),
            encoding="utf-8",
        )
        result = YamlVocabularySource(f).load_corrections()
        assert ("Cloud Code", "Claude Code") in result
        assert ("CloudCode", "Claude Code") in result

    def test_skips_incomplete_entries(self, tmp_path: Path) -> None:
        f = tmp_path / "vocabulary.yaml"
        f.write_text(
            yaml.dump({
                "corrections": [
                    {"wrong": "Cloud Code", "right": "Claude Code"},
                    {"wrong": "orphan"},
                    {"right": "orphan"},
                    "not a dict",
                ]
            }),
            encoding="utf-8",
        )
        result = YamlVocabularySource(f).load_corrections()
        assert result == [("Cloud Code", "Claude Code")]

    def test_returns_empty_when_section_absent(self, tmp_path: Path) -> None:
        f = tmp_path / "vocabulary.yaml"
        f.write_text(yaml.dump({"brands": ["Claude Code"]}), encoding="utf-8")
        assert YamlVocabularySource(f).load_corrections() == []

    def test_returns_empty_on_malformed_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "vocabulary.yaml"
        f.write_text(":: bad yaml ::", encoding="utf-8")
        assert YamlVocabularySource(f).load_corrections() == []

    def test_corrections_do_not_bleed_into_prompt_terms(self, tmp_path: Path) -> None:
        f = tmp_path / "vocabulary.yaml"
        f.write_text(
            yaml.dump({
                "brands": ["Claude Code"],
                "corrections": [{"wrong": "Cloud Code", "right": "Claude Code"}],
            }),
            encoding="utf-8",
        )
        prompt = YamlVocabularySource(f).build_prompt()
        assert prompt is not None
        assert "wrong" not in prompt
        assert "right" not in prompt
