from geo import area as geo_area


def test_perimeter():
    assert geo_area.perimeter(2, 3) == 10
