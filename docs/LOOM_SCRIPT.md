# 5-minute Loom script

**0:00–0:30 — What the API does**
- Show README and the CSV (8,151 records).
- Say: “The API takes a US start and finish, calculates one driving route, then finds cost-effective fuel stops while enforcing a 500-mile range and 10 MPG assumption.”

**0:30–1:15 — Architecture**
- Show `fuelroute/views.py` and `services/routing.py`.
- Explain: Django API → two endpoint geocodes + one batch station geocode → one OSRM route call → local fuel-price optimization.
- Point out that route and geocode responses are cached.

**1:15–2:00 — Optimization**
- Show `_plan_stops`.
- Explain the vehicle starts with a full tank, so the first 500 miles require no incremental purchase.
- Dynamic programming chooses a feasible sequence of stations minimizing estimated fuel spend; every leg is ≤500 miles.

**2:00–3:30 — Postman demo**
- Run `GET /health/`.
- Run `POST /api/v1/route-fuel/` with New York → Chicago.
- Highlight distance, duration, GeoJSON route, fuel stops, station prices, gallons and total cost.
- Run the same request again and mention cached route/geocode results reduce provider calls.

**3:30–4:20 — Tests / engineering**
- Show `tests/`, `Dockerfile`, `requirements.txt`.
- Mention the CSV is bundled as immutable input data and external providers are isolated behind the service layer.

**4:20–5:00 — Tradeoffs**
- Be transparent: the supplied CSV has no coordinates, so a small price-diverse candidate pool is resolved through one batch geocoding request and cached.
- Production improvement: pre-geocode all stations once and persist coordinates, reducing a normal request to endpoint geocoding + one OSRM route call.
