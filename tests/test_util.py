import pytest

from soundpad_linux.util import fmt_duration, parse_duration


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0:02", 2.0), ("1:05", 65.0), ("1:00:01", 3601.0), ("2,5", 2.5), ("", None), ("abc", None), ("0:00", None)],
)
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, ""), (0, "0:00"), (2.4, "0:02"), (65, "1:05"), (3601, "1:00:01")],
)
def test_fmt_duration(seconds, expected):
    assert fmt_duration(seconds) == expected
