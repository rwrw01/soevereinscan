import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")
os.environ.setdefault("LOOKYLOO_URL", "http://localhost:5100")
os.environ.setdefault("GEOLITE2_ASN_PATH", "./data/GeoLite2-ASN.mmdb")
os.environ.setdefault("GEOLITE2_COUNTRY_PATH", "./data/GeoLite2-Country.mmdb")
