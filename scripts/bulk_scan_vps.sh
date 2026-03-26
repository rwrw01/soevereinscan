#!/bin/bash
# Bulk scan alle gemeenten op de VPS
# Draait direct op de VPS, praat met de app container via docker network
#
# Usage: ssh ralph@100.64.0.2 'bash -s' < scripts/bulk_scan_vps.sh

API="http://192.168.96.4:8000"
PSQL="docker exec postgres-soevereinscan psql -U soevereinscan -d soevereinscan -tAc"

echo "=== SoevereinScan: Bulk Scan Gemeenten ==="
echo "Start: $(date)"

# Get all gemeenten
GEMEENTEN=$($PSQL "SELECT id || '|' || name || '|' || website FROM organizations WHERE category = 'gemeente' ORDER BY name")
TOTAL=$(echo "$GEMEENTEN" | wc -l)
echo "Totaal gemeenten: $TOTAL"

# Count already scanned (last 7 days)
ALREADY=$($PSQL "SELECT COUNT(DISTINCT o.id) FROM organizations o JOIN scans s ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status = 'done' AND s.created_at > NOW() - INTERVAL '7 days'")
echo "Al gescand (7 dagen): $ALREADY"

SUCCESS=0
ERRORS=0
CACHED=0
COUNT=0

echo ""
echo "$GEMEENTEN" | while IFS='|' read -r ORG_ID NAME WEBSITE; do
    [ -z "$WEBSITE" ] && continue
    COUNT=$((COUNT + 1))

    # Check if already scanned recently
    EXISTING=$($PSQL "SELECT s.id FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.id = '$ORG_ID' AND s.status = 'done' AND s.created_at > NOW() - INTERVAL '7 days' LIMIT 1")
    if [ -n "$EXISTING" ]; then
        echo "  [$COUNT/$TOTAL] SKIP   $NAME (already scanned)"
        continue
    fi

    # Submit scan
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/api/scan" \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"$WEBSITE\"}" \
        --max-time 30)

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "200" ]; then
        SCAN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
        STATUS=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

        if [ -n "$SCAN_ID" ]; then
            $PSQL "UPDATE scans SET organization_id = '$ORG_ID' WHERE id = '$SCAN_ID'" >/dev/null 2>&1
        fi

        if [ "$STATUS" = "done" ]; then
            echo "  [$COUNT/$TOTAL] CACHED $NAME"
            CACHED=$((CACHED + 1))
        else
            echo "  [$COUNT/$TOTAL] QUEUED $NAME -> scan $SCAN_ID"
        fi
        SUCCESS=$((SUCCESS + 1))
    elif [ "$HTTP_CODE" = "422" ]; then
        echo "  [$COUNT/$TOTAL] INVALID $NAME -> $WEBSITE ($BODY)"
        ERRORS=$((ERRORS + 1))
    else
        echo "  [$COUNT/$TOTAL] ERR$HTTP_CODE $NAME -> $WEBSITE"
        ERRORS=$((ERRORS + 1))
    fi

    # Pacing: every 3 submissions, check queue depth
    if [ $((COUNT % 3)) -eq 0 ]; then
        ACTIVE=$($PSQL "SELECT COUNT(*) FROM scans WHERE status IN ('queued','scanning','analyzing')")
        if [ "$ACTIVE" -ge 6 ] 2>/dev/null; then
            echo "    ... $ACTIVE scans actief, wacht 90s ..."
            sleep 90
        elif [ "$ACTIVE" -ge 3 ] 2>/dev/null; then
            echo "    ... $ACTIVE scans actief, wacht 45s ..."
            sleep 45
        else
            sleep 3
        fi
    fi
done

echo ""
echo "=== Resultaat ==="
echo "Klaar: $(date)"
TOTAL_DONE=$($PSQL "SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status = 'done'")
TOTAL_QUEUED=$($PSQL "SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status IN ('queued','scanning','analyzing')")
TOTAL_ERROR=$($PSQL "SELECT COUNT(*) FROM scans s JOIN organizations o ON s.organization_id = o.id WHERE o.category = 'gemeente' AND s.status = 'error'")
echo "Afgerond: $TOTAL_DONE"
echo "In wachtrij: $TOTAL_QUEUED"
echo "Fouten: $TOTAL_ERROR"
