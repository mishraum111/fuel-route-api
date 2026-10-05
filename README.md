# Fuel Route API

Django 6.1 API that calculates a driving route between two US locations and recommends cost-effective fuel stops using the supplied 8,151-record fuel-price dataset.

## Architecture
- **Django 6.1.1** — HTTP/API layer.
- **OSRM public demo** — one driving-route request per uncached route, returning GeoJSON geometry and distance/duration.
- **Photon + US Census batch geocoder** — Photon geocodes start/finish; the Census batch endpoint resolves the small station-candidate city set in one HTTP request. Station coordinates are cached.
- **Local CSV** — fuel prices are loaded once at service startup.
- **Django cache** — route and geocode results are cached, reducing external calls for repeat requests.

The OSRM demo server is suitable for development/assessment traffic only; its published guidance limits usage to reasonable, non-commercial use and recommends self-hosting for production. Photon’s public demo is likewise intended for reasonable use. The US Census batch geocoder is used only for the capped candidate set. See provider links in `docs/PROVIDERS.md`.

## API
`POST /api/v1/route-fuel/` with `{"start":"New York, NY","finish":"Chicago, IL"}` (GET query parameters are also supported)

Returns:
- route GeoJSON LineString (directly usable by Leaflet/Mapbox/OpenLayers for a map)
- distance and duration
- vehicle assumptions: 500-mile range, 10 MPG
- recommended fuel stops
- station price/location
- total gallons and estimated fuel spend

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py runserver
```

Example:
```bash
curl "http://127.0.0.1:8000/api/v1/route-fuel/?start=New%20York,%20NY&finish=Chicago,%20IL"
```

## Tests
```bash
pytest
```

## Important modeling assumption
The input file has no latitude/longitude columns. The implementation selects a capped, price-diverse candidate set and resolves all candidate cities in one batch geocoding request, then caches those coordinates. A cold request therefore uses two endpoint geocodes, one batch station geocode, and one OSRM route call; repeat requests are cache-backed. For production, a one-time offline station-coordinate import could reduce runtime calls further.

## Postman / Loom

Import `postman_collection.json`. For the main request use:
```json
{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}
```

