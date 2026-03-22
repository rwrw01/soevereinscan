from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

SECRETS_DIR = Path("/run/secrets")


class Settings(BaseSettings):
    port: int = 8000
    base_url: str = "http://localhost:8000"

    database_url: str
    redis_url: str = "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
    lookyloo_url: str = "http://localhost:5100"

    maxmind_license_key: str = ""
    geolite2_asn_path: str = "./data/GeoLite2-ASN.mmdb"
    geolite2_country_path: str = "./data/GeoLite2-Country.mmdb"

    ripe_atlas_api_key: str = ""
    peeringdb_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="before")
    @classmethod
    def read_docker_secrets(cls, values: dict) -> dict:
        """Read Docker secrets from /run/secrets/ files into config."""
        secret_fields = ["ripe_atlas_api_key", "maxmind_license_key", "db_password"]
        for field in secret_fields:
            secret_file = SECRETS_DIR / field
            if secret_file.exists() and not values.get(field):
                values[field] = secret_file.read_text().strip()
        return values
