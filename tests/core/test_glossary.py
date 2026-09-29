from __future__ import annotations

from pathlib import Path

from linfilededuplication.core.glossary import Glossary

DATA = Path(__file__).resolve().parents[2] / "data" / "glossary" / "en.json"


def _load() -> Glossary:
    return Glossary.load(str(DATA))


def test_glossary_loads_and_gets():
    g = _load()
    assert g.entries, "glossary should not be empty"
    e = g.get("hard-link")
    assert e is not None and e.short


def test_search_by_alias():
    g = _load()
    hits = g.search("dupe")
    assert any(e.key == "duplicate" for e in hits)


def test_every_infohint_key_resolves():
    """Every term key used by an InfoHint in the UI must exist in the glossary."""
    g = _load()
    used = {
        "match-kind", "backup-file", "keeper", "near-duplicate", "min-size",
        "newest-older", "system-file", "cache", "package-artifact", "exclusions",
        "trash", "spotcheck-diff",
    }
    missing = {k for k in used if g.get(k) is None}
    assert not missing, f"glossary missing keys: {missing}"
