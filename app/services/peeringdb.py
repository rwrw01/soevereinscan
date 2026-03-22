import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PARENT_COMPANIES_PATH = Path(__file__).parent.parent.parent / "data" / "us_parent_companies.json"


@dataclass
class PeeringDBResult:
    org_name: str | None
    org_country: str | None
    net_type: str | None


class PeeringDBService:
    BASE_URL = "https://www.peeringdb.com/api"

    def __init__(self, redis_url: str | None, api_key: str = ""):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=10.0,
            headers={"Authorization": f"Api-Key {api_key}"} if api_key else {},
        )
        self._redis = None
        self._redis_url = redis_url
        self._parent_companies = self._load_parent_companies()

    def _load_parent_companies(self) -> dict:
        if PARENT_COMPANIES_PATH.exists():
            return json.loads(PARENT_COMPANIES_PATH.read_text())
        return {}

    async def _get_redis(self):
        if self._redis is None and self._redis_url:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def lookup_asn(self, asn: int) -> PeeringDBResult | None:
        cache = await self._get_redis()
        cache_key = f"peeringdb:asn:{asn}"

        if cache:
            cached = await cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                return PeeringDBResult(**data)

        try:
            response = await self._client.get(f"/net?asn={asn}")
            if response.status_code != 200:
                logger.warning("PeeringDB returned %d for ASN %d", response.status_code, asn)
                return None

            data = response.json().get("data", [])
            if not data:
                return None

            entry = data[0]
            org = entry.get("org", {})
            result = PeeringDBResult(
                org_name=org.get("name"),
                org_country=org.get("country"),
                net_type=entry.get("info_type"),
            )

            if cache:
                await cache.setex(
                    cache_key,
                    7 * 86400,
                    json.dumps({
                        "org_name": result.org_name,
                        "org_country": result.org_country,
                        "net_type": result.net_type,
                    }),
                )

            return result
        except httpx.HTTPError:
            logger.exception("PeeringDB lookup failed for ASN %d", asn)
            return None

    def get_parent_company(self, org_name: str) -> tuple[str | None, str | None]:
        """Returns (parent_company, parent_country) from us_parent_companies.json."""
        entry = self._parent_companies.get(org_name)
        if entry:
            return entry["parent"], entry["country"]
        return None, None

    async def close(self):
        await self._client.aclose()
        if self._redis:
            await self._redis.aclose()
