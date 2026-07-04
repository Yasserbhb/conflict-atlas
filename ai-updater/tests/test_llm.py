from conflict_updater.llm import _extract_json


def test_plain_json():
    assert _extract_json('{"a": 1, "b": {"c": 2}}') == {"a": 1, "b": {"c": 2}}


def test_fenced_json_with_nested_object():
    text = 'Here you go:\n```json\n{"a": 1, "b": {"c": 2}}\n```\nhope that helps'
    assert _extract_json(text) == {"a": 1, "b": {"c": 2}}


def test_prose_before_and_after_the_object():
    text = 'Sure! The answer is {"x": [1, 2, 3]} and nothing else.'
    assert _extract_json(text) == {"x": [1, 2, 3]}


def test_stray_brace_in_prose_before_the_real_object():
    # a naive first-brace..last-brace slice would capture "{see note}: {...}" and fail
    text = 'Here is my answer {see note}: {"ok": true}'
    assert _extract_json(text) == {"ok": True}


def test_no_json_raises():
    import pytest
    with pytest.raises(ValueError):
        _extract_json("there is no json here at all")
