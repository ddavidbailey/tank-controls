from tank_controls.audio.intent import match_intent


def test_exact_match_returns_action_and_binding():
    result = match_intent("fire", {"fire": "space"}, threshold=0.8)
    assert result == ("fire", "space")


def test_fuzzy_match_above_threshold():
    # "fired" vs "fire" — SequenceMatcher ratio ≈ 0.89
    result = match_intent("fired", {"fire": "space"}, threshold=0.8)
    assert result == ("fire", "space")


def test_below_threshold_returns_none():
    result = match_intent("hello", {"fire": "space"}, threshold=0.8)
    assert result is None


def test_empty_press_returns_none():
    result = match_intent("fire", {}, threshold=0.8)
    assert result is None


def test_underscore_converted_to_space():
    result = match_intent("shell one", {"shell_one": "1"}, threshold=0.8)
    assert result == ("shell_one", "1")


def test_best_match_selected_among_multiple():
    press = {"fire": "space", "range_finder": "ctrl+r"}
    result = match_intent("fire", press, threshold=0.8)
    assert result == ("fire", "space")


def test_multi_word_fuzzy_match():
    # "shell won" vs "shell one" — SequenceMatcher ratio ≈ 0.89
    result = match_intent("shell won", {"shell_one": "1"}, threshold=0.8)
    assert result == ("shell_one", "1")
