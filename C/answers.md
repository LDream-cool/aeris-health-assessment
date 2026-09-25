# Task C - Xero Integration Review

## Assumptions

- Xero Accounting API (`/api.xro/2.0`), OAuth 2.0 Authorization Code flow, and a multi-tenant server-side application. No particular SDK is assumed.
- Background workers synchronise invoices. Tokens, tenant IDs, and sync state are associated with each connected organisation. If organisations share an OAuth grant, token refresh is coordinated across those connections.
- For C5, one internal order creates one sales invoice (`ACCREC`) per tenant. Retry policies and database constraints below are application design choices, not Xero guarantees.
- Official documentation checked on 24 September 2026. Scope availability depends on the app's migration status. Codex assisted with research, drafting, and review.

## C1 - Connection verification

1. Load the connection's access token and stored expiry. If expired or close to expiry, refresh through `POST https://identity.xero.com/connect/token`. A successful refresh proves the refresh credentials were accepted; expiry metadata alone does not prove the access token is still valid.
2. Call `GET https://api.xero.com/connections` with `Authorization: Bearer <access_token>`. A successful response proves that token is accepted for listing connections.
3. Match the stored tenant ID against a returned `tenantId` with `tenantType: ORGANISATION`. This proves the intended organisation is connected for this authorization. Use that value as `xero-tenant-id`, not the connection's separate `id`.

Stop if no match exists. These checks establish authentication and tenant selection, but do not prove invoice scopes or permissions. See [Authorization Code flow][oauth].

## C2 - Failure diagnosis

After `/connections` succeeds, inspect the failing invoice request and its sanitised error body. These are starting points, not universal rules; tenant and permission failures can overlap status categories. See [response codes][errors] and [error handling][troubleshooting].

- **401 -> investigate authentication first.** Is the worker using the same current access token, with the Bearer header? Check expiry, stale cached tokens, and accidental use of an ID token. Refresh an expired token and retry once. If it still fails, investigate revocation or disconnection and request reconnection when necessary.
- **403 -> investigate authorization first.** Check granted invoice scopes, then the exact `xero-tenant-id`. Verify the authorising user still has the required organisation permissions and the organisation remains active. A listed connection is not proof of invoice access.
- **404 -> investigate the path and resource first.** Verify `https://api.xero.com/api.xro/2.0/Invoices` and any appended InvoiceID. Confirm the resource belongs to the selected tenant; do not reuse IDs from another organisation or environment.

For every branch, compare development, staging, and production: client ID, secret version, registered redirect URI, granted scopes, token storage, tenant mapping, request URL, and resource IDs. A successful connection check in one environment says nothing about another worker's configuration.

**Refresh handling:** request `offline_access` for background refresh. Access tokens last 30 minutes; unused refresh tokens expire after 60 days. Save the replacement access/refresh tokens and expiry together, with one refresher per OAuth grant. A lost refresh response has a documented 30-minute grace period for retrying the previous refresh token; an unusable grant requires reauthorization. See [token types][tokens] and [OAuth FAQ][oauth-faq].

**Scopes:** check what was actually granted, not just what the app requested. Current granular scopes include `accounting.invoices`; older grants may still use broad transaction scopes during migration. Request only the access needed, and obtain fresh user consent when adding scopes: existing tokens do not gain them automatically. See [granular scopes FAQ][scopes].

## C3 - Incremental synchronisation

Use one active sync per tenant and store a committed UTC high-water mark: the time through which a complete scan has succeeded.

1. Read the previous mark `C`; save this run's start time `T`. Request invoices with `If-Modified-Since: <C minus a small overlap>`, using the documented UTC timestamp format. On the first run, perform a full paginated import.
2. Fetch `page=1`, then subsequent pages, using the same lower bound and consistent ordering, such as `InvoiceId ASC`. The documented default page size when using `page` is 100. Continue until a short or empty page. See [Invoices][invoices].
3. Commit each page with an **upsert**: insert a new local row, or update the existing one, keyed uniquely by `(tenant_id, InvoiceID)`. Reprocessing the same invoice must not create another row or repeat business side effects. Avoid overwriting newer data with an older `UpdatedDateUTC`.
4. Only after every page is fetched and saved successfully, set the committed mark to `T`, not the completion time or largest timestamp seen. The intended coverage is from `C` through `T`; newer records returned during the scan can also be saved and safely replayed next time.
5. If a page fails or the worker crashes, keep the old committed mark. Restart from page 1 with that mark and the overlap. Already committed pages are safe to replay, so a saved page number is not needed for correctness.

Assume a reasonably synchronised server clock; a small overlap, for example two minutes, reduces timestamp-boundary risk. Do not assume numbered pages form a frozen snapshot during concurrent edits. Keep ordering consistent and periodically reconcile a wider range if completeness is critical; overlap alone is not an absolute guarantee.

## C4 - Rate limits

On **429**, reschedule the job rather than retrying in a tight loop:

