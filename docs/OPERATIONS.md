# Local operations, deployment and recovery

## Configuration

`python scripts/configure.py` creates a root `.env` with a random signing secret, Fernet key and Docker database password. It preserves existing values and does not print them. The local launcher copies it to `backend/.env`, because Pydantic resolves the environment file from the backend working directory. `.env`, private storage, the local cluster and virtual environments are ignored by Git and Docker build context. Never rotate a populated environment's encryption key casually.

Use environment-owned secrets for production, set `ENVIRONMENT=production` and an HTTPS `PUBLIC_ORIGIN`. Startup refuses the development signing key, missing encryption key, or a non-HTTPS production origin. Frontend requests always use relative `/api`; the production bundle has no localhost API fallback. Vite's localhost proxy exists only in the development configuration.

## Local services separately

From `backend/`, with PostgreSQL already running:

```bash
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

In a second terminal in `backend/`: `../.venv/bin/python -m app.worker`. In `web/`: `npm ci && npm run dev`. Startup does not silently create the schema or known accounts in production. The explicit seed is rejected outside development.

`GET /api/health` checks the database and the worker's last heartbeat. A missing/stale worker is `degraded` with `worker=offline`; a database outage returns 503. The frontend displays worker-offline status to admins. Logs use request correlation IDs, route paths, status and duration; request bodies, password values and credential query strings are not logged. Worker errors identify jobs and attempts without raw credentials. Organization cycles run in a bounded pool of four, with organization locks preserving idempotency and periodic heartbeats during slow cycles. A slow provider in one workspace can no longer stall every other workspace.

## Isolated Docker environment

With Docker running, create secrets and configure `.env`. For local Docker, set `PUBLIC_ORIGIN=http://localhost:8080` and keep `ENVIRONMENT=development`.

```bash
python scripts/configure.py
docker compose config --quiet
docker compose up --build -d
docker compose exec api python -m app.seed
```

The migration service completes before API/worker startup. PostgreSQL has no host port. Private files and the database have durable named volumes. The web proxy binds only to loopback port 8080. Containers run the Python application under an unprivileged UID. Attachment request size is capped at the proxy, ASGI layer and application.

For a **separately authorized** production host: set `ENVIRONMENT=production`, `PUBLIC_ORIGIN=https://YOUR_DOMAIN`, `DOMAIN=YOUR_DOMAIN`, contact details and unique secrets. Ensure the domain points to the new host and firewall exposes only HTTPS/HTTP to Caddy, then run `docker compose --profile production up --build -d`. Caddy terminates TLS; the database and API remain private. Configure host monitoring, volume backup and secure secret management. Pin the resolved base-image digests in the deployment repository after validating images on the target architecture.

Create the first platform owner interactively with `docker compose exec api python -m app.seed --bootstrap-owner`. There is no public signup and no production seed. Create organizations and their first administrators through the platform UI. Do not reuse the reference project's accounts, databases, AWS settings or domains.

**Runtime Docker validation requires a running Docker daemon.** The build files and Compose configuration can be reviewed/validated locally even if the daemon is unavailable. Do not report a container deployment or TLS issuance as successful until verified on its intended host.

## Database and file backup

Application snapshots are JSON exports with sensitive fields and file bytes omitted. They are not a replacement for disaster-recovery backups and there is no restore UI.

For a coordinated operator backup, put the environment into a maintenance window and stop API/worker writes. Keep the database, attachment volume and encryption/signing configuration from the same recovery point:

```bash
docker compose stop api worker web
docker compose exec -T db pg_dump -U crm -d talkocrm -Fc > talkocrm.dump
docker compose run --rm --no-deps --user 0 -v "$PWD:/backup" api python -c "import tarfile; t=tarfile.open('/backup/talkocrm-files.tar.gz','w:gz'); t.add('/storage',arcname='storage'); t.close()"
docker compose start api worker web
```

