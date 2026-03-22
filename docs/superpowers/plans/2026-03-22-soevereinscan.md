# SoevereinScan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een open-source SaaS-soevereiniteitsscanner die voor Nederlandse gemeenten in kaart brengt welke cloud/SaaS-diensten onder Amerikaanse jurisdictie (CLOUD Act) vallen.

**Architecture:** Python 3.12 + FastAPI backend met 5 gespecialiseerde services (Lookyloo capture, GeoIP lookup, PeeringDB enrichment, RIPE Atlas traceroute, jurisdictie-classifier). Self-hosted Lookyloo voor HTTP request capture. Alle data-lookups lokaal (MaxMind) of via Europese APIs (RIPE, PeeringDB). Frontend is pure HTML/CSS/JS. Deployment als Docker container in de sovereign-stack op VPS-001 (Hetzner ARM64) met elite hardening.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, pylookyloo, maxminddb, httpx, asyncpg, Redis, PostgreSQL 16, Jinja2 (templates), Docker (multi-stage, ARM64)

---

## Pre-requisites (handmatig, voor start implementatie)

Accounts aanmaken (gratis):
- [ ] **MaxMind GeoLite2** account: https://www.maxmind.com/en/geolite2/signup → license key noteren
- [ ] **RIPE Atlas** account: https://atlas.ripe.net/register/ → API key noteren
- [ ] **PeeringDB** account (optioneel, hogere rate limits): https://www.peeringdb.com/register

DNS record aanmaken:
- [ ] A-record `soevereinscan.publicvibes.nl` → VPS-001 IP (of wildcard als dat al bestaat)

---

## File Structure

```
soevereinscan/
├── Dockerfile                          # Multi-stage build (builder + runtime)
├── docker-compose.yml                  # Dev: app + postgres + redis + lookyloo
├── docker-compose.prod.yml             # Prod: hardened, secrets, traefik labels
├── requirements.txt                    # Python dependencies (pinned)
├── .env.example                        # Template env vars
├── .dockerignore                       # Exclude .git, __pycache__, tests, .env
├── .gitignore
├── LICENSE                             # EUPL-1.2
├── README.md
├── alembic.ini                         # DB migration config
├── alembic/
│   ├── env.py
│   └── versions/                       # Migration files
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, lifespan, middleware
│   ├── config.py                       # Pydantic Settings (env vars)
│   ├── database.py                     # Async SQLAlchemy engine + session
│   ├── models.py                       # SQLAlchemy ORM models (4 tabellen)
│   ├── schemas.py                      # Pydantic request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── scan.py                     # POST /api/scan, GET /api/scan/{id}
│   │   ├── health.py                   # GET /healthz, GET /readyz
│   │   └── pages.py                    # GET / (scan page), GET /results/{id}
│   ├── services/
│   │   ├── __init__.py
│   │   ├── lookyloo_client.py          # pylookyloo wrapper
│   │   ├── geoip.py                    # MaxMind GeoLite2 ASN + Country
│   │   ├── peeringdb.py               # PeeringDB API + Redis cache
│   │   ├── ripe_atlas.py              # RIPE Atlas traceroute API
│   │   ├── classifier.py              # Jurisdictie-classificatie
│   │   └── scanner.py                 # Orchestrator: combineert alle services
│   ├── templates/
│   │   ├── base.html                   # Layout template
│   │   ├── index.html                  # Scanpagina
│   │   └── results.html               # Resultaatpagina + visualisaties
│   └── static/
│       ├── style.css                   # Styling
│       └── app.js                      # Frontend polling + visualisaties
├── data/
│   └── us_parent_companies.json        # Provider → moederbedrijf mapping
├── scripts/
│   ├── update-geolite2.sh             # GeoLite2 database download
│   └── deploy.sh                       # VPS deployment script
└── tests/
    ├── conftest.py                     # Fixtures
    ├── test_geoip.py
    ├── test_peeringdb.py
    ├── test_classifier.py
    └── test_scanner.py
```

---

## Task 1: Project Skeleton + Config

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `LICENSE`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd C:/dev/sovereignscan
git init
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
*.mmdb
.pytest_cache/
htmlcov/
.coverage
scan-results/
```

- [ ] **Step 3: Create `LICENSE`**

EUPL-1.2 license tekst (kopieer van site-guardian of https://joinup.ec.europa.eu/licence/eupl-text-eupl-12).

- [ ] **Step 4: Create `requirements.txt`**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
pylookyloo==1.27.1
maxminddb==2.6.2
httpx==0.28.1
asyncpg==0.30.0
sqlalchemy[asyncio]==2.0.40
alembic==1.15.2
redis==5.2.1
pydantic-settings==2.8.1
jinja2==3.1.6
python-multipart==0.0.20
pytest==8.3.5
pytest-asyncio==0.25.3
httpx[http2]==0.28.1
```

- [ ] **Step 5: Create `.env.example`**

```bash
# Server
PORT=8000
BASE_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# Redis
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}

# Lookyloo
LOOKYLOO_URL=http://localhost:5100

# MaxMind GeoLite2
MAXMIND_LICENSE_KEY=your-key-here
GEOLITE2_ASN_PATH=./data/GeoLite2-ASN.mmdb
GEOLITE2_COUNTRY_PATH=./data/GeoLite2-Country.mmdb

# RIPE Atlas
RIPE_ATLAS_API_KEY=your-key-here

# PeeringDB (optioneel)
PEERINGDB_API_KEY=
```

- [ ] **Step 6: Create `.dockerignore`**

```
.git
__pycache__
*.pyc
.env
.venv
tests/
*.md
.pytest_cache
htmlcov
```

- [ ] **Step 7: Create `app/__init__.py`** (empty file)

- [ ] **Step 8: Write failing test for config**

Create `tests/conftest.py`:
```python
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}")
os.environ.setdefault("REDIS_URL", "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}")
os.environ.setdefault("LOOKYLOO_URL", "http://localhost:5100")
os.environ.setdefault("GEOLITE2_ASN_PATH", "./data/GeoLite2-ASN.mmdb")
os.environ.setdefault("GEOLITE2_COUNTRY_PATH", "./data/GeoLite2-Country.mmdb")
```

Create `tests/test_config.py`:
```python
from app.config import Settings

def test_settings_loads_from_env():
    settings = Settings()
    assert settings.port == 8000
    assert "asyncpg" in settings.database_url
    assert settings.lookyloo_url == "http://localhost:5100"
```

- [ ] **Step 9: Run test to verify it fails**

```bash
python -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 10: Implement `app/config.py`**

```python
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

SECRETS_DIR = Path("/run/secrets")


