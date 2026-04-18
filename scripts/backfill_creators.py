"""Backfill videos.creator_id from existing M001-M005 rows (M006/S01).

Default mode is --dry-run: probe every video via Downloader.probe(),
print the creator row that would be upserted + the resulting
videos.creator_id, write NOTHING. --apply is required to actually
mutate the database.

Per-video transaction: each video's creator upsert + video update
runs in its own SqliteUnitOfWork. A mid-run Ctrl-C leaves the DB in
a consistent state (every committed creator has a matching video FK;
no half-written creator rows).

Idempotent: skip videos where creator_id IS NOT NULL.

Orphan path (D-02): ProbeStatus.NOT_FOUND or AUTH_REQUIRED produces a
creator row with is_orphan=True and platform_user_id synthesised as
"orphan:{author or 'unknown'}" so UNIQUE(platform, platform_user_id)
stays satisfiable for every legacy video.

Usage
-----
    python -m uv run python scripts/backfill_creators.py            # dry-run (default)
    python -m uv run python scripts/backfill_creators.py --apply    # actually mutate
    python -m uv run python scripts/backfill_creators.py --apply --limit 5

Exit codes
----------
    0  — completed (in dry-run mode, this is a pure report; in --apply
         mode, at least one row was processed successfully)
    1  — fatal error (bad DB path, container build failed)
    2  — partial failure (some probes raised, some succeeded — see
         the summary line)
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import select, update

from vidscope.adapters.sqlite.schema import videos as videos_table
from vidscope.domain import Creator, Platform, PlatformUserId
from vidscope.infrastructure.container import Container, build_container
from vidscope.ports import ProbeResult, ProbeStatus

__all__ = ["main"]


@dataclass(slots=True)
class BackfillStats:
    total: int = 0
    ok: int = 0
    orphan: int = 0
    skipped_already_linked: int = 0
    failed: int = 0


def main(argv: list[str] | None = None, *, container: Container | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the DB. Default is --dry-run (zero writes).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N videos (useful for testing).",
    )
    args = parser.parse_args(argv)
    dry_run = not args.apply

    if container is None:
        try:
            container = build_container()
        except Exception as exc:
            sys.stderr.write(f"fatal: could not build container: {exc}\n")
            return 1

    mode_label = "DRY-RUN (no writes)" if dry_run else "APPLY (WILL MUTATE)"
    sys.stdout.write(f"backfill_creators.py :: mode = {mode_label}\n")
    if dry_run:
        sys.stdout.write("  (pass --apply to actually write)\n")

    stats = _run_backfill(container, dry_run=dry_run, limit=args.limit)

    sys.stdout.write(
        f"\n=== Summary ===\n"
        f"  Total videos scanned:        {stats.total}\n"
        f"  Already linked (skipped):    {stats.skipped_already_linked}\n"
        f"  Linked to fresh creator:     {stats.ok}\n"
        f"  Linked to orphan creator:    {stats.orphan}\n"
        f"  Failed (probe error):        {stats.failed}\n"
    )
    if stats.failed > 0 and not dry_run:
        return 2
    return 0


def _run_backfill(
    container: Container, *, dry_run: bool, limit: int | None
) -> BackfillStats:
    """Iterate videos with creator_id IS NULL, probe each, upsert
    creator + set videos.creator_id (unless dry-run). Per-video UoW
    for Ctrl-C safety.
    """
    stats = BackfillStats()

    # First pass: list target videos with a READ-ONLY UoW. We release
    # this connection before opening per-video write UoWs so the writes
    # don't contend with the long-lived read.
    with container.unit_of_work() as uow:
        conn = uow._connection  # type: ignore[attr-defined]  # internal but stable
        stmt = select(
            videos_table.c.id,
            videos_table.c.platform,
            videos_table.c.platform_id,
            videos_table.c.url,
            videos_table.c.author,
            videos_table.c.creator_id,
        )
        rows = conn.execute(stmt).mappings().all()

    target_rows = [r for r in rows if r["creator_id"] is None]
    stats.total = len(rows)
    stats.skipped_already_linked = len(rows) - len(target_rows)

    if limit is not None:
        target_rows = target_rows[:limit]

    for idx, row in enumerate(target_rows, start=1):
        video_url = str(row["url"])
        platform_str = str(row["platform"])
        platform = Platform(platform_str)
        legacy_author = row["author"]

        sys.stdout.write(
            f"[{idx}/{len(target_rows)}] probing {platform_str}/"
            f"{row['platform_id']} ... "
        )
        try:
            probe = container.downloader.probe(video_url)
        except Exception as exc:
            # Downloader.probe is documented never to raise (every
            # failure is encoded in status), but guard anyway.
            sys.stdout.write(f"EXCEPTION: {exc}\n")
            stats.failed += 1
            continue

        creator = _creator_from_probe(
            probe=probe, platform=platform, legacy_author=legacy_author
        )
        if creator is None:
            # NETWORK_ERROR / ERROR / UNSUPPORTED — don't create orphan,
            # just report and skip this video.
            sys.stdout.write(f"SKIP ({probe.status.value}: {probe.detail[:80]})\n")
            stats.failed += 1
            continue

        label = "ORPHAN" if creator.is_orphan else "OK"
        sys.stdout.write(
            f"{label} -> {creator.platform.value}/{creator.platform_user_id}"
            f" ({creator.display_name or 'no display_name'})\n"
        )

        if dry_run:
            if creator.is_orphan:
                stats.orphan += 1
            else:
                stats.ok += 1
            continue

        # Per-video write transaction: creator upsert + video link.
        try:
            with container.unit_of_work() as uow:
                stored_creator = uow.creators.upsert(creator)
                _link_video_to_creator(
                    uow, video_row=row, creator=stored_creator
                )
            if creator.is_orphan:
                stats.orphan += 1
            else:
                stats.ok += 1
        except Exception as exc:
            sys.stdout.write(f"    FAILED WRITE: {exc}\n")
            stats.failed += 1

    return stats


def _creator_from_probe(
    *,
    probe: ProbeResult,
    platform: Platform,
    legacy_author: str | None,
) -> Creator | None:
    """Build a Creator from a ProbeResult. Returns None for transient
    failures (network / unknown error) where orphan creation would
    pollute data quality.
    """
    if probe.status == ProbeStatus.OK:
        platform_user_id = probe.uploader_id or probe.uploader
        if not platform_user_id:
            # Extractor didn't expose uploader_id AND uploader — extremely
            # rare but treat as orphan to preserve FK invariants.
            return _orphan_creator(platform=platform, legacy_author=legacy_author)
        return Creator(
            platform=platform,
            platform_user_id=PlatformUserId(str(platform_user_id)),
            handle=_handle_best_effort(probe),
            display_name=probe.uploader,
            profile_url=probe.uploader_url,
            avatar_url=probe.uploader_thumbnail,
            follower_count=probe.channel_follower_count,
            is_verified=probe.uploader_verified,
            is_orphan=False,
        )

    if probe.status in (ProbeStatus.NOT_FOUND, ProbeStatus.AUTH_REQUIRED):
        return _orphan_creator(platform=platform, legacy_author=legacy_author)

    # NETWORK_ERROR / ERROR / UNSUPPORTED — don't create an orphan,
    # so the user can retry without polluting the creator table.
    return None


def _orphan_creator(
    *, platform: Platform, legacy_author: str | None
) -> Creator:
    """Orphan fallback: synthesise a stable platform_user_id from the
    legacy videos.author so UNIQUE(platform, platform_user_id) stays
    satisfiable and is_orphan=True surfaces the condition to the
    user."""
    author = legacy_author or "unknown"
    synthetic = f"orphan:{author}"
    return Creator(
        platform=platform,
        platform_user_id=PlatformUserId(synthetic),
        display_name=author,
        is_orphan=True,
    )


def _handle_best_effort(probe: ProbeResult) -> str | None:
    """Derive a @-handle from probe fields. yt-dlp doesn't expose a
    clean "handle" field that works across all platforms; use the
    uploader name prefixed by @ as a pragmatic default (open Q2 in
    S01-RESEARCH.md)."""
    if probe.uploader:
        return f"@{probe.uploader}"
    return None


def _link_video_to_creator(uow, *, video_row, creator: Creator) -> None:  # type: ignore[no-untyped-def]
    """Set videos.creator_id + videos.author (write-through) via a
    raw UPDATE since the existing VideoRepository.upsert_by_platform_id
    path requires the full Video entity. For backfill we already know
    the row id — a targeted UPDATE is cleaner than re-reading + re-
    upserting.
    """
    stmt = (
        update(videos_table)
        .where(videos_table.c.id == int(video_row["id"]))
        .values(
            creator_id=int(creator.id) if creator.id is not None else None,
            author=creator.display_name,  # D-03 write-through
        )
    )
    conn = uow._connection  # type: ignore[attr-defined]
    conn.execute(stmt)


if __name__ == "__main__":
    sys.exit(main())
