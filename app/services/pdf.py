import logging
import uuid
from pathlib import Path

from jinja2 import Template
from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Scan

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report_pdf.html"

ALTERNATIVES = {
    "cloudflare": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
    "google": "Europees alternatief: Matomo of Fathom",
    "akamai": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
    "fastly": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
    "amazon": "Europese alternatieven: Hetzner (Duitsland), Scaleway (Frankrijk)",
    "microsoft": "Europese alternatieven: Nextcloud, Collabora",
    "adobe": "Tip: lettertypen zelf hosten op uw eigen server",
}

COUNTRY_NAMES = {
    "NL": "Nederland", "DE": "Duitsland", "US": "Verenigde Staten",
    "IE": "Ierland", "FR": "Frankrijk", "GB": "Verenigd Koninkrijk",
    "BE": "België", "SE": "Zweden", "FI": "Finland", "CH": "Zwitserland",
    "NO": "Noorwegen", "DK": "Denemarken", "AT": "Oostenrijk",
    "ES": "Spanje", "IT": "Italië", "PL": "Polen", "LU": "Luxemburg",
    "CZ": "Tsjechië", "JP": "Japan", "SG": "Singapore", "AU": "Australië",
    "CA": "Canada", "BR": "Brazilië",
}

SOVEREIGNTY_LABELS = {
    5: "Volledig soeverein",
    4: "Grotendeels soeverein",
    3: "Gedeeltelijk soeverein",
    2: "Beperkt soeverein",
    1: "Minimaal soeverein",
    0: "Niet soeverein",
}


async def generate_report_pdf(
    scan_id: str, session: AsyncSession
) -> bytes | None:
    """Generate a professionally formatted PDF report from scan data."""
    try:
        stmt = (
            select(Scan)
            .options(
                selectinload(Scan.ip_analyses),
                selectinload(Scan.resources),
            )
            .where(Scan.id == uuid.UUID(scan_id))
        )
        result = await session.execute(stmt)
        scan = result.scalar_one_or_none()

        if not scan or scan.status != "done":
            return None

        data = _build_template_data(scan)

        template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
        template = Template(template_str)
        html = template.render(**data)

        return await _html_to_pdf(html)
    except Exception:
        logger.exception("PDF generation failed for scan %s", scan_id)
        return None


