from helpers import assert_record_shape
from people.records import make_record


def test_record_shape():
    assert_record_shape(make_record(1, "Ana"))


def test_record_values():
    record = make_record(1, "Ana")
    assert record["id"] == 1 and record["name"] == "Ana"
