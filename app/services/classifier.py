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

# Countries with EU adequacy decision — not EU but considered adequate for data protection
ADEQUATE_COUNTRIES = {
    "GB",  # United Kingdom (post-Brexit adequacy decision)
    "JP",  # Japan
    "KR",  # South Korea
    "NZ",  # New Zealand
    "IL",  # Israel
    "CH",  # Switzerland (already in EU_COUNTRIES, but listed for completeness)
}

SOVEREIGNTY_LABELS = {
    5: "Volledig soeverein",
    4: "Grotendeels soeverein",
    3: "Gedeeltelijk soeverein",
    2: "Beperkt soeverein",
    1: "Minimaal soeverein",
    0: "Niet soeverein",
}


@dataclass
class JurisdictionResult:
    level: int  # 0-5
    label: str
    reasons: list[str] = field(default_factory=list)


def classify_jurisdiction(
    geoip: GeoIPResult,
    peeringdb: PeeringDBResult | None,
    parent_company: str | None,
    parent_country: str | None,
) -> JurisdictionResult:
    reasons: list[str] = []

    parent_in_eu = parent_country is not None and parent_country in EU_COUNTRIES
    parent_is_non_eu = parent_country is not None and parent_country not in EU_COUNTRIES
    server_in_eu = geoip.country_code is not None and geoip.country_code in EU_COUNTRIES
    peeringdb_in_eu = peeringdb is not None and peeringdb.org_country in EU_COUNTRIES
    peeringdb_known = peeringdb is not None and peeringdb.org_country is not None

    # Level 0: no data available, or explicitly non-EU everything
    if geoip.country_code is None and peeringdb is None and parent_country is None:
        reasons.append("Onvoldoende gegevens voor classificatie")
        return JurisdictionResult(level=0, label=SOVEREIGNTY_LABELS[0], reasons=reasons)

    # Level 5: parent in EU AND server in EU AND peeringdb org in EU
    if parent_in_eu and server_in_eu and peeringdb_in_eu:
        reasons.append(
            f"EU-bedrijf ({parent_company} in {parent_country}), "
            f"server in {geoip.country_code}, "
            f"netwerkeigenaar {peeringdb.org_name} in {peeringdb.org_country}"
        )
        return JurisdictionResult(level=5, label=SOVEREIGNTY_LABELS[5], reasons=reasons)

    # Level 4: parent in EU AND server in EU (peeringdb unknown is OK)
    if parent_in_eu and server_in_eu:
        reasons.append(
            f"EU-bedrijf ({parent_company} in {parent_country}), "
            f"server in {geoip.country_code}"
        )
        if not peeringdb_known:
            reasons.append("PeeringDB-gegevens niet beschikbaar")
        return JurisdictionResult(level=4, label=SOVEREIGNTY_LABELS[4], reasons=reasons)

    # Level 4 (alt): no parent from manual mapping, but PeeringDB confirms EU organization
    if server_in_eu and parent_country is None and peeringdb_in_eu:
        reasons.append(
            f"Server in {geoip.country_code}, "
            f"netwerkeigenaar {peeringdb.org_name} in {peeringdb.org_country} (PeeringDB)"
        )
        return JurisdictionResult(level=4, label=SOVEREIGNTY_LABELS[4], reasons=reasons)

    # Level 3: server in EU AND parent unknown AND peeringdb unknown
    # Important: do NOT catch non-EU parents here — those should fall through to level 2
    if server_in_eu and parent_country is None and not peeringdb_known:
        reasons.append(f"Server in {geoip.country_code}")
        if parent_country is None:
            reasons.append("Moederbedrijf onbekend")
        if not peeringdb_known:
            reasons.append("PeeringDB-gegevens niet beschikbaar")
        return JurisdictionResult(level=3, label=SOVEREIGNTY_LABELS[3], reasons=reasons)

    # Level 3 (adequate): parent in adequate country (GB, JP, etc.) and server in EU
    if server_in_eu and parent_country in ADEQUATE_COUNTRIES and parent_country not in EU_COUNTRIES:
        reasons.append(
            f"Moederbedrijf {parent_company} in {parent_country} (adequaatheidsbesluit), "
            f"server in {geoip.country_code}"
        )
        return JurisdictionResult(level=3, label=SOVEREIGNTY_LABELS[3], reasons=reasons)

    # Level 2: non-EU parent AND server in EU
    if parent_is_non_eu and server_in_eu:
        reasons.append(
            f"Moederbedrijf {parent_company} is gevestigd buiten de EU ({parent_country}), "
            f"maar data staat in {geoip.country_code}"
        )
        return JurisdictionResult(level=2, label=SOVEREIGNTY_LABELS[2], reasons=reasons)

    # Level 1: non-EU parent AND server NOT in EU (or server location unknown)
    if parent_is_non_eu and not server_in_eu:
        location = geoip.country_code or "onbekend (anycast/CDN)"
        reasons.append(
            f"Moederbedrijf {parent_company} is gevestigd buiten de EU ({parent_country}), "
            f"serverlocatie: {location}"
        )
        return JurisdictionResult(level=1, label=SOVEREIGNTY_LABELS[1], reasons=reasons)

    # Level 0: fallback — no data at all
    reasons.append(
        f"Server in {geoip.country_code or 'onbekend'}, "
        f"geen waarborgen voor digitale soevereiniteit vastgesteld"
    )
    return JurisdictionResult(level=0, label=SOVEREIGNTY_LABELS[0], reasons=reasons)
