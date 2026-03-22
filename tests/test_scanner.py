import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.scanner import ScanOrchestrator
from app.services.geoip import GeoIPResult


def _make_orchestrator():
    settings = MagicMock()
    geoip = MagicMock()
    peeringdb = MagicMock()
    ripe_atlas = MagicMock()
    lookyloo = MagicMock()
    return ScanOrchestrator(
        settings=settings,
        geoip=geoip,
        peeringdb=peeringdb,
        ripe_atlas=ripe_atlas,
        lookyloo=lookyloo,
    )


def test_orchestrator_has_start_and_process():
    orch = _make_orchestrator()
    assert callable(orch.start_scan)
    assert callable(orch.process_scan)


@pytest.mark.asyncio
async def test_start_scan_creates_pending_scan():
    orch = _make_orchestrator()
    session = AsyncMock()

    async def fake_refresh(scan):
        scan.id = uuid.uuid4()

    session.refresh = fake_refresh

    scan = await orch.start_scan(session, "https://example.com")
    assert scan.url == "https://example.com"
    assert scan.status == "pending"
    session.add.assert_called_once()
    session.commit.assert_called_once()
