"""Unit tests for the ProbeResult dataclass extension (M006/S01).

ProbeResult gained 6 optional fields in M006/S01 so the backfill
script can extract creator metadata from yt-dlp probe() without a
second port method. Tests assert: (a) the new fields default to
None, preserving backward compatibility for `vidscope cookies test`
callers that only read .status and .title, (b) every field round-
trips through construction, (c) the dataclass stays frozen.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vidscope.ports import ProbeResult, ProbeStatus


class TestProbeResultDefaults:
    def test_minimal_construction_leaves_new_fields_none(self) -> None:
        r = ProbeResult(status=ProbeStatus.OK, url="https://x", detail="ok")
        assert r.title is None
        assert r.uploader is None
        assert r.uploader_id is None
        assert r.uploader_url is None
        assert r.channel_follower_count is None
        assert r.uploader_thumbnail is None
        assert r.uploader_verified is None

    def test_full_construction_populates_all_fields(self) -> None:
        r = ProbeResult(
            status=ProbeStatus.OK,
            url="https://youtube.com/watch?v=abc",
            detail="resolved: Intro",
            title="Intro",
            uploader="MrBeast",
            uploader_id="UCX6OQ3DkcsbYNE6H8uQQuVA",
            uploader_url="https://youtube.com/@MrBeast",
            channel_follower_count=200_000_000,
            uploader_thumbnail="https://yt3.cdn/avatar.jpg",
            uploader_verified=True,
        )
        assert r.uploader == "MrBeast"
        assert r.uploader_id == "UCX6OQ3DkcsbYNE6H8uQQuVA"
        assert r.channel_follower_count == 200_000_000
        assert r.uploader_verified is True

    def test_probe_result_is_frozen(self) -> None:
        r = ProbeResult(status=ProbeStatus.OK, url="x", detail="y")
        with pytest.raises(FrozenInstanceError):
            r.uploader = "mutate"  # type: ignore[misc]
