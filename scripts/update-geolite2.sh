#!/bin/bash
set -euo pipefail

# MaxMind GeoLite2 database download with SHA256 verification
# Usage: MAXMIND_LICENSE_KEY=xxx bash scripts/update-geolite2.sh [data-dir]

LICENSE_KEY="${MAXMIND_LICENSE_KEY:?Set MAXMIND_LICENSE_KEY}"
DATA_DIR="${1:-./data}"
mkdir -p "$DATA_DIR"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

for EDITION in GeoLite2-ASN GeoLite2-Country; do
    echo "Downloading $EDITION..."
    curl -sL -u "${LICENSE_KEY}:" \
        "https://download.maxmind.com/geoip/databases/${EDITION}/download?suffix=tar.gz" \
        -o "$TMPDIR/${EDITION}.tar.gz"

    echo "Downloading ${EDITION} SHA256..."
    curl -sL -u "${LICENSE_KEY}:" \
        "https://download.maxmind.com/geoip/databases/${EDITION}/download?suffix=tar.gz.sha256" \
        -o "$TMPDIR/${EDITION}.tar.gz.sha256"

    echo "Verifying SHA256 checksum..."
    cd "$TMPDIR"
    EXPECTED_HASH=$(awk '{print $1}' "${EDITION}.tar.gz.sha256")
    ACTUAL_HASH=$(sha256sum "${EDITION}.tar.gz" | awk '{print $1}')
    if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
        echo "ERROR: SHA256 mismatch for ${EDITION}!"
        echo "  Expected: $EXPECTED_HASH"
        echo "  Actual:   $ACTUAL_HASH"
        exit 1
    fi
    echo "SHA256 OK for ${EDITION}"
    cd - > /dev/null

    tar xzf "$TMPDIR/${EDITION}.tar.gz" --strip-components=1 -C "$DATA_DIR" --wildcards "*.mmdb"
    echo "${EDITION} updated successfully"
done

echo "GeoLite2 databases updated in $DATA_DIR"
ls -la "$DATA_DIR"/*.mmdb
