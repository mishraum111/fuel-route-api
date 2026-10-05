from types import SimpleNamespace

from services.routing import RouteFuelService


def test_range_rule_and_dp():
    service = RouteFuelService()

    # Synthetic route: 900 miles represented directly by cumulative
    # distance along the route. Station coordinates are placed on-route.
    route = {
        "distance_miles": 900,
        "geometry": [
            [0.0, 0.0],
            [4.0, 0.0],
            [8.0, 0.0],
        ],
    }

    stations = [
        SimpleNamespace(
            name="A",
            address="",
            city="",
            state="",
            price=3.5,
            lat=0.0,
            lon=4.0,
        ),
        SimpleNamespace(
            name="B",
            address="",
            city="",
            state="",
            price=2.5,
            lat=0.0,
            lon=8.0,
        ),
    ]

    stops, cost, _ = service._plan_stops(route, stations)

    assert stops
    assert cost > 0