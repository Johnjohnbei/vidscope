"""Unit tests for SponsorDetector — marker coverage."""

from __future__ import annotations

import pytest

from vidscope.adapters.heuristic.sponsor_detector import (
    SPONSOR_MARKERS,
    SponsorDetector,
)


@pytest.fixture
def det() -> SponsorDetector:
    return SponsorDetector()


class TestSponsorPositiveEnglish:
    @pytest.mark.parametrize("text", [
        "This video is sponsored by BrandX",
        "Sponsored by Acme today",
        "In paid partnership with Nike",
    ])
    def test_positive_en(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is True


class TestSponsorPositiveFrench:
    @pytest.mark.parametrize("text", [
        "En partenariat avec Nike",
        "Cette vidéo est sponsorisée",
        "En collaboration avec Sephora",
    ])
    def test_positive_fr(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is True


class TestSponsorPromoCode:
    @pytest.mark.parametrize("text", [
        "Use code SAVE20 at checkout",
        "Utilisez le code promo VID10",
    ])
    def test_promo_code_triggers(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is True


class TestSponsorHashtags:
    @pytest.mark.parametrize("text", [
        "Check it out #ad #sponsored",
        "#paidpartnership with brand",
    ])
    def test_hashtag_triggers(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is True


class TestSponsorAffiliate:
    @pytest.mark.parametrize("text", [
        "My affiliate link is below",
        "Affiliate links in description",
    ])
    def test_affiliate_triggers(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is True


class TestSponsorLinkInBio:
    def test_link_in_bio_triggers(self, det: SponsorDetector) -> None:
        assert det.detect("Link in bio to buy") is True

    def test_lien_en_bio_triggers(self, det: SponsorDetector) -> None:
        assert det.detect("Lien en bio pour commander") is True


class TestSponsorNegatives:
    @pytest.mark.parametrize("text", [
        "Today we'll cook pasta",
        "Just a regular tutorial about Python",
        "",
    ])
    def test_no_marker_returns_false(self, det: SponsorDetector, text: str) -> None:
        assert det.detect(text) is False


class TestSponsorCaseInsensitive:
    def test_uppercase_still_detected(self, det: SponsorDetector) -> None:
        assert det.detect("SPONSORED CONTENT") is True


class TestSponsorLimitationDocumented:
    def test_negation_not_parsed(self, det: SponsorDetector) -> None:
        """Known limitation: 'not sponsored' still triggers. Documented."""
        assert det.detect("this is not sponsored") is True


class TestMarkersSize:
    def test_markers_set_not_empty(self) -> None:
        assert len(SPONSOR_MARKERS) >= 20
