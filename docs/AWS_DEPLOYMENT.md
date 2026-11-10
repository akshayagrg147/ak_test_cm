# ViaCRM AWS deployment

The production repository is `akshayagrg147/ak_test_cm`. Push a commit to `main`
to run the GitHub Actions pipeline. Other branches and pull requests run checks
without changing the production host. Local edits take effect after they are
committed and pushed; a failed check prevents deployment.

## Release process

1. Run Android, backend, built-browser, deployment-tool and Docker persistence checks.
2. Build Linux AMD64 API and web images and push them to private Amazon ECR repositories.
3. Authenticate to AWS with GitHub OIDC. The role trusts only this repository's `main` branch, using the exact ID-based subject prefix from its GitHub OIDC settings.
4. Package immutable image digests and deployment scripts in the private encrypted S3 release bucket.
5. Run the release on the dedicated Mumbai EC2 instance through Systems Manager.
6. Pull images, stop application writes, and back up the database, uploaded files and matching secret configuration.
7. Apply Alembic migrations, replace containers, and verify public HTTPS, the database, the worker and the exact deployed commit.
8. Remove unused ViaCRM images while keeping the current and previous release images.

Updates have a short maintenance window while writes stop and migrations run.
Deployments are serialized. A commit superseded on `main` before its deployment
step is skipped so an older slow build cannot replace newer code.

Compose removes replaced containers and obsolete containers within the `viacrm`
project. The named `viacrm_database`, `viacrm_files`, `viacrm_tls` and
`viacrm_caddy_config` volumes remain. The deployment never prunes volumes or runs
`docker compose down --volumes` against production. Docker volume removal in the
CI job applies only to its disposable `aven-ci` stack on a GitHub runner.

## Configuration and access

CloudFormation source is `infra/aws/stack.json`; regenerate it with
`python3 scripts/deploy/aws_template.py`. The `viacrm-production` stack contains
one `t3.small` instance, encrypted 30 GiB gp3 root storage, a stable public IP,
private ECR/S3 resources, and the scoped IAM roles. The host and storage are
retained if the stack is deleted; terminate them deliberately only after a
verified backup. Stack termination protection is enabled.

Only TCP 80/443 are exposed. SSH, PostgreSQL and the API have no public inbound
port. Administration uses SSM with the operator's own AWS session. IMDSv2 is
required and container access to instance credentials is restricted by a hop
limit of one. CPU credits use standard mode to avoid unlimited-credit charges.

Production starts with a fresh database; development fixtures, existing local
records and local recordings are not uploaded. Initial owner credentials are
provided separately in a private local file. Never commit that file, `.env`,
signing keys, backups, recordings or generated QA artifacts.

Host secrets are generated once under `/opt/viacrm/shared`, owned by root with
0600 permissions. Subsequent releases preserve encryption/signing keys and the
database password. No long-lived AWS keys or SSH private keys are stored in GitHub.

GitHub Actions repository variables:

The CloudFormation `GitHubSubjectPrefix` parameter must match the repository's
`sub_claim_prefix` from `gh api repos/OWNER/REPO/actions/oidc/customization/sub`.
This repository enables immutable owner/repository IDs. Do not disable that
setting or replace the exact `main` subject with a wildcard to resolve a login
failure.

| Variable | Purpose |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Scoped OIDC role, also enables the deploy job |
| `EC2_INSTANCE_ID` | The one production server |
| `RELEASE_BUCKET` | Private release bucket |
| `API_REPOSITORY`, `WEB_REPOSITORY` | Private ECR repository URLs |
| `POSTGRES_IMAGE`, `CADDY_IMAGE` | Tested upstream images pinned by sha256 digest |

Caddy obtains and renews publicly trusted certificates with the Let's Encrypt
short-lived profile. Until a domain is configured, the stable public IP is the
HTTPS address. With no optional values, `PUBLIC_ALIASES` is empty and
`TLS_DEFAULT_SNI` uses `PUBLIC_HOST`, preserving the existing IP configuration.

For `viacrm.in`, first point its apex A record at the existing production IP
`13.234.72.21` and set `www` to a CNAME for `viacrm.in`. Remove conflicting web A
or AAAA records only; preserve mail MX/TXT records and unrelated DNS entries.
Confirm the authoritative and public DNS answers before enabling the names in
Caddy. Both names must reach this server on TCP 80/443 for certificate issuance;
do not publish an AAAA record unless this host has working public IPv6.