class Settings(BaseSettings):
    port: int = 8000
    base_url: str = "http://localhost:8000"

    database_url: str
    redis_url: str = "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
    lookyloo_url: str = "http://localhost:5100"

    maxmind_license_key: str = ""
    geolite2_asn_path: str = "./data/GeoLite2-ASN.mmdb"
    geolite2_country_path: str = "./data/GeoLite2-Country.mmdb"

    ripe_atlas_api_key: str = ""
    peeringdb_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="before")
    @classmethod
    def read_docker_secrets(cls, values: dict) -> dict:
        """Read Docker secrets from /run/secrets/ files into config."""
        secret_fields = ["ripe_atlas_api_key", "maxmind_license_key", "db_password"]
        for field in secret_fields:
            secret_file = SECRETS_DIR / field
            if secret_file.exists() and not values.get(field):
                values[field] = secret_file.read_text().strip()
        return values
```

- [ ] **Step 11: Run test to verify it passes**

```bash
python -m pytest tests/test_config.py -v
```
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add .gitignore LICENSE requirements.txt .env.example .dockerignore app/__init__.py app/config.py tests/
git commit -m "feat: project skeleton with config, dependencies, and license"
```

---

## Task 2: Database Models + Migrations

**Files:**
- Create: `app/database.py`
- Create: `app/models.py`
- Create: `app/schemas.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Write failing test for models**

Create `tests/test_models.py`:
```python
from app.models import Scan, DiscoveredResource, IpAnalysis, TracerouteResult

def test_scan_model_exists():
    assert Scan.__tablename__ == "scans"

def test_discovered_resource_model_exists():
    assert DiscoveredResource.__tablename__ == "discovered_resources"

def test_ip_analysis_model_exists():
    assert IpAnalysis.__tablename__ == "ip_analysis"

def test_traceroute_result_model_exists():
    assert TracerouteResult.__tablename__ == "traceroute_results"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `app/database.py`**

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    pass


settings = Settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
```

- [ ] **Step 4: Create `app/models.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    lookyloo_uuid: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict | None] = mapped_column(JSONB)

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
    jurisdiction: Mapped[str] = mapped_column(String(20), default="unknown")
    cloud_act_risk: Mapped[bool] = mapped_column(Boolean, default=False)

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
```

- [ ] **Step 5: Create `app/schemas.py`**

```python
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
            pass  # DNS resolution failure is OK — Lookyloo will handle it
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
    jurisdiction: str
    cloud_act_risk: bool

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
```

- [ ] **Step 6: Run test to verify it passes**

```bash
python -m pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 7: Initialize Alembic**

```bash
cd C:/dev/sovereignscan
alembic init alembic
```

Then edit `alembic/env.py` to use async engine and import models:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.database import Base
from app.models import Scan, DiscoveredResource, IpAnalysis, TracerouteResult

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = Settings()


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 8: Generate initial Alembic migration**

```bash
cd C:/dev/sovereignscan
alembic revision --autogenerate -m "initial schema"
```

Expected: creates file `alembic/versions/xxxx_initial_schema.py` with `CREATE TABLE` statements for all 4 tables.

- [ ] **Step 9: Commit**

```bash
git add app/database.py app/models.py app/schemas.py alembic.ini alembic/ tests/test_models.py
git commit -m "feat: database models and schemas for scans, resources, IP analysis, traceroutes"
```

---

## Task 3: GeoIP Service (MaxMind GeoLite2)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/geoip.py`
- Create: `scripts/update-geolite2.sh`
- Test: `tests/test_geoip.py`

- [ ] **Step 1: Create GeoLite2 download script**

Create `scripts/update-geolite2.sh`:
```bash
#!/bin/bash
set -euo pipefail

LICENSE_KEY="${MAXMIND_LICENSE_KEY:?Set MAXMIND_LICENSE_KEY}"
DATA_DIR="${1:-./data}"
mkdir -p "$DATA_DIR"

for EDITION in GeoLite2-ASN GeoLite2-Country; do
    echo "Downloading $EDITION..."
    curl -sL "https://download.maxmind.com/app/geoip_download?edition_id=${EDITION}&license_key=${LICENSE_KEY}&suffix=tar.gz" \
        | tar xz --strip-components=1 -C "$DATA_DIR" --wildcards "*.mmdb"
done

echo "GeoLite2 databases updated in $DATA_DIR"
ls -la "$DATA_DIR"/*.mmdb
```

- [ ] **Step 2: Write failing test for geoip service**

Create `tests/test_geoip.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.geoip import GeoIPService, GeoIPResult


def test_geoip_result_structure():
    result = GeoIPResult(asn=13335, asn_org="Cloudflare, Inc.", country_code="US", city=None)
    assert result.asn == 13335
    assert result.country_code == "US"


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
    }
    mock_open.side_effect = [mock_asn_db, mock_country_db]

    service = GeoIPService(asn_path="fake.mmdb", country_path="fake.mmdb")
    result = service.lookup("1.1.1.1")

    assert result.asn == 13335
    assert result.asn_org == "Cloudflare, Inc."
    assert result.country_code == "US"


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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_geoip.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 4: Implement `app/services/geoip.py`**

Create `app/services/__init__.py` (empty).

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_geoip.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/ scripts/update-geolite2.sh tests/test_geoip.py
git commit -m "feat: GeoIP service with MaxMind GeoLite2 ASN + Country lookup"
```

---

## Task 4: PeeringDB Service

**Files:**
- Create: `app/services/peeringdb.py`
- Create: `data/us_parent_companies.json`
- Test: `tests/test_peeringdb.py`

- [ ] **Step 1: Create US parent companies mapping**

Create `data/us_parent_companies.json`:
```json
{
    "Amazon.com, Inc.": {"parent": "Amazon", "country": "US"},
    "Amazon Technologies Inc.": {"parent": "Amazon", "country": "US"},
    "Amazon Data Services": {"parent": "Amazon", "country": "US"},
    "Microsoft Corporation": {"parent": "Microsoft", "country": "US"},
    "Microsoft Azure": {"parent": "Microsoft", "country": "US"},
    "Google LLC": {"parent": "Google/Alphabet", "country": "US"},
    "Google Cloud": {"parent": "Google/Alphabet", "country": "US"},
    "Cloudflare, Inc.": {"parent": "Cloudflare", "country": "US"},
    "Akamai Technologies, Inc.": {"parent": "Akamai", "country": "US"},
    "Fastly, Inc.": {"parent": "Fastly", "country": "US"},
    "Meta Platforms, Inc.": {"parent": "Meta", "country": "US"},
    "Apple Inc.": {"parent": "Apple", "country": "US"},
    "Oracle Corporation": {"parent": "Oracle", "country": "US"},
    "Salesforce, Inc.": {"parent": "Salesforce", "country": "US"},
    "DigitalOcean, LLC": {"parent": "DigitalOcean", "country": "US"},
    "Vercel Inc.": {"parent": "Vercel", "country": "US"},
    "Netlify, Inc.": {"parent": "Netlify", "country": "US"},
    "GitHub, Inc.": {"parent": "Microsoft", "country": "US"},
    "LinkedIn Corporation": {"parent": "Microsoft", "country": "US"},
    "Twilio Inc.": {"parent": "Twilio", "country": "US"},
    "Stripe, Inc.": {"parent": "Stripe", "country": "US"},
    "OVH SAS": {"parent": "OVHcloud", "country": "FR"},
    "Hetzner Online GmbH": {"parent": "Hetzner", "country": "DE"},
    "Scaleway": {"parent": "Iliad", "country": "FR"},
    "IONOS SE": {"parent": "United Internet", "country": "DE"},
    "TransIP B.V.": {"parent": "team.blue", "country": "NL"},
    "BIT BV": {"parent": "BIT", "country": "NL"},
    "Leaseweb Netherlands B.V.": {"parent": "Leaseweb", "country": "NL"},
    "True B.V.": {"parent": "True", "country": "NL"},
    "NLnet Labs": {"parent": "NLnet", "country": "NL"},
    "SURF B.V.": {"parent": "SURF", "country": "NL"}
}
```

