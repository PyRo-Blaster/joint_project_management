"""The importer reads the synthetic sheet's 13 headers and rows without the real fixture."""

from io import BytesIO

from app.importers.excel.parse import read_rows
from tests.fixtures.synthetic import build_synthetic_sheet


def test_read_rows_maps_headers_and_rows():
    rows = read_rows(BytesIO(build_synthetic_sheet()))
    assert len(rows) == 5
    first = rows[0].values
    assert first["entry_no"] == 1
    assert "~" in str(first["date"])
    assert first["owner"] == "GenSci"
