import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h]
ROOT_URLCONF = "config.urls"
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
INSTALLED_APPS = ["django.contrib.contenttypes", "fuelroute"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
GEOCODER_BASE_URL = os.getenv("GEOCODER_BASE_URL", "https://photon.komoot.io/api")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
ROOT_PATH = BASE_DIR
FUEL_DATA_PATH = BASE_DIR / "data" / "fuel-prices.csv"

BATCH_GEOCODER_URL = os.getenv("BATCH_GEOCODER_URL", "https://geocoding.geo.census.gov/geocoder/locations/addressbatch")
BATCH_GEOCODER_BENCHMARK = os.getenv("BATCH_GEOCODER_BENCHMARK", "Public_AR_Current")
BATCH_GEOCODER_VINTAGE = os.getenv("BATCH_GEOCODER_VINTAGE", "Current_Current")
STATION_CANDIDATE_LIMIT = int(os.getenv("STATION_CANDIDATE_LIMIT", "15"))
