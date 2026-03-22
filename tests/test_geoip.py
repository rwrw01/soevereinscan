import pytest
from unittest.mock import MagicMock, patch
from app.services.geoip import GeoIPService, GeoIPResult


def test_geoip_result_structure():
    result = GeoIPResult(
        asn=13335, asn_org="Cloudflare, Inc.", country_code="US", city=None,
        latitude=37.7749, longitude=-122.4194,
    )
    assert result.asn == 13335
    assert result.country_code == "US"
    assert result.latitude == 37.7749
    assert result.longitude == -122.4194


@patch("app.services.geoip.maxminddb.open_database")
def test_lookup_returns_result(mock_open):
    mock_asn_db = MagicMock()
    mock_asn_db.get.return_value = {
        "autonomous_system_number": 13335,
        "autonomous_system_organization": "Cloudflare, Inc.",
    }
    mock_country_db = MagicMock()
    mock_country_db.get.return_value = {
        "country": {"iso_code": "US"},
        "city": {"names": {"en": "San Francisco"}},
        "location": {"latitude": 37.7749, "longitude": -122.4194},
    }
    mock_open.side_effect = [mock_asn_db, mock_country_db]

    service = GeoIPService(asn_path="fake.mmdb", country_path="fake.mmdb")
    result = service.lookup("1.1.1.1")

    assert result.asn == 13335
    assert result.asn_org == "Cloudflare, Inc."
    assert result.country_code == "US"
    assert result.latitude == 37.7749
    assert result.longitude == -122.4194


@patch("app.services.geoip.maxminddb.open_database")
def test_lookup_handles_missing_data(mock_open):
    mock_asn_db = MagicMock()
    mock_asn_db.get.return_value = None
    mock_country_db = MagicMock()
    mock_country_db.get.return_value = None
    mock_open.side_effect = [mock_asn_db, mock_country_db]

    service = GeoIPService(asn_path="fake.mmdb", country_path="fake.mmdb")
    result = service.lookup("192.168.1.1")

    assert result.asn is None
    assert result.country_code is None
    assert result.latitude is None
    assert result.longitude is None
