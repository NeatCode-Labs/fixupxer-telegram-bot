"""Run the same JSON test cases the Android app uses against the Python port."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cleaners import deep_clean

_FIXTURE = Path(__file__).parent / "fixtures" / "test-cases.json"


def _load_cases():
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    out = []
    for cat in data["testCases"]:
        category = cat["category"]
        for case in cat["cases"]:
            label = f"{category}: {case['description']}"
            out.append(pytest.param(case["input"], case["expected"], id=label))
    return out


@pytest.mark.parametrize("input_url, expected", _load_cases())
def test_json_cases(input_url: str, expected: str) -> None:
    assert deep_clean(input_url) == expected
