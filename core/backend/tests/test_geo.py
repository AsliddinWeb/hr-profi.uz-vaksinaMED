import pytest

from app.geo import haversine_m, valid_coordinates, within_radius


def test_haversine_known_distance():
    # Toshkent (Amir Temur xiyoboni) -> Samarqand (Registon): ~ 268 km
    d = haversine_m(41.3111, 69.2797, 39.6542, 66.9757)
    assert 265_000 < d < 272_000
    assert haversine_m(41.0, 69.0, 41.0, 69.0) == 0


def test_within_radius_100m():
    lat, lng = 41.3111, 69.2797
    # ~ 0.0005 daraja kenglik ~ 55 m
    assert within_radius(lat + 0.0005, lng, lat, lng, 100)
    # ~ 0.002 daraja ~ 222 m
    assert not within_radius(lat + 0.002, lng, lat, lng, 100)


@pytest.mark.parametrize(
    "lat,lng,ok",
    [(41.3, 69.2, True), (91, 0, False), (0, 181, False), (None, 1, False), (-90, -180, True)],
)
def test_valid_coordinates(lat, lng, ok):
    assert valid_coordinates(lat, lng) is ok
