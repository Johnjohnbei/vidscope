"""SetVideoTrackingUseCase — M011/S01/R056.

Writes a user workflow overlay for a single video: ``status``, ``starred``,
``notes``. Idempotent via the repository's ``upsert`` — calling ``execute``
twice with the same inputs produces the same end state.

``notes`` semantics (D1 + Open Question 3 of M011 RESEARCH):
- ``notes=None`` -> preserve existing notes if the row exists (no-op on notes).
- ``notes=""`` -> explicit clear (set DB notes to "").
- ``notes="text"`` -> set to text.

Follows hexagonal discipline: only imports from vidscope.domain and
vidscope.ports. No adapter reach-in.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import TrackingStatus, VideoId, VideoTracking
from vidscope.ports import UnitOfWorkFactory

__all__ = ["SetVideoTrackingResult", "SetVideoTrackingUseCase"]


@dataclass(frozen=True, slots=True)
class SetVideoTrackingResult:
    """Outcome of :class:`SetVideoTrackingUseCase.execute`."""

    tracking: VideoTracking
    created: bool  # True if this was the first tracking row for the video


class SetVideoTrackingUseCase:
    """Upsert the workflow overlay for a single video."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        video_id: int,
        *,
        status: TrackingStatus,
        starred: bool = False,
        notes: str | None = None,
    ) -> SetVideoTrackingResult:
        """Set or update the tracking row for ``video_id``.

        Parameters
        ----------
        video_id:
            Primary key of the target video.
        status:
            New :class:`TrackingStatus` value.
        starred:
            New starred flag (default False).
        notes:
            ``None`` preserves existing notes when the row already
            exists; empty string clears them; any other string replaces.
        """
        vid = VideoId(int(video_id))
        with self._uow_factory() as uow:
            existing = uow.video_tracking.get_for_video(vid)
            resolved_notes: str | None
            if notes is None and existing is not None:
                resolved_notes = existing.notes  # preserve
            else:
                resolved_notes = notes  # may be "", replace; may be str, replace

            new_entity = VideoTracking(
                video_id=vid,
                status=status,
                starred=starred,
                notes=resolved_notes,
            )
            persisted = uow.video_tracking.upsert(new_entity)
            return SetVideoTrackingResult(
                tracking=persisted,
                created=existing is None,
            )
