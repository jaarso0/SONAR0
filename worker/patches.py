"""Workaround: livekit-plugins-sarvam passes a null language_code into
LanguageCode(), which crashes the STT stream. Remove when fixed upstream."""
from livekit.agents import language as _language

_original_normalize = _language._normalize_language


def _normalize_language(code):
    if not code:
        return _original_normalize("en-IN")
    return _original_normalize(code)


_language._normalize_language = _normalize_language