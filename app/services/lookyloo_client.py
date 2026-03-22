import logging
from urllib.parse import urlparse

from pylookyloo import Lookyloo

logger = logging.getLogger(__name__)


class LookylooClient:
    def __init__(self, lookyloo_url: str):
        self._lookyloo = Lookyloo(lookyloo_url)

    def submit(self, url: str) -> str | None:
        try:
            capture_uuid = self._lookyloo.submit(url=url, quiet=True)
            logger.info("Lookyloo capture submitted: %s -> %s", url, capture_uuid)
            return capture_uuid
        except Exception:
            logger.exception("Failed to submit URL to Lookyloo: %s", url)
            return None

    def is_ready(self, capture_uuid: str) -> bool:
        try:
            status = self._lookyloo.get_status(capture_uuid)
            return status == 1
        except Exception:
            return False

    def get_resources(self, capture_uuid: str) -> tuple[dict[str, list[str]], set[str]]:
        """Returns (hostname_to_ips mapping, unique_ips set)."""
        try:
            redirects = self._lookyloo.get_redirects(capture_uuid)
            hostname_ips: dict[str, list[str]] = {}
            all_ips: set[str] = set()

            if isinstance(redirects, dict):
                response = redirects.get("response", {})
                ips_data = response.get("ips", {})
                for hostname, ips in ips_data.items():
                    hostname_ips[hostname] = ips
                    all_ips.update(ips)

            return hostname_ips, all_ips
        except Exception:
            logger.exception("Failed to get resources from Lookyloo capture %s", capture_uuid)
            return {}, set()

    def get_hostnames(self, capture_uuid: str) -> set[str]:
        hostname_ips, _ = self.get_resources(capture_uuid)
        return set(hostname_ips.keys())

    def classify_third_party(self, scan_url: str, hostname: str) -> bool:
        scan_domain = urlparse(scan_url).netloc
        return hostname != scan_domain and not hostname.endswith(f".{scan_domain}")
