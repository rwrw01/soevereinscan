import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OVERRIDES_PATH = Path(__file__).parent.parent.parent / "data" / "overrides.json"


@dataclass
class PeeringDBResult:
    org_name: str | None
    org_country: str | None  # Now from /api/org/{org_id}, not from /net
    net_type: str | None
    org_id: int | None = None
    aka: str | None = None  # "Also Known As" field


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
        self._overrides = self._load_overrides()

    def _load_overrides(self) -> dict:
        if OVERRIDES_PATH.exists():
            data = json.loads(OVERRIDES_PATH.read_text())
            return data.get("overrides_by_org", {})
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
            org_id = entry.get("org_id")
            org_name = entry.get("name")  # Network name
            net_type = entry.get("info_type")
            aka = entry.get("aka")

            # Fetch org details for country
            org_country = None
            if org_id:
                org_country = await self._fetch_org_country(org_id)

            result = PeeringDBResult(
                org_name=org_name,
                org_country=org_country,
                net_type=net_type,
                org_id=org_id,
                aka=aka,
            )

            if cache:
                await cache.setex(
                    cache_key,
                    7 * 86400,
                    json.dumps({
                        "org_name": result.org_name,
                        "org_country": result.org_country,
                        "net_type": result.net_type,
                        "org_id": result.org_id,
                        "aka": result.aka,
                    }),
                )

            return result
        except httpx.HTTPError:
            logger.exception("PeeringDB lookup failed for ASN %d", asn)
            return None

    async def _fetch_org_country(self, org_id: int) -> str | None:
        """Fetch organization country from PeeringDB org endpoint."""
        cache = await self._get_redis()
        cache_key = f"peeringdb:org:{org_id}"

        if cache:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached.decode() if cached != b"" else None

        try:
            response = await self._client.get(f"/org/{org_id}")
            if response.status_code != 200:
                return None

            org_data = response.json().get("data", [])
            if not org_data:
                return None

            country = org_data[0].get("country", "")

            if cache:
                await cache.setex(cache_key, 7 * 86400, country or "")

            return country if country else None
        except Exception:
            logger.warning("Failed to fetch PeeringDB org %d", org_id)
            return None

    def get_override(self, asn_org: str, asn: int | None = None) -> tuple[str | None, str | None]:
        """Check override list for known exceptions (daughter companies, acquisitions)."""
        # Exact match first
        entry = self._overrides.get(asn_org)
        if entry:
            return entry["parent"], entry["country"]

        # Fuzzy match: check if any key starts with the org_name or vice versa
        org_lower = asn_org.lower().strip()
        for key, value in self._overrides.items():
            if key.startswith("_"):
                continue
            key_lower = key.lower()
            # "Cloudflare" matches "Cloudflare, Inc."
            if key_lower.startswith(org_lower) or org_lower.startswith(key_lower):
                return value["parent"], value["country"]
            # "Amazon.com" matches "Amazon.com, Inc."
            if org_lower.split(",")[0].strip() == key_lower.split(",")[0].strip():
                return value["parent"], value["country"]

        return None, None

    async def close(self):
        await self._client.aclose()
        if self._redis:
            await self._redis.aclose()
