#!/usr/bin/env bash
# Runs as root on the dedicated ViaCRM EC2 host. Never remove persistent volumes.
set -Eeuo pipefail
umask 077
release_dir="$(cd "$(dirname "$0")" && pwd)"
deploy_root="${DEPLOY_ROOT:-/opt/viacrm}"
mkdir -p "$deploy_root/shared" "$deploy_root/backups"
exec 9>"$deploy_root/shared/deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
set -a
# shellcheck source=/dev/null
source "$deploy_root/shared/host.env"
# shellcheck source=/dev/null
source "$release_dir/images.env"
set +a
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid release commit'; exit 1; }
[[ "$(basename "$release_dir")" == "$RELEASE_SHA" ]] || { echo 'Release path does not match commit'; exit 1; }
python3 "$release_dir/host_config.py" --root "$deploy_root" --host "$PUBLIC_HOST"
export DEPLOY_ROOT="$deploy_root"
# The Instagram lead bot runs only once its private settings file exists on the host.
if [[ -f "$deploy_root/shared/igbot.env" ]]; then export COMPOSE_PROFILES=igbot; else unset COMPOSE_PROFILES; fi
install_schedule_files() {
    # Each step returns explicitly: set -e is ignored inside the caller's || list.
    install -d -m 700 "$deploy_root/bin" || return 1
    install -m 700 "$release_dir/backup.sh" "$deploy_root/bin/viacrm-backup" || return 1
    install -m 700 "$release_dir/monitor.sh" "$deploy_root/bin/viacrm-monitor" || return 1
    local unit
    for unit in viacrm-backup.service viacrm-backup.timer viacrm-monitor.service viacrm-monitor.timer; do
        install -m 644 "$release_dir/$unit" "/etc/systemd/system/$unit" || return 1
    done
    systemctl daemon-reload || return 1
    systemctl enable --now viacrm-backup.timer viacrm-monitor.timer >/dev/null || return 1
}
install_schedules() {
    # Daily off-server backups and five-minute health/disk reports. Never fatal for a
    # healthy release; missing reports raise the CloudWatch alarms instead.
    install_schedule_files || echo 'Backup and monitoring schedules need operator attention'
}
compose() { docker compose --project-name viacrm --env-file "$deploy_root/shared/host.env" --env-file "$release_dir/images.env" -f "$release_dir/compose.yaml" "$@"; }
previous_dir="$(readlink -f "$deploy_root/current" 2>/dev/null || true)"
# Log in before the rerun check: a rerun may need to pull the optional bot image.
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null
trap 'docker logout "$ECR_REGISTRY" >/dev/null 2>&1 || true' EXIT
if [[ "$previous_dir" == "$release_dir" ]]; then
    echo "Release $RELEASE_SHA is already current"
    compose up -d --wait --wait-timeout 240 --remove-orphans
    install_schedules
    exit 0
fi
compose config --quiet
# Pull everything before interrupting the current application.
compose pull
compose up -d --wait --wait-timeout 180 db
old_revision="$(compose run --rm --no-deps api alembic current 2>/dev/null || true)"
maintenance=false
rollback_on_error() {
    result=$?
    trap - ERR
    echo "Deployment $RELEASE_SHA failed (exit $result)"
    if [[ "$maintenance" == true && -n "$previous_dir" && -f "$previous_dir/images.env" ]]; then
        new_revision="$(compose run --rm --no-deps api alembic current 2>/dev/null || true)"
        if [[ -n "$old_revision" && "$old_revision" == "$new_revision" ]]; then
            echo 'Schema is unchanged; restoring the previous application release'
            docker compose --project-name viacrm --env-file "$deploy_root/shared/host.env" --env-file "$previous_dir/images.env" -f "$previous_dir/compose.yaml" up -d --wait --wait-timeout 240 --remove-orphans || true
        else
            echo 'Schema changed or cannot be confirmed; automatic database downgrade is disabled. Restore the matched backup or deploy a compatible fix.'
        fi
    fi
    exit "$result"
}
trap rollback_on_error ERR
# Stop writes before the coordinated database backup and migration.
compose stop web api worker
maintenance=true
backup="$deploy_root/backups/$(date -u +%Y%m%dT%H%M%SZ)-$RELEASE_SHA"
mkdir -m 700 "$backup"
compose exec -T db pg_dump -U crm -d talkocrm -Fc > "$backup/database.dump"
cp "$deploy_root/shared/app.env" "$deploy_root/shared/database.env" "$backup/"
docker run --rm --network none -v viacrm_files:/source:ro -v "$backup:/backup" --entrypoint tar "$POSTGRES_IMAGE" -czf /backup/files.tar.gz -C /source .
compose run --rm --no-deps api alembic upgrade head
compose up -d --wait --wait-timeout 240 --remove-orphans
python3 - "$PUBLIC_HOST" "$RELEASE_SHA" <<'PY'
import json, sys, time, urllib.request
host, sha = sys.argv[1:]
for attempt in range(60):
    try:
        with urllib.request.urlopen(f'https://{host}/api/health', timeout=10) as response:
            health = json.load(response)
        with urllib.request.urlopen(f'https://{host}/release.json', timeout=10) as response:
            release = json.load(response)
        assert all(health.get(k) == 'ok' for k in ['status', 'database', 'worker'])
        assert release.get('commit') == sha
        print(f'HTTPS, database, worker and release {sha} verified')
        break
    except Exception:
        if attempt == 59:
            raise RuntimeError('Public HTTPS health/release verification did not pass') from None
        time.sleep(5)
PY
maintenance=false
if [[ -n "$previous_dir" && -f "$previous_dir/images.env" ]]; then
    ln -sfn "$previous_dir" "$deploy_root/previous"
fi
ln -sfn "$release_dir" "$deploy_root/current"
install_schedules
# Copy the pre-migration recovery point off the server after the release is healthy.
"$deploy_root/bin/viacrm-backup" upload "$backup" ||
    echo 'Pre-deployment backup is kept on the server; its off-server upload needs attention'
# Compose already removes superseded containers. Remove unused project images,
# retaining current and previous images for a schema-compatible rollback.
if ! python3 "$release_dir/cleanup_images.py" "$deploy_root"; then
    echo 'Application is healthy; image cleanup needs operator attention'
fi
echo "Deployed $RELEASE_SHA successfully"