def _build_template_data(scan: Scan) -> dict:
    """Build all template variables from scan data."""
    summary = scan.summary or {}
    ip_list = list(scan.ip_analyses)

    # Group by organisation
    org_map: dict = {}
    for ip in ip_list:
        key = (ip.parent_company or ip.asn_org or ip.ip_address).lower()
        if key not in org_map:
            org_map[key] = {
                "name": ip.parent_company or ip.asn_org or ip.ip_address,
                "country": ip.country_code,
                "country_name": COUNTRY_NAMES.get(
                    ip.country_code, ip.country_code or "Onbekend"
                ),
                "level": ip.sovereignty_level,
                "label": ip.sovereignty_label or SOVEREIGNTY_LABELS.get(
                    ip.sovereignty_level, ""
                ),
                "ips": [],
                "hostnames": [],
            }
        org_map[key]["ips"].append(ip.ip_address)
        if ip.sovereignty_level < org_map[key]["level"]:
            org_map[key]["level"] = ip.sovereignty_level
            org_map[key]["label"] = ip.sovereignty_label

    # Add hostnames from hostname_ips mapping
    hostname_ips = summary.get("hostname_ips", {})
    for hostname, ips in hostname_ips.items():
        for org in org_map.values():
            if any(ip in org["ips"] for ip in ips):
                if hostname not in org["hostnames"]:
                    org["hostnames"].append(hostname)

    # Extract scan domain for third-party detection
    scan_domain = (
        scan.url.replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )
    scan_base = ".".join(scan_domain.split(".")[-2:])

    # Build services list with alternatives
    services = []
    for key, org in sorted(org_map.items(), key=lambda x: x[1]["level"]):
        alt = None
        for kw, text in ALTERNATIVES.items():
            if kw in key:
                alt = text
                break
        is_third_party = any(
            ".".join(h.split(".")[-2:]) != scan_base
            for h in org["hostnames"]
        )
        services.append({
            **org,
            "alternative": alt,
            "action": (
                "U kunt dit wijzigen"
                if is_third_party and org["level"] < 4
                else ""
            ),
        })

    # Counts
    total_orgs = len(org_map)
    eu_count = sum(1 for o in org_map.values() if o["level"] >= 4)
    non_eu_count = sum(1 for o in org_map.values() if o["level"] <= 2)

    # Average level
    avg = summary.get("average_level", 0)

    # Energy label
    if avg >= 4.5:
        label = "A"
    elif avg >= 4.0:
        label = "B"
    elif avg >= 3.0:
        label = "C"
    elif avg >= 2.0:
        label = "D"
    elif avg >= 1.0:
        label = "E"
    else:
        label = "F"

    # Recommendations
    recs = _build_recommendations(org_map)

    # Improvement steps
    steps = _build_improvement_steps(org_map)

    # Questions
    questions = _build_questions(org_map, hostname_ips)

    # Distribution
    dist = summary.get("level_distribution", {})

    # Country bars
    country_counts: dict = {}
    for ip in ip_list:
        cn = COUNTRY_NAMES.get(
            ip.country_code, ip.country_code or "Onbekend"
        )
        country_counts[cn] = country_counts.get(cn, 0) + 1
    country_bars = sorted(country_counts.items(), key=lambda x: -x[1])

    # Resource tree
    tree = summary.get("resource_tree")

    # IP table
    ip_table = [
        {
            "ip": ip.ip_address,
            "asn": ip.asn,
            "org": ip.asn_org or "-",
            "country": COUNTRY_NAMES.get(
                ip.country_code, ip.country_code or "-"
            ),
            "parent": ip.parent_company or "-",
            "level": ip.sovereignty_level,
            "label": ip.sovereignty_label or "",
        }
        for ip in ip_list
    ]

    return {
        "url": scan.url,
        "scan_date": (scan.completed_at or scan.created_at).strftime(
            "%d %B %Y om %H:%M"
        ),
        "score": avg,
        "energy_label": label,
        "total_services": total_orgs,
        "eu_count": eu_count,
        "non_eu_count": non_eu_count,
        "recommendations": recs,
        "services": services,
        "improvement_steps": steps,
        "questions": questions,
        "distribution": dist,
        "tree": tree,
        "country_bars": country_bars,
        "ip_table": ip_table,
        "has_redirect": summary.get("has_redirect", False),
        "original_url": summary.get("original_url", scan.url),
        "final_url": summary.get("final_url", scan.url),
    }


def _build_recommendations(org_map: dict) -> list[dict]:
    """Build actionable recommendations based on detected services."""
    tips = {
        "google": {
            "text": "Stap over op een Europees analytics-pakket zoals "
                    "Matomo of Fathom.",
            "cost": "Weinig",
            "who": "Leverancier",
        },
        "facebook": {
            "text": "Verwijder de Meta/Facebook tracking pixel.",
            "cost": "Weinig",
            "who": "Leverancier",
        },
        "pinterest": {
            "text": "Verwijder de Pinterest tracking pixel.",
            "cost": "Weinig",
            "who": "Leverancier",
        },
        "cloudflare": {
            "text": "Bespreek een Europees CDN-alternatief "
                    "(Gcore, OVHcloud).",
            "cost": "Midden",
            "who": "Leverancier",
        },
        "akamai": {
            "text": "Bespreek een Europees CDN-alternatief "
                    "(Gcore, OVHcloud).",
            "cost": "Midden",
            "who": "Leverancier",
        },
        "fastly": {
            "text": "Bespreek een Europees CDN-alternatief "
                    "(Gcore, OVHcloud).",
            "cost": "Midden",
            "who": "Leverancier",
        },
        "amazon": {
            "text": "Bespreek Europese hosting-alternatieven "
                    "(Hetzner, Scaleway).",
            "cost": "Veel",
            "who": "Organisatie + Leverancier",
        },
        "microsoft": {
            "text": "Bespreek Europese alternatieven "
                    "(Nextcloud, Collabora).",
            "cost": "Veel",
            "who": "Organisatie + Leverancier",
        },
    }
    recs = []
    seen: set = set()
    for key, org in org_map.items():
        if org["level"] >= 4:
            continue
        for kw, tip in tips.items():
            if kw in key and kw not in seen:
                seen.add(kw)
                recs.append(tip)
                break
    return recs


