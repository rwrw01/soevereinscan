import uuid
from datetime import datetime
from pydantic import BaseModel, HttpUrl, field_validator

BLOCKED_NETWORKS = [
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10",
    "0.0.0.0/8", "::1/128", "fc00::/7", "fe80::/10",
]


class ScanRequest(BaseModel):
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def validate_not_internal(cls, v: HttpUrl) -> HttpUrl:
        import ipaddress
        import socket
        hostname = str(v).split("//")[1].split("/")[0].split(":")[0]
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            for network in BLOCKED_NETWORKS:
                if ip in ipaddress.ip_network(network):
                    raise ValueError(f"Interne/gereserveerde adressen zijn niet toegestaan: {hostname}")
        except socket.gaierror:
            pass
        return v


class ScanResponse(BaseModel):
    id: uuid.UUID
    url: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IpAnalysisResponse(BaseModel):
    ip_address: str
    asn: int | None
    asn_org: str | None
    country_code: str | None
    peeringdb_org_name: str | None
    peeringdb_org_country: str | None
    parent_company: str | None
    sovereignty_level: int
    sovereignty_label: str

    model_config = {"from_attributes": True}


class ScanResultResponse(BaseModel):
    id: uuid.UUID
    url: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    summary: dict | None
    ip_analyses: list[IpAnalysisResponse]

    model_config = {"from_attributes": True}
