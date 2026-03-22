import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TracerouteHop:
    hop_number: int
    ip: str | None
    rtt_ms: float | None


class RipeAtlasService:
    BASE_URL = "https://atlas.ripe.net/api/v2"

    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"Authorization": f"Key {api_key}"} if api_key else {},
        )

    async def create_traceroute(self, target_ip: str, probe_count: int = 3) -> int | None:
        payload = {
            "definitions": [
                {
                    "target": target_ip,
                    "af": 4,
                    "type": "traceroute",
                    "protocol": "ICMP",
                    "resolve_on_probe": False,
                    "description": f"SoevereinScan traceroute to {target_ip}",
                    "is_oneoff": True,
                }
            ],
            "probes": [
                {
                    "requested": probe_count,
                    "type": "country",
                    "value": "NL",
                }
            ],
        }

        try:
            response = await self._client.post("/measurements/", json=payload)
            if response.status_code == 201:
                data = response.json()
                measurements = data.get("measurements", [])
                return measurements[0] if measurements else None
            logger.warning("RIPE Atlas returned %d: %s", response.status_code, response.text)
            return None
        except httpx.HTTPError:
            logger.exception("RIPE Atlas measurement creation failed for %s", target_ip)
            return None

    async def get_results(self, measurement_id: int) -> list[TracerouteHop]:
        try:
            response = await self._client.get(f"/measurements/{measurement_id}/results/")
            if response.status_code != 200:
                return []

            hops: list[TracerouteHop] = []
            data = response.json()
            if not data:
                return []

            probe_result = data[0].get("result", [])
            for hop_data in probe_result:
                hop_num = hop_data.get("hop")
                results = hop_data.get("result", [])
                if results and "from" in results[0]:
                    hops.append(TracerouteHop(
                        hop_number=hop_num,
                        ip=results[0].get("from"),
                        rtt_ms=results[0].get("rtt"),
                    ))
                else:
                    hops.append(TracerouteHop(hop_number=hop_num, ip=None, rtt_ms=None))

            return hops
        except httpx.HTTPError:
            logger.exception("RIPE Atlas results fetch failed for measurement %d", measurement_id)
            return []

    async def close(self):
        await self._client.aclose()