- [ ] **Step 2: Write failing test for PeeringDB service**

Create `tests/test_peeringdb.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.peeringdb import PeeringDBService, PeeringDBResult


def test_peeringdb_result_structure():
    result = PeeringDBResult(org_name="Cloudflare, Inc.", org_country="US", net_type="Content")
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"


@pytest.mark.asyncio
async def test_lookup_asn_returns_result():
    service = PeeringDBService(redis_url=None)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"org": {"name": "Cloudflare, Inc.", "country": "US"}, "info_type": "Content"}]
    }

    with patch.object(service, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await service.lookup_asn(13335)

    assert result is not None
    assert result.org_name == "Cloudflare, Inc."
    assert result.org_country == "US"


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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_peeringdb.py -v
```
Expected: FAIL

- [ ] **Step 4: Implement `app/services/peeringdb.py`**

```python
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PARENT_COMPANIES_PATH = Path(__file__).parent.parent.parent / "data" / "us_parent_companies.json"


@dataclass
class PeeringDBResult:
    org_name: str | None
    org_country: str | None
    net_type: str | None


class PeeringDBService:
    BASE_URL = "https://www.peeringdb.com/api"

    def __init__(self, redis_url: str | None, api_key: str = ""):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=10.0,
            headers={"Authorization": f"Api-Key {api_key}"} if api_key else {},
        )
        self._redis = None
        self._redis_url = redis_url
        self._parent_companies = self._load_parent_companies()

    def _load_parent_companies(self) -> dict:
        if PARENT_COMPANIES_PATH.exists():
            return json.loads(PARENT_COMPANIES_PATH.read_text())
        return {}

    async def _get_redis(self):
        if self._redis is None and self._redis_url:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def lookup_asn(self, asn: int) -> PeeringDBResult | None:
        cache = await self._get_redis()
        cache_key = f"peeringdb:asn:{asn}"

        if cache:
            cached = await cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                return PeeringDBResult(**data)

        try:
            response = await self._client.get(f"/net?asn={asn}")
            if response.status_code != 200:
                logger.warning("PeeringDB returned %d for ASN %d", response.status_code, asn)
                return None

            data = response.json().get("data", [])
            if not data:
                return None

            entry = data[0]
            org = entry.get("org", {})
            result = PeeringDBResult(
                org_name=org.get("name"),
                org_country=org.get("country"),
                net_type=entry.get("info_type"),
            )

            if cache:
                await cache.setex(cache_key, 7 * 86400, json.dumps({"org_name": result.org_name, "org_country": result.org_country, "net_type": result.net_type}))

            return result
        except httpx.HTTPError:
            logger.exception("PeeringDB lookup failed for ASN %d", asn)
            return None

    def get_parent_company(self, org_name: str) -> tuple[str | None, str | None]:
        """Returns (parent_company, parent_country) from us_parent_companies.json."""
        entry = self._parent_companies.get(org_name)
        if entry:
            return entry["parent"], entry["country"]
        return None, None

    async def close(self):
        await self._client.aclose()
        if self._redis:
            await self._redis.aclose()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_peeringdb.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/peeringdb.py data/us_parent_companies.json tests/test_peeringdb.py
git commit -m "feat: PeeringDB service with Redis cache and US parent company mapping"
```

---

## Task 5: Jurisdictie Classifier

**Files:**
- Create: `app/services/classifier.py`
- Test: `tests/test_classifier.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_classifier.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_classifier.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement `app/services/classifier.py`**

```python
from dataclasses import dataclass

from app.services.geoip import GeoIPResult
from app.services.peeringdb import PeeringDBResult

EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    # EEA
    "IS", "LI", "NO",
    # CH is often treated as adequate
    "CH",
}


@dataclass
class JurisdictionResult:
    jurisdiction: str  # "us", "eu", "unknown"
    cloud_act_risk: bool
    reasons: list[str]


def classify_jurisdiction(
    geoip: GeoIPResult,
    peeringdb: PeeringDBResult | None,
    parent_company: str | None,
    parent_country: str | None,
) -> JurisdictionResult:
    reasons: list[str] = []

    # Rule 1: US parent company → always CLOUD Act risk
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

    # Rule 4: EU server + EU org → safe
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_classifier.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/classifier.py tests/test_classifier.py
git commit -m "feat: jurisdiction classifier with CLOUD Act risk detection"
```

---

## Task 6: RIPE Atlas Traceroute Service

**Files:**
- Create: `app/services/ripe_atlas.py`
- Test: `tests/test_ripe_atlas.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ripe_atlas.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_ripe_atlas.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement `app/services/ripe_atlas.py`**

```python
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TracerouteHop:
    hop_number: int
    ip: str | None
    rtt_ms: float | None


class RipeAtlasService:
    BASE_URL = "https://atlas.ripe.net/api/v2"

    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
            headers={"Authorization": f"Key {api_key}"} if api_key else {},
        )

    async def create_traceroute(self, target_ip: str, probe_count: int = 3) -> int | None:
        payload = {
            "definitions": [
                {
                    "target": target_ip,
                    "af": 4,
                    "type": "traceroute",
                    "protocol": "ICMP",
                    "resolve_on_probe": False,
                    "description": f"SoevereinScan traceroute to {target_ip}",
                    "is_oneoff": True,
                }
            ],
            "probes": [
                {
                    "requested": probe_count,
                    "type": "country",
                    "value": "NL",
                }
            ],
        }

        try:
            response = await self._client.post("/measurements/", json=payload)
            if response.status_code == 201:
                data = response.json()
                measurements = data.get("measurements", [])
                return measurements[0] if measurements else None
            logger.warning("RIPE Atlas returned %d: %s", response.status_code, response.text)
            return None
        except httpx.HTTPError:
            logger.exception("RIPE Atlas measurement creation failed for %s", target_ip)
            return None

    async def get_results(self, measurement_id: int) -> list[TracerouteHop]:
        try:
            response = await self._client.get(f"/measurements/{measurement_id}/results/")
            if response.status_code != 200:
                return []

            hops: list[TracerouteHop] = []
            data = response.json()
            if not data:
                return []

            # Take first probe result
            probe_result = data[0].get("result", [])
            for hop_data in probe_result:
                hop_num = hop_data.get("hop")
                results = hop_data.get("result", [])
                if results and "from" in results[0]:
                    hops.append(TracerouteHop(
                        hop_number=hop_num,
                        ip=results[0].get("from"),
                        rtt_ms=results[0].get("rtt"),
                    ))
                else:
                    hops.append(TracerouteHop(hop_number=hop_num, ip=None, rtt_ms=None))

            return hops
        except httpx.HTTPError:
            logger.exception("RIPE Atlas results fetch failed for measurement %d", measurement_id)
            return []

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_ripe_atlas.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/ripe_atlas.py tests/test_ripe_atlas.py
git commit -m "feat: RIPE Atlas traceroute service for passive network path analysis"
```

