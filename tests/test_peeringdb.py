import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.peeringdb import PeeringDBService, PeeringDBResult


def test_peeringdb_result_structure():
    result = PeeringDBResult(org_name="Cloudflare, Inc.", org_country="US", net_type="Content")
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"


@pytest.mark.asyncio
async def test_lookup_asn_returns_result():
    service = PeeringDBService(redis_url=None)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"org": {"name": "Cloudflare, Inc.", "country": "US"}, "info_type": "Content"}]
    }

    with patch.object(service, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await service.lookup_asn(13335)

    assert result is not None
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"


@pytest.mark.asyncio
async def test_lookup_asn_not_found():
    service = PeeringDBService(redis_url=None)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    with patch.object(service, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await service.lookup_asn(99999999)

    assert result is None
