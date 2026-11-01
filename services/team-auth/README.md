# GitHub sign-in and owner-only research API

This Worker provides real GitHub sign-in for the existing public Pages app. Any
GitHub user may authenticate. Authentication does **not** establish team membership.
Only the identity returned by GitHub with numeric user ID `350433501` may read the
research memo. The private repository and its collaborator permissions are not
changed by this service. No private memo content, credential, token or real-user
test fixture is shipped in this directory.

## Deployment prerequisites

1. Create a Cloudflare account and Workers application. Keep the stable production
   Worker hostname; it determines the OAuth callback. This source has not been
   deployed merely by being committed. The SQLite Durable Object binding is
   `AUTH_STATE`. The included `new_sqlite_classes` migration works with Wrangler's
   supported migration format; do not change it to legacy `new_classes`.
2. Register a **public GitHub App** to allow other GitHub accounts to complete
   identity login. A private App restricts who can authorize it and cannot promise
   arbitrary-user login. Public *App registration* does not publish the private
   repository or permit other users to read the memo. Install it on the owner's
   account, selecting **only** `supercon-research-notes` and **Contents: read-only**.
   Do not request organization, member-list, email, administration or write
   permissions. Leave expiring user tokens enabled. Device flow is not needed.
3. Set Homepage URL to `https://diracmagic.github.io/supercon-ml/`. Set the GitHub
   App callback to `https://<actual-worker-host>/auth/github/callback`, exactly.
   Do not use the Pages URL as the provider callback. The Worker redirects back
   to Pages after it has exchanged and checked the GitHub grant.
4. Configure `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `SESSION_KEY` as
   Cloudflare runtime secrets. `SESSION_KEY` is an unpadded base64url encoding of
   32 random bytes. Enter values using the hosting platform's secret controls or
   an interactive secret prompt, never shell arguments, repository files, chat,
   screenshots or logs. Client ID is not the GitHub App numeric App ID.
5. Run `node --test tests/*.test.mjs` from this directory. Validate the deployment
   with Wrangler before publishing, then configure the public frontend with only
   the actual HTTPS API origin. The API fails closed while configuration is
   absent. Perform real owner and non-owner browser acceptance before claiming
   production authentication works.

No refresh tokens are stored or used. The user access-token flow needs the App's
client secret; this implementation does not use installation JWTs/private keys
or a broad personal access token. No OAuth `repo` scope is requested. GitHub App
permissions and the authenticated user's permissions both restrict private reads.

## Browser/API contract

The sole CORS origin is `https://diracmagic.github.io`; the sole return document
is `https://diracmagic.github.io/supercon-ml/`. The backend never accepts a caller's
return URL, repository ID, filename, account ID or role as authorization.

| Endpoint | Contract |
| --- | --- |
| `GET /health` | Public configuration-readiness check only: `{status:'ready',configured:true}` or a 503 configuration error. Does not return settings/secrets and does not claim a successful GitHub registration, consent or login. |
| `GET /auth/start?challenge=...&state=...` | Each field is 43 base64url characters. `challenge` is SHA-256 of the browser's 43-character verifier. Creates a 10-minute server transaction, provider PKCE and a Secure/HttpOnly/SameSite=Lax host cookie, then redirects to GitHub. |
| `GET /auth/github/callback` | Validates transaction state, cookie and callback binding; atomically consumes it; exchanges GitHub's code and reads `/user`. Returns to Pages with `#team_ticket=...&team_state=...`, or a fixed `team_error` code. |
| `POST /auth/exchange` | Exact JSON `{ticket,verifier,state}`. Five-minute ticket, bound to browser PKCE and client state, consumed atomically once. Returns `{session_token,expires_at,user:{id,login},can_read_memo}`. |
| `GET /api/session` | Bearer session; revalidates GitHub identity. Returns the same session metadata without its token. |
| `GET /api/memo` | Bearer session; revalidates GitHub identity and the numeric owner guard on every read. Returns only `{entries,reviewed_on,updated,entry_count}`. |
| `POST /auth/logout` | Bearer session; destroys that session. It does not modify other sessions or repository access. |

`expires_at` is Unix **milliseconds**. Ticket and session tokens are 43 base64url
characters. Session lifetime is at most one hour, bounded by the provider token's
expiry measured at grant receipt. The frontend keeps the bearer session only in
memory. Only transient login state/verifier may survive the top-level redirect;
clear them after completing or abandoning the flow. Strip callback fragments
immediately. Never put the session or GitHub token in a URL, browser persistence,
service-worker cache, analytics event or error report.

All API fetches use `credentials: 'omit'`, exact-origin CORS and the Authorization
header. This avoids reliance on third-party cookies after returning to Pages.
The provider transaction cookie is only used during top-level backend navigation.
Sibling projects hosted under `diracmagic.github.io` share the same browser origin;
CORS cannot distinguish their paths. Keep that origin's scripts trusted, and use
a separate app origin if that trust boundary changes.

## Private-data boundary

GitHub tokens are AES-GCM encrypted with fresh IVs and type/token-specific AAD
before entering Durable Object storage. Object names use hashes of random
capabilities. The transaction, ticket and session are separate objects; atomic
transactional consume prevents parallel replay. Alarms remove expired records.
There is no frontend credential or unauthenticated private-data route.

Every memo read resolves repository ID `1442131882`, requires it to remain private
and owned by numeric ID `350433501`, then pins one `main` commit for all reads.
Only `data/external_research_memo.json` and the three fixed
`data/external-research-memo/part-01.json` through `part-03.json` paths are allowed.
Each file's decoded bytes must match the GitHub Contents API's Git blob SHA-1;
each part must also match the manifest's `translation.part_sha256`. External
download URLs and arbitrary manifest paths are never fetched. Payload sizes,
entry counts, IDs, HTTPS links, progress statuses and output fields are bounded.
Unknown fields are omitted; raw HTML is not rendered by this API contract.

All responses use `Cache-Control: private, no-store`. The frontend must also
exclude auth/private endpoints from its service worker and clear rendered notes
on logout or rejected/expired sessions. Private responses cannot be included in
the static app bundle or offline fallback. Revoked GitHub credentials cause a
401 on the next identity check and the corresponding server session is deleted.
Upstream errors fail closed; there is no cached-private fallback. An owner can
also disable the App installation or rotate secrets. Rotating `SESSION_KEY`
invalidates stored encrypted grants/sessions. Cloudflare storage backups may
retain ciphertext according to the hosting plan's retention policy.

Worker observability is disabled in configuration, and application code writes
no logs. Do not enable request-body/token/query capture when operating this
service. Consider platform rate limits for the public login endpoints before
wider use; cryptographic challenge validation is not a bot-cost control.

## Verification and limits

Tests use a memory Durable Object adapter and a fake GitHub transport containing
only invented records. They exercise callback cookies/state, both PKCE stages,
parallel replay, expiry, owner/non-owner access, upstream identity substitution,
revocation, logout, exact CORS, path/hash/size bounds and secret redaction. These
tests do not prove the Cloudflare deployment, GitHub App registration, account
consent or real browser redirect has been completed.

Official references: [GitHub App visibility](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/making-a-github-app-public-or-private),
[user authorization and PKCE](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app),
[identity permissions](https://docs.github.com/en/rest/users/users#get-the-authenticated-user),
[Contents read permission](https://docs.github.com/en/rest/repos/contents#get-repository-content),
[Durable Object transactions](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/),
[SQLite namespace migration](https://developers.cloudflare.com/durable-objects/best-practices/access-durable-objects-storage/).
