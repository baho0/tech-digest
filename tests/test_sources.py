import pytest

from techdigest.sources.github_releases import parse_release
from techdigest.sources.lobsters import hint_from_tags


@pytest.mark.parametrize("tag,level,expected", [
    ("Rust 1.99.0", "minor", "1.99.0"),
    ("Rust 1.99.1", "minor", None),
    ("v3.15.0", "minor", "3.15.0"),
    ("v3.15.0a1", "minor", None),
    ("v3.15.0rc2", "minor", None),
    ("go1.25.0", "minor", "1.25.0"),
    ("REL_18_0", "minor", "18.0"),
    ("REL_17_6", "minor", None),
    ("REL_18_BETA1", "minor", None),
    ("v1.35.0-alpha.1", "minor", None),
    ("v25.0.0", "major", "25.0.0"),
    ("v25.1.0", "major", None),
    ("llvmorg-22-init", "minor", None),
])
def test_parse_release(tag, level, expected):
    assert parse_release(tag, level) == expected


def test_lobsters_tag_hints():
    assert hint_from_tags(["security", "rust"]) == "security"
    assert hint_from_tags(["c", "release", "zig"]) == "software"
    assert hint_from_tags(["show"]) is None
