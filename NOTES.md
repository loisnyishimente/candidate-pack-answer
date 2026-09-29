# Engineering notes

## Design

The central records are `User`, `Episode`, `DatasetRequest`, `Assignment`, and `StatusHistory`. A request belongs to one client. Assignment is the join between requests and episodes, with a unique constraint on `episode_id`; this makes “at most one request at a time” safe even under concurrent API calls. A request stores its current status for fast listing, while every initial submission and subsequent change is appended to `StatusHistory` with actor and timestamp. The API and PostgreSQL are the sources of truth; React holds only transient presentation state and the browser token.

The hardest decision was how strictly to encode the workflow. I chose a small transition matrix keyed by actor role instead of accepting arbitrary status updates. It is easy to audit: operators/admins own submitted → in progress → delivered and rejected → in progress, while the owning client alone can accept or reject a delivered request. Delivery also checks the assigned count in the same transaction.

For duplicate assignment, I use both a readable application error and a database uniqueness constraint. The database constraint is essential because two operators may race after both have observed an available episode. A production-heavy version would additionally lock selected episode rows (`SELECT ... FOR UPDATE`) so the loser receives a predictable conflict before insert.

For import, I treat `episode_id` as the upstream identity and normalize casing/whitespace before comparison. Duplicate IDs, unknown robots, invalid dates/durations/quality, and missing required values are skipped with line-numbered reasons; valid rows are committed. Re-importing the file therefore adds nothing. Known date variants are parsed explicitly rather than guessing. I chose partial success because one malformed export row should not discard hundreds of valid episodes.

## Deliberate scope

I did not select a stretch item: correctness and operability of the required system were more valuable within the stated time box. The interface intentionally has no design system, pagination UI, assignment removal, bulk picker, analytics charts, password reset, refresh tokens, or CSV import screen (the documented API endpoint is available through Swagger/curl). Admin user APIs are complete but the small UI focuses on the explicitly requested client/operator journeys.

With two more days I would add cursor pagination and richer task/quality filters, an operator import/report screen, assignment removal with an audit trail, UI/API contract tests, rate limiting on login/import, and a production-scale `COPY` staging importer. I would also make status transition and assignment updates use explicit row locking, and expose actor names in the history response.

## Something that went wrong

The first analytics implementation naturally computed the median after fetching delivery durations. Reviewing it against the brief caught that this violated the requirement that analytics be computed in the database. I replaced that shape with a window/rank query so the database computes the median while the API only serializes its scalar result. This was a useful reminder that a correct number is not necessarily a correct implementation when data volume is part of the requirement.

## Security

Passwords are never stored directly: they use PBKDF2-HMAC-SHA256 with a unique random salt and 600,000 iterations. Login returns a signed, expiring HS256 bearer token. Authentication is required by dependency on every non-public operation; role and client ownership checks run server-side. Pydantic validates types, lengths, counts, dates, emails, and enum values. SQLAlchemy binds query parameters, avoiding SQL injection. CSV fields are treated as data rather than executed, and imports have explicit type/domain checks.

Production would require HTTPS, a secret-manager-provided signing key, shorter access tokens plus rotating refresh tokens (preferably in secure HttpOnly cookies), login throttling, audit-log retention, upload/body limits, and security headers. The two risks I would watch most closely are broken object-level authorization (one client reading/changing another client’s request) and resource exhaustion through very large CSV uploads or costly unbounded queries. Tests cover the first; ingress limits, streaming/chunked import, pagination, timeouts, and rate limits address the second. XSS is also relevant because notes/task names originate with users; React escapes rendered strings by default and the app does not inject raw HTML.

## Scale

At 10× users, the first pressure points are list endpoints without pagination, database connection limits, and competing assignment writes. I would add cursor pagination, tune a bounded connection pool, use row locks for assignment/workflow mutations, and run multiple stateless API workers behind a load balancer.

At 100× episodes, the synchronous ORM importer and available-episode search break first. The importer currently reads the upload into memory and creates ORM objects row by row. I would stream uploads to object storage, validate asynchronously into an unlogged staging table with PostgreSQL `COPY`, and merge using `ON CONFLICT`. Episode browsing would use keyset pagination plus selective composite indexes. The analytics queries already aggregate in the database and have date/robot/quality indexes; I would validate them with realistic `EXPLAIN (ANALYZE, BUFFERS)` runs, partition episodes by recorded month if maintenance/query pruning justified it, and introduce daily rollups or a read replica only after measurement.

## AI tooling

I used OpenAI Codex to accelerate scaffolding, test construction, and review against the brief. I reviewed the generated domain rules, schema, import policy, and security decisions and can explain or modify them. No generated code was accepted merely because it compiled; the tests and written trade-offs target the assignment’s stated evaluation criteria.
