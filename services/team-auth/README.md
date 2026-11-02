# Team sign-in and private research API

This Worker provides real GitHub sign-in for the existing public Pages app. Any
GitHub user may authenticate. Authentication does **not** establish team membership.
The identity returned by GitHub with numeric user ID `350433501` is the sole team
administrator. The administrator and explicitly invited, verified email/password
members may read the research memo. Membership does not grant GitHub repository
collaborator permissions. No private memo content, credential, token or real-user
test fixture is shipped in this directory. Ordinary GitHub sign-in does not
automatically create membership or link to an email account.

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

## Invited email/password members

Firebase Authentication manages user-chosen passwords, email verification and
password reset. The browser sends passwords directly to Firebase, not this
Worker. Use the Spark project configured by the public `FIREBASE_PROJECT_ID` and
`FIREBASE_API_KEY` variables. Enable email/password authentication, a suitable
password policy and email-enumeration protection. Configure authorized domains
for the Pages app and the Worker email-action host. Set the email templates'
custom action URL to `https://<actual-worker-host>/auth/email/action`. Its GET
handler does not consume a code: it returns a no-store redirect to the fixed
Pages app with the action code in a fragment, which the app immediately removes.
The browser uses only its configured project key and fixed return URL.

This design intentionally permits Firebase identity registration through its
public API. Registration alone gives **no access** to the team or memo. The
administrator invites an email using the application API. A new provider account
is initialized with a cryptographically random, unshared password that is never
stored by the Worker; the recipient sets their own password through Firebase's
built-in password-reset email. For an existing Firebase account, the invitation
remains bound to its email until a fresh, provider-verified login atomically binds
the UID. Do not claim that all Firebase sign-up is disabled.

An application membership invitation does not expire, including invitations
issued by earlier versions. Firebase's single-use password and verification links
still expire according to Firebase's rules; the administrator can resend them.
Joining requires a fresh login after the original invitation was issued.
The login must have a currently verified email, match the invitation, and use the
password provider. If setting a password did not verify the email, the app must
complete Firebase's verification-email flow before joining. No admin code marks
an unverified email as verified. An email request marked `accepted` means Firebase
accepted the request; it is not proof of delivery. Failed sends remain visible in
the administrator's member list. Resending a pending invitation preserves its
original login threshold, pinned Firebase UID and any earlier accepted invitation;
a failed resend does not withdraw that invitation. It advances the authorization
version and reports the latest email request status. Inviting an active member is
an explicit no-op and does not send an email. Revocation invalidates all application
sessions and hides the member from the list, while retaining an internal tombstone
to reject stale in-flight invitations. Deliberately inviting that email again starts
a new authorization version and requires a fresh login after the new invitation.

An optional display name is trimmed, consecutive spaces are collapsed, and names
are limited to 80 characters without control characters. Existing records without
a name return an empty string. Only the administrator may edit names; a name edit
does not change identity, permissions, authorization versions or sessions, and sends
no email. Names are display data, never an authorization input.

The `TeamDirectory` SQLite Durable Object uses the `TEAM_DIRECTORY` binding and
the additive `v2` migration. It caps the directory at 100 retained member records and persists
per-IP/global login limits and per-email/global invitation limits. Only the
GitHub administrator may list, invite or revoke members. Anonymous responses do
not disclose the membership list. No Firebase service-account key or project IAM
role is required. The public Firebase key may be API-restricted; browser-only
HTTP-referrer restrictions would block this Worker's server-side requests.

Firebase private session checks and memo reads also share persistent limits:
12/minute and 120/hour per member, 120/minute and 600/hour for the team. These
budgets allow minute polling and ordinary note openings for a small team while
bounding provider work. Limits run before Google/GitHub requests; identity,
membership and installation checks are never replaced with a cached success.

Every email session is revalidated through Google's authenticated `accounts:lookup`
for the exact ID token. Decoding JWT claims is only preliminary validation, never
the authenticity check. Project, issuer, expiry, UID, verified email, provider,
disabled status, `validSince` and `passwordUpdatedAt` are checked. Missing
revocation fields fail closed. The encrypted ID token is kept only until its
expiry; no Firebase refresh token persists. Password changes and membership
version changes invalidate existing application sessions on their next check.

Members read notes using a short-lived GitHub App installation token minted from
the Cloudflare secret `GITHUB_APP_PRIVATE_KEY`. The installation reader pins App
ID `5570777`, installation `177619503`, owner `350433501`, repository `1442131882`
and read-only Contents/Metadata permissions. It revalidates the installation and
restricts every issued token to that one repository. Installation tokens never
reach the browser. Removing or widening the installation fails closed. The key
and actual email delivery/login must be configured and verified before claiming
the deployed member flow works.

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
| `GET /api/session` | Bearer session; revalidates its provider identity, current membership and private-source access. Returns the same session metadata without its token. |
| `GET /api/memo` | Bearer session; revalidates provider identity and administrator/member authorization on every read, including a membership check after loading. Returns only `{entries,reviewed_on,updated,entry_count}`. |
| `POST /auth/logout` | Bearer session; destroys that session. It does not modify other sessions or repository access. |
| `GET /auth/email/action` | Accepts a unique `mode` (`resetPassword`, `verifyEmail`, or `recoverEmail`) and bounded `oobCode`; optional `apiKey` must equal configured project key. Ignores caller continuation URLs. Redirects to the fixed app's `team_email_mode`/`team_email_code` fragment without consuming the code. Recovery never signs in automatically. |
| `POST /auth/firebase` | Exact JSON `{id_token}`. Google validates the token, then the directory claims/checks the invitation. Returns the same bounded bearer session contract, with `user.provider:'firebase'`, `user.id:'firebase:'+UID`, and the member's own email. |
| `GET /api/team` | GitHub administrator only. Returns `{members:[...]}` with opaque member IDs, optional display name (empty string if absent), email, status, timestamps, version and delivery status. Revoked records are excluded. |
| `POST /api/team/invite` | GitHub administrator only. `{email}` with optional `name`; unknown fields are rejected. Creates/reissues an invitation or resends a pending one. Returns `{member,email_request:'accepted'}` after Firebase accepts the email request; this does not promise delivery. For an active member, returns `email_request:'not_sent_active'` without sending an email or changing the name. Omitting `name` on resend preserves the existing name. Limited to one request per email per minute and 20 requests per hour globally. |
| `POST /api/team/revoke` | GitHub administrator only. Exact `{member_id}`; returns `{member}`, increments its authorization version and removes it from the visible list. |
| `POST /api/team/name` | GitHub administrator only. Exact `{member_id,name}`; changes display data for an invited or active member. Returns `{member}`. Revoked records cannot be renamed; no email is sent. |

