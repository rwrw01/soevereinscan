import logging
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import DiscoveredResource, IpAnalysis, Scan
from app.services.capture import CaptureService
from app.services.classifier import classify_jurisdiction
from app.services.geoip import GeoIPService
from app.services.peeringdb import PeeringDBService
from app.services.ripe_atlas import RipeAtlasService
from app.services.ripestat import RipeStatService

logger = logging.getLogger(__name__)

# Category weights for impact-weighted scoring
_CATEGORY_WEIGHTS = {
    "hosting": 5,
    "cdn": 3,
    "analytics": 1,
    "tracking": 1,
    "fonts": 0.5,
    "email": 1,
    "other": 2,
}

_HOSTNAME_PATTERNS: list[tuple[str, str]] = [
    (r"fonts\.|typekit|fontawesome", "fonts"),
    (r"analytics\.|gtag|googletagmanager|stats\.|matomo|piwik", "analytics"),
    (r"pixel\.|track\.|adserv|doubleclick|adsystem", "tracking"),
    (r"cdn\.|static\.|assets\.|cache\.|\.akamaized\.net|\.cloudfront\.net|\.fastly\.net", "cdn"),
    (r"mail\.|smtp\.|mx\.|outlook\.", "email"),
]

_ORG_PATTERNS: list[tuple[str, str]] = [
    (r"cloudflare|akamai|fastly|cloudfront|bunny|incapsula|stackpath|keycdn|cdn77", "cdn"),
    (r"facebook|pinterest|doubleclick|hotjar|hubspot|linkedin|twitter|tiktok", "tracking"),
    (r"adobe|typekit", "fonts"),
    (r"amazon|aws|azure|microsoft|hetzner|ovh|scaleway|transip|strato|leaseweb|digitalocean|linode|vultr", "hosting"),
]


def _classify_org_category(org_key: str, hostnames: list[str], scan_url: str) -> str:
    """Classify an organisation into an impact category."""
    import re
    from urllib.parse import urlparse

    joined = " ".join(hostnames).lower()

    # Priority 1: hostname patterns
    for pattern, cat in _HOSTNAME_PATTERNS:
        if re.search(pattern, joined):
            return cat

    # Priority 2: org keywords
    for pattern, cat in _ORG_PATTERNS:
        if re.search(pattern, org_key):
            # Google special case
            if "google" in org_key:
                if re.search(r"fonts", joined):
                    return "fonts"
                if re.search(r"cloud|compute|storage", joined):
                    return "hosting"
                return "analytics"
            return cat
    if "google" in org_key:
        if re.search(r"fonts", joined):
            return "fonts"
        return "analytics"

    # Priority 3: fallback — first-party = hosting, else other
    scan_domain = urlparse(scan_url).netloc
    scan_base = ".".join(scan_domain.split(".")[-2:])
    for h in hostnames:
        h_base = ".".join(h.split(".")[-2:])
        if h_base == scan_base:
            return "hosting"

    return "other"


def _compute_weighted_average(
    ip_results: list[dict],
    hostname_ips: dict[str, list[str]],
    scan_url: str,
) -> float:
    """Compute impact-weighted sovereignty score.

    Groups IPs by organisation, classifies each org into a category,
    and returns a weighted average where hosting counts more than tracking.
    """
    # Build org map: org_key -> { level (worst), ips }
    org_map: dict[str, dict] = {}
    for r in ip_results:
        key = r["org"]
        if key not in org_map:
            org_map[key] = {"level": r["level"], "ips": set()}
        org_map[key]["ips"].add(r["ip"])
        if r["level"] < org_map[key]["level"]:
            org_map[key]["level"] = r["level"]

    # Build org -> hostnames from hostname_ips
    org_hostnames: dict[str, list[str]] = {k: [] for k in org_map}
    for hostname, ips in hostname_ips.items():
        for org_key, org in org_map.items():
            if any(ip in org["ips"] for ip in ips):
                if hostname not in org_hostnames[org_key]:
                    org_hostnames[org_key].append(hostname)

    # Classify and weight
    weighted_sum = 0.0
    weight_total = 0.0
    for org_key, org in org_map.items():
        cat = _classify_org_category(org_key, org_hostnames.get(org_key, []), scan_url)
        weight = _CATEGORY_WEIGHTS.get(cat, 2)
        weighted_sum += weight * org["level"]
        weight_total += weight

    if weight_total == 0:
        return 0.0
    return round(weighted_sum / weight_total, 1)


