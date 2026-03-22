import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ripe_atlas import RipeAtlasService, TracerouteHop


def test_traceroute_hop_structure():
    hop = TracerouteHop(hop_number=1, ip="1.1.1.1", rtt_ms=5.2)
    assert hop.hop_number == 1
    assert hop.ip == "1.1.1.1"


@pytest.mark.asyncio
async def test_create_measurement_returns_id():
    service = RipeAtlasService(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"measurements": [12345]}

    with patch.object(service, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        measurement_id = await service.create_traceroute("1.1.1.1")

    assert measurement_id == 12345


@pytest.mark.asyncio
async def test_get_results_parses_hops():
    service = RipeAtlasService(api_key="test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "result": [
                {"hop": 1, "result": [{"from": "10.0.0.1", "rtt": 1.5}]},
                {"hop": 2, "result": [{"from": "172.16.0.1", "rtt": 5.3}]},
            ]
        }
    ]

    with patch.object(service, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        hops = await service.get_results(12345)

    assert len(hops) == 2
    assert hops[0].hop_number == 1
    assert hops[0].ip == "10.0.0.1"
    assert hops[1].rtt_ms == 5.3