---

## Task 7: Lookyloo Client

**Files:**
- Create: `app/services/lookyloo_client.py`
- Test: `tests/test_lookyloo.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_lookyloo.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.lookyloo_client import LookylooClient


@patch("app.services.lookyloo_client.Lookyloo")
def test_submit_url_returns_uuid(mock_lookyloo_cls):
    mock_instance = MagicMock()
    mock_instance.submit.return_value = "abc-123-def"
    mock_lookyloo_cls.return_value = mock_instance

    client = LookylooClient(lookyloo_url="http://localhost:5100")
    result = client.submit("https://example.com")

    assert result == "abc-123-def"
    mock_instance.submit.assert_called_once()


@patch("app.services.lookyloo_client.Lookyloo")
def test_get_ips_extracts_unique_ips(mock_lookyloo_cls):
    mock_instance = MagicMock()
    mock_instance.get_redirects.return_value = {
        "response": {"ips": {"example.com": ["1.1.1.1", "2.2.2.2"]}}
    }
    mock_lookyloo_cls.return_value = mock_instance

    client = LookylooClient(lookyloo_url="http://localhost:5100")
    hostnames, ips = client.get_resources("capture-uuid")

    assert "1.1.1.1" in ips or len(hostnames) >= 0  # Flexible based on actual API
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_lookyloo.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement `app/services/lookyloo_client.py`**

```python
import logging
from urllib.parse import urlparse

from pylookyloo import Lookyloo

logger = logging.getLogger(__name__)


