from dataclasses import dataclass

import maxminddb


@dataclass
class GeoIPResult:
    asn: int | None
    asn_org: str | None
    country_code: str | None
    city: str | None


class GeoIPService:
    def __init__(self, asn_path: str, country_path: str):
        self._asn_db = maxminddb.open_database(asn_path)
        self._country_db = maxminddb.open_database(country_path)

    def lookup(self, ip: str) -> GeoIPResult:
        asn_data = self._asn_db.get(ip)
        country_data = self._country_db.get(ip)

        asn = None
        asn_org = None
        country_code = None
        city = None

        if asn_data:
            asn = asn_data.get("autonomous_system_number")
            asn_org = asn_data.get("autonomous_system_organization")

        if country_data:
            country = country_data.get("country", {})
            country_code = country.get("iso_code") if country else None
            city_data = country_data.get("city", {})
            city = city_data.get("names", {}).get("en") if city_data else None

        return GeoIPResult(asn=asn, asn_org=asn_org, country_code=country_code, city=city)

    def close(self):
        self._asn_db.close()
        self._country_db.close()
