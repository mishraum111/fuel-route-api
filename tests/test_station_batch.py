import csv
from types import SimpleNamespace

from django.core.cache import cache

from services.routing import RouteFuelService


class FakeHttp:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get_json(self, url, params=None):
        self.get_calls.append((url, params))
        if "photon" in url:
            return {"features": [{"geometry": {"coordinates": [-74.0, 40.7]}, "properties": {"countrycode": "US", "name": "Test"}}]}
        return {"code": "Ok", "routes": [{"distance": 1000000, "duration": 3600, "geometry": {"coordinates": [[-74.0, 40.7], [-73.0, 41.0]]}}]}

    def post_form(self, url, fields, files):
        self.post_calls.append((url, fields, files))
        rows = []
        content = files["addressFile"][1].decode()
        for row in csv.reader(content.splitlines()):
            rows.append(row)
        # Census batch response shape: id, input..., match, type, ... , coordinates.
        return "\n".join(f'{r[0]},"{r[1]}",Match,Exact,OK,OK,OK,"-74.0,40.7"' for r in rows)


def test_station_candidates_use_one_batch_geocode(monkeypatch):
    cache.clear()
    http = FakeHttp()
    service = RouteFuelService(http=http)
    monkeypatch.setattr(service, "_candidate_rows", lambda: [
        {"name": "A", "address": "", "city": "Testville", "state": "NY", "price": 2.5},
        {"name": "B", "address": "", "city": "Other", "state": "NY", "price": 2.8},
    ])
    geometry = [[-74.0, 40.7], [-73.0, 41.0]]
    service._candidate_stations(geometry)
    assert len(http.post_calls) == 1
    assert len(http.get_calls) == 0


def test_foreign_geocode_is_rejected(monkeypatch):
    cache.clear()
    class ForeignHttp(FakeHttp):
        def get_json(self, url, params=None):
            return {"features": [{"geometry": {"coordinates": [2.35, 48.85]}, "properties": {"countrycode": "FR"}}]}
    service = RouteFuelService(http=ForeignHttp())
    try:
        service._geocode("Paris, France")
    except Exception as exc:
        assert "USA" in str(exc)
    else:
        raise AssertionError("Foreign location should be rejected")