def _build_improvement_steps(org_map: dict) -> list[dict]:
    """Build a simplified improvement roadmap."""
    steps = []
    has_tracking = any(
        kw in k
        for k in org_map
        for kw in ["facebook", "pinterest", "doubleclick", "hotjar"]
    )
    has_analytics = any(
        kw in k and org_map[k]["level"] < 4
        for k in org_map
        for kw in ["google"]
    )
    has_infra = any(
        kw in k and org_map[k]["level"] < 4
        for k in org_map
        for kw in ["cloudflare", "akamai", "fastly", "amazon", "microsoft"]
    )

    if has_tracking:
        steps.append({
            "title": "Verwijder onnodige tracking",
            "description": "Verwijder tracking pixels en advertentiediensten "
                           "die niet noodzakelijk zijn.",
            "effort": "1 dag",
            "who": "Leverancier",
            "estimated_score": "",
            "estimated_label": "",
        })
    if has_analytics:
        steps.append({
            "title": "Kies Europese bezoekersstatistieken",
            "description": "Vervang Google Analytics door Matomo of Fathom.",
            "effort": "1-2 weken",
            "who": "Leverancier",
            "estimated_score": "",
            "estimated_label": "",
        })
    if has_infra:
        steps.append({
            "title": "Bespreek Europese alternatieven voor infrastructuur",
            "description": "Bespreek met uw leverancier of hosting en CDN "
                           "bij een Europese partij ondergebracht "
                           "kunnen worden.",
            "effort": "1-6 maanden",
            "who": "Organisatie + Leverancier",
            "estimated_score": "4.0",
            "estimated_label": "B",
        })
    return steps[:3]


def _build_questions(org_map: dict, hostname_ips: dict) -> list[str]:
    """Build relevant questions for the information advisor."""
    questions = []
    for org in org_map.values():
        if org["level"] <= 2:
            questions.append(
                f"Heeft u een verwerkersovereenkomst met {org['name']}? "
                f"Staan daarin afspraken over subverwerkers buiten de EU?"
            )
    for hostname in hostname_ips:
        if any(kw in hostname for kw in ["cdn", "fonts", "static", "assets"]):
            questions.append(
                f"Is {hostname} standaard onderdeel van uw websitepakket, "
                f"of apart geconfigureerd?"
            )
            break
    questions.append(
        "Moet u op basis van deze bevindingen een DPIA "
        "(Data Protection Impact Assessment) uitvoeren?"
    )
    return questions


async def _html_to_pdf(html: str) -> bytes:
    """Convert HTML string to PDF using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(500)

        pdf_bytes = await page.pdf(
            format="A4",
            margin={
                "top": "20mm",
                "bottom": "25mm",
                "left": "15mm",
                "right": "15mm",
            },
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="width:100%;text-align:center;font-size:8pt;'
                'color:#999;padding:0 15mm">'
                "<span>SoevereinScan \u2014 scan.publicvibes.nl/soeverein"
                "</span>"
                '<span style="float:right">Pagina '
                '<span class="pageNumber"></span> / '
                '<span class="totalPages"></span></span></div>'
            ),
        )

        await browser.close()
        return pdf_bytes
