"""Tests for ShowVideoUseCase — M007/S04-P02.

Pattern: FakeUoW with fakes for Video, Hashtag, Mention, Link repositories.
The use case must return ShowVideoResult with hashtags/mentions/links fields.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

from vidscope.application.show_video import ShowVideoResult, ShowVideoUseCase
from vidscope.domain import (
    Analysis,
    Creator,
    Frame,
    FrameText,
    Hashtag,
    Link,
    Mention,
    Platform,
    Transcript,
    Video,
    VideoId,
)
from vidscope.domain.values import CreatorId, PlatformId

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeVideoRepo:
    def __init__(self, videos: dict[int, Video] | None = None) -> None:
        self._videos: dict[int, Video] = videos or {}

    def get(self, video_id: VideoId) -> Video | None:
        return self._videos.get(int(video_id))

    def add(self, video: Video) -> Video:
        return video

    def upsert_by_platform_id(self, video: Video, creator: Any = None) -> Video:
        return video

    def get_by_platform_id(self, platform: Any, platform_id: Any) -> Video | None:
        return None

    def list_recent(self, limit: int = 20) -> list[Video]:
        return []

    def count(self) -> int:
        return 0

    def list_by_creator(self, creator_id: CreatorId, *, limit: int = 50) -> list[Video]:
        return []

    def count_by_creator(self, creator_id: CreatorId) -> int:
        return 0


class FakeTranscriptRepo:
    def __init__(self, transcript: Transcript | None = None) -> None:
        self._transcript = transcript

    def get_for_video(self, video_id: VideoId) -> Transcript | None:
        return self._transcript

    def add(self, transcript: Transcript) -> Transcript:
        return transcript


class FakeFrameRepo:
    def __init__(self, frames: list[Frame] | None = None) -> None:
        self._frames = frames or []

    def list_for_video(self, video_id: VideoId) -> list[Frame]:
        return self._frames

    def add_many(self, frames: list[Frame]) -> list[Frame]:
        return frames


class FakeAnalysisRepo:
    def __init__(self, analysis: Analysis | None = None) -> None:
        self._analysis = analysis

    def get_latest_for_video(self, video_id: VideoId) -> Analysis | None:
        return self._analysis

    def add(self, analysis: Analysis) -> Analysis:
        return analysis


class FakeCreatorRepo:
    def __init__(self, creator: Creator | None = None) -> None:
        self._creator = creator

    def get(self, creator_id: CreatorId) -> Creator | None:
        return self._creator

    def upsert(self, creator: Creator) -> Creator:
        return creator

    def find_by_platform_user_id(self, platform: Any, platform_user_id: Any) -> Creator | None:
        return None

    def find_by_handle(self, platform: Any, handle: str) -> Creator | None:
        return None

    def list_by_platform(self, platform: Any, *, limit: int = 50) -> list[Creator]:
        return []

    def list_by_min_followers(self, min_count: int, *, limit: int = 50) -> list[Creator]:
        return []

    def count(self) -> int:
        return 0


class FakeHashtagRepo:
    def __init__(self, hashtags_by_video: dict[int, list[Hashtag]] | None = None) -> None:
        self._hashtags: dict[int, list[Hashtag]] = hashtags_by_video or {}

    def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
        return self._hashtags.get(int(video_id), [])

    def replace_for_video(self, video_id: VideoId, tags: list[str]) -> None:
        pass

    def find_video_ids_by_tag(self, tag: str, *, limit: int = 50) -> list[VideoId]:
        return []


class FakeMentionRepo:
    def __init__(self, mentions_by_video: dict[int, list[Mention]] | None = None) -> None:
        self._mentions: dict[int, list[Mention]] = mentions_by_video or {}

    def list_for_video(self, video_id: VideoId) -> list[Mention]:
        return self._mentions.get(int(video_id), [])

    def replace_for_video(self, video_id: VideoId, mentions: list[Mention]) -> None:
        pass

    def find_video_ids_by_handle(self, handle: str, *, limit: int = 50) -> list[VideoId]:
        return []


class FakeLinkRepo:
    def __init__(self, links_by_video: dict[int, list[Link]] | None = None) -> None:
        self._links: dict[int, list[Link]] = links_by_video or {}

    def list_for_video(self, video_id: VideoId, *, source: str | None = None) -> list[Link]:
        all_links = self._links.get(int(video_id), [])
        if source is not None:
            return [lk for lk in all_links if lk.source == source]
        return list(all_links)

    def add_many_for_video(self, video_id: VideoId, links: list[Link]) -> list[Link]:
        return []

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return False

    def find_video_ids_with_any_link(self, *, limit: int = 50) -> list[VideoId]:
        return []


class FakeFrameTextRepo:
    def __init__(self, frame_texts_by_video: dict[int, list[FrameText]] | None = None) -> None:
        self._frame_texts: dict[int, list[FrameText]] = frame_texts_by_video or {}

    def list_for_video(self, video_id: VideoId) -> list[FrameText]:
        return self._frame_texts.get(int(video_id), [])

    def add_many_for_frame(
        self, frame_id: int, video_id: VideoId, texts: list[FrameText]
    ) -> list[FrameText]:
        return texts

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return bool(self._frame_texts.get(int(video_id)))

    def find_video_ids_by_text(self, query: str, *, limit: int = 50) -> list[VideoId]:
        return []


class FakeUoW:
    def __init__(
        self,
        *,
        videos: FakeVideoRepo | None = None,
        transcripts: FakeTranscriptRepo | None = None,
        frames: FakeFrameRepo | None = None,
        analyses: FakeAnalysisRepo | None = None,
        creators: FakeCreatorRepo | None = None,
        hashtags: FakeHashtagRepo | None = None,
        mentions: FakeMentionRepo | None = None,
        links: FakeLinkRepo | None = None,
        frame_texts: FakeFrameTextRepo | None = None,
    ) -> None:
        self.videos = videos or FakeVideoRepo()
        self.transcripts = transcripts or FakeTranscriptRepo()
        self.frames = frames or FakeFrameRepo()
        self.analyses = analyses or FakeAnalysisRepo()
        self.creators = creators or FakeCreatorRepo()
        self.hashtags = hashtags or FakeHashtagRepo()
        self.mentions = mentions or FakeMentionRepo()
        self.links = links or FakeLinkRepo()
        self.frame_texts = frame_texts or FakeFrameTextRepo()

    def __enter__(self) -> FakeUoW:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


def _make_uow_factory(**kwargs: Any) -> Any:
    uow = FakeUoW(**kwargs)

    def _factory() -> FakeUoW:
        return uow

    return _factory


def _make_video(vid: int = 42) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=f"Video {vid}",
        creator_id=None,
    )


def _make_hashtag(vid: int, tag: str, hid: int = 1) -> Hashtag:
    return Hashtag(video_id=VideoId(vid), tag=tag, id=hid)


def _make_mention(vid: int, handle: str, mid: int = 1) -> Mention:
    return Mention(video_id=VideoId(vid), handle=handle, id=mid)


def _make_link(
    vid: int,
    url: str = "https://example.com",
    source: str = "description",
    lid: int = 1,
) -> Link:
    return Link(
        video_id=VideoId(vid),
        url=url,
        normalized_url=url.lower(),
        source=source,
        id=lid,
    )


# ---------------------------------------------------------------------------
# T01 — Test 1: found=True returns hashtags/mentions/links from repos
# ---------------------------------------------------------------------------


class TestShowVideoUseCaseEnriched:
    def test_returns_hashtags_mentions_links_from_uow(self) -> None:
        """execute(42) retourne ShowVideoResult avec hashtags/mentions/links."""
        vid = 42
        video = _make_video(vid)
        hashtags = [_make_hashtag(vid, "cooking"), _make_hashtag(vid, "recipe", 2)]
        mentions = [_make_mention(vid, "alice")]
        links = [_make_link(vid, "https://example.com")]

        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            hashtags=FakeHashtagRepo({vid: hashtags}),
            mentions=FakeMentionRepo({vid: mentions}),
            links=FakeLinkRepo({vid: links}),
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.found is True
        assert len(result.hashtags) == 2
        assert result.hashtags[0].tag == "cooking"
        assert len(result.mentions) == 1
        assert result.mentions[0].handle == "alice"
        assert len(result.links) == 1
        assert result.links[0].url == "https://example.com"

    def test_found_false_new_fields_are_empty_tuples(self) -> None:
        """execute(999) → found=False, hashtags=(), mentions=(), links=()."""
        factory = _make_uow_factory()  # empty repos
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(999)

        assert result.found is False
        assert result.hashtags == ()
        assert result.mentions == ()
        assert result.links == ()

    def test_found_true_calls_all_three_list_for_video(self) -> None:
        """found=True → hashtags/mentions/links proviennent de uow.*list_for_video."""
        vid = 7
        video = _make_video(vid)
        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            hashtags=FakeHashtagRepo({vid: [_make_hashtag(vid, "python")]}),
            mentions=FakeMentionRepo({vid: [_make_mention(vid, "bob")]}),
            links=FakeLinkRepo({vid: [_make_link(vid, "https://bob.dev")]}),
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.found is True
        assert result.hashtags == (Hashtag(video_id=VideoId(vid), tag="python", id=1),)
        assert result.mentions == (Mention(video_id=VideoId(vid), handle="bob", id=1),)
        assert len(result.links) == 1
        assert result.links[0].url == "https://bob.dev"

    def test_backward_compat_missing_m007_data_returns_empty_tuples(self) -> None:
        """Appelants existants sans données M007 → champs vides, pas d'erreur."""
        vid = 5
        video = _make_video(vid)
        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            # No hashtags, mentions, or links seeded
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.found is True
        assert result.hashtags == ()
        assert result.mentions == ()
        assert result.links == ()
        # Other fields still work as before
        assert result.video is not None
        assert result.video.id == VideoId(vid)

    def test_result_has_all_new_fields_as_tuples(self) -> None:
        """ShowVideoResult expose hashtags, mentions, links comme tuple fields."""
        result = ShowVideoResult(found=False)
        assert isinstance(result.hashtags, tuple)
        assert isinstance(result.mentions, tuple)
        assert isinstance(result.links, tuple)
        assert result.hashtags == ()
        assert result.mentions == ()
        assert result.links == ()


