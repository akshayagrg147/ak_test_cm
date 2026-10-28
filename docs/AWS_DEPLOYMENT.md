# ViaCRM AWS deployment

The production repository is `akshayagrg147/ak_test_cm`. Push a commit to `main`
to run the GitHub Actions pipeline. Other branches and pull requests run checks
without changing the production host. Local edits take effect after they are
committed and pushed; a failed check prevents deployment.

## Release process

1. Run Android, backend, built-browser, deployment-tool and Docker persistence checks.
2. Build Linux AMD64 API and web images and push them to private Amazon ECR repositories.
3. Authenticate to AWS with GitHub OIDC. The role trusts only this repository's `main` branch.
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

| Variable | Purpose |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Scoped OIDC role, also enables the deploy job |
| `EC2_INSTANCE_ID` | The one production server |
| `RELEASE_BUCKET` | Private release bucket |
| `API_REPOSITORY`, `WEB_REPOSITORY` | Private ECR repository URLs |
| `POSTGRES_IMAGE`, `CADDY_IMAGE` | Tested upstream images pinned by sha256 digest |

Caddy obtains and renews publicly trusted certificates with the Let's Encrypt
short-lived profile. Until a domain is configured, the stable public IP is the
HTTPS address. To adopt a domain, point its A record at the server, update
`PUBLIC_HOST` in `shared/host.env` and `PUBLIC_ORIGIN` in `shared/app.env`, then
run the current release's `deploy.sh`. Review production CORS/refresh-cookie
behavior when changing the origin; existing sessions may need to sign in again.

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
