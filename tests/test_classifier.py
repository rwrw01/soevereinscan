from app.services.classifier import classify_jurisdiction, JurisdictionResult
from app.services.geoip import GeoIPResult
from app.services.peeringdb import PeeringDBResult


def test_us_server_us_org_is_cloud_act():
    geoip = GeoIPResult(asn=16509, asn_org="Amazon.com, Inc.", country_code="US", city="Ashburn")
    peeringdb = PeeringDBResult(org_name="Amazon.com, Inc.", org_country="US", net_type="Content")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Amazon", parent_country="US")
    assert result.jurisdiction == "us"
    assert result.cloud_act_risk is True


def test_eu_server_eu_org_is_safe():
    geoip = GeoIPResult(asn=24940, asn_org="Hetzner Online GmbH", country_code="DE", city="Falkenstein")
    peeringdb = PeeringDBResult(org_name="Hetzner Online GmbH", org_country="DE", net_type="NSP")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Hetzner", parent_country="DE")
    assert result.jurisdiction == "eu"
    assert result.cloud_act_risk is False


def test_eu_server_us_parent_is_cloud_act():
    geoip = GeoIPResult(asn=16509, asn_org="Amazon.com, Inc.", country_code="DE", city="Frankfurt")
    peeringdb = PeeringDBResult(org_name="Amazon.com, Inc.", org_country="US", net_type="Content")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Amazon", parent_country="US")
    assert result.jurisdiction == "us"
    assert result.cloud_act_risk is True


def test_unknown_when_no_data():
    geoip = GeoIPResult(asn=None, asn_org=None, country_code=None, city=None)
    result = classify_jurisdiction(geoip, None, parent_company=None, parent_country=None)
    assert result.jurisdiction == "unknown"
    assert result.cloud_act_risk is False
