import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.peeringdb import PeeringDBService, PeeringDBResult


def test_peeringdb_result_structure():
    result = PeeringDBResult(org_name="Cloudflare, Inc.", org_country="US", net_type="Content")
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"


def test_peeringdb_result_new_fields():
    result = PeeringDBResult(
        org_name="Cloudflare, Inc.", org_country="US", net_type="Content",
        org_id=123, aka="CF"
    )
    assert result.org_id == 123
    assert result.aka == "CF"


@pytest.mark.asyncio
async def test_lookup_asn_returns_result():
    service = PeeringDBService(redis_url=None)

    net_response = MagicMock()
    net_response.status_code = 200
    net_response.json.return_value = {
        "data": [{"name": "Cloudflare, Inc.", "org_id": 456, "info_type": "Content", "aka": "CF"}]
    }

    org_response = MagicMock()
    org_response.status_code = 200
    org_response.json.return_value = {
        "data": [{"country": "US"}]
    }

    with patch.object(service, "_client") as mock_client:
        mock_client.get = AsyncMock(side_effect=[net_response, org_response])
        result = await service.lookup_asn(13335)

    assert result is not None
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"
    assert result.org_id == 456
    assert result.aka == "CF"


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


def test_get_override_exact_match():
    service = PeeringDBService(redis_url=None)
    parent, country = service.get_override("Akamai International B.V.")
    assert parent == "Akamai"
    assert country == "US"


def test_get_override_no_match():
    service = PeeringDBService(redis_url=None)
    parent, country = service.get_override("Some Unknown Org")
    assert parent is None
    assert country is None
