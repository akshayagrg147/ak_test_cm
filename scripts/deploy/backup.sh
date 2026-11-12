#!/usr/bin/env bash
# Off-server ViaCRM backups. Runs as root on the production host.
#
#   backup.sh daily          Take an online backup of the database, uploaded files and
#                            matching secret configuration, then upload it to S3.
#   backup.sh upload DIR     Upload an existing pre-deployment backup directory.
#
# The host may only upload (s3:PutObject) to the backup bucket; it cannot list, read or
# delete earlier copies. A successful upload publishes ViaCRM/BackupSucceeded=1, which a
# CloudWatch alarm expects at least once every 26 hours.
set -Eeuo pipefail
umask 077
deploy_root="${DEPLOY_ROOT:-/opt/viacrm}"
backups="$deploy_root/backups"
keep_local_daily="${KEEP_LOCAL_DAILY:-3}"
keep_local_release="${KEEP_LOCAL_RELEASE:-5}"

set -a
# shellcheck source=/dev/null
source "$deploy_root/shared/host.env"
set +a
region="${AWS_REGION:?AWS_REGION is required}"

account() { aws sts get-caller-identity --query Account --output text --region "$region"; }
bucket_name() {
    if [[ -n "${BACKUP_BUCKET:-}" ]]; then echo "$BACKUP_BUCKET"; else echo "viacrm-backups-$(account)-$region"; fi
}

metric() {
    aws cloudwatch put-metric-data --region "$region" --namespace ViaCRM \
        --metric-name "$1" --value "$2" --unit "${3:-Count}" >/dev/null
}

manifest() {
    python3 - "$1" <<'PY'
import hashlib, json, sys
from pathlib import Path
folder = Path(sys.argv[1])
files = {}
for path in sorted(folder.iterdir()):
    if path.is_file() and path.name != "manifest.json":
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        files[path.name] = {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}
if "database.dump" not in files or files["database.dump"]["bytes"] == 0:
    raise SystemExit("database.dump is missing or empty; refusing to upload an incomplete backup")
(folder / "manifest.json").write_text(json.dumps({"backup": folder.name, "files": files}, indent=2) + "\n")
print(sum(item["bytes"] for item in files.values()))
PY
}

upload() {
    local folder="$1" prefix="$2" bytes bucket owner
    [[ -d "$folder" ]] || { echo "Backup folder $folder does not exist"; return 1; }
    bytes="$(manifest "$folder")"
    owner="$(account)"
    bucket="$(bucket_name)"
    aws s3 cp "$folder" "s3://$bucket/$prefix/$(basename "$folder")/" --recursive \
        --sse AES256 --expected-bucket-owner "$owner" --only-show-errors --region "$region"
    touch "$folder/.uploaded"
    metric BackupSucceeded 1
    metric BackupBytes "$bytes" Bytes
    echo "Uploaded $(basename "$folder") ($bytes bytes) to s3://$bucket/$prefix/"
}

prune() {
    # Keep a few local copies for quick restores; older ones exist in S3. Only copies that
    # were uploaded successfully are removed.
    local pattern="$1" keep="$2" index=0 folder
    while IFS= read -r folder; do
        index=$((index + 1))
        if (( index > keep )) && [[ -f "$folder/.uploaded" ]]; then
            rm -rf -- "$folder"
        fi
    done < <(find "$backups" -mindepth 1 -maxdepth 1 -type d -name "$pattern" | sort -r)
}

daily() {
    local current release folder
    current="$(readlink -f "$deploy_root/current")"
    [[ -f "$current/images.env" && -f "$current/compose.yaml" ]] || { echo 'No current release'; return 1; }
    set -a
    # shellcheck source=/dev/null
    source "$current/images.env"
    set +a
    # Wait for a running deployment instead of overlapping with its maintenance window.
    exec 9>"$deploy_root/shared/deploy.lock"
    flock -w 3600 9 || { echo 'Deployment lock is still held after one hour'; return 1; }
    folder="$backups/daily-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -m 700 "$folder"
    # pg_dump reads one consistent snapshot while the CRM stays online.
    docker compose --project-name viacrm --env-file "$deploy_root/shared/host.env" \
        --env-file "$current/images.env" -f "$current/compose.yaml" \
        exec -T db pg_dump -U crm -d talkocrm -Fc > "$folder/database.dump"
    docker run --rm --network none -v viacrm_files:/source:ro -v "$folder:/backup" \
        --entrypoint tar "$POSTGRES_IMAGE" -czf /backup/files.tar.gz -C /source .
    if docker volume inspect viacrm_igbot_data >/dev/null 2>&1; then
        docker run --rm --network none -v viacrm_igbot_data:/source:ro -v "$folder:/backup" \
            --entrypoint tar "$POSTGRES_IMAGE" -czf /backup/igbot-data.tar.gz -C /source .
    fi
    cp "$deploy_root/shared/app.env" "$deploy_root/shared/database.env" "$folder/"
    if [[ -f "$deploy_root/shared/igbot.env" ]]; then cp "$deploy_root/shared/igbot.env" "$folder/"; fi
    release="$(basename "$current")"
    echo "$release" > "$folder/release.txt"
    flock -u 9
    upload "$folder" daily
    prune 'daily-*' "$keep_local_daily"
}

case "${1:-}" in
    daily) daily ;;
    upload)
        upload "${2:?Backup folder required}" release
        prune '2*' "$keep_local_release"
        ;;
    *) echo 'Usage: backup.sh daily | backup.sh upload DIR'; exit 2 ;;
esac
