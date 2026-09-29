from __future__ import annotations

from linfilededuplication.core import metadata


def test_filename_similarity():
    assert metadata.filename_similarity("/a/report_final.docx", "/b/report_final.docx") == 1.0
    high = metadata.filename_similarity("/a/vacation-photo.jpg", "/b/vacation-photo (1).jpg")
    low = metadata.filename_similarity("/a/vacation.jpg", "/b/spreadsheet.xlsx")
    assert high > 0.7
    assert low < high
