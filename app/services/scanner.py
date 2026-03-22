import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import DiscoveredResource, IpAnalysis, Scan
from app.services.capture import CaptureService
from app.services.classifier import classify_jurisdiction
from app.services.geoip import GeoIPService
from app.services.peeringdb import PeeringDBService
from app.services.ripe_atlas import RipeAtlasService

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    def __init__(
        self,
        settings: Settings,
        geoip: GeoIPService | None,
        peeringdb: PeeringDBService,
        ripe_atlas: RipeAtlasService,
        capture: CaptureService,
    ):
        self._settings = settings
        self._geoip = geoip
        self._peeringdb = peeringdb
        self._ripe_atlas = ripe_atlas
        self._capture = capture

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
            us_count = 0
            eu_count = 0
            unknown_count = 0

            for ip in capture_result.all_ips:
                geoip_result = self._geoip.lookup(ip) if self._geoip else None
                if not geoip_result:
                    unknown_count += 1
                    ip_analysis = IpAnalysis(
                        scan_id=scan.id,
                        ip_address=ip,
                        jurisdiction="unknown",
                        cloud_act_risk=False,
                    )
                    session.add(ip_analysis)
                    continue

                peeringdb_result = (
                    await self._peeringdb.lookup_asn(geoip_result.asn)
                    if geoip_result.asn
                    else None
                )
                parent, parent_country = self._peeringdb.get_parent_company(
                    geoip_result.asn_org or ""
                )

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
                    peeringdb_org_name=peeringdb_result.org_name if peeringdb_result else None,
                    peeringdb_org_country=peeringdb_result.org_country if peeringdb_result else None,
                    parent_company=parent,
                    parent_company_country=parent_country,
                    jurisdiction=jurisdiction.jurisdiction,
                    cloud_act_risk=jurisdiction.cloud_act_risk,
                )
                session.add(ip_analysis)

                if jurisdiction.jurisdiction == "us":
                    us_count += 1
                elif jurisdiction.jurisdiction == "eu":
                    eu_count += 1
                else:
                    unknown_count += 1

            # Phase 4: Summary
            total = us_count + eu_count + unknown_count
            scan.summary = {
                "total_ips": total,
                "us_count": us_count,
                "eu_count": eu_count,
                "unknown_count": unknown_count,
                "us_percentage": round(us_count / total * 100, 1) if total > 0 else 0,
                "cloud_act_risk": us_count > 0,
                "total_hostnames": len(capture_result.hostname_ips),
                "third_party_hostnames": len(capture_result.third_party_domains),
                "cookies_total": len(capture_result.cookies),
                "third_party_cookies": sum(
                    1 for c in capture_result.cookies if c.get("third_party", False)
                ),
            }
            scan.status = "done"
            scan.completed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception:
            logger.exception("Scan processing failed for %s", scan_id)
            scan.status = "error"
            await session.commit()
