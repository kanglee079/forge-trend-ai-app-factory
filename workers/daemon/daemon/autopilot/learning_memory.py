def classify_failure(reason: str | None) -> str:
    text = (reason or "").lower()
    if not text:
        return "none"
    if "codex" in text and "auth" in text:
        return "provider_auth_missing"
    if "pub get" in text:
        return "flutter_pub_get_failed"
    if "analyze" in text:
        return "flutter_analyze_failed"
    if "test" in text:
        return "flutter_test_failed"
    if "build" in text or "apk" in text:
        return "flutter_build_failed"
    if "generic" in text or "placeholder" in text:
        return "generic_template_copy"
    if "vietnamese" in text:
        return "missing_vietnamese"
    if "policy" in text or "trademark" in text:
        return "policy_risk"
    if "store asset" in text:
        return "store_asset_missing"
    if "budget" in text:
        return "budget_exceeded"
    if "timeout" in text:
        return "timeout"
    return "unknown"
