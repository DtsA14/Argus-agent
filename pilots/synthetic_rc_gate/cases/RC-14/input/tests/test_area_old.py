from geo import area as geo_area


def test_area():
    assert geo_area.area(2, 3) == 6
