from __future__ import annotations

from linfilededuplication.core import backup_detect, policy
from linfilededuplication.core.model import KIND_EXACT, DuplicateGroup, FileEntry


def test_classify_backup_names():
    e = FileEntry(path="/docs/report.docx.bak", size=100, mtime=10)
    backup_detect.classify(e)
    assert e.is_backup
    plain = FileEntry(path="/docs/report.docx", size=100, mtime=10)
    backup_detect.classify(plain)
    assert not plain.is_backup


def test_embedded_date_orders_by_age():
    old = FileEntry(path="/b/db-2023-01-01.sql", size=100, mtime=999)   # newer mtime, older name-date
    new = FileEntry(path="/b/db-2024-06-01.sql", size=100, mtime=1)
    g = DuplicateGroup(kind=KIND_EXACT, key="k", files=[old, new])
    backup_detect.analyze_group(g)
    assert g.has_backups
    policy.rank(g, keep_newest=True)
    assert g.keeper is new                   # newest embedded date kept, not newest mtime


def test_close_dates_keep_non_backup_original():
    # config.yaml and its .bak saved seconds apart -> keep the non-backup original.
    live = FileEntry(path="/x/config.yaml", size=100, mtime=1000.0)
    bak = FileEntry(path="/x/config.yaml.bak", size=100, mtime=1005.0)   # 5s newer
    g = DuplicateGroup(kind=KIND_EXACT, key="k", files=[bak, live])
    backup_detect.analyze_group(g)
    assert g.has_backups
    policy.rank(g, keep_newest=True)
    assert g.keeper is live                  # close in time -> original beats the .bak


def test_non_backup_group_unaffected():
    a = FileEntry(path="/x/IMG_1.jpg", size=100, mtime=5)
    b = FileEntry(path="/y/IMG_1.jpg", size=100, mtime=9)
    g = DuplicateGroup(kind=KIND_EXACT, key="k", files=[a, b])
    backup_detect.analyze_group(g)
    assert not g.has_backups                 # ordinary duplicate, not flagged
