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
compose() { docker compose --project-name viacrm --env-file "$deploy_root/shared/host.env" --env-file "$release_dir/images.env" -f "$release_dir/compose.yaml" "$@"; }
previous_dir="$(readlink -f "$deploy_root/current" 2>/dev/null || true)"
if [[ "$previous_dir" == "$release_dir" ]]; then
    echo "Release $RELEASE_SHA is already current"
    compose up -d --wait --wait-timeout 240 --remove-orphans
    exit 0
fi
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null
trap 'docker logout "$ECR_REGISTRY" >/dev/null 2>&1 || true' EXIT
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
# Compose already removes superseded containers. Remove unused project images,
# retaining current and previous images for a schema-compatible rollback.
if ! python3 "$release_dir/cleanup_images.py" "$deploy_root"; then
    echo 'Application is healthy; image cleanup needs operator attention'
fi
echo "Deployed $RELEASE_SHA successfully"
