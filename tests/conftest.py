import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}")
os.environ.setdefault("REDIS_URL", "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}")
os.environ.setdefault("LOOKYLOO_URL", "http://localhost:5100")
os.environ.setdefault("GEOLITE2_ASN_PATH", "./data/GeoLite2-ASN.mmdb")
os.environ.setdefault("GEOLITE2_COUNTRY_PATH", "./data/GeoLite2-Country.mmdb")