Protect dump, file archive and secrets using encrypted storage and restricted access. Choose retention and off-site storage according to business needs. Backups can contain personal data and password hashes. Never commit them. PostgreSQL should use production password authentication, private networking and its own persistent volume.

## Restore drill

Restore into a new isolated database and private file volume first. Stop writes, create the empty target database, use `pg_restore --exit-on-error --no-owner --dbname=TARGET talkocrm.dump`, unpack the `storage` directory into the new volume, restore the matching encryption key, point `DATABASE_URL`/`STORAGE_PATH` at that environment and run `alembic upgrade head`. Confirm migration head, counts, login, tenant boundaries, representative downloads, payroll and worker catch-up before switching traffic. Run an initial restore drill and periodic recovery drills; a dump file alone does not prove restoration works.

The local verification includes fresh migration upgrade/downgrade/upgrade and a PostgreSQL dump/restore to a separate test database. Production volume restoration, host failover and TLS are separate environment-dependent checks.

Repeat the local drill from the project root with `.venv/bin/python scripts/verify_recovery.py`. It targets only the dedicated loopback cluster on port 55432, creates unique test databases, verifies restored counts/file hashes and removes its temporary databases afterward.

## Rollback

Revision `0009` adds nullable `site_visits.actual_started_at`. It preserves the
agreed schedule separately from explicitly confirmed early attendance; existing
rows remain unchanged. Back up, upgrade, then restart the API. Its downgrade
refuses while actual visit times exist to prevent losing attendance history.

Revision `0008` adds the field-work handoff table and a new application role. It
does not rewrite existing leads/calls/visits or create employee accounts. Upgrade
the schema before restarting the new API. The existing worker can continue and
must use the same environment/database. Its downgrade refuses when field handoffs
or `field_executive` accounts exist, because the older application cannot represent
their access and history. Retain the new release or restore a matched backup; do
not delete user/work records simply to make a rollback pass.

Record the previous release commit, resolved image digests and migration revision before deploying. Take a coordinated backup before schema changes. Prefer rolling back application images when schema compatibility allows. Run `alembic downgrade PREVIOUS_REVISION` only after reviewing the downgrade and stopping writes. Revision `0002` removes provenance columns on downgrade; downgrade to `base` deletes application tables and must never be used on an environment containing needed data. For incompatible schema/data changes, restore the matched database and file backup into a fresh environment and switch traffic only after verification.

Archived organizations/leads/members retain data; restoration/purge requires a deliberate operator migration. Orphaned bytes are intentionally retained until a backup-aware retention process removes objects unreferenced by both live records and retained recovery points. There is no invented restore or purge button.

Revision `0007` adds payment-method flags/instructions and UPI/cash payment records.
It preserves existing UPI references and defaults cash to disabled. Its downgrade
refuses when any COD payment history exists, before schema changes, because the old
schema cannot represent cash without fabricating a UPI reference. Keep the new
schema/application or restore a matched earlier recovery point deliberately;
do not delete payment history to force a downgrade. Fresh upgrades, UPI-only
rollback/re-upgrade, legacy preservation and this cash-history guard are covered
by the payment regression suite.


## Repeat the local container verification

Use a separate Compose project, its own generated secret file, an override binding web to a free loopback port, and its own volumes. After explicitly seeding that development stack, run:

```bash
.venv/bin/python scripts/verify_container.py --project aven-final-qa --env-file .local/qa-container.env --override .local/qa-compose.yaml --url http://localhost:18080
```

The smoke script refuses a non-development environment or a project not prefixed `aven-`. It checks the built frontend, proxy headers, login cookie, creates an isolated QA organization, uploads a private image, restarts API/worker/web, verifies refresh/database/file persistence, revokes its session and archives only its own QA organization. It never targets the reference services. Browser tests accept `E2E_BASE_URL`, `E2E_BROWSER` (chromium/firefox), and `E2E_ARTIFACT_DIR`.
