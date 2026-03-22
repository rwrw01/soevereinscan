#!/bin/bash
set -euo pipefail

# SoevereinScan — Deployment to VPS-001 (sovereign-stack)
# Usage: bash scripts/deploy.sh

VPS_HOST="ralph@100.64.0.2"
DEPLOY_DIR="/opt/soevereinscan"
SSH_KEY="$HOME/.ssh/id_ed25519"
SSH="ssh -i $SSH_KEY $VPS_HOST"

echo "=== SoevereinScan Deployment ==="
echo "Target: $VPS_HOST:$DEPLOY_DIR"

# 1. Create deployment directory on VPS
echo "[1/7] Creating deployment directory..."
$SSH "sudo mkdir -p $DEPLOY_DIR && sudo chown ralph:ralph $DEPLOY_DIR"

# 2. Sync files to VPS (exclude dev files, secrets, databases)
echo "[2/7] Syncing files to VPS..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='*.mmdb' \
    --exclude='.pytest_cache' \
    --exclude='htmlcov' \
    --exclude='e2e' \
    --exclude='tests' \
    --exclude='secrets/' \
    --exclude='docker-compose.yml' \
    -e "ssh -i $SSH_KEY" \
    . "$VPS_HOST:$DEPLOY_DIR/"

# 3. Create Docker spoke network if not exists
echo "[3/7] Creating Docker network..."
$SSH "docker network create net-fe-soevereinscan 2>/dev/null || true"

# 4. Create secrets directory if not exists
echo "[4/7] Checking secrets..."
$SSH "
    if [ ! -d $DEPLOY_DIR/secrets ]; then
        mkdir -p $DEPLOY_DIR/secrets
        chmod 700 $DEPLOY_DIR/secrets
        echo 'WARNING: Secrets directory created — populate secrets before starting!'
        echo 'Required files:'
        echo '  $DEPLOY_DIR/secrets/db_password'
        echo '  $DEPLOY_DIR/secrets/ripe_atlas_api_key'
        echo '  $DEPLOY_DIR/secrets/maxmind_license_key'
        exit 1
    fi
    # Verify all required secrets exist
    for secret in db_password ripe_atlas_api_key maxmind_license_key; do
        if [ ! -f $DEPLOY_DIR/secrets/\$secret ]; then
            echo \"ERROR: Missing secret: $DEPLOY_DIR/secrets/\$secret\"
            exit 1
        fi
    done
    echo 'All secrets present'
"

# 5. Download GeoLite2 databases if not present
echo "[5/7] Checking GeoLite2 databases..."
$SSH "
    if [ ! -f $DEPLOY_DIR/data/GeoLite2-ASN.mmdb ] || [ ! -f $DEPLOY_DIR/data/GeoLite2-Country.mmdb ]; then
        echo 'Downloading GeoLite2 databases...'
        cd $DEPLOY_DIR
        MAXMIND_LICENSE_KEY=\$(cat secrets/maxmind_license_key) bash scripts/update-geolite2.sh ./data
    else
        echo 'GeoLite2 databases already present'
    fi
"

# 6. Build and deploy
echo "[6/7] Building and deploying..."
$SSH "cd $DEPLOY_DIR && docker compose -f docker-compose.prod.yml up --build -d"

# 7. Verify
echo "[7/7] Verifying deployment..."
sleep 5
$SSH "docker ps --filter 'name=soevereinscan' --format 'table {{.Names}}\t{{.Status}}'"

echo ""
echo "=== Deployment complete ==="
echo "App: https://soevereinscan.publicvibes.nl"
echo ""
echo "IMPORTANT: Update egress filter on VPS:"
echo "  sudo nano /opt/scripts/egress-filter.sh"
echo "  sudo systemctl restart egress-filter"
