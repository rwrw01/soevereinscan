#!/usr/bin/env python3
"""
Bulk scan alle gemeenten. Draait op de VPS.
Praat met de app container via docker network en met postgres via docker exec.

Usage: ssh ralph@VPS 'python3 -s' < scripts/bulk_scan_vps.py
"""
import json
import subprocess
import time
import urllib.request
import urllib.error

API = "http://192.168.96.4:8000"


def psql(sql):
    """Execute SQL on postgres container, return stdout."""
    result = subprocess.run(
        ["docker", "exec", "postgres-soevereinscan",
         "psql", "-U", "soevereinscan", "-d", "soevereinscan", "-tAc", sql],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip()


def api_post(url, data):
    """POST JSON to the API."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.fp else {}
    except Exception as e:
        return 0, {"error": str(e)}


def main():
    print("=== SoevereinScan: Bulk Scan Gemeenten ===")
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get all gemeenten
    raw = psql(
        "SELECT id || '|' || name || '|' || website "
        "FROM organizations WHERE category = 'gemeente' ORDER BY name"
    )
    orgs = []
    for line in raw.split("\n"):
        if "|" in line:
            parts = line.split("|", 2)
            orgs.append({"id": parts[0], "name": parts[1], "website": parts[2]})

    total = len(orgs)
    print(f"Totaal gemeenten: {total}")

    # Find already scanned (last 7 days)
    scanned_raw = psql(
        "SELECT DISTINCT o.id FROM organizations o "
        "JOIN scans s ON s.organization_id = o.id "
        "WHERE o.category = 'gemeente' AND s.status = 'done' "
        "AND s.created_at > NOW() - INTERVAL '7 days'"
    )
    already = set(scanned_raw.split("\n")) if scanned_raw else set()
    to_scan = [o for o in orgs if o["id"] not in already]
    print(f"Al gescand: {len(already)}")
    print(f"Te scannen: {len(to_scan)}")
    print()

    success = 0
    errors = 0
    error_list = []

    for i, org in enumerate(to_scan):
        org_id = org["id"]
        name = org["name"]
        website = org["website"]

        status_code, data = api_post(f"{API}/api/scan", {"url": website})

        if status_code in (200, 201):
            scan_id = data.get("id", "")
            scan_status = data.get("status", "?")

            # Link scan to organization
            if scan_id:
                psql(f"UPDATE scans SET organization_id = '{org_id}' WHERE id = '{scan_id}'")

            tag = "CACHED" if scan_status == "done" else "QUEUED"
            print(f"  [{i+1:3d}/{len(to_scan)}] {tag:6s} {name:40s} {website}")
            success += 1
        elif status_code == 422:
            detail = data.get("detail", [])
            msg = detail[0].get("msg", str(detail)) if isinstance(detail, list) and detail else str(detail)
            print(f"  [{i+1:3d}/{len(to_scan)}] SKIP   {name:40s} {msg[:60]}")
            errors += 1
            error_list.append({"name": name, "url": website, "status": status_code, "detail": msg})
        else:
            print(f"  [{i+1:3d}/{len(to_scan)}] ERR{status_code:3d}  {name:40s} {website}")
            errors += 1
            error_list.append({"name": name, "url": website, "status": status_code, "detail": str(data)[:200]})

        # Pacing every 3 submissions
        if (i + 1) % 3 == 0:
            active_raw = psql("SELECT COUNT(*) FROM scans WHERE status IN ('queued','scanning','analyzing')")
            active = int(active_raw) if active_raw.isdigit() else 0
            if active >= 8:
                print(f"    ... {active} scans actief, wacht 120s ...")
                time.sleep(120)
            elif active >= 5:
                print(f"    ... {active} scans actief, wacht 60s ...")
                time.sleep(60)
            elif active >= 3:
                print(f"    ... {active} scans actief, wacht 30s ...")
                time.sleep(30)
            else:
                time.sleep(3)

    print()
    print("=" * 60)
    print(f"Klaar: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Gesubmit: {success}, Fouten: {errors}")

    # Final stats
    done = psql("SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status = 'done'")
    queued = psql("SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status IN ('queued','scanning','analyzing')")
    err = psql("SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status = 'error'")
    print(f"\nDatabase status:")
    print(f"  Afgerond:     {done}")
    print(f"  In wachtrij:  {queued}")
    print(f"  Fouten:       {err}")

    if error_list:
        print(f"\nGemeenten met fouten:")
        for e in error_list:
            print(f"  {e['name']:40s} HTTP {e['status']}: {e['detail'][:80]}")


if __name__ == "__main__":
    main()
