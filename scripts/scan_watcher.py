#!/usr/bin/env python3
"""
Scan Watcher — monitort de scan-queue en zorgt dat scans niet vastlopen.

Taken:
1. Detecteert vastgelopen scans (scanning/analyzing > 5 min) en reset ze
2. Pakt queued scans zonder actieve verwerking op en hersubmit ze via de API
3. Rapporteert voortgang

Draait op de VPS: nohup python3 -u /tmp/scan_watcher.py > /tmp/scan_watcher.log 2>&1 &
"""
import json
import subprocess
import time
import urllib.request
import urllib.error

API = "http://192.168.96.4:8000"
MAX_CONCURRENT = 2
CHECK_INTERVAL = 30  # seconds
STUCK_THRESHOLD = 300  # 5 minutes


def psql(sql):
    result = subprocess.run(
        ["docker", "exec", "postgres-soevereinscan",
         "psql", "-U", "soevereinscan", "-d", "soevereinscan", "-tAc", sql],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout.strip()


def api_post(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()) if e.fp else {}
    except Exception as e:
        return 0, {"error": str(e)}


def fix_stuck_scans():
    """Reset scans stuck in scanning/analyzing for too long."""
    stuck = psql(
        f"UPDATE scans SET status = 'queued', completed_at = NULL "
        f"WHERE status IN ('scanning', 'analyzing') "
        f"AND created_at < NOW() - INTERVAL '{STUCK_THRESHOLD} seconds' "
        f"RETURNING id, url"
    )
    if stuck:
        count = len([l for l in stuck.split("\n") if l.strip()])
        print(f"  Reset {count} vastgelopen scan(s)")
        return count
    return 0


def get_active_count():
    """Count currently processing scans."""
    raw = psql("SELECT COUNT(*) FROM scans WHERE status IN ('scanning', 'analyzing')")
    return int(raw) if raw.isdigit() else 0


def submit_queued_scans(batch_size=2):
    """Pick up queued scans and submit them via the API."""
    active = get_active_count()
    slots = MAX_CONCURRENT - active
    if slots <= 0:
        return 0

    # Get oldest queued scans with organization link
    rows = psql(
        f"SELECT s.id, s.url, o.id AS org_id, o.name "
        f"FROM scans s "
        f"LEFT JOIN organizations o ON s.organization_id = o.id "
        f"WHERE s.status = 'queued' "
        f"ORDER BY s.created_at ASC "
        f"LIMIT {min(slots, batch_size)}"
    )
    if not rows:
        return 0

    submitted = 0
    for line in rows.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        scan_id, url, org_id = parts[0], parts[1], parts[2]
        name = parts[3] if len(parts) > 3 else url

        # Submit via API (which creates a new scan, then we can delete the queued one)
        # OR: directly trigger the scan background task
        # Simplest: just call the API, it will either create new or return cached
        status_code, data = api_post(f"{API}/api/scan", {"url": url})

        if status_code in (200, 201):
            new_scan_id = data.get("id", "")
            new_status = data.get("status", "?")

            # Link new scan to organization
            if new_scan_id and org_id:
                psql(f"UPDATE scans SET organization_id = '{org_id}' WHERE id = '{new_scan_id}'")

            # Remove the old queued scan if a new one was created
            if new_scan_id != scan_id:
                psql(f"DELETE FROM scans WHERE id = '{scan_id}'")

            tag = "CACHED" if new_status == "done" else "SUBMIT"
            print(f"  {tag} {name:40s} {url}")
            submitted += 1
        elif status_code == 422:
            # Validation error (DNS fail, etc.) — mark as error
            psql(f"UPDATE scans SET status = 'error', completed_at = NOW() WHERE id = '{scan_id}'")
            print(f"  INVALID {name:40s} {url}")
        else:
            print(f"  ERR{status_code} {name:40s} {url}")

    return submitted


def print_status():
    """Print current scan status summary."""
    raw = psql(
        "SELECT status, COUNT(*) FROM scans WHERE organization_id IS NOT NULL "
        "GROUP BY status ORDER BY status"
    )
    status_line = " | ".join(raw.replace("\n", " | ").split("|")) if raw else "geen data"
    # Cleaner format
    stats = {}
    for line in raw.split("\n"):
        if "|" in line:
            parts = line.split("|")
            stats[parts[0].strip()] = parts[1].strip()

    done = stats.get("done", "0")
    queued = stats.get("queued", "0")
    scanning = stats.get("scanning", "0")
    error = stats.get("error", "0")
    print(f"  Status: done={done} queued={queued} scanning={scanning} error={error}")


def main():
    print("=== SoevereinScan Watcher ===")
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Check interval: {CHECK_INTERVAL}s, Max concurrent: {MAX_CONCURRENT}")
    print()

    iteration = 0
    while True:
        iteration += 1
        timestamp = time.strftime("%H:%M:%S")

        # 1. Fix stuck scans
        fixed = fix_stuck_scans()

        # 2. Submit queued scans
        submitted = submit_queued_scans()

        # 3. Print status every 5 iterations or when something happened
        if iteration % 5 == 1 or fixed > 0 or submitted > 0:
            print(f"[{timestamp}] Iteration {iteration}:")
            print_status()

        # Check if we're done
        queued_raw = psql("SELECT COUNT(*) FROM scans WHERE status = 'queued' AND organization_id IS NOT NULL")
        queued = int(queued_raw) if queued_raw.isdigit() else 0
        active = get_active_count()

        if queued == 0 and active == 0:
            print(f"\n[{timestamp}] Alle scans verwerkt!")
            print_status()

            # Final report
            print("\n=== Eindresultaat ===")
            report = psql(
                "SELECT o.name, "
                "ROUND((s.summary->>'weighted_average_level')::numeric, 2) AS score "
                "FROM scans s JOIN organizations o ON s.organization_id = o.id "
                "WHERE s.status = 'done' AND o.category = 'gemeente' "
                "ORDER BY score DESC LIMIT 10"
            )
            print("Top 10 meest soeverein:")
            for line in report.split("\n"):
                if "|" in line:
                    parts = line.split("|")
                    print(f"  {parts[0].strip():40s} score: {parts[1].strip()}")
            break

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
