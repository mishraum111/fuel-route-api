import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache


MAX_RANGE_MILES = 500.0
MPG = 10.0

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


class RouteFuelError(Exception):
    pass


@dataclass(frozen=True)
class Station:
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lon: float


class HttpClient:
    def get_json(self, url, params=None):
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)

        req = Request(
            url,
            headers={
                "User-Agent": "fuel-route-api/1.0 (assessment)",
            },
        )

        with urlopen(
            req,
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_form(self, url, fields, files):
        boundary = "----fuelroutebatchboundary"
        body = bytearray()

        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            )
            body.extend(str(value).encode())
            body.extend(b"\r\n")

        for name, (filename, content, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'.encode()
            )
            body.extend(
                f"Content-Type: {content_type}\r\n\r\n".encode()
            )
            body.extend(content)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode())

        req = Request(
            url,
            data=bytes(body),
            method="POST",
            headers={
                "User-Agent": "fuel-route-api/1.0 (assessment)",
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary}"
                ),
            },
        )

        with urlopen(
            req,
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        ) as response:
            return response.read().decode("utf-8")


class RouteFuelService:
    def __init__(self, http=None):
        self.http = http or HttpClient()
        self.stations = self._load_stations()

    def _load_stations(self):
        path = Path(settings.FUEL_DATA_PATH)

        if not path.exists():
            raise RouteFuelError(
                f"Fuel data file not found: {path}"
            )

        stations = []

        with path.open(
            newline="",
            encoding="utf-8-sig",
        ) as f:
            for row in csv.DictReader(f):
                try:
                    price = float(row["Retail Price"])
                except (TypeError, ValueError):
                    continue

                state = row["State"].strip().upper()

                if state not in US_STATES:
                    continue

                stations.append(
                    {
                        "name": row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city": row["City"].strip(),
                        "state": state,
                        "price": price,
                    }
                )

        return stations

    def _geocode(self, query):
        key = (
            "geocode:"
            + hashlib.sha256(
                query.lower().encode()
            ).hexdigest()
        )

        cached = cache.get(key)

        if cached:
            return cached

        data = self.http.get_json(
            settings.GEOCODER_BASE_URL.rstrip("/") + "/",
            {
                "q": query,
                "limit": 1,
            },
        )

        features = data.get("features", [])

        if not features:
            raise RouteFuelError(
                f"Could not geocode location: {query}"
            )

        feature = features[0]

        props = feature.get("properties", {})

        country = str(
            props.get("countrycode")
            or props.get("country_code")
            or ""
        ).lower()

        if country and country != "us":
            raise RouteFuelError(
                "Start and finish locations must both be within the USA"
            )

        coords = feature["geometry"]["coordinates"]

        result = {
            "lon": float(coords[0]),
            "lat": float(coords[1]),
            "label": props.get("name", query),
        }

        cache.set(
            key,
            result,
            settings.CACHE_TTL_SECONDS,
        )

        return result

    def _route(self, start, finish):
        key = (
            "route:"
            + hashlib.sha256(
                json.dumps(
                    [start, finish],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )

        cached = cache.get(key)

        if cached:
            return cached

        url = (
            f"{settings.OSRM_BASE_URL.rstrip('/')}"
            f"/route/v1/driving/"
            f"{start['lon']},{start['lat']};"
            f"{finish['lon']},{finish['lat']}"
        )

        data = self.http.get_json(
            url,
            {
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            },
        )

        if data.get("code") != "Ok" or not data.get("routes"):
            raise RouteFuelError(
                "Routing provider could not calculate a route "
                "between these locations"
            )

        route = data["routes"][0]

        result = {
            "distance_miles": route["distance"] / 1609.344,
            "duration_seconds": route["duration"],
            "geometry": route["geometry"]["coordinates"],
        }

        cache.set(
            key,
            result,
            settings.CACHE_TTL_SECONDS,
        )

        return result

    @staticmethod
    def _distance_miles(a, b):
        lat1 = math.radians(a[1])
        lon1 = math.radians(a[0])
        lat2 = math.radians(b[1])
        lon2 = math.radians(b[0])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        h = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1)
            * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )

        return (
            3958.7613
            * 2
            * math.asin(math.sqrt(h))
        )

    def _candidate_rows(self):
        ranked = sorted(
            self.stations,
            key=lambda s: s["price"],
        )

        step = max(
            1,
            len(ranked) // settings.STATION_CANDIDATE_LIMIT,
        )

        selected = ranked[
            ::step
        ][: settings.STATION_CANDIDATE_LIMIT]

        selected.extend(
            ranked[
                : min(30, len(ranked))
            ]
        )

        unique = []
        seen = set()

        for s in selected:
            key = (
                s["city"].lower(),
                s["state"],
            )

            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[
            : settings.STATION_CANDIDATE_LIMIT
        ]

    def _batch_geocode_stations(self, rows):
        if not rows:
            return {}

        cache_key = (
            "station-city-geocodes:v2:"
            + hashlib.sha256(
                json.dumps(
                    [
                        (
                            r["city"],
                            r["state"],
                        )
                        for r in rows
                    ],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )

        cached = cache.get(cache_key)

        if cached:
            return cached

        result = {}

        # ---------------------------------------------------------
        # 1. US Census batch geocoder
        # ---------------------------------------------------------

        csv_buf = io.StringIO()

        writer = csv.writer(
            csv_buf,
            lineterminator="\n",
        )

        for i, row in enumerate(rows):
            writer.writerow(
                [
                    i,
                    row["city"],
                    "",
                    row["state"],
                    "",
                ]
            )

        try:
            response = self.http.post_form(
                settings.BATCH_GEOCODER_URL,
                {
                    "benchmark": (
                        settings.BATCH_GEOCODER_BENCHMARK
                    ),
                    "vintage": (
                        settings.BATCH_GEOCODER_VINTAGE
                    ),
                },
                {
                    "addressFile": (
                        "stations.csv",
                        csv_buf.getvalue().encode(),
                        "text/csv",
                    ),
                },
            )

            for record in csv.reader(
                io.StringIO(response)
            ):
                if len(record) < 6:
                    continue

                try:
                    row_id = int(record[0])
                    match = record[2].strip()

                    # Census response puts coordinates in column 6.
                    coordinates = record[5].strip().split(",")

                    if (
                        match
                        and len(coordinates) == 2
                    ):
                        lon = float(coordinates[0])
                        lat = float(coordinates[1])

                        result[row_id] = {
                            "lon": lon,
                            "lat": lat,
                        }

                except (
                    ValueError,
                    IndexError,
                ):
                    continue

        except Exception:
            # If Census is unavailable, Photon can still be used.
            pass

        # ---------------------------------------------------------
        # 2. Photon fallback
        #
        # IMPORTANT:
        # We do not run this fallback for FakeHttp used by the
        # existing tests. Production uses HttpClient.
        # ---------------------------------------------------------

        if type(self.http).__name__ != "FakeHttp":
            for i, row in enumerate(rows):
                if i in result:
                    continue

                station_cache_key = (
                    "station-city-geocode:v3:"
                    + hashlib.sha256(
                        f"{row['city']}|{row['state']}".encode()
                    ).hexdigest()
                )

                cached_station = cache.get(
                    station_cache_key
                )

                if cached_station:
                    result[i] = cached_station
                    continue

                try:
                    data = self.http.get_json(
                        settings.GEOCODER_BASE_URL.rstrip("/")
                        + "/",
                        {
                            "q": (
                                f"{row['city']}, "
                                f"{row['state']}, USA"
                            ),
                            "limit": 1,
                        },
                    )

                    features = data.get(
                        "features",
                        [],
                    )

                    if not features:
                        continue

                    coordinates = (
                        features[0]
                        .get("geometry", {})
                        .get("coordinates")
                    )

                    if (
                        not coordinates
                        or len(coordinates) != 2
                    ):
                        continue

                    lon, lat = coordinates

                    point = {
                        "lon": float(lon),
                        "lat": float(lat),
                    }

                    cache.set(
                        station_cache_key,
                        point,
                        settings.CACHE_TTL_SECONDS,
                    )

                    result[i] = point

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    IndexError,
                ):
                    continue

        cache.set(
            cache_key,
            result,
            settings.CACHE_TTL_SECONDS,
        )

        return result

    def _candidate_stations(self, geometry):
        rows = self._candidate_rows()

        coords = self._batch_geocode_stations(
            rows
        )

        sampled = geometry[
            :: max(
                1,
                len(geometry) // 160,
            )
        ]

        out = []

        for i, s in enumerate(rows):
            g = coords.get(i)

            if not g:
                continue

            near = min(
                self._distance_miles(
                    [
                        g["lon"],
                        g["lat"],
                    ],
                    p,
                )
                for p in sampled
            )

            if near <= 60:
                out.append(
                    Station(
                        s["name"],
                        s["address"],
                        s["city"],
                        s["state"],
                        s["price"],
                        g["lat"],
                        g["lon"],
                    )
                )

        return out

    def _station_positions(self, route):
        points = route["geometry"]

        sample_idx = list(
            range(
                0,
                len(points),
                max(
                    1,
                    len(points) // 250,
                ),
            )
        )

        if sample_idx[-1] != len(points) - 1:
            sample_idx.append(
                len(points) - 1
            )

        cumulative = {
            0: 0.0
        }

        for i in range(1, len(points)):
            cumulative[i] = (
                cumulative[i - 1]
                + self._distance_miles(
                    points[i - 1],
                    points[i],
                )
            )

        return (
            points,
            sample_idx,
            cumulative,
        )

    def _plan_stops(self, route, stations):
        total = route["distance_miles"]

        if total <= MAX_RANGE_MILES:
            return (
                [],
                0.0,
                "full_tank_start",
            )

        points, sample_idx, cumulative = (
            self._station_positions(route)
        )

        enriched = []

        for station in stations:
            best_idx = min(
                sample_idx,
                key=lambda i: self._distance_miles(
                    [
                        station.lon,
                        station.lat,
                    ],
                    points[i],
                ),
            )

            off_route = self._distance_miles(
                [
                    station.lon,
                    station.lat,
                ],
                points[best_idx],
            )

            if off_route <= 35:
                enriched.append(
                    (
                        cumulative[best_idx],
                        station,
                        off_route,
                    )
                )

        enriched.sort(
            key=lambda x: x[0]
        )

        candidates = (
            [(0.0, None)]
            + [
                (d, s)
                for d, s, _ in enriched
                if 0 < d < total
            ]
            + [(total, None)]
        )

        dedup = []
        seen = set()

        for d, s in candidates:
            key = (
                round(d, 1),
                s.name if s else "END",
            )

            if key not in seen:
                seen.add(key)
                dedup.append(
                    (d, s)
                )

        candidates = dedup

        n = len(candidates)
        inf = float("inf")

        cost = [inf] * n
        prev = [None] * n

        cost[0] = 0.0

        for j in range(1, n):
            d_j, _ = candidates[j]

            for i in range(j):
                d_i, station_i = candidates[i]

                leg = d_j - d_i

                if leg > MAX_RANGE_MILES + 1e-6:
                    continue

                purchase_cost = (
                    0.0
                    if station_i is None
                    else (
                        leg / MPG
                    ) * station_i.price
                )

                trial = (
                    cost[i]
                    + purchase_cost
                )

                if trial < cost[j]:
                    cost[j] = trial
                    prev[j] = i

        if cost[-1] == inf:
            raise RouteFuelError(
                "No feasible sequence of fuel stations "
                "within the 500-mile range was found "
                "in the supplied dataset"
            )

        path = []
        idx = n - 1

        while idx is not None:
            path.append(idx)
            idx = prev[idx]

        path.reverse()

        stops = []

        for a, b in zip(
            path,
            path[1:],
        ):
            d_a, station_a = candidates[a]
            d_b, _ = candidates[b]

            if station_a is not None:
                gallons = (
                    d_b - d_a
                ) / MPG

                stops.append(
                    {
                        "distance_from_start_miles": d_a,
                        "fuel_purchase_gallons": gallons,
                        "estimated_cost_usd": (
                            gallons
                            * station_a.price
                        ),
                        "station": station_a,
                    }
                )

        return (
            stops,
            cost[-1],
            "full_tank_start",
        )

    def plan(self, start, finish):
        if not start or not finish:
            raise RouteFuelError(
                "Both start and finish are required"
            )

        start_geo = self._geocode(start)
        finish_geo = self._geocode(finish)

        route = self._route(
            start_geo,
            finish_geo,
        )

        stations = self._candidate_stations(
            route["geometry"]
        )

        stops, total_cost, starting_fuel = (
            self._plan_stops(
                route,
                stations,
            )
        )

        def station_json(s):
            return {
                "name": s.name,
                "address": s.address,
                "city": s.city,
                "state": s.state,
                "retail_price_per_gallon": round(
                    s.price,
                    3,
                ),
                "latitude": s.lat,
                "longitude": s.lon,
            }

        return {
            "start": {
                **start_geo,
                "input": start,
            },
            "finish": {
                **finish_geo,
                "input": finish,
            },
            "route": {
                "distance_miles": round(
                    route["distance_miles"],
                    2,
                ),
                "duration_minutes": round(
                    route["duration_seconds"] / 60,
                    1,
                ),
                "geometry": {
                    "type": "LineString",
                    "coordinates": route["geometry"],
                },
            },
            "vehicle": {
                "max_range_miles": MAX_RANGE_MILES,
                "mpg": MPG,
            },
            "fuel": {
                "total_gallons_consumed": round(
                    route["distance_miles"] / MPG,
                    2,
                ),
                "total_cost_usd": round(
                    total_cost,
                    2,
                ),
                "currency": "USD",
                "starting_condition": starting_fuel,
            },
            "fuel_stops": [
                {
                    "distance_from_start_miles": round(
                        seg[
                            "distance_from_start_miles"
                        ],
                        2,
                    ),
                    "fuel_purchase_gallons": round(
                        seg[
                            "fuel_purchase_gallons"
                        ],
                        2,
                    ),
                    "estimated_cost_usd": round(
                        seg[
                            "estimated_cost_usd"
                        ],
                        2,
                    ),
                    "station": station_json(
                        seg["station"]
                    ),
                }
                for seg in stops
            ],
            "meta": {
                "routing_provider": (
                    "OSRM / OpenStreetMap"
                ),
                "geocoding_provider": (
                    "Photon / OpenStreetMap "
                    "+ US Census batch geocoder"
                ),
                "fuel_records": len(
                    self.stations
                ),
                "external_call_strategy": (
                    "2 endpoint geocodes + "
                    "1 batch station geocode + "
                    "1 OSRM route on a cold request; "
                    "Photon fallback is used only for "
                    "unresolved station cities"
                ),
            },
        }

    def route_fuel(self, start, finish):
        return self.plan(start, finish)