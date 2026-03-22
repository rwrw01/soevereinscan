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
