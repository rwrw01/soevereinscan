from app.services.classifier import classify_jurisdiction, JurisdictionResult
from app.services.geoip import GeoIPResult
from app.services.peeringdb import PeeringDBResult


def test_level_5_eu_parent_eu_server_eu_peeringdb():
    geoip = GeoIPResult(asn=24940, asn_org="Hetzner Online GmbH", country_code="DE", city="Falkenstein", latitude=50.47, longitude=12.37)
    peeringdb = PeeringDBResult(org_name="Hetzner Online GmbH", org_country="DE", net_type="NSP")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Hetzner", parent_country="DE")
    assert result.level == 5
    assert result.label == "Volledig soeverein"


def test_level_4_eu_parent_eu_server_no_peeringdb():
    geoip = GeoIPResult(asn=24940, asn_org="Hetzner Online GmbH", country_code="DE", city="Falkenstein", latitude=50.47, longitude=12.37)
    result = classify_jurisdiction(geoip, None, parent_company="Hetzner", parent_country="DE")
    assert result.level == 4
    assert result.label == "Grotendeels soeverein"


def test_level_3_eu_server_unknown_parent():
    geoip = GeoIPResult(asn=24940, asn_org="Hetzner Online GmbH", country_code="DE", city="Falkenstein", latitude=50.47, longitude=12.37)
    result = classify_jurisdiction(geoip, None, parent_company=None, parent_country=None)
    assert result.level == 3
    assert result.label == "Gedeeltelijk soeverein"


def test_level_2_us_parent_eu_server():
    geoip = GeoIPResult(asn=16509, asn_org="Amazon.com, Inc.", country_code="DE", city="Frankfurt", latitude=50.11, longitude=8.68)
    peeringdb = PeeringDBResult(org_name="Amazon.com, Inc.", org_country="US", net_type="Content")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Amazon", parent_country="US")
    assert result.level == 2
    assert result.label == "Beperkt soeverein"


def test_level_1_us_parent_us_server():
    geoip = GeoIPResult(asn=16509, asn_org="Amazon.com, Inc.", country_code="US", city="Ashburn", latitude=39.04, longitude=-77.49)
    peeringdb = PeeringDBResult(org_name="Amazon.com, Inc.", org_country="US", net_type="Content")
    result = classify_jurisdiction(geoip, peeringdb, parent_company="Amazon", parent_country="US")
    assert result.level == 1
    assert result.label == "Minimaal soeverein"


def test_level_0_no_data():
    geoip = GeoIPResult(asn=None, asn_org=None, country_code=None, city=None, latitude=None, longitude=None)
    result = classify_jurisdiction(geoip, None, parent_company=None, parent_country=None)
    assert result.level == 0
    assert result.label == "Niet soeverein"


def test_level_3_eu_server_known_parent_unknown_peeringdb():
    """EU server with known EU parent but no peeringdb should be level 4, not 3."""
    geoip = GeoIPResult(asn=24940, asn_org="TransIP", country_code="NL", city="Amsterdam", latitude=52.37, longitude=4.89)
    result = classify_jurisdiction(geoip, None, parent_company="TransIP", parent_country="NL")
    assert result.level == 4
    assert result.label == "Grotendeels soeverein"
