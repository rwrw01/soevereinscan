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
    "doubleclick": "Tip: advertentietracking verwijderen",
    "hotjar": "Europees alternatief: Open Web Analytics",
}

CATEGORY_ALTERNATIVES = {
    "hosting": "Europese alternatieven: Hetzner (Duitsland), Scaleway (Frankrijk), OVHcloud (Frankrijk)",
    "cdn": "Europese alternatieven: Gcore (Luxemburg) en OVHcloud (Frankrijk)",
    "analytics": "Europees alternatief: Matomo of Fathom",
    "tracking": "Tip: overweeg of deze tracking noodzakelijk is voor uw website",
    "fonts": "Tip: lettertypen zelf hosten op uw eigen server",
}

SERVICE_ROLES = {
    "cloudflare": "Beveiligt en versnelt het laden van uw website",
    "akamai": "Beveiligt en versnelt het laden van uw website",
    "fastly": "Versnelt het laden van uw website",
    "cloudfront": "Versnelt het laden van uw website",
    "google": "Bezoekersstatistieken en analyse",
    "amazon": "Hosting van (delen van) uw website",
    "aws": "Hosting van (delen van) uw website",
    "microsoft": "Hosting of online diensten",
    "azure": "Hosting van (delen van) uw website",
    "adobe": "Levert lettertypen voor uw website",
    "typekit": "Levert lettertypen voor uw website",
    "facebook": "Volgt bezoekers voor advertenties",
    "pinterest": "Volgt bezoekers voor advertenties",
    "doubleclick": "Advertentietracking",
    "hotjar": "Analyseert bezoekersgedrag op uw website",
    "hetzner": "Hosting van (delen van) uw website",
    "ovh": "Hosting van (delen van) uw website",
    "scaleway": "Hosting van (delen van) uw website",
    "transip": "Hosting van (delen van) uw website",
    "leaseweb": "Hosting van (delen van) uw website",
}

US_PARENT_COMPANIES = {
    "amazon", "aws", "google", "microsoft", "azure", "meta", "facebook",
    "apple", "cloudflare", "akamai", "fastly", "adobe", "oracle",
    "ibm", "salesforce", "pinterest", "doubleclick", "hotjar",
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
    4: "Volledig soeverein",
    3: "Grotendeels soeverein",
    2: "Gedeeltelijk soeverein",
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

    # Import category classifier from scanner
    from app.services.scanner import _classify_org_category

    # Category definitions (mirrors JS SERVICE_CATEGORIES)
    pdf_categories = {
        "hosting":  {"label": "Hosting & infrastructuur",       "weight": 5},
        "cdn":      {"label": "Beveiliging & versnelling (CDN)", "weight": 3},
        "analytics":{"label": "Bezoekersstatistieken",          "weight": 1},
        "tracking": {"label": "Tracking & advertenties",        "weight": 1},
        "fonts":    {"label": "Lettertypen & hulpbestanden",    "weight": 0.5},
        "email":    {"label": "E-mail",                          "weight": 1},
        "other":    {"label": "Overige diensten",                "weight": 2},
    }
    category_order = ["hosting", "cdn", "analytics", "tracking", "fonts", "email", "other"]

    # Build services list with categories and alternatives
    services = []
    weighted_sum = 0.0
    weight_total = 0.0
    for key, org in sorted(org_map.items(), key=lambda x: x[1]["level"]):
        is_third_party = any(
            ".".join(h.split(".")[-2:]) != scan_base
            for h in org["hostnames"]
        )

        # Category classification
        cat_key = _classify_org_category(key, org["hostnames"], scan.url)

        # Alternative: provider-specific first, then category-based
        alt = None
        for kw, text in ALTERNATIVES.items():
            if kw in key:
                alt = text
                break
        if alt is None:
            alt = CATEGORY_ALTERNATIVES.get(cat_key)
        cat_def = pdf_categories.get(cat_key, pdf_categories["other"])
        weight = cat_def["weight"]
        weighted_sum += weight * org["level"]
        weight_total += weight

        # Service role from category
        role = None
        hostnames_lower = " ".join(org["hostnames"]).lower()
        if any(kw in hostnames_lower for kw in ("fonts", "typekit")):
            role = "Levert lettertypen voor uw website"
        elif any(kw in hostnames_lower for kw in ("analytics", "gtag", "googletagmanager")):
            role = "Bezoekersstatistieken en analyse"
        elif any(kw in hostnames_lower for kw in ("pixel", "track", "adserv")):
            role = "Volgt bezoekers voor advertenties"
        elif any(kw in hostnames_lower for kw in ("cdn", "static", "assets", "cache")):
            role = "Versnelt het laden van uw website"
        else:
            for kw, text in SERVICE_ROLES.items():
                if kw in key:
                    role = text
                    break

        # Parent company country note
        is_us_parent = any(c in key for c in US_PARENT_COMPANIES)
        country_display = org["country_name"]
        if is_us_parent and org.get("country") != "US":
            country_display += " (Amerikaans moederbedrijf)"

        services.append({
            **org,
            "alternative": alt,
            "role": role or "",
            "country_display": country_display,
            "category": cat_key,
            "category_label": cat_def["label"],
            "action": (
                "U kunt dit wijzigen"
                if is_third_party and org["level"] < 3
                else ""
            ),
        })

    # Group services by category for template
    services_by_category = []
    for cat_key in category_order:
        cat_services = [s for s in services if s.get("category") == cat_key]
        if cat_services:
            cat_services.sort(key=lambda s: s["level"])
            services_by_category.append({
                "label": pdf_categories[cat_key]["label"],
                "services": cat_services,
            })

    # Counts
    total_orgs = len(org_map)
    eu_count = sum(1 for o in org_map.values() if o["level"] >= 3)
    non_eu_count = sum(1 for o in org_map.values() if o["level"] <= 1)

    # Weighted average level (use backend value if available, else compute)
    avg = summary.get("weighted_average_level") or (
        round(weighted_sum / weight_total, 1) if weight_total > 0 else 0
    )

    # Energy label (based on weighted average, scale 0-4)
    if avg >= 3.6:
        label = "A"
    elif avg >= 3.0:
        label = "B"
    elif avg >= 2.0:
        label = "C"
    elif avg >= 1.0:
        label = "D"
    elif avg >= 0.5:
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
        "services_by_category": services_by_category,
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
        if org["level"] >= 3:
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
        kw in k and org_map[k]["level"] < 3
        for k in org_map
        for kw in ["google"]
    )
    has_infra = any(
        kw in k and org_map[k]["level"] < 3
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
            "estimated_score": "3.0",
            "estimated_label": "B",
        })
    return steps[:3]


def _build_questions(org_map: dict, hostname_ips: dict) -> list[str]:
    """Build relevant questions for the information advisor."""
    questions = []
    for org in org_map.values():
        if org["level"] <= 1:
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
    questions.append(
        "SoevereinScan controleert niet op cookiegebruik of privacywetgeving. "
        "Voor een scan op beveiliging, toegankelijkheid, privacy en cookiegebruik "
        "kunt u terecht bij SiteGuardian (siteguardian.publicvibes.nl)."
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
