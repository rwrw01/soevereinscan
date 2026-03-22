from dataclasses import dataclass, field

from app.services.geoip import GeoIPResult
from app.services.peeringdb import PeeringDBResult

EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO",
    "CH",
}


@dataclass
class JurisdictionResult:
    jurisdiction: str  # "us", "eu", "unknown"
    cloud_act_risk: bool
    reasons: list[str] = field(default_factory=list)


def classify_jurisdiction(
    geoip: GeoIPResult,
    peeringdb: PeeringDBResult | None,
    parent_company: str | None,
    parent_country: str | None,
) -> JurisdictionResult:
    reasons: list[str] = []

    # Rule 1: US parent company -> always CLOUD Act risk
    if parent_country == "US":
        reasons.append(f"Moederbedrijf {parent_company} is Amerikaans")
        return JurisdictionResult(jurisdiction="us", cloud_act_risk=True, reasons=reasons)

    # Rule 2: PeeringDB org country is US
    if peeringdb and peeringdb.org_country == "US":
        reasons.append(f"ASN-eigenaar {peeringdb.org_name} is gevestigd in de VS")
        return JurisdictionResult(jurisdiction="us", cloud_act_risk=True, reasons=reasons)

    # Rule 3: Server physically in US
    if geoip.country_code == "US":
        reasons.append("Server staat fysiek in de Verenigde Staten")
        return JurisdictionResult(jurisdiction="us", cloud_act_risk=True, reasons=reasons)

    # Rule 4: EU server + EU org -> safe
    if geoip.country_code in EU_COUNTRIES:
        if peeringdb and peeringdb.org_country in EU_COUNTRIES:
            reasons.append(f"Server in {geoip.country_code}, eigenaar in {peeringdb.org_country}")
            return JurisdictionResult(jurisdiction="eu", cloud_act_risk=False, reasons=reasons)
        if peeringdb is None and parent_country and parent_country in EU_COUNTRIES:
            reasons.append(f"Server in {geoip.country_code}, moederbedrijf in {parent_country}")
            return JurisdictionResult(jurisdiction="eu", cloud_act_risk=False, reasons=reasons)

    # Rule 5: Not enough info
    if geoip.country_code is None and peeringdb is None:
        reasons.append("Onvoldoende gegevens voor classificatie")
        return JurisdictionResult(jurisdiction="unknown", cloud_act_risk=False, reasons=reasons)

    # Rule 6: Non-US, non-EU
    reasons.append(f"Server in {geoip.country_code or 'onbekend'}, nader onderzoek nodig")
    return JurisdictionResult(jurisdiction="unknown", cloud_act_risk=False, reasons=reasons)
