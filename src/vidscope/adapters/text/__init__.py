"""Text-only adapters: regex URL extraction + URL normalization.

This sub-package is structurally isolated by the import-linter contract
``text-adapter-is-self-contained`` — it imports only stdlib + domain +
ports. No SQLAlchemy, no yt-dlp, no faster-whisper.

Used by:
- :class:`~vidscope.pipeline.stages.metadata_extract_stage.MetadataExtractStage`
  (M007/S03) to surface URLs from caption + transcript.
- :class:`~vidscope.adapters.ocr.*` (M008/S02) to surface URLs from
  OCR output over the same regex.
"""

from __future__ import annotations

from vidscope.adapters.text.regex_link_extractor import RegexLinkExtractor
from vidscope.adapters.text.url_normalizer import normalize_url

__all__ = ["RegexLinkExtractor", "normalize_url"]
