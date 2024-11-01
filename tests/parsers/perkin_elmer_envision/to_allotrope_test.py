from pathlib import Path

import pytest

from allotropy.exceptions import AllotropeConversionError
from allotropy.parser_factory import Vendor
from allotropy.testing.utils import from_file
from tests.to_allotrope_test import ParserTest

VENDOR_TYPE = Vendor.PERKIN_ELMER_ENVISION
TESTDATA = f"{Path(__file__).parent}/testdata"


class TestParser(ParserTest):
    VENDOR = VENDOR_TYPE


def test_parse_file_missing_headers() -> None:
    test_filepath = f"{TESTDATA}/example01_missing_header_error.csv"
    # TODO: Handle the underlying error better in src
    with pytest.raises(
        AllotropeConversionError,
        match="Expected non-null value for Basic assay information.",
    ):
        from_file(test_filepath, VENDOR_TYPE)