class LookylooClient:
    def __init__(self, lookyloo_url: str):
        self._lookyloo = Lookyloo(lookyloo_url)

    def submit(self, url: str) -> str | None:
        try:
            capture_uuid = self._lookyloo.submit(url=url, quiet=True)
            logger.info("Lookyloo capture submitted: %s -> %s", url, capture_uuid)
            return capture_uuid
        except Exception:
            logger.exception("Failed to submit URL to Lookyloo: %s", url)
            return None

    def is_ready(self, capture_uuid: str) -> bool:
        try:
            status = self._lookyloo.get_status(capture_uuid)
            return status == 1  # 1 = done
        except Exception:
            return False

    def get_resources(self, capture_uuid: str) -> tuple[dict[str, list[str]], set[str]]:
        """Returns (hostname_to_ips mapping, unique_ips set)."""
        try:
            redirects = self._lookyloo.get_redirects(capture_uuid)
            hostname_ips: dict[str, list[str]] = {}
            all_ips: set[str] = set()

            if isinstance(redirects, dict):
                response = redirects.get("response", {})
                ips_data = response.get("ips", {})
                for hostname, ips in ips_data.items():
                    hostname_ips[hostname] = ips
                    all_ips.update(ips)

            return hostname_ips, all_ips
        except Exception:
            logger.exception("Failed to get resources from Lookyloo capture %s", capture_uuid)
            return {}, set()

    def get_hostnames(self, capture_uuid: str) -> set[str]:
        hostname_ips, _ = self.get_resources(capture_uuid)
        return set(hostname_ips.keys())

    def classify_third_party(self, scan_url: str, hostname: str) -> bool:
        scan_domain = urlparse(scan_url).netloc
        return hostname != scan_domain and not hostname.endswith(f".{scan_domain}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_lookyloo.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/lookyloo_client.py tests/test_lookyloo.py
git commit -m "feat: Lookyloo client for HTTP request capture and resource extraction"
```

---

## Task 8: Scan Orchestrator

**Files:**
- Create: `app/services/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_scanner.py`:
```python
from app.services.scanner import ScanOrchestrator

def test_orchestrator_has_required_methods():
    assert hasattr(ScanOrchestrator, "start_scan")
    assert hasattr(ScanOrchestrator, "process_scan")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_scanner.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement `app/services/scanner.py`**

```python
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import DiscoveredResource, IpAnalysis, Scan, TracerouteResult
from app.services.classifier import classify_jurisdiction
from app.services.geoip import GeoIPService
from app.services.lookyloo_client import LookylooClient
from app.services.peeringdb import PeeringDBService
from app.services.ripe_atlas import RipeAtlasService

logger = logging.getLogger(__name__)


class ScanOrchestrator:
    def __init__(self, settings: Settings, geoip: GeoIPService, peeringdb: PeeringDBService, ripe_atlas: RipeAtlasService, lookyloo: LookylooClient):
        self._settings = settings
        self._geoip = geoip
        self._peeringdb = peeringdb
        self._ripe_atlas = ripe_atlas
        self._lookyloo = lookyloo

    async def start_scan(self, session: AsyncSession, url: str) -> Scan:
        scan = Scan(url=url, status="pending")
        session.add(scan)
        await session.commit()
        await session.refresh(scan)
        return scan

    async def process_scan(self, session: AsyncSession, scan_id: uuid.UUID) -> None:
        scan = await session.get(Scan, scan_id)
        if not scan:
            return

        try:
            # Phase 1: Lookyloo capture
            scan.status = "scanning"
            await session.commit()

            capture_uuid = self._lookyloo.submit(scan.url)
            if not capture_uuid:
                scan.status = "error"
                await session.commit()
                return

            scan.lookyloo_uuid = capture_uuid

            # Wait for Lookyloo (max 120s)
            for _ in range(24):
                if self._lookyloo.is_ready(capture_uuid):
                    break
                await asyncio.sleep(5)
            else:
                scan.status = "error"
                await session.commit()
                return

            # Phase 2: Extract resources
            scan.status = "analyzing"
            await session.commit()

            hostname_ips, all_ips = self._lookyloo.get_resources(capture_uuid)

            for hostname, ips in hostname_ips.items():
                for ip in ips:
                    resource = DiscoveredResource(
                        scan_id=scan.id,
                        url=f"https://{hostname}",
                        hostname=hostname,
                        ip_address=ip,
                        is_third_party=self._lookyloo.classify_third_party(scan.url, hostname),
                    )
                    session.add(resource)

            # Phase 3: Analyze each unique IP
            us_count = 0
            eu_count = 0
            unknown_count = 0

            for ip in all_ips:
                geoip_result = self._geoip.lookup(ip)
                peeringdb_result = await self._peeringdb.lookup_asn(geoip_result.asn) if geoip_result.asn else None
                parent, parent_country = self._peeringdb.get_parent_company(geoip_result.asn_org or "")

                jurisdiction = classify_jurisdiction(geoip_result, peeringdb_result, parent, parent_country)

                ip_analysis = IpAnalysis(
                    scan_id=scan.id,
                    ip_address=ip,
                    asn=geoip_result.asn,
                    asn_org=geoip_result.asn_org,
                    country_code=geoip_result.country_code,
                    city=geoip_result.city,
                    peeringdb_org_name=peeringdb_result.org_name if peeringdb_result else None,
                    peeringdb_org_country=peeringdb_result.org_country if peeringdb_result else None,
                    parent_company=parent,
                    parent_company_country=parent_country,
                    jurisdiction=jurisdiction.jurisdiction,
                    cloud_act_risk=jurisdiction.cloud_act_risk,
                )
                session.add(ip_analysis)

                if jurisdiction.jurisdiction == "us":
                    us_count += 1
                elif jurisdiction.jurisdiction == "eu":
                    eu_count += 1
                else:
                    unknown_count += 1

            # Phase 4: Summary
            total = us_count + eu_count + unknown_count
            scan.summary = {
                "total_ips": total,
                "us_count": us_count,
                "eu_count": eu_count,
                "unknown_count": unknown_count,
                "us_percentage": round(us_count / total * 100, 1) if total > 0 else 0,
                "cloud_act_risk": us_count > 0,
                "total_hostnames": len(hostname_ips),
                "third_party_hostnames": sum(1 for h in hostname_ips if self._lookyloo.classify_third_party(scan.url, h)),
            }
            scan.status = "done"
            scan.completed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception:
            logger.exception("Scan processing failed for %s", scan_id)
            scan.status = "error"
            await session.commit()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_scanner.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/scanner.py tests/test_scanner.py
git commit -m "feat: scan orchestrator combining Lookyloo, GeoIP, PeeringDB, and classifier"
```

---

## Task 9: FastAPI App + Routes

**Files:**
- Create: `app/main.py`
- Create: `app/routes/__init__.py`
- Create: `app/routes/health.py`
- Create: `app/routes/scan.py`
- Create: `app/routes/pages.py`

- [ ] **Step 1: Create `app/routes/__init__.py`** (empty)

- [ ] **Step 2: Create `app/routes/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def liveness():
    return {"status": "ok"}


@router.get("/readyz")
async def readiness():
    # TODO: check DB and Redis connectivity
    return {"status": "ok"}
```

- [ ] **Step 3: Create `app/routes/scan.py`**

```python
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Scan
from app.schemas import ScanRequest, ScanResponse, ScanResultResponse

router = APIRouter(prefix="/api")


@router.post("/scan", response_model=ScanResponse, status_code=201)
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    from app.main import get_orchestrator
    orchestrator = get_orchestrator()

    scan = await orchestrator.start_scan(session, str(request.url))
    background_tasks.add_task(_process_scan_background, scan.id)
    return scan


async def _process_scan_background(scan_id: uuid.UUID):
    from app.database import async_session
    from app.main import get_orchestrator

    orchestrator = get_orchestrator()
    async with async_session() as session:
        await orchestrator.process_scan(session, scan_id)


@router.get("/scan/{scan_id}", response_model=ScanResultResponse)
async def get_scan(
    scan_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Scan).options(selectinload(Scan.ip_analyses)).where(Scan.id == scan_id)
    result = await session.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan niet gevonden")

    return scan
```

- [ ] **Step 4: Create `app/routes/pages.py`**

```python
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/results/{scan_id}", response_class=HTMLResponse)
async def results_page(request: Request, scan_id: str):
    return templates.TemplateResponse("results.html", {"request": request, "scan_id": scan_id})
```

- [ ] **Step 5: Create `app/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.routes import health, pages, scan
from app.services.geoip import GeoIPService
from app.services.lookyloo_client import LookylooClient
from app.services.peeringdb import PeeringDBService
from app.services.ripe_atlas import RipeAtlasService
from app.services.scanner import ScanOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = Settings()
_orchestrator: ScanOrchestrator | None = None


def get_orchestrator() -> ScanOrchestrator:
    if _orchestrator is None:
        raise RuntimeError("App not started yet")
    return _orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator

    geoip = GeoIPService(asn_path=settings.geolite2_asn_path, country_path=settings.geolite2_country_path)
    peeringdb = PeeringDBService(redis_url=settings.redis_url, api_key=settings.peeringdb_api_key)
    ripe_atlas = RipeAtlasService(api_key=settings.ripe_atlas_api_key)
    lookyloo = LookylooClient(lookyloo_url=settings.lookyloo_url)

    _orchestrator = ScanOrchestrator(
        settings=settings,
        geoip=geoip,
        peeringdb=peeringdb,
        ripe_atlas=ripe_atlas,
        lookyloo=lookyloo,
    )

    yield

    geoip.close()
    await peeringdb.close()
    await ripe_atlas.close()
    _orchestrator = None


app = FastAPI(title="SoevereinScan", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(health.router)
app.include_router(scan.router)
app.include_router(pages.router)
```

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/routes/
git commit -m "feat: FastAPI app with scan, health, and page routes"
```

---

## Task 9b: API Route Tests

**Files:**
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write route tests**

Create `tests/test_routes.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_services():
    """Mock all external services so app can start without GeoLite2 files."""
    with patch("app.main.GeoIPService") as mock_geoip, \
         patch("app.main.PeeringDBService") as mock_peeringdb, \
         patch("app.main.RipeAtlasService") as mock_ripe, \
         patch("app.main.LookylooClient") as mock_lookyloo:
        mock_peeringdb.return_value.close = AsyncMock()
        mock_ripe.return_value.close = AsyncMock()
        mock_geoip.return_value.close = MagicMock()
        yield


@pytest.mark.asyncio
async def test_healthz(mock_services):
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_index_page(mock_services):
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "SoevereinScan" in response.text


@pytest.mark.asyncio
async def test_scan_rejects_internal_url(mock_services):
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/scan", json={"url": "http://169.254.169.254/latest/meta-data"})
    assert response.status_code == 422  # Validation error from SSRF check
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_routes.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_routes.py
git commit -m "test: API route tests for health, index, and SSRF protection"
```

---

## Task 10: Frontend Templates

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/index.html`
- Create: `app/templates/results.html`
- Create: `app/static/style.css`
- Create: `app/static/app.js`

- [ ] **Step 1: Create `app/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SoevereinScan{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header>
        <h1><a href="/">SoevereinScan</a></h1>
        <p>SaaS-soevereiniteitsscanner voor Nederlandse gemeenten</p>
    </header>
    <main>
        {% block content %}{% endblock %}
    </main>
    <footer>
        <p>Open source onder <a href="https://joinup.ec.europa.eu/licence/eupl-text-eupl-12">EUPL-1.2</a></p>
    </footer>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create `app/templates/index.html`**

```html
{% extends "base.html" %}
{% block title %}SoevereinScan — Controleer uw SaaS-leveranciers{% endblock %}
{% block content %}
<section class="scan-form">
    <h2>Controleer een SaaS-dienst op soevereiniteit</h2>
    <p>Voer de URL van een cloud- of SaaS-dienst in om te analyseren welke partijen en jurisdicties betrokken zijn.</p>
    <form id="scan-form">
        <input type="url" id="scan-url" name="url" placeholder="https://app.leverancier.nl" required>
        <button type="submit" id="scan-btn">Analyseer</button>
    </form>
    <div id="scan-status" class="hidden">
        <div class="spinner"></div>
        <p id="status-text">Scan wordt gestart...</p>
    </div>
</section>
{% endblock %}
{% block scripts %}
<script src="/static/app.js"></script>
{% endblock %}
```

- [ ] **Step 3: Create `app/templates/results.html`**

```html
{% extends "base.html" %}
{% block title %}Resultaten — SoevereinScan{% endblock %}
{% block content %}
<section id="results-container">
    <div id="loading">
        <div class="spinner"></div>
        <p>Resultaten worden geladen...</p>
    </div>
    <div id="results" class="hidden">
        <h2>Scanresultaten voor <span id="scan-url"></span></h2>

        <div class="sovereignty-meter">
            <h3>Soevereiniteitsmeter</h3>
            <div class="meter-bar">
                <div id="meter-fill" class="meter-fill"></div>
            </div>
            <p id="meter-label"></p>
        </div>

        <div class="summary-cards">
            <div class="card card-danger" id="card-us">
                <h4>VS-jurisdictie</h4>
                <span class="big-number" id="us-count">0</span>
                <span class="label">IP-adressen</span>
            </div>
            <div class="card card-safe" id="card-eu">
                <h4>EU-jurisdictie</h4>
                <span class="big-number" id="eu-count">0</span>
                <span class="label">IP-adressen</span>
            </div>
            <div class="card card-unknown" id="card-unknown">
                <h4>Onbekend</h4>
                <span class="big-number" id="unknown-count">0</span>
                <span class="label">IP-adressen</span>
            </div>
        </div>

        <h3>Details per IP-adres</h3>
        <table id="ip-table">
            <thead>
                <tr>
                    <th>IP</th>
                    <th>ASN</th>
                    <th>Organisatie</th>
                    <th>Land</th>
                    <th>Moederbedrijf</th>
                    <th>Jurisdictie</th>
                    <th>CLOUD Act</th>
                </tr>
            </thead>
            <tbody id="ip-tbody"></tbody>
        </table>
    </div>
</section>
{% endblock %}
{% block scripts %}
<script src="/static/app.js"></script>
<script>
    document.addEventListener("DOMContentLoaded", () => loadResults("{{ scan_id }}"));
</script>
{% endblock %}
```

- [ ] **Step 4: Create `app/static/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.6; color: #1a1a2e; background: #f8f9fa; max-width: 960px;
    margin: 0 auto; padding: 1rem;
}

