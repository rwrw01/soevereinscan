"""
Bulk scan alle gemeenten via de SoevereinScan API.
Koppelt elke scan aan de juiste organization via SSH naar de VPS database.

Usage:
  python scripts/bulk_scan_gemeenten.py
"""
import asyncio
import json
import subprocess
import uuid

import aiohttp

API_BASE = "https://soevereinscan.publicvibes.nl"
SSH_CMD = ["ssh", "-i", "C:/Users/RalphWagterM&IPartne/.ssh/id_ed25519", "ralph@100.64.0.2"]
PSQL = "docker exec postgres-soevereinscan psql -U soevereinscan -d soevereinscan -tAc"


def db_query(sql: str) -> str:
    """Execute a SQL query on the VPS database via SSH."""
    cmd = SSH_CMD + [f'{PSQL} "{sql}"']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.stdout.strip()


def db_exec(sql: str) -> None:
    """Execute a SQL statement on the VPS database via SSH."""
    cmd = SSH_CMD + [f'{PSQL} "{sql}"']
    subprocess.run(cmd, capture_output=True, text=True, timeout=15)


async def main():
    # Get all gemeenten that need scanning
    raw = db_query(
        "SELECT id || '|' || name || '|' || website FROM organizations "
        "WHERE category = 'gemeente' ORDER BY name"
    )
    orgs = []
    for line in raw.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 2)
            orgs.append({"id": parts[0], "name": parts[1], "website": parts[2]})

    print(f"Totaal gemeenten: {len(orgs)}")

    # Check which already have a recent scan
    scanned_raw = db_query(
        "SELECT DISTINCT o.website FROM organizations o "
        "JOIN scans s ON s.organization_id = o.id "
        "WHERE o.category = 'gemeente' AND s.status = 'done' "
        "AND s.created_at > NOW() - INTERVAL '7 days'"
    )
    already_scanned = set(scanned_raw.split("\n")) if scanned_raw else set()
    to_scan = [o for o in orgs if o["website"] not in already_scanned]
    print(f"Al gescand (7 dagen): {len(already_scanned)}")
    print(f"Te scannen: {len(to_scan)}")

    if not to_scan:
        print("Alles is al gescand!")
        return

    success = 0
    errors = 0
    error_list = []

    async with aiohttp.ClientSession() as http:
        for i, org in enumerate(to_scan):
            url = org["website"]
            name = org["name"]
            org_id = org["id"]

            try:
                async with http.post(
                    f"{API_BASE}/api/scan",
                    json={"url": url},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        scan_id = data.get("id")
                        status = data.get("status", "?")

                        # Link scan to organization
                        if scan_id:
                            db_exec(
                                f"UPDATE scans SET organization_id = '{org_id}' "
                                f"WHERE id = '{scan_id}'"
                            )

                        success += 1
                        tag = "CACHED" if status == "done" else "QUEUED"
                        print(f"  [{i+1:3d}/{len(to_scan)}] {tag:6s} {name:40s} {url}")
                    else:
                        body = await resp.text()
                        errors += 1
                        error_list.append({"name": name, "url": url, "status": resp.status, "body": body[:200]})
                        print(f"  [{i+1:3d}/{len(to_scan)}] ERR{resp.status:3d} {name:40s} {url}")

            except Exception as e:
                errors += 1
                error_list.append({"name": name, "url": url, "error": str(e)[:200]})
                print(f"  [{i+1:3d}/{len(to_scan)}] ERROR  {name:40s} {str(e)[:60]}")

            # Pace: the app processes max 2 concurrent scans (~90s each)
            # Submit in small batches, then wait for some to finish
            if (i + 1) % 3 == 0:
                # Check how many are queued/scanning
                active = db_query(
                    "SELECT COUNT(*) FROM scans WHERE status IN ('queued','scanning','analyzing')"
                )
                active_count = int(active) if active.isdigit() else 0
                if active_count >= 6:
                    print(f"    ... {active_count} scans in queue, wacht 60s ...")
                    await asyncio.sleep(60)
                elif active_count >= 3:
                    print(f"    ... {active_count} scans in queue, wacht 30s ...")
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(2)

    print(f"\n{'='*60}")
    print(f"Resultaat: {success} OK, {errors} fouten")

    if error_list:
        print(f"\nFouten:")
        for e in error_list:
            print(f"  {e['name']:40s} {e.get('url','')}")
            if 'status' in e:
                print(f"    HTTP {e['status']}: {e.get('body','')[:100]}")
            if 'error' in e:
                print(f"    {e['error'][:100]}")

    # Save errors to file for review
    if error_list:
        with open("scripts/bulk_scan_errors.json", "w", encoding="utf-8") as f:
            json.dump(error_list, f, indent=2, ensure_ascii=False)
        print(f"\nFouten opgeslagen in scripts/bulk_scan_errors.json")


if __name__ == "__main__":
    asyncio.run(main())
