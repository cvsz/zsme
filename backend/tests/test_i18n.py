from app.i18n import DEFAULT_LOCALE, FALLBACK_LOCALE, SUPPORTED_LOCALES, resolve_locale


def test_supported_locales_are_exactly_five() -> None:
    assert SUPPORTED_LOCALES == ("th", "en", "zh-CN", "ja", "vi")


def test_no_header_uses_thailand_first_default() -> None:
    assert DEFAULT_LOCALE == "th"
    assert resolve_locale(None) == "th"


def test_common_regional_tags_normalize() -> None:
    assert resolve_locale("th-TH") == "th"
    assert resolve_locale("en-US") == "en"
    assert resolve_locale("zh-Hans") == "zh-CN"
    assert resolve_locale("ja-JP") == "ja"
    assert resolve_locale("vi-VN") == "vi"


def test_quality_values_choose_best_supported_language() -> None:
    assert resolve_locale("en;q=0.7,ja-JP;q=0.9") == "ja"


def test_explicit_unsupported_language_falls_back_to_english() -> None:
    assert FALLBACK_LOCALE == "en"
    assert resolve_locale("fr-FR") == "en"
