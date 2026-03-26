"""
Import gemeenten into the organizations table and trigger bulk scans.

Usage:
  # Import only (no scanning):
  python scripts/import_and_scan_gemeenten.py --import-only

  # Import + scan all:
  python scripts/import_and_scan_gemeenten.py

  # Scan only (already imported):
  python scripts/import_and_scan_gemeenten.py --scan-only

Requires DATABASE_URL env var or .env file.
Run against the VPS database via SSH tunnel or directly.
"""
import argparse
import asyncio
import csv
import json
import uuid
from datetime import datetime, timezone

import asyncpg


async def get_connection(dsn: str) -> asyncpg.Connection:
    return await asyncpg.connect(dsn)


async def import_gemeenten(conn: asyncpg.Connection, csv_path: str) -> int:
    """Import gemeenten from CSV into organizations table."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    imported = 0
    skipped = 0
    for row in rows:
        naam = row["naam"]
        website = row["website"]
        provincie = row.get("provincie", "")
        cbs_code = row.get("cbs_code", "")

        if not website:
            print(f"  SKIP {naam}: geen website")
            skipped += 1
            continue

        # Check if already exists
        existing = await conn.fetchrow(
            "SELECT id FROM organizations WHERE website = $1", website
        )
        if existing:
            skipped += 1
            continue

        await conn.execute(
            """INSERT INTO organizations (id, name, category, website, provincie, cbs_code, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            uuid.uuid4(),
            naam,
            "gemeente",
            website,
            provincie or None,
            cbs_code or None,
            datetime.now(timezone.utc),
        )
        imported += 1

    print(f"Geimporteerd: {imported}, overgeslagen: {skipped}")
    return imported


async def trigger_bulk_scan(conn: asyncpg.Connection, api_base: str, category: str = "gemeente"):
    """Trigger scans for all organizations in a category via the API."""
    import aiohttp

    orgs = await conn.fetch(
        """SELECT id, name, website FROM organizations
           WHERE category = $1
           ORDER BY name""",
        category,
    )
    print(f"\n{len(orgs)} organisaties gevonden voor categorie '{category}'")

    # Check which ones already have a recent scan (last 7 days)
    scanned = set()
    recent = await conn.fetch(
        """SELECT DISTINCT o.id
           FROM organizations o
           JOIN scans s ON s.organization_id = o.id
           WHERE o.category = $1 AND s.status = 'done'
             AND s.created_at > NOW() - INTERVAL '7 days'""",
        category,
    )
    scanned = {r["id"] for r in recent}

    to_scan = [o for o in orgs if o["id"] not in scanned]
    print(f"Al gescand (afgelopen 7 dagen): {len(scanned)}")
    print(f"Te scannen: {len(to_scan)}")

    if not to_scan:
        print("Niets te scannen!")
        return

    # Scan in batches — the app has a semaphore of 2 concurrent scans
    # so we submit slowly to avoid overloading
    async with aiohttp.ClientSession() as http:
        success = 0
        errors = 0
        cached = 0
        for i, org in enumerate(to_scan):
            url = org["website"]
            name = org["name"]
            org_id = org["id"]

            try:
                resp = await http.post(
                    f"{api_base}/api/scan",
                    json={"url": url},
                    timeout=aiohttp.ClientTimeout(total=15),
                )
                data = await resp.json()

                if resp.status == 201:
                    scan_id = data.get("id")
                    # Link the scan to the organization
                    if scan_id:
                        await conn.execute(
                            "UPDATE scans SET organization_id = $1 WHERE id = $2",
                            org_id,
                            uuid.UUID(scan_id),
                        )
                    success += 1
                    status_text = "NEW" if data.get("status") == "queued" else "CACHED"
                    if status_text == "CACHED":
                        cached += 1
                elif resp.status == 200:
                    # Cached scan returned
                    scan_id = data.get("id")
                    if scan_id:
                        await conn.execute(
                            "UPDATE scans SET organization_id = $1 WHERE id = $2",
                            org_id,
                            uuid.UUID(scan_id),
                        )
                    cached += 1
                    success += 1
                    status_text = "CACHED"
                else:
                    errors += 1
                    status_text = f"ERR:{resp.status}"

                print(f"  [{i+1}/{len(to_scan)}] {status_text:8s} {name:40s} {url}")

            except Exception as e:
                errors += 1
                print(f"  [{i+1}/{len(to_scan)}] ERROR    {name:40s} {str(e)[:60]}")

            # Pace: wait between submissions to not overload
            if (i + 1) % 5 == 0:
                await asyncio.sleep(2)

        print(f"\nResultaat: {success} OK ({cached} cached), {errors} fouten")


async def main():
    parser = argparse.ArgumentParser(description="Import gemeenten en start bulk scans")
    parser.add_argument("--import-only", action="store_true", help="Alleen importeren, niet scannen")
    parser.add_argument("--scan-only", action="store_true", help="Alleen scannen, niet importeren")
    parser.add_argument("--dsn", default="postgresql://soevereinscan:soevereinscan@localhost:5432/soevereinscan",
                        help="PostgreSQL DSN")
    parser.add_argument("--api", default="https://soevereinscan.publicvibes.nl",
                        help="API base URL")
    parser.add_argument("--csv", default="scripts/gemeenten_websites.csv",
                        help="CSV bestand met gemeenten")
    parser.add_argument("--category", default="gemeente", help="Organisatie categorie")
    args = parser.parse_args()

    conn = await get_connection(args.dsn)

    try:
        if not args.scan_only:
            print("=== Gemeenten importeren ===")
            await import_gemeenten(conn, args.csv)

        if not args.import_only:
            print("\n=== Bulk scan starten ===")
            await trigger_bulk_scan(conn, args.api, args.category)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
