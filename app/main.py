import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.routes import health, pages, scan
from app.services.capture import CaptureService
from app.services.geoip import GeoIPService
from app.services.peeringdb import PeeringDBService
from app.services.ripe_atlas import RipeAtlasService
from app.services.scanner import ScanOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = Settings()
_orchestrator: ScanOrchestrator | None = None


def get_orchestrator() -> ScanOrchestrator:
    if _orchestrator is None:
        raise RuntimeError("App not started yet")
    return _orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator

    geoip = None
    try:
        geoip = GeoIPService(asn_path=settings.geolite2_asn_path, country_path=settings.geolite2_country_path)
    except FileNotFoundError:
        logging.warning("GeoLite2 databases not found — GeoIP lookups disabled")

    peeringdb = PeeringDBService(redis_url=settings.redis_url, api_key=settings.peeringdb_api_key)
    ripe_atlas = RipeAtlasService(api_key=settings.ripe_atlas_api_key)
    capture = CaptureService()

    _orchestrator = ScanOrchestrator(
        settings=settings,
        geoip=geoip,
        peeringdb=peeringdb,
        ripe_atlas=ripe_atlas,
        capture=capture,
    )

    yield

    if geoip:
        geoip.close()
    await peeringdb.close()
    await ripe_atlas.close()
    _orchestrator = None


app = FastAPI(
    title="SoevereinScan",
    version="0.1.0",
    lifespan=lifespan,
    root_path="/soeverein",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(health.router)
app.include_router(scan.router)
app.include_router(pages.router)
