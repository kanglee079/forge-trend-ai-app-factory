def human_review_reason(qa_output: dict | None, policy_output: dict | None, quality_output: dict | None) -> str | None:
    if qa_output and not qa_output.get("passed"):
        failed = qa_output.get("failed") or {}
        return f"QA failed: {failed.get('command', 'unknown command')}"
    if policy_output and not policy_output.get("passed"):
        return "; ".join(policy_output.get("issues") or ["Policy gate failed"])
    if quality_output and not quality_output.get("passed"):
        return "; ".join(quality_output.get("issues") or ["Quality gate failed"])
    return None
