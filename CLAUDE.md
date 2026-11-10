@AGENTS.md

# ViaCRM development and deployment

This is the current real-estate ViaCRM project. The owner authorized Claude
Desktop Code to implement requested ViaCRM changes, commit and push them, and
deploy through the existing GitHub Actions pipeline. Follow the scope of the
current request. Review-only work does not request a production change.

## Project and access

- Repository: https://github.com/akshayagrg147/ak_test_cm
- Production website: https://viacrm.in
- Customer login: https://viacrm.in/login
- Local Git and `gh` already authenticate as `akshayagrg147` on this Mac.
- AWS deployment uses the existing main-only GitHub OIDC role. Normal releases
  require no AWS root login, copied keys, SSH access, or new IAM permissions.
- Read `docs/AWS_DEPLOYMENT.md` before deployment or infrastructure work.

This folder is a separate Git worktree of the current deployed source. The
original `../talkocrm` folder has unfinished Android/documentation work and a
local QA branch (`fix/qa-06-event-loop-and-deps`). Preserve that folder and its
work. Reconcile any requested older QA changes with current `origin/main` before
testing or publishing them. The insurance worktree is a separate product.

## Commit and deploy requested changes

1. Inspect `git status`, the current branch and recent commits. Fetch
   `origin/main` before editing or preparing a release.
2. Work on the task branch. Integrate newer `origin/main` changes without
   discarding local or other people's work. Resolve conflicts deliberately.
3. Run the checks appropriate to the change. Commit only intended files; keep
   private `.env` files, credentials, customer records, recordings, backups,
   signing keys and generated artifacts out of commits.
4. Push the task branch with `git push -u origin HEAD` for branch CI. This does
   not deploy to AWS. For a requested production release, the tested commit must
   include the current main history, then use `git push origin HEAD:main` without
   force. A reviewed PR merge into `main` uses the same deployment pipeline.
5. Find the CI run for the exact pushed SHA and monitor all jobs, including
   `deploy`. A successful push alone is not a successful deployment:

   ```bash
   gh run list --repo akshayagrg147/ak_test_cm --branch main \
     --json databaseId,headSha,status,conclusion,url
   gh run watch RUN_ID --repo akshayagrg147/ak_test_cm --exit-status
   ```

6. After deployment, verify trusted HTTPS `/api/health` reports application,
   database and worker `ok`, and `/release.json` equals the intended full SHA.
   Preserve TLS verification. Report the actual commit, CI result and live
   verification. Diagnose failed checks rather than bypassing them.

## Checks and runtime

- Node 24; Python 3.12 for application development; PostgreSQL only.
- Create this worktree's own `.venv` and install `backend/requirements.lock`.
- Backend: from `backend/`, `../.venv/bin/ruff check app tests` and
  `TEST_DATABASE_URL=DEDICATED_TEST_DATABASE_URL ../.venv/bin/pytest -q`.
- Use a dedicated disposable database whose name ends in `_test`; tests can
  truncate it. Do not reuse the development or production database.
- Web: from `web/`, `npm ci`, `npm run lint`, `npm run build`.
- Browser: from the repository root, `.venv/bin/python scripts/test_browser.py
  --production`; this provisions disposable services/database/storage. Follow
  its help for focused runs; do not aim mutation suites at the live domain.
- Deployment scripts: `python3 -m unittest discover -s scripts/deploy
  -p 'test_*.py' -v` and `bash -n scripts/deploy/deploy.sh`.
- Record executed verification in `docs/ACCEPTANCE.md`.

## Preserve the live domain and client compatibility

The server's existing non-secret host settings are:

```dotenv
PUBLIC_HOST=viacrm.in
PUBLIC_ALIASES="www.viacrm.in 13.234.72.21"
TLS_DEFAULT_SNI=13.234.72.21
```

The private app environment uses `PUBLIC_ORIGIN="https://viacrm.in"`.
Domain/www/IP certificates are automatically managed by Caddy. Alias browser
pages redirect to the canonical domain. Legacy IP `/api` and `/api/*` paths
remain direct because installed Android clients reject redirects. Preserve
host-only Secure/HttpOnly/SameSite cookies and exact-origin protections.

Nginx resolves the API container at startup. Domain activation and rollback
force recreation of the web proxy along with the API; preserve that fix and
public API readiness checks. Static web health alone does not prove API health.
The manual domain and proxy recovery workflows share deployment locks. Inspect
an ambiguous SSM command before retrying it. Normal releases preserve the
existing host secrets, domain settings and persistent volumes.
