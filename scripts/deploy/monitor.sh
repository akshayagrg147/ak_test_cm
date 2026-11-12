#!/usr/bin/env bash
# Every five minutes: report public HTTPS health and disk use to CloudWatch (namespace ViaCRM).
# If this host stops reporting, the HealthOK alarm treats the missing data as an outage.
set -Euo pipefail
deploy_root="${DEPLOY_ROOT:-/opt/viacrm}"
set -a
# shellcheck source=/dev/null
source "$deploy_root/shared/host.env"
set +a
region="${AWS_REGION:?AWS_REGION is required}"

# Certificate verification stays on; the check uses the same public address as users.
body="$(curl --silent --show-error --max-time 20 "https://$PUBLIC_HOST/api/health" 2>/dev/null || true)"
healthy="$(python3 -c '
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(1 if all(data.get(k) == "ok" for k in ("status", "database", "worker")) else 0)
except Exception:
    print(0)
' "$body")"
disk="$(df --output=pcent / | tail -1 | tr -dc '0-9')"

aws cloudwatch put-metric-data --region "$region" --namespace ViaCRM --metric-data \
    "MetricName=HealthOK,Value=$healthy,Unit=Count" \
    "MetricName=DiskUsedPercent,Value=${disk:-0},Unit=Percent" >/dev/null
[[ "$healthy" == 1 ]] || echo "ViaCRM health check failed: ${body:-no response}"