class ScanOrchestrator:
    def __init__(
        self,
        settings: Settings,
        geoip: GeoIPService | None,
        peeringdb: PeeringDBService,
        ripe_atlas: RipeAtlasService,
        capture: CaptureService,
        ripestat: RipeStatService,
    ):
        self._settings = settings
        self._geoip = geoip
        self._peeringdb = peeringdb
        self._ripe_atlas = ripe_atlas
        self._capture = capture
        self._ripestat = ripestat

    async def start_scan(self, session: AsyncSession, url: str) -> Scan:
        scan = Scan(url=url, status="pending")
        session.add(scan)
        await session.commit()
        await session.refresh(scan)
        return scan

    async def process_scan(self, session: AsyncSession, scan_id: uuid.UUID) -> None:
        scan = await session.get(Scan, scan_id)
        if not scan:
            return

        try:
            # Phase 1: Capture page
            scan.status = "scanning"
            await session.commit()

            capture_result = await self._capture.capture(scan.url)

            if capture_result.error:
                logger.error("Capture failed for %s: %s", scan.url, capture_result.error)
                scan.status = "error"
                await session.commit()
                return

            # Phase 2: Store discovered resources
            scan.status = "analyzing"
            await session.commit()

            for hostname, ips in capture_result.hostname_ips.items():
                for ip in ips:
                    resource = DiscoveredResource(
                        scan_id=scan.id,
                        url=f"https://{hostname}",
                        hostname=hostname,
                        ip_address=ip,
                        is_third_party=CaptureService.classify_third_party(scan.url, hostname),
                    )
                    session.add(resource)

            # Phase 3: Analyze each unique IP
            level_counter: Counter[int] = Counter()
            level_sum = 0
            ip_results: list[dict] = []  # Collect for weighted scoring

            for ip in capture_result.all_ips:
                geoip_result = self._geoip.lookup(ip) if self._geoip else None
                if not geoip_result:
                    level_counter[0] += 1
                    ip_analysis = IpAnalysis(
                        scan_id=scan.id,
                        ip_address=ip,
                        sovereignty_level=0,
                        sovereignty_label="Niet soeverein",
                    )
                    session.add(ip_analysis)
                    continue

                peeringdb_result = (
                    await self._peeringdb.lookup_asn(geoip_result.asn)
                    if geoip_result.asn
                    else None
                )

                # WATERFALL: determine parent company and country
                # Step 1: Override (highest priority — for known exceptions)
                parent, parent_country = self._peeringdb.get_override(
                    geoip_result.asn_org or "", geoip_result.asn
                )

                # Step 2: PeeringDB org country
                if parent_country is None and peeringdb_result:
                    if peeringdb_result.org_country:
                        parent = peeringdb_result.org_name
                        parent_country = peeringdb_result.org_country

                # Step 3: RIPEstat as fallback
                if parent_country is None and geoip_result.asn:
                    ripestat_country = await self._ripestat.get_country(geoip_result.asn)
                    if ripestat_country:
                        parent = peeringdb_result.org_name if peeringdb_result else geoip_result.asn_org
                        parent_country = ripestat_country

                jurisdiction = classify_jurisdiction(
                    geoip_result, peeringdb_result, parent, parent_country
                )

                ip_analysis = IpAnalysis(
                    scan_id=scan.id,
                    ip_address=ip,
                    asn=geoip_result.asn,
                    asn_org=geoip_result.asn_org,
                    country_code=geoip_result.country_code,
                    city=geoip_result.city,
                    latitude=geoip_result.latitude,
                    longitude=geoip_result.longitude,
                    peeringdb_org_name=peeringdb_result.org_name if peeringdb_result else None,
                    peeringdb_org_country=peeringdb_result.org_country if peeringdb_result else None,
                    parent_company=parent,
                    parent_company_country=parent_country,
                    sovereignty_level=jurisdiction.level,
                    sovereignty_label=jurisdiction.label,
                )
                session.add(ip_analysis)

                level_counter[jurisdiction.level] += 1
                level_sum += jurisdiction.level
                ip_results.append({
                    "ip": ip,
                    "org": (parent or geoip_result.asn_org or ip).lower(),
                    "level": jurisdiction.level,
                })

            # Phase 4: Summary — mark as error if no IPs found
            total = sum(level_counter.values())
            if total == 0:
                logger.warning("No IPs found for %s — marking as error", scan.url)
                scan.status = "error"
                await session.commit()
                return
            level_distribution = {str(k): level_counter.get(k, 0) for k in range(6)}
            average_level = round(level_sum / total, 1) if total > 0 else 0

            # Weighted average: group by org, classify by impact category
            weighted_average_level = _compute_weighted_average(
                ip_results, capture_result.hostname_ips, scan.url,
            )

            final_url = (
                capture_result.redirects[-1]
                if capture_result.redirects
                else scan.url
            )
            scan.summary = {
                "total_ips": total,
                "average_level": average_level,
                "weighted_average_level": weighted_average_level,
                "level_distribution": level_distribution,
                "total_hostnames": len(capture_result.hostname_ips),
                "third_party_hostnames": len(capture_result.third_party_domains),
                "cookies_total": len(capture_result.cookies),
                "third_party_cookies": sum(
                    1 for c in capture_result.cookies if c.get("third_party", False)
                ),
                "resource_tree": capture_result.resource_tree,
                "hostname_ips": {h: list(ips) for h, ips in capture_result.hostname_ips.items()},
                "original_url": scan.url,
                "final_url": final_url,
                "has_redirect": (
                    len(capture_result.redirects) > 0
                    and final_url != scan.url
                ),
            }
            scan.status = "done"
            scan.completed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception:
            logger.exception("Scan processing failed for %s", scan_id)
            scan.status = "error"
            await session.commit()
