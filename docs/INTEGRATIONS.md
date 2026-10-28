# Integration setup and verification boundaries

## IndiaMART

The adapter calls the fixed HTTPS v2 CRM endpoint at `https://mapi.indiamart.com/wservice/crm/crmListing/v2/` using `glusr_crm_key`, `start_time` and `end_time`. Records map `UNIQUE_QUERY_ID`/`QUERY_ID`, `SENDER_NAME`, `SENDER_MOBILE`, `SENDER_CITY`, `SENDER_STATE` and `QUERY_MESSAGE`. A 200/204 provider code is accepted. Provider HTTP failure, 429, malformed response and missing entitlement are surfaced with bounded retry; raw response bodies and credential-bearing URLs are not included in product errors.

1. Confirm current CRM API entitlement and the v2 contract in your IndiaMART seller account. Generate a separate CRM key for this environment.
2. In Integrations → IndiaMART, enter the key and enable polling.
3. Ensure the worker is online. Polling is scheduled every 15 minutes, with a five-minute overlap and provenance/phone deduplication.
4. Use Sync now and inspect the sync run. The initial request covers the prior day. A recovered cursor fetches bounded seven-day windows so a long outage can catch up without skipping the older cursor.
5. Create a real test enquiry through the provider account. Verify exact source, details, unassigned owner, counts and retry deduplication.

The key is encrypted at rest and never returned in API responses or audits. Rotating `ENCRYPTION_KEY` without re-encrypting records will make stored secrets unreadable; keep a protected backup of it. Disconnect erases the stored credential and pauses the integration. Reconnecting requires a new credential.

Public official documentation was not sufficient to independently verify every current account-specific entitlement. The implementation follows the v2 field contract, and deterministic provider response tests are included. **No real IndiaMART delivery was tested; credentials and provider-side confirmation remain required.** Do not describe a configured key alone as a verified connection.

## Justdial push

1. Agree lead-push activation, payload mapping and authentication transport with your Justdial account manager. There is no assumed self-service connection.
2. Configure a unique random token of at least 16 characters in Integrations → Justdial.
3. Register `POST https://YOUR_DOMAIN/api/webhooks/justdial/ORGANIZATION_ID`. Send the secret in `X-Webhook-Token`. Never put it into a public page or browser bundle.
4. The baseline JSON mapping accepts one record or up to 100 records. Supported identity fields are `leadid`/`id`, `name`/`customer_name`, `mobile`/`phone`, `city`, `state`, and `enquiry`/`message`. Provider-shaped `SENDER_*` aliases are also supported.
5. Check actual provider payload examples before activation. If your contracted delivery format or authentication differs, configure an approved private gateway to map that contract; do not claim it is connected until a genuine push is verified.

Requests without a valid token, to a paused/disconnected integration, or to a suspended organization cannot create leads. External IDs and normalized phones prevent repeated delivery duplicates. Accepted leads remain unassigned. Credentials for one organization cannot ingest into another.

Tests use simulated provider payloads, retries and failures; **actual Justdial delivery and its account-specific contract remain unverified**.

## Android calling companion

The separately authorized Android companion reads the phone's call log after employee consent and OS permissions, then uses `POST /api/phone-calls/sync` with an installation ID and per-call stable identifiers. The OpenAPI schema documents exact fields. Only currently assigned unambiguous lead numbers are stored. The app retains pending work in SQLite, encrypts its session with Android Keystore, and uses WorkManager plus a bounded user-started transfer service. See [Android setup and limitations](../android/README.md).

The phone's built-in recorder creates the audio; the APK uploads accessible recordings from the explicitly selected folder. Recording files are uploaded to `POST /api/leads/{lead_id}/files` as multipart `file` plus `phone_call_id`. Supported audio containers are validated; linked recordings allow up to 64 MiB by default, while ordinary attachments retain a 10 MiB limit. Reusing the same recording on an unrelated call is rejected. Web and mobile history/playback use authenticated requests and current permissions. Telecallers cannot delete audio, including their own recordings. Emulator tests use synthetic audio and do not certify two-speaker recording or folder access on a physical OPPO or another OEM phone.

## External documentation consulted

- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/) and [API reference](https://fastapi.tiangolo.com/reference/).
- [SQLAlchemy row locks](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.Select.with_for_update).
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview) and [Vite setup](https://vite.dev/guide/).
- [Pillow content verification](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify) and [Mutagen media containers](https://mutagen.readthedocs.io/en/latest/api/base.html).

Installed exact dependency versions and transitive versions are locked in the repository. No original application source was copied or modified.
