def assert_record_shape(record):
    assert set(record) == {"id", "name"}, sorted(record)
