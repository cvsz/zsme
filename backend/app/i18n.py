DEFAULT_LOCALE = "th"
FALLBACK_LOCALE = "en"
SUPPORTED_LOCALES = ("th", "en", "zh-CN", "ja", "vi")

LOCALE_ALIASES = {
    "th-TH": "th",
    "en-US": "en",
    "en-GB": "en",
    "zh": "zh-CN",
    "zh-Hans": "zh-CN",
    "ja-JP": "ja",
    "vi-VN": "vi",
}


def normalize_locale(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value in SUPPORTED_LOCALES:
        return value
    if value in LOCALE_ALIASES:
        return LOCALE_ALIASES[value]
    primary = value.split("-", 1)[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return None


def resolve_locale(accept_language: str | None) -> str:
    if not accept_language:
        return DEFAULT_LOCALE
    candidates: list[tuple[float, int, str]] = []
    for index, item in enumerate(accept_language.split(",")):
        parts = [part.strip() for part in item.split(";")]
        tag = parts[0]
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        candidates.append((quality, -index, tag))
    for quality, _, tag in sorted(candidates, reverse=True):
        if quality <= 0:
            continue
        locale = normalize_locale(tag)
        if locale:
            return locale
    return FALLBACK_LOCALE
