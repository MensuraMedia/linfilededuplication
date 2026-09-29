"""Local glossary / FAQ store: load, look up, and search terms. Pure (stdlib only)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Entry:
    key: str
    term: str
    short: str = ""
    body: str = ""
    category: str = "Terms"
    aliases: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


class Glossary:
    def __init__(self, entries: list[Entry]) -> None:
        self.entries = entries
        self._by_key = {e.key: e for e in entries}

    @classmethod
    def load(cls, path: str) -> "Glossary":
        try:
            data = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            return cls([])
        entries = []
        for row in data.get("entries", []):
            known = {f for f in Entry.__dataclass_fields__}
            entries.append(Entry(**{k: v for k, v in row.items() if k in known}))
        return cls(entries)

    def get(self, key: str) -> Entry | None:
        return self._by_key.get(key)

    def short(self, key: str) -> str:
        e = self._by_key.get(key)
        return e.short if e else ""

    def search(self, query: str) -> list[Entry]:
        q = query.strip().lower()
        if not q:
            return list(self.entries)
        out = []
        for e in self.entries:
            haystack = " ".join([e.term, e.short, e.body, " ".join(e.aliases)]).lower()
            if q in haystack:
                out.append(e)
        return out

    def categories(self) -> list[str]:
        seen: list[str] = []
        for e in self.entries:
            if e.category not in seen:
                seen.append(e.category)
        return seen