After the current `main` commit has passed CI and deployed, run the manual
**Configure ViaCRM domain** GitHub Actions workflow on `main`. It uses the
existing scoped deployment role and instance, without AWS root credentials or
new IAM permissions. The operation is restricted to `viacrm.in`, `www.viacrm.in`
and the existing IP. It requires that exact release to be active, checks DNS,
takes the deployment lock, saves private copies of both environment files and
recreates services with the values below. Trusted public health, release and
alias checks must pass; otherwise both environment files and the previous
service configuration are restored. Inspect the SSM command before retrying an
ambiguous submission or status timeout. No database migration or volume removal
is part of this domain operation.

Set these non-secret values in `/opt/viacrm/shared/host.env`:

```dotenv
PUBLIC_HOST=viacrm.in
PUBLIC_ALIASES="www.viacrm.in 13.234.72.21"
TLS_DEFAULT_SNI=13.234.72.21
```

Update only `PUBLIC_ORIGIN="https://viacrm.in"` in `shared/app.env`, with no
trailing slash. Preserve the database URL, signing/encryption keys and other
values. `host_config.py` initializes secrets once; calling it with a new host
does not update an existing `PUBLIC_ORIGIN`. Apply the release containing this
Caddy/Compose configuration through the authorized deployment process. A rerun
of an already-current release starts its containers but skips the script's
public health/release verification, so perform those checks explicitly.

Alias browser pages redirect to the same path and query on `https://viacrm.in`.
The aliases' `/api` and `/api/*` routes continue proxying directly, including the
old IP address. Keep `TLS_DEFAULT_SNI` set to the IP while it remains supported:
IP clients can omit TLS SNI and still need the certificate valid for that IP.
The existing Android app rejects HTTP redirects; redirecting its API requests
would break sign-in, refresh and call uploads. Keep installed apps on their
existing server setting. Signing in with a different server address clears the
app's local call queue, contacts and recording-folder grant; do not migrate an
app with pending local work by changing its address or reinstalling it. New
installations can use `https://viacrm.in` without changing the call-sync API.

Refresh cookies are host-only, Secure, HttpOnly and SameSite=Strict. Browser
users sign in once at the new domain; existing IP cookies do not transfer.
Production CORS and browser refresh/logout checks permit the exact
`PUBLIC_ORIGIN`; do not broaden them or relax cookie settings for the move.
The Justdial setup screen derives its webhook URL from the browser origin.
Update any registered provider URL deliberately; the old IP API route remains
available during migration. IndiaMART polling uses an outbound fixed URL.

Before production changes, validate the Caddyfile using the pinned Caddy version:

```bash
python3 scripts/deploy/verify_caddy.py --caddy /path/to/verified/caddy
```

This check requires the Docker Compose CLI, without a running Docker daemon.
It verifies Compose defaults, adapts and validates both the original IP and
domain/alias configurations, then checks routing on disposable loopback HTTP
listeners without issuing certificates or contacting the production CRM. After
application, verify trusted TLS for the domain, `www` and the IP without disabling
certificate verification; domain `/api/health` must report application, database
and worker `ok`, and `/release.json` must match the intended commit. Check alias
page redirects preserve path/query, IP API requests do not redirect, and a real
browser can sign in, reload to refresh its session and sign out at the domain.
An unauthenticated refresh request with `X-Requested-With: TalkoCRM` should reach
authentication (401) for the canonical origin or no Origin header, while a
different Origin is rejected (403). Preserve the previous host/origin settings
privately so a configuration rollback can restore both together.

## Operations and recovery

Use `aws ssm start-session --target INSTANCE_ID --region ap-south-1` with an
authorized operator profile, or use Run Command in the AWS console. From the host:

```bash
cd /opt/viacrm/current
docker compose --project-name viacrm --env-file /opt/viacrm/shared/host.env --env-file images.env -f compose.yaml ps
```

`current` is updated only after health checks pass. `previous` records the last
successful release. If a deployment fails and its schema is unchanged, the script
attempts to restore the previous application. If the schema changed or cannot be
confirmed, automatic database downgrade is disabled; inspect the failed command
and deploy a compatible fix or restore the coordinated backup. Never downgrade a
populated database merely to force an older application to start.

Coordinated backups are retained in `/opt/viacrm/backups`, accessible only to root.
They contain personal data and secrets. They are host-local recovery points;
off-host backup scheduling, monitoring and retention must be configured before
depending on this single-server installation for disaster recovery. Release
artifacts in S3 are code bundles and are not database/file backups.

See `docs/OPERATIONS.md` for a restore drill and schema compatibility limits.
The pipeline retains 20 images per ECR repository, S3 code bundles for 90 days,
and one previous application image locally. Application logs rotate at three
10 MiB files per service. This is a single-server installation; it does not
provide multi-zone failover or zero-downtime migrations.
