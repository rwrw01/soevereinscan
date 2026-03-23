import logging

import httpx

logger = logging.getLogger(__name__)


class RipeStatService:
    """Lookup ASN registration country via RIPE NCC RIPEstat API."""

    BASE_URL = "https://stat.ripe.net/data/rir-stats-country/data.json"

    def __init__(self, redis_url: str | None = None):
        self._client = httpx.AsyncClient(timeout=10.0)
        self._redis = None
        self._redis_url = redis_url

    async def _get_redis(self):
        if self._redis is None and self._redis_url:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def get_country(self, asn: int) -> str | None:
        """Get the RIR registration country for an ASN."""
        cache = await self._get_redis()
        cache_key = f"ripestat:country:{asn}"

        if cache:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached.decode() if cached != b"" else None

        try:
            response = await self._client.get(
                self.BASE_URL,
                params={"resource": f"AS{asn}"},
            )
            if response.status_code != 200:
                return None

            data = response.json()
            resources = data.get("data", {}).get("located_resources", [])
            if resources:
                country = resources[0].get("location", "")
                if cache:
                    await cache.setex(cache_key, 7 * 86400, country or "")
                return country if country else None

            return None
        except Exception:
            logger.warning("RIPEstat lookup failed for ASN %d", asn)
            return None

    async def close(self):
        await self._client.aclose()
        if self._redis:
            await self._redis.aclose()