- Honour `Retry-After` in seconds. Use a delay of at least that value, combined with capped exponential backoff and random jitter so workers do not retry together.
- Inspect `X-Rate-Limit-Problem`, `X-MinLimit-Remaining`, `X-DayLimit-Remaining`, and `X-AppMinLimit-Remaining`. Pause the affected tenant, or the whole app when its allowance is exhausted. Daily allowances can depend on tier. See [rate limits][limits].
- Share concurrency and request-rate controls across workers, both per tenant and application-wide. A simple starting point is one in-flight request per tenant, plus an application-wide cap.
- Use a finite attempt/time budget, for example five attempts per job execution. Persist the next retry time. After exhaustion, retain the failed job for inspection or later scheduled recovery; alert on repeated failures.

Normally do not blindly retry validation-related **400**, permission-related **403**, or genuine resource/path/configuration **404** errors. Correct the cause first. For **401**, refresh an expired token and retry once where appropriate. Temporary network failures, selected **5xx** responses such as 503, and **429** can use controlled backoff. Creation retries must also follow C5 because a missing response does not mean nothing happened. See [response codes][errors].

## C5 - Data integrity

**A timeout can mean Xero created the invoice but the response was lost. Sending another create request immediately can create a duplicate.**

1. Before sending, persist the create intent, exact payload, and a stable, unique `Idempotency-Key` for this logical operation. Enforce local uniqueness on `(tenant_id, internal_order_id)` and allow only one worker to create it at a time.
2. Retry the same request with the same key within Xero's retention window. Xero caches idempotent responses for **6 minutes from the first call**. Reusing a key with a different request is invalid; after expiry the key no longer prevents another creation. See [idempotent requests][idempotency].
3. On confirmed success, durably store the internal-order-to-Xero-InvoiceID mapping and mark the operation complete. Also enforce uniqueness on `(tenant_id, InvoiceID)`. Later order retries return that mapping instead of creating again.
4. If the response is lost, mark the outcome as unknown. A same-key replay within the window can recover the response. Before any fresh create, check Xero: use a known InvoiceID, or a deterministic, app-assigned sales InvoiceNumber agreed with the business. Sales invoice numbers are unique in Xero and can be queried; verify the matching invoice's details before saving the mapping. See [Invoices][invoices].
5. After key expiry, do not blindly resend, even with the old key. Reconcile first. Only begin a new create when absence is established and no earlier request remains in flight. If the result is still uncertain, stop for review instead of guessing.

The short-lived key protects transport retries; the durable mapping protects future business retries.

## C6 - Observability and security

- **Structured logs:** sync/job ID, local request ID, returned `Xero-Correlation-Id` where available, internal organisation ID, a hashed tenant identifier, internal order ID, Xero InvoiceID where known, endpoint/action, HTTP status, retry attempt, duration, and final outcome. Keep a safe error category without dumping response bodies. Xero shows its correlation header in the [rate-limit response example][limits].
- **Metrics:** sync successes/failures, 401/403/429/5xx counts, retries, API latency, records processed, queue depth, and sync lag or age of the last successful sync.
- **Alerts:** repeated authentication failures, excessive throttling, growing sync lag, abnormal failure rates, and repeatedly failed/dead-letter jobs (jobs set aside after exhausting retries). Include the job identifier and a clear next action.
- **Never log** access tokens, refresh tokens, client secrets, or Authorization headers. Avoid complete invoice/customer payloads. Apply redaction to HTTP tracing and exception reporting too.
- **Protect credentials:** encrypt tokens and secrets in an appropriate credential store, restrict access to the workers that need them, and separate environment credentials. Use least-privilege scopes and access controls for stored data and logs. Persist refreshed tokens atomically, preventing an older worker from overwriting newer credentials. Follow [Xero security guidance][security] and [token handling][tokens].

## References

Only official Xero Developer sources are used:

- [Authorization Code flow and connections][oauth]
- [Token types and refresh handling][tokens]
- [OAuth 2.0 FAQ][oauth-faq]
- [Granular scopes and migration FAQ][scopes]
- [Accounting API: Invoices][invoices]
- [Accounting API: HTTP response codes][errors]
- [Error handling and tenant/permission diagnosis][troubleshooting]
- [Rate limits and response headers][limits]
- [Idempotent requests][idempotency]
- [Security standard for Xero API consumers][security]

[oauth]: https://developer.xero.com/documentation/guides/oauth2/auth-flow
[tokens]: https://developer.xero.com/documentation/guides/oauth2/token-types
[oauth-faq]: https://developer.xero.com/faq/oauth2
[scopes]: https://developer.xero.com/faq/granular-scopes
[invoices]: https://developer.xero.com/documentation/api/accounting/invoices
[errors]: https://developer.xero.com/documentation/api/accounting/responsecodes
[troubleshooting]: https://developer.xero.com/documentation/best-practices/user-experience/error-handling
[limits]: https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits
[idempotency]: https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/
[security]: https://developer.xero.com/partner/security-standard-for-xero-api-consumers
