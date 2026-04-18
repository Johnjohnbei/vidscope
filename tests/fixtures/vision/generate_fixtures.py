"""Generate synthetic JPG fixtures for M008 vision adapter tests.

Run once from the repo root:

    uv run python tests/fixtures/vision/generate_fixtures.py

Creates deterministic fixtures under tests/fixtures/vision/ that
the unit tests consume. Re-running overwrites — safe.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).parent


def _require_pil() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to generate vision fixtures.\n"
            "Install with: uv add --dev Pillow"
        ) from exc


def generate_text_jpg(
    path: Path, text: str, size: tuple[int, int] = (400, 100)
) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    # Default font — deterministic bitmap rendering across platforms.
    draw.text((10, 40), text, fill="black")
    img.save(path, format="JPEG", quality=95)


def generate_blank_jpg(
    path: Path, size: tuple[int, int] = (400, 100), color: str = "white"
) -> None:
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    img.save(path, format="JPEG", quality=95)


def main() -> None:
    _require_pil()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # OCR fixtures
    generate_text_jpg(FIXTURE_DIR / "text_present.jpg", "Link in bio: example.com")
    generate_text_jpg(FIXTURE_DIR / "text_fr.jpg", "Lien en bio : promo.fr")
    generate_blank_jpg(FIXTURE_DIR / "no_text.jpg")

    # Face fixtures — a blank is enough because we stub cascade in
    # unit tests. A real frontal-face JPG is only needed for the
    # (slow, excluded-by-default) integration tests shipped in S02.
    generate_blank_jpg(FIXTURE_DIR / "face_none.jpg")

    print(f"Generated fixtures in {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