Session metadata includes `can_read_memo` and `can_manage_team`; only the verified
GitHub administrator receives the latter. Health also reports boolean
`github_login`, `email_login`, and `team_notes` configuration flags. These flags
do not perform real provider login, verify a configured key, or send an email.

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

GitHub user tokens and Firebase ID tokens are AES-GCM encrypted with fresh IVs and type/token-specific AAD
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

The team message board uses the separate `TEAM_BOARD` binding and the additive
`v3` SQLite migration for `TeamBoardDO`. Its Worker route rechecks the same live
identity, active membership and repository access as private Notes. A member's
current administrator-assigned display name is captured when posting; blank names
become `Team member`. Email addresses and internal actor IDs are never returned.

`GET /api/board` returns the latest 50 messages in ascending ID order. `before=N`
pages older messages; `after=N` pages newer messages; `limit` is 1–50. The response
is `{messages, latest_id, has_more}`, where each message contains `id`, `body`,
`created_at` (epoch milliseconds), and `author: {name, is_self}`. `has_more` refers
to older history for initial/`before` pages and newer messages for nonzero `after`.
`POST /api/board` accepts only `{body}` and returns `{message, latest_id}`. Trimmed
plain text is limited to 2,000 UTF-16 code units and the request to 8 KiB; control
characters other than LF/TAB are rejected. Transactional limits allow one message
per three seconds and twenty per rolling hour per actor. Messages use independent
durable keys, with no automatic deletion. Member reads share the existing private
API rate budget, so visible-page polling should run no faster than once a minute.
No board messages are logged, cached publicly, or written during synthetic tests.
Revocation is acknowledged only after a persistent membership-version fence is
written to the board's own transaction queue. An old in-flight append after that
fence is rejected, even following an object restart or later reinvitation. A post
that commits before the fence is an accepted in-flight operation and receives its
success receipt; it is not falsely reported as a failed post after committing.

`GET /api/presence` uses the same live team and repository authorization as the
board. Its response is `{presence: {members, window_seconds: 150, observed_at}}`;
each active member has only `{name, is_self, online: true}`. No email, membership
ID, provider ID, or session key is returned. "Online" means a successful verified
board/session/presence request within the preceding 150 seconds, not a confirmed
live connection. The timestamp is the server's check time. Closed or hidden apps
age out; it is not an offline team roster. Names are server-assigned and duplicate
devices appear as one person. This same object piggybacks existing board and
eligible session responses so clients need no new polling loop. Manual presence
reads share the existing private API rate limits.

Presence uses the existing board object and private, non-cacheable responses.
Only internal session hashes and short-lived activity records are stored there.
Logout removes that session, retaining other active devices; a durable logout
fence lasts until the session expiry so a delayed request cannot restore it.
Member revocation removes all its devices in the same transaction as the existing
revocation fence. Expired activity and logout fences are pruned on subsequent
updates. External provider changes are detected on subsequent authenticated
requests; the recent-activity label does not claim continuous monitoring.

A token-endpoint HTTP 429 stores an application-wide cooldown deadline in the
existing `AUTH_STATE` namespace. Valid `Retry-After` seconds/HTTP dates are respected;
future `x-ratelimit-reset` epochs also apply when `x-ratelimit-remaining` is exactly
`0` (the longer applicable wait wins), capped at 24 hours;
missing or invalid hints use 60 seconds. This conservative pause does not identify
the provider's quota scope or guarantee success afterward. It blocks new GitHub
redirects and pending exchanges, consumes verified callback transactions once,
and never retries a one-use code. Only a deadline persists, with atomic maximum
updates; no provider response body or headers are stored. The APP receives the
fixed 429 diagnostic and bounded `login_retry_after` seconds. Email login is
unaffected. Existing in-flight provider requests may finish; no automatic retry
or background request is introduced.

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


### Installed desktop session bridge (APP 0.3.16)

The bundled main window starts a bounded native sign-in attempt before navigating
in the same window to the fixed hosted form. Existing GitHub PKCE and email
verification remain at the hosted origin. That exact hosted APP path has only
`complete_team_sign_in` and `cancel_team_sign_in` native permissions. Completion
validates the returned session with the fixed Worker, keeps its bearer in Rust
process memory and returns a fixed local home URL. Cancellation clears the native
epoch even if remote logout is unavailable. No credential is put in a URL, browser
storage or application file.

The local main window restores only server-verified session metadata. Its narrow
native request command accepts the existing private route/method/body allowlist;
it supplies the fixed service Origin header required by the Worker and never
accepts a caller-controlled host, header or credential. Redirects are rejected,
responses are bounded, live server membership checks remain authoritative, and
late responses from a cleared session are discarded. Native installer commands
remain local-only. UI reloads retain the in-memory session; process exit does not.
