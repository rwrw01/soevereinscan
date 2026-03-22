# SoevereinScan

Digitale soevereiniteitsscanner voor de Nederlandse publieke sector.

Analyseert welke buitenlandse diensten, servers en jurisdicties betrokken zijn bij een SaaS-applicatie. Regelgebaseerd: geen AI in de bevindingen. Gratis, open source, zelf gehost.

**Live:** [scan.publicvibes.nl/soeverein](https://scan.publicvibes.nl/soeverein/)

---

## Hoe het werkt

1. Voer de URL van een SaaS-dienst of website in
2. De scanner opent de pagina in een echte Chromium-browser (met anti-detectie)
3. Alle HTTP-verzoeken, domeinen en IP-adressen worden vastgelegd
4. Per IP-adres wordt het ASN, de organisatie, het land en het moederbedrijf bepaald
5. Elke dienst krijgt een soevereiniteitsniveau van 0 tot 5
6. Het resultaat toont welke keuzes de organisatie zelf kan beïnvloeden

## Soevereiniteitsniveaus

| Niveau | Label | Betekenis |
|:------:|-------|-----------|
| **5** | Volledig soeverein | EU-bedrijf, EU-servers, geen buitenlandse jurisdictie |
| **4** | Grotendeels soeverein | EU-bedrijf, EU-servers, minimale externe afhankelijkheden |
| **3** | Gedeeltelijk soeverein | EU-servers, maar moederbedrijf onbekend of buiten EU |
| **2** | Beperkt soeverein | Niet-EU moederbedrijf, maar data in EU |
| **1** | Minimaal soeverein | Niet-EU moederbedrijf, servers buiten EU |
| **0** | Niet soeverein | Volledig onder buitenlandse jurisdictie |

Indeling gebaseerd op het [DICTU-toetsingsinstrument Soevereiniteit Clouddiensten](https://www.dictu.nl/toetsingsinstrument-helpt-de-soevereiniteit-van-clouddiensten-te-beoordelen) (januari 2026) en de [Rijksvisie Digitale Soevereiniteit](https://www.rijksoverheid.nl/documenten/rapporten/2025/12/18/bijlage-2-visie-digitale-autonomie-en-soevereiniteit-van-de-overheid) (december 2025).

## Wat wordt gescand

- **Hosting** — waar draait de webserver (ASN, organisatie, land)
- **Third-party scripts** — analytics, tracking pixels, chat widgets
- **Fonts en CDN** — Google Fonts, Adobe Typekit, Cloudflare, Akamai
- **Cookies** — welke cookies worden gezet door welke domeinen
- **Afhankelijkheidsboom** — welk domein laadt welk ander domein
- **Serverlocaties** — wereldkaart met geolocatie van alle servers

## Scanresultaat

Het rapport toont:

- **Gemiddeld soevereiniteitsniveau** (0-5 schaal)
- **Uw keuzes** — diensten die de organisatie direct kan beïnvloeden (hosting, analytics, fonts, tracking)
- **Afhankelijkheidsboom** — visueel overzicht van alle geladen diensten
- **Serverlocaties** — wereldkaart met gekleurde dots per soevereiniteitsniveau
- **Detailtabel** — per IP-adres het ASN, organisatie, land, moederbedrijf en niveau

## Inspiratie en erkenning

Dit project is geïnspireerd door en bouwt voort op het werk van:

- **[Lookyloo](https://github.com/Lookyloo/lookyloo)** (CIRCL, Luxembourg) — het concept van website-analyse via browser-capture. SoevereinScan gebruikt twee kernbibliotheken uit het Lookyloo-ecosysteem: [PlaywrightCapture](https://github.com/Lookyloo/PlaywrightCapture) voor anti-detectie en cookie-consent-afhandeling, en [har2tree](https://github.com/Lookyloo/har2tree) voor cookie-analyse en afhankelijkheidsbomen.
- **[SoevereinProbe](https://soevereinprobe.nl/)** — vergelijkbaar concept voor soevereiniteitsanalyse (niet open source).
- **[urlscan.io](https://urlscan.io/)** — visuele website-analyse met domain tree en serverlocaties.

## Architectuur

- **Backend**: Python 3.12 + FastAPI
- **Capture engine**: PlaywrightCapture (Chromium met anti-detectie, cookie-consent, stealth mode)
- **Analyse**: har2tree (cookie-analyse, afhankelijkheidsboom)
- **GeoIP**: MaxMind GeoLite2 (ASN + City, lokale databases)
- **Moederbedrijf-mapping**: handmatige mapping van ~30 grote providers naar moederbedrijven
- **Database**: PostgreSQL 16 via SQLAlchemy (async)
- **Cache**: Redis (PeeringDB-cache, scan-deduplicatie)
- **Frontend**: Jinja2 templates, pure HTML/CSS/JS (geen framework, geen CDN)

## Deployment

Draait op een Hetzner VPS (ARM64) als onderdeel van de [sovereign-stack](https://github.com/rwrw01/sovereign-stack) met elite hardening:

| Maatregel | Details |
|-----------|---------|
| Reverse proxy | Traefik met CrowdSec WAF |
| Container hardening | `cap_drop: ALL`, `no-new-privileges`, `read_only` |
| Netwerk | Spoke-netwerk isolatie, egress filtering via DOCKER-USER iptables |
| Secrets | Docker secrets (geen env vars voor credentials) |
| Resources | App: 1 GB, PostgreSQL: 256 MB, Redis: 128 MB |

### Containers

| Container | Functie |
|-----------|---------|
| `soevereinscan-app` | FastAPI applicatie + Playwright/Chromium |
| `postgres-soevereinscan` | PostgreSQL 16 database |
| `redis-soevereinscan` | Redis cache |

### Lokaal draaien

```bash
git clone https://github.com/rwrw01/soevereinscan.git
cd soevereinscan
cp .env.example .env
docker compose up -d
# Open http://localhost:8000
```

### Standalone scan (CLI)

```bash
pip install -r requirements.txt
playwright install chromium
python -m uvicorn app.main:app --port 8000
# Open http://localhost:8000
```

## Databronnen

| Bron | Wat het levert | Kosten |
|------|---------------|--------|
| [PlaywrightCapture](https://github.com/Lookyloo/PlaywrightCapture) | HTTP-verzoeken, cookies, redirects, anti-detectie | Gratis (BSD-3) |
| [har2tree](https://github.com/Lookyloo/har2tree) | Cookie-analyse, afhankelijkheidsboom | Gratis (BSD-3) |
| [MaxMind GeoLite2](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/) | IP → ASN, organisatie, land, stad, coördinaten | Gratis (account vereist) |
| [PeeringDB](https://www.peeringdb.com/apidocs/) | ASN → organisatie, land, type netwerk | Gratis API |

## Zusterprojecten

SoevereinScan is onderdeel van de [PublicVibes](https://scan.publicvibes.nl) scanner-suite:

| Project | Functie |
|---------|---------|
| **[SiteGuardian](https://siteguardian.publicvibes.nl)** | Website compliance scanner (beveiliging, WCAG, privacy) |
| **[Git Guardian](https://gitguardian.publicvibes.nl)** | Repository compliance scanner (security, dependencies) |
| **SoevereinScan** | Digitale soevereiniteitsscanner |
| **[Transcriptie](https://transcriptie.publicvibes.nl)** | Vergadertranscriptie |

## Dependencies

### Runtime

| Package | Versie | Licentie | Doel |
|---------|--------|----------|------|
| FastAPI | 0.115.12 | MIT | Web framework |
| Uvicorn | 0.34.2 | BSD-3 | ASGI server |
| PlaywrightCapture | 1.37.1 | BSD-3 | Website capture met anti-detectie |
| har2tree | 1.37.0 | BSD-3 | Cookie-analyse, afhankelijkheidsboom |
| Playwright | 1.58.0 | Apache-2.0 | Browser automation |
| playwright-stealth | 2.0.2 | MIT | Bot-detectie bypass |
| maxminddb | 2.6.2 | Apache-2.0 | GeoLite2 MMDB lookups |
| httpx | 0.28.1 | BSD-3 | HTTP client (PeeringDB, RIPE Atlas) |
| asyncpg | 0.30.0 | Apache-2.0 | PostgreSQL async driver |
| SQLAlchemy | 2.0.40 | MIT | ORM |
| Alembic | 1.15.2 | MIT | Database migraties |
| Redis | 5.2.1 | MIT | Cache |
| Pydantic | 2.12.5 | MIT | Data validatie |
| pydantic-settings | 2.8.1 | MIT | Configuratie via env vars |
| Jinja2 | 3.1.6 | BSD-3 | HTML templates |

### Infrastructuur

| Software | Versie | Licentie | Doel |
|----------|--------|----------|------|
| PostgreSQL | 16-alpine | PostgreSQL License | Database |
| Redis | 7-alpine | BSD-3 | Cache |
| Docker | - | Apache-2.0 | Containerisatie |
| Traefik | 2.11 | MIT | Reverse proxy |
| CrowdSec | - | MIT | WAF/IPS |
| Chromium | - | BSD-3 | Headless browser voor captures |

### Databronnen

| Bron | Licentie | Doel |
|------|----------|------|
| MaxMind GeoLite2 | [GeoLite2 EULA](https://www.maxmind.com/en/geolite2/eula) | IP-geolocatie en ASN |
| PeeringDB | [AUP](https://www.peeringdb.com/aup) | ASN-organisatiegegevens |

## Bronnen

- [DICTU Toetsingsinstrument Soevereiniteit Clouddiensten (2026)](https://www.dictu.nl/toetsingsinstrument-helpt-de-soevereiniteit-van-clouddiensten-te-beoordelen)
- [Rijksvisie Digitale Autonomie en Soevereiniteit (2025)](https://www.rijksoverheid.nl/documenten/rapporten/2025/12/18/bijlage-2-visie-digitale-autonomie-en-soevereiniteit-van-de-overheid)
- [VNG Position Paper Digitale Autonomie (2025)](https://vng.nl/artikelen/raadgever-digitale-autonomie-en-cloud)
- [Lookyloo — CIRCL](https://github.com/Lookyloo/lookyloo)
- [IBD Dreigingsbeeld 2025-2026](https://vng.nl/nieuws/dreigingsbeeld-informatiebeveiliging-2025-2026-uit)
- [Informatiebeveiligingsdienst — Risico's Amerikaanse partij](https://www.informatiebeveiligingsdienst.nl/risicos-verwerking-persoonsgegevens-door-amerikaanse-partij/)

## Licentie

[EUPL-1.2](LICENSE)

Dit project is gratis ter beschikking gesteld vanuit [publicvibes.nl](https://publicvibes.nl), een open source initiatief van Ralph Wagter.