# ---------------------------------------------------------------------------
# M008 tests — frame_texts + thumbnail_key + content_shape
# ---------------------------------------------------------------------------


def _make_frame_text(vid: int, frame_id: int, text: str, fid: int = 1) -> FrameText:
    return FrameText(
        video_id=VideoId(vid),
        frame_id=frame_id,
        text=text,
        confidence=0.90,
        id=fid,
    )


def _make_video_with_visual(
    vid: int = 42,
    thumbnail_key: str | None = None,
    content_shape: str | None = None,
) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=f"Video {vid}",
        thumbnail_key=thumbnail_key,
        content_shape=content_shape,
    )


class TestShowVideoM008Fields:
    def test_defaults_when_not_found(self) -> None:
        """ShowVideoResult(found=False) a frame_texts=(), thumbnail_key=None, content_shape=None."""
        result = ShowVideoResult(found=False)
        assert result.frame_texts == ()
        assert result.thumbnail_key is None
        assert result.content_shape is None

    def test_use_case_returns_empty_frame_texts_when_none(self) -> None:
        """Use case sans frame_texts → result.frame_texts == ()."""
        vid = 42
        video = _make_video_with_visual(vid)
        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            frame_texts=FakeFrameTextRepo(),
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.found is True
        assert result.frame_texts == ()

    def test_use_case_returns_frame_texts_when_present(self) -> None:
        """Use case avec 2 frame_texts → result.frame_texts a 2 éléments."""
        vid = 42
        video = _make_video_with_visual(vid)
        ft1 = _make_frame_text(vid, frame_id=1, text="Hello world", fid=1)
        ft2 = _make_frame_text(vid, frame_id=2, text="Promo code", fid=2)
        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            frame_texts=FakeFrameTextRepo({vid: [ft1, ft2]}),
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.found is True
        assert len(result.frame_texts) == 2
        assert result.frame_texts[0].text == "Hello world"
        assert result.frame_texts[1].text == "Promo code"

    def test_use_case_returns_thumbnail_key(self) -> None:
        """result.thumbnail_key == video.thumbnail_key depuis la DB."""
        vid = 42
        video = _make_video_with_visual(vid, thumbnail_key="videos/yt/abc/thumb.jpg")
        factory = _make_uow_factory(videos=FakeVideoRepo({vid: video}))
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.thumbnail_key == "videos/yt/abc/thumb.jpg"

    def test_use_case_returns_content_shape(self) -> None:
        """result.content_shape == video.content_shape depuis la DB."""
        vid = 42
        video = _make_video_with_visual(vid, content_shape="talking_head")
        factory = _make_uow_factory(videos=FakeVideoRepo({vid: video}))
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert result.content_shape == "talking_head"

    def test_frame_texts_is_tuple(self) -> None:
        """result.frame_texts est bien un tuple (immutabilité)."""
        vid = 42
        video = _make_video_with_visual(vid)
        ft = _make_frame_text(vid, frame_id=1, text="Hi")
        factory = _make_uow_factory(
            videos=FakeVideoRepo({vid: video}),
            frame_texts=FakeFrameTextRepo({vid: [ft]}),
        )
        uc = ShowVideoUseCase(unit_of_work_factory=factory)

        result = uc.execute(vid)

        assert isinstance(result.frame_texts, tuple)