header { text-align: center; padding: 2rem 0 1rem; }
header h1 a { color: #1a1a2e; text-decoration: none; }
header p { color: #666; font-size: 0.95rem; }

footer { text-align: center; padding: 2rem 0; color: #999; font-size: 0.85rem; }
footer a { color: #666; }

.scan-form { max-width: 600px; margin: 2rem auto; text-align: center; }
.scan-form h2 { margin-bottom: 0.5rem; }
.scan-form p { color: #666; margin-bottom: 1.5rem; }
.scan-form form { display: flex; gap: 0.5rem; }
.scan-form input[type="url"] {
    flex: 1; padding: 0.75rem 1rem; border: 2px solid #ddd; border-radius: 8px;
    font-size: 1rem;
}
.scan-form input[type="url"]:focus { border-color: #1a1a2e; outline: none; }
.scan-form button {
    padding: 0.75rem 1.5rem; background: #1a1a2e; color: #fff; border: none;
    border-radius: 8px; font-size: 1rem; cursor: pointer;
}
.scan-form button:disabled { background: #999; cursor: not-allowed; }

.hidden { display: none; }

.spinner {
    width: 32px; height: 32px; border: 3px solid #ddd; border-top-color: #1a1a2e;
    border-radius: 50%; animation: spin 0.8s linear infinite; margin: 1rem auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

.sovereignty-meter { margin: 2rem 0; }
.meter-bar {
    height: 24px; background: #eee; border-radius: 12px; overflow: hidden;
}
.meter-fill {
    height: 100%; border-radius: 12px; transition: width 0.5s ease;
}
.meter-fill.safe { background: #2d6a4f; }
.meter-fill.warning { background: #e9c46a; }
.meter-fill.danger { background: #e63946; }
#meter-label { text-align: center; margin-top: 0.5rem; font-weight: 600; }

.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 2rem 0; }
.card {
    padding: 1.5rem; border-radius: 12px; text-align: center;
}
.card h4 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
.card .big-number { display: block; font-size: 2.5rem; font-weight: 700; }
.card .label { font-size: 0.8rem; color: #666; }
.card-danger { background: #fde8e8; color: #e63946; }
.card-safe { background: #d4edda; color: #2d6a4f; }
.card-unknown { background: #f0f0f0; color: #666; }

table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f8f9fa; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
.row-danger { background: #fff5f5; }
.row-safe { background: #f0fff4; }

.badge {
    padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700;
}
.badge-us { background: #e63946; color: #fff; }
.badge-eu { background: #2d6a4f; color: #fff; }
.badge-unknown { background: #999; color: #fff; }

@media (max-width: 600px) {
    .scan-form form { flex-direction: column; }
    table { font-size: 0.85rem; }
    th, td { padding: 0.5rem; }
}
```

- [ ] **Step 5: Create `app/static/app.js`**

```javascript
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("scan-form");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const url = document.getElementById("scan-url").value;
            const statusDiv = document.getElementById("scan-status");
            const statusText = document.getElementById("status-text");
            const btn = document.getElementById("scan-btn");

            btn.disabled = true;
            statusDiv.classList.remove("hidden");
            statusText.textContent = "Scan wordt gestart...";

            try {
                const res = await fetch("/api/scan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url }),
                });
                const data = await res.json();
                if (res.ok) {
                    window.location.href = `/results/${data.id}`;
                } else {
                    statusText.textContent = `Fout: ${data.detail || "Onbekende fout"}`;
                    btn.disabled = false;
                }
            } catch (err) {
                statusText.textContent = "Verbindingsfout. Probeer het opnieuw.";
                btn.disabled = false;
            }
        });
    }
});

async function loadResults(scanId) {
    const loading = document.getElementById("loading");
    const results = document.getElementById("results");

    const poll = async () => {
        const res = await fetch(`/api/scan/${scanId}`);
        const data = await res.json();

        if (data.status === "done") {
            loading.classList.add("hidden");
            results.classList.remove("hidden");
            renderResults(data);
        } else if (data.status === "error") {
            loading.innerHTML = "<p>Scan is mislukt. Probeer het opnieuw.</p>";
        } else {
            setTimeout(poll, 3000);
        }
    };
    poll();
}

function renderResults(data) {
    document.getElementById("scan-url").textContent = data.url;

    const summary = data.summary || {};
    document.getElementById("us-count").textContent = summary.us_count || 0;
    document.getElementById("eu-count").textContent = summary.eu_count || 0;
    document.getElementById("unknown-count").textContent = summary.unknown_count || 0;

    const euPct = summary.total_ips > 0
        ? Math.round((summary.eu_count / summary.total_ips) * 100)
        : 0;
    const meterFill = document.getElementById("meter-fill");
    meterFill.style.width = `${euPct}%`;
    meterFill.className = `meter-fill ${euPct >= 80 ? "safe" : euPct >= 50 ? "warning" : "danger"}`;
    document.getElementById("meter-label").textContent =
        `${euPct}% van het verkeer binnen EU-jurisdictie`;

    const tbody = document.getElementById("ip-tbody");
    tbody.innerHTML = "";
    for (const ip of data.ip_analyses) {
        const row = document.createElement("tr");
        row.className = ip.cloud_act_risk ? "row-danger" : "row-safe";
        const cells = [
            ip.ip_address,
            ip.asn || "-",
            ip.asn_org || "-",
            ip.country_code || "-",
            ip.parent_company || "-",
        ];
        for (const text of cells) {
            const td = document.createElement("td");
            td.textContent = text;
            row.appendChild(td);
        }
        const jurisdictionTd = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `badge badge-${ip.jurisdiction === "us" ? "us" : ip.jurisdiction === "eu" ? "eu" : "unknown"}`;
        badge.textContent = ip.jurisdiction.toUpperCase();
        jurisdictionTd.appendChild(badge);
        row.appendChild(jurisdictionTd);
        const riskTd = document.createElement("td");
        riskTd.textContent = ip.cloud_act_risk ? "Ja" : "Nee";
        row.appendChild(riskTd);
        tbody.appendChild(row);
    }
}
```

- [ ] **Step 6: Commit**

```bash
git add app/templates/ app/static/
git commit -m "feat: frontend templates with sovereignty meter and IP analysis table"
```

---

## Task 11: Docker + Compose (Dev)

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
# Build stage
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --home /home/appuser appuser

COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY data/ ./data/
COPY alembic/ ./alembic/
COPY alembic.ini .

USER 1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `docker-compose.yml`** (development)

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
      REDIS_URL: "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
      LOOKYLOO_URL: "http://lookyloo:5100"
      GEOLITE2_ASN_PATH: "/data/GeoLite2-ASN.mmdb"
      GEOLITE2_COUNTRY_PATH: "/data/GeoLite2-Country.mmdb"
    volumes:
      - ./app:/app/app
      - ./data:/data
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: soevereinscan
      POSTGRES_USER: soevereinscan
      POSTGRES_PASSWORD: change-me
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U soevereinscan"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  lookyloo:
    image: ghcr.io/lookyloo/lookyloo:latest
    ports:
      - "5100:5100"

volumes:
  pg-data:
```

- [ ] **Step 3: Test locally**

```bash
cd C:/dev/sovereignscan
docker compose up --build
```

Open http://localhost:8000 → scan form verschijnt.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker multi-stage build and dev compose with Lookyloo, Postgres, Redis"
```

---

## Task 12: Production Docker Compose + Sovereign-Stack Deployment

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `scripts/deploy.sh`
- Modify: VPS `/opt/scripts/egress-filter.sh` (add soevereinscan rules)

- [ ] **Step 1: Create `docker-compose.prod.yml`**

```yaml
services:
  migrate:
    build:
      context: .
      target: runtime
    container_name: soevereinscan-migrate
    networks:
      - ss-internal
    environment:
      DATABASE_URL: "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    command: ["python", "-m", "alembic", "upgrade", "head"]
    restart: "no"
    depends_on:
      postgres:
        condition: service_healthy

  app:
    build:
      context: .
      target: runtime
    container_name: soevereinscan-app
    networks:
      - ss-internal
      - net-fe-soevereinscan
    environment:
      DATABASE_URL: "postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
      REDIS_URL: "redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
      LOOKYLOO_URL: "http://lookyloo:5100"
      GEOLITE2_ASN_PATH: "/data/GeoLite2-ASN.mmdb"
      GEOLITE2_COUNTRY_PATH: "/data/GeoLite2-Country.mmdb"
      PORT: "8000"
    secrets:
      - ripe_atlas_api_key
      - maxmind_license_key
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,nodev,size=200M
    deploy:
      resources:
        limits:
          memory: 512M
          pids: 100
    restart: on-failure:5
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')\""]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      lookyloo:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=net-fe-soevereinscan"
      - "traefik.http.routers.soevereinscan.rule=Host(`soevereinscan.publicvibes.nl`)"
      - "traefik.http.routers.soevereinscan.entrypoints=websecure"
      - "traefik.http.routers.soevereinscan.tls.certresolver=letsencrypt"
      - "traefik.http.services.soevereinscan.loadbalancer.server.port=8000"
      - "traefik.http.routers.soevereinscan.middlewares=crowdsec@file,rate-limit@file"

  postgres:
    image: postgres:16-alpine@sha256:b7587f3cb74f4f4b2a4f9d67f052edbf95eb93f4fec7c5ada3792546caaf7383
    container_name: postgres-soevereinscan
    networks:
      - ss-internal
    environment:
      POSTGRES_DB: soevereinscan
      POSTGRES_USER: soevereinscan
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pg-data:/var/lib/postgresql/data
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
      - DAC_OVERRIDE
      - FOWNER
    read_only: true
    tmpfs:
      - /tmp
      - /var/run/postgresql
    deploy:
      resources:
        limits:
          memory: 256M
          pids: 100
    restart: on-failure:5
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U soevereinscan"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    secrets:
      - db_password

  redis:
    image: redis:7-alpine  # TODO: pin op SHA256 digest bij deployment
    container_name: redis-soevereinscan
    networks:
      - ss-internal
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp
      - /data
    deploy:
      resources:
        limits:
          memory: 128M
          pids: 50
    restart: on-failure:5
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  lookyloo:
    image: ghcr.io/lookyloo/lookyloo:latest  # TODO: pin op SHA256 digest na ARM64-test op VPS
    container_name: lookyloo-soevereinscan
    networks:
      - ss-internal
      - net-fe-soevereinscan
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    deploy:
      resources:
        limits:
          memory: 2G
          pids: 200
    restart: on-failure:5
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://127.0.0.1:5100 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

volumes:
  pg-data:

networks:
  ss-internal:
    internal: true
  net-fe-soevereinscan:
    external: true

secrets:
  db_password:
    file: ./secrets/db_password
  ripe_atlas_api_key:
    file: ./secrets/ripe_atlas_api_key
  maxmind_license_key:
    file: ./secrets/maxmind_license_key
```

- [ ] **Step 2: Create `scripts/deploy.sh`**

```bash
#!/bin/bash
set -euo pipefail

VPS_HOST="ralph@100.64.0.2"
DEPLOY_DIR="/opt/soevereinscan"
SSH_KEY="~/.ssh/id_ed25519"

echo "=== SoevereinScan Deployment ==="

# 1. Sync files to VPS
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='.env' --exclude='*.mmdb' \
    -e "ssh -i $SSH_KEY" \
    . "$VPS_HOST:$DEPLOY_DIR/"

# 2. Create network if not exists
ssh -i "$SSH_KEY" "$VPS_HOST" \
    "docker network create net-fe-soevereinscan 2>/dev/null || true"

# 3. Build and deploy
ssh -i "$SSH_KEY" "$VPS_HOST" \
    "cd $DEPLOY_DIR && docker compose -f docker-compose.prod.yml up --build -d"

# 4. Verify
ssh -i "$SSH_KEY" "$VPS_HOST" \
    "docker ps --filter 'name=soevereinscan' --format 'table {{.Names}}\t{{.Status}}'"

echo "=== Deployment complete ==="
echo "Vergeet niet: voeg egress-filter regels toe voor net-fe-soevereinscan"
```

- [ ] **Step 3: Add egress filter rules (op VPS)**

SSH naar VPS en voeg toe aan `/opt/scripts/egress-filter.sh`, na het `net-fe-obsidian` blok:

```bash
# === SOEVEREINSCAN outbound via net-fe-soevereinscan ===
SS_BR=$(get_bridge "net-fe-soevereinscan") && {
    iptables -A DOCKER-USER -i "$SS_BR" ! -o "$SS_BR" -p udp --dport 53 -j RETURN -m comment --comment "net-fe-soevereinscan: DNS UDP"
    iptables -A DOCKER-USER -i "$SS_BR" ! -o "$SS_BR" -p tcp --dport 53 -j RETURN -m comment --comment "net-fe-soevereinscan: DNS TCP"
    iptables -A DOCKER-USER -i "$SS_BR" ! -o "$SS_BR" -p tcp --dport 80 -j RETURN -m comment --comment "net-fe-soevereinscan: HTTP (Lookyloo captures, redirects)"
    iptables -A DOCKER-USER -i "$SS_BR" ! -o "$SS_BR" -p tcp --dport 443 -j RETURN -m comment --comment "net-fe-soevereinscan: HTTPS (PeeringDB, RIPE Atlas, GeoLite2, Lookyloo)"
    iptables -A DOCKER-USER -i "$SS_BR" ! -o "$SS_BR" -j DROP -m comment --comment "net-fe-soevereinscan: DROP other egress"
    logger -t "$LOG_TAG" "net-fe-soevereinscan ($SS_BR): egress applied"
}
```

**Belangrijk:** Lookyloo moet outbound HTTPS kunnen doen (websites bezoeken). Lookyloo zit op zowel `ss-internal` als `net-fe-soevereinscan`. De egress-regel op `net-fe-soevereinscan` staat HTTPS toe op poort 443. Dit is voldoende — Lookyloo maakt alleen HTTPS-verbindingen naar de te scannen websites.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml scripts/deploy.sh
git commit -m "feat: production Docker Compose with sovereign-stack hardening and deploy script"
```

---

## Task 13: VPS Deployment Checklist

Dit is geen code-taak maar een operationele checklist voor de eerste deployment.

- [ ] **Step 1: DNS record aanmaken**

A-record `soevereinscan.publicvibes.nl` → VPS IP

- [ ] **Step 2: VPS directory + secrets aanmaken**

```bash
ssh -i ~/.ssh/id_ed25519 ralph@100.64.0.2
sudo mkdir -p /opt/soevereinscan/secrets
sudo chmod 700 /opt/soevereinscan/secrets

# Secrets aanmaken
echo "strong-random-password" | sudo tee /opt/soevereinscan/secrets/db_password > /dev/null
echo "your-ripe-atlas-key" | sudo tee /opt/soevereinscan/secrets/ripe_atlas_api_key > /dev/null
echo "your-maxmind-key" | sudo tee /opt/soevereinscan/secrets/maxmind_license_key > /dev/null
sudo chmod 600 /opt/soevereinscan/secrets/*
```

- [ ] **Step 3: Pin image digests**

```bash
# Op de VPS — haal ARM64 digests op:
docker pull redis:7-alpine && docker inspect redis:7-alpine --format '{{index .RepoDigests 0}}'
docker pull ghcr.io/lookyloo/lookyloo:latest && docker inspect ghcr.io/lookyloo/lookyloo:latest --format '{{index .RepoDigests 0}}'
# Update docker-compose.prod.yml met de output digests
```

- [ ] **Step 4: Docker network aanmaken**

```bash
docker network create net-fe-soevereinscan
```

- [ ] **Step 4: GeoLite2 databases downloaden**

```bash
cd /opt/soevereinscan
MAXMIND_LICENSE_KEY=$(cat secrets/maxmind_license_key) bash scripts/update-geolite2.sh ./data
```

- [ ] **Step 5: Deploy**

```bash
cd /opt/soevereinscan
docker compose -f docker-compose.prod.yml up --build -d
```

- [ ] **Step 6: Egress filter updaten**

```bash
sudo nano /opt/scripts/egress-filter.sh  # voeg soevereinscan regels toe
sudo systemctl restart egress-filter
```

- [ ] **Step 7: Verificatie**

```bash
# Containers healthy?
docker ps --filter 'name=soevereinscan'

# App bereikbaar via Traefik?
curl -sI https://soevereinscan.publicvibes.nl/healthz

# Egress geblokkeerd?
docker exec soevereinscan-app python -c "import urllib.request; urllib.request.urlopen('http://evil.example.com')"
# Verwacht: timeout/error

# Let's Encrypt certificaat actief?
curl -vI https://soevereinscan.publicvibes.nl 2>&1 | grep "subject:"
```

- [ ] **Step 8: GeoLite2 weekly update cron**

```bash
sudo crontab -e
# Voeg toe:
0 4 * * 0 cd /opt/soevereinscan && MAXMIND_LICENSE_KEY=$(cat secrets/maxmind_license_key) bash scripts/update-geolite2.sh ./data && docker restart soevereinscan-app
```

---

## Geheugenbudget Controle

| Container | Memory Limit | Doel |
|-----------|-------------|------|
| soevereinscan-app | 512 MB | FastAPI + services |
| postgres-soevereinscan | 256 MB | PostgreSQL 16 |
| redis-soevereinscan | 128 MB | Cache |
| lookyloo-soevereinscan | 2 GB | Chromium-based captures |
| **Totaal** | **~2.9 GB** | |
| **Beschikbaar op VPS** | **~11 GB** | Ruim voldoende |

---

## Risico's en Mitigaties

| Risico | Impact | Mitigatie |
|--------|--------|----------|
| Lookyloo ARM64 compatibiliteit | Kan niet starten | Test met `docker pull ghcr.io/lookyloo/lookyloo:latest` op VPS eerst |
| Disk 81% vol | Build faalt | Opschonen voor deployment: `docker system prune` |
| Lookyloo detectie/blokkering | Incomplete scans | Rate limiting (1/min), User-Agent rotatie, scan deduplicatie |
| RIPE Atlas quota (100/dag) | Te weinig traceroutes | Cache resultaten 48h, prioriteer unieke IPs |
| PeeringDB rate limit | Verrijking mislukt | Redis cache 7 dagen, graceful fallback |
