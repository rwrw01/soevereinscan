import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # gemeente, provincie, zbo, waterschap, ...
    website: Mapped[str] = mapped_column(String(2048), nullable=False)
    provincie: Mapped[str | None] = mapped_column(String(100))
    cbs_code: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scans: Mapped[list["Scan"]] = relationship(back_populates="organization")

    __table_args__ = (
        Index("ix_organizations_category", "category"),
        Index("ix_organizations_website", "website", unique=True),
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    lookyloo_uuid: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)

    organization: Mapped["Organization | None"] = relationship(back_populates="scans")
    resources: Mapped[list["DiscoveredResource"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    ip_analyses: Mapped[list["IpAnalysis"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    traceroutes: Mapped[list["TracerouteResult"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class DiscoveredResource(Base):
    __tablename__ = "discovered_resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    resource_type: Mapped[str | None] = mapped_column(String(50))
    is_third_party: Mapped[bool] = mapped_column(Boolean, default=False)

    scan: Mapped["Scan"] = relationship(back_populates="resources")


class IpAnalysis(Base):
    __tablename__ = "ip_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    asn: Mapped[int | None] = mapped_column(Integer)
    asn_org: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(255))
    peeringdb_org_name: Mapped[str | None] = mapped_column(String(255))
    peeringdb_org_country: Mapped[str | None] = mapped_column(String(2))
    parent_company: Mapped[str | None] = mapped_column(String(255))
    parent_company_country: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    sovereignty_level: Mapped[int] = mapped_column(Integer, default=0)
    sovereignty_label: Mapped[str] = mapped_column(String(50), default="Niet soeverein")

    scan: Mapped["Scan"] = relationship(back_populates="ip_analyses")


class TracerouteResult(Base):
    __tablename__ = "traceroute_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    target_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    hop_number: Mapped[int | None] = mapped_column(Integer)
    hop_ip: Mapped[str | None] = mapped_column(String(45))
    hop_asn: Mapped[int | None] = mapped_column(Integer)
    hop_asn_org: Mapped[str | None] = mapped_column(String(255))
    hop_country: Mapped[str | None] = mapped_column(String(2))
    rtt_ms: Mapped[float | None] = mapped_column(Float)

    scan: Mapped["Scan"] = relationship(back_populates="traceroutes")
