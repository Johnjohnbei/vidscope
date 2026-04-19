"""Backfill creator_id for videos ingested before M006 (R042).

Usage:
    python scripts/backfill_creators.py [--apply] [--limit N] [--help]

Dry-run by default. Pass --apply to mutate the database.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sqlalchemy import text

from vidscope.domain.entities import Creator
from vidscope.domain.values import Platform, PlatformUserId, VideoId
from vidscope.ports.pipeline import ProbeStatus


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill creator_id for pre-M006 videos."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to the database (default: dry-run).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N unlinked videos.",
    )
    return parser.parse_args(argv)


def _fetch_unlinked(conn: Any, limit: int | None) -> list[tuple[int, str, str, str | None]]:
    """Return (id, platform, url, author) rows where creator_id IS NULL.

    Uses the raw connection because VideoRepository has no public
    'list without creator_id' query — acceptable in a backfill script.
    """
    q = "SELECT id, platform, url, author FROM videos WHERE creator_id IS NULL"
    if limit is not None:
        q += f" LIMIT {int(limit)}"
    return list(conn.execute(text(q)).fetchall())


def main(argv: list[str], *, container: Any = None) -> int:
    args = _parse_args(argv)

    if container is None:
        from vidscope.infrastructure.container import build_container  # noqa: PLC0415
        container = build_container()

    with container.unit_of_work() as uow:
        rows = _fetch_unlinked(uow._connection, args.limit)  # type: ignore[attr-defined]

    if not rows:
        print("Nothing to backfill.")
        return 0

    print(f"Found {len(rows)} unlinked video(s). dry_run={not args.apply}")

    for video_id, platform_str, url, author in rows:
        try:
            platform = Platform(platform_str)
        except ValueError:
            print(f"  SKIP video {video_id}: unknown platform {platform_str!r}")
            continue

        result = container.downloader.probe(url)

        if result.status == ProbeStatus.OK and result.uploader_id:
            creator = Creator(
                platform=platform,
                platform_user_id=PlatformUserId(result.uploader_id),
                handle=result.uploader,
                display_name=result.uploader,
                profile_url=result.uploader_url,
                avatar_url=result.uploader_thumbnail,
                follower_count=result.channel_follower_count,
                is_verified=result.uploader_verified,
                is_orphan=False,
            )
            action = "LINK"
        else:
            creator = Creator(
                platform=platform,
                platform_user_id=PlatformUserId(f"orphan:{video_id}"),
                handle=author,
                display_name=author,
                is_orphan=True,
            )
            action = "ORPHAN"

        print(f"  {action} video {video_id} ({url[:60]}) → creator {creator.platform_user_id}")

        if args.apply:
            try:
                with container.unit_of_work() as uow:
                    video = uow.videos.get(VideoId(video_id))
                    if video is None:
                        print(f"  ERROR video {video_id} not found — skipping")
                        continue
                    saved = uow.creators.upsert(creator)
                    if saved.id is None:
                        print(f"  ERROR creator upsert returned no id for video {video_id} — skipping")
                        continue
                    uow.videos.upsert_by_platform_id(video, creator=saved)
            except Exception as exc:
                print(f"  ERROR video {video_id}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
