import difflib


def match_intent(
    transcription: str,
    press: dict[str, str],
    threshold: float,
) -> tuple[str, str] | None:
    best_ratio = 0.0
    best_action: str | None = None
    best_binding: str | None = None

    for action, binding in press.items():
        candidate = action.replace("_", " ")
        ratio = difflib.SequenceMatcher(None, transcription, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_action = action
            best_binding = binding

    if best_ratio >= threshold and best_action is not None and best_binding is not None:
        return (best_action, best_binding)
    return None
