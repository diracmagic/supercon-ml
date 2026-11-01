import { APP_ORIGIN, APP_RETURN, OWNER_ID, REPOSITORY_ID, TOKEN_PATTERN, AuthError, boundedJson, demand, decryptToken, encryptionKey, encryptToken, equalSecret, jsonResponse, plainObject, randomToken, securityHeaders, sha256 } from './security.mjs';
import { stateAccess } from './state.mjs';
import { readMemo, verifyMemoAccess } from './memo.mjs';
export { AuthState } from './state.mjs';

const COOKIE = '__Host-supercon_oauth';
const TEN_MINUTES = 600000, FIVE_MINUTES = 300000, ONE_HOUR = 3600000;
const OAUTH_ERRORS = new Set(['oauth_state_invalid', 'oauth_denied', 'oauth_failed', 'oauth_credentials_invalid', 'oauth_redirect_invalid', 'oauth_exchange_unavailable', 'oauth_identity_unavailable']);
const PROVIDER_ERRORS = new Map([['incorrect_client_credentials', 'oauth_credentials_invalid'], ['redirect_uri_mismatch', 'oauth_redirect_invalid'], ['bad_verification_code', 'oauth_failed']]);
const PROVIDER_HTTP_STATUSES = new Set([301, 302, 303, 307, 308, 400, 401, 403, 404, 429, 500, 502, 503, 504]);
const httpDiagnostic = status => PROVIDER_HTTP_STATUSES.has(status) ? 'provider_http_' + status : 'provider_http_other';
const CALLBACK_DIAGNOSTICS = new Set(['callback_parameters', 'callback_state', 'code_invalid', 'provider_bad_code', 'transaction_storage', 'provider_denied', 'provider_credentials', 'provider_redirect', 'provider_transport', 'provider_response_json', 'provider_http_other', ...[...PROVIDER_HTTP_STATUSES].map(httpDiagnostic), 'provider_grant_error_unknown', 'provider_email_unverified', 'provider_token_format', 'provider_token_type', 'provider_expiry', 'provider_identity', 'ticket_encryption', 'ticket_storage', 'unexpected']);
const ROUTES = new Map([['/health', 'GET'], ['/auth/start', 'GET'], ['/auth/github/callback', 'GET'], ['/auth/exchange', 'POST'], ['/api/session', 'GET'], ['/api/memo', 'GET'], ['/auth/logout', 'POST']]);
const cookie = (value, expiry = 600) => COOKIE + '=' + value + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + expiry;
function cookieValue(request) {
  const matches = (request.headers.get('cookie') || '').split(';').map(value => value.trim()).filter(value => value.startsWith(COOKIE + '='));
  return matches.length === 1 ? matches[0].slice(COOKIE.length + 1) : '';
}
function parameters(url, required, optional = []) {
  for (const key of url.searchParams.keys()) demand([...required, ...optional].includes(key) && url.searchParams.getAll(key).length === 1);
  for (const key of required) demand(url.searchParams.has(key));
}
function callbackParameters(url) {
  // RFC 6749 section 4.1.2 requires ignoring unrecognized authorization response
  // parameters. Only these known fields are consumed; duplicates remain invalid.
  demand(url.searchParams.has('state'));
  for (const key of ['state', 'code', 'error', 'error_description', 'error_uri']) demand(url.searchParams.getAll(key).length <= 1);
}
function redirect(location, origin, cookieHeader) {
  const headers = securityHeaders(origin); headers.set('Location', location);
  if (cookieHeader) headers.set('Set-Cookie', cookieHeader);
  return new Response(null, { status: 303, headers });
}
function returnToApp(values, origin, diagnostic) {
  const destination = new URL(APP_RETURN);
  if (diagnostic) destination.searchParams.set('login_status', CALLBACK_DIAGNOSTICS.has(diagnostic) ? diagnostic : 'unexpected');
  destination.hash = new URLSearchParams(values).toString();
  return redirect(destination.href, origin, cookie('', 0));
}
const presentation = record => ({ expires_at: record.expiresAt, user: { id: record.user.id, login: record.user.login }, can_read_memo: record.user.id === OWNER_ID });

// Injectable dependencies are for local tests, never environment-driven mocks.
export function createHandler({ fetchImpl = (...args) => fetch(...args), now = () => Date.now() } = {}) {
  async function github(path, token, maximum = 131072) {
    demand(typeof path === 'string' && path.startsWith('/') && !path.startsWith('//'), 'upstream_unavailable', 503);
    let response;
    try {
      // Workers supports manual, not redirect:'error'; never forward a bearer token.
      response = await fetchImpl('https://api.github.com' + path, { redirect: 'manual', signal: AbortSignal.timeout(10000), headers: {
        Accept: 'application/vnd.github+json', Authorization: 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'supercon-team-auth',
      } });
    } catch { throw new AuthError('upstream_unavailable', 503); }
    if (response.status >= 300 && response.status < 400) { await response.body?.cancel(); throw new AuthError('upstream_unavailable', 503); }
    if (response.status === 401) { await response.body?.cancel(); throw new AuthError('session_revoked', 401); }
    const privateRead = path === '/repositories/' + REPOSITORY_ID || path.startsWith('/repos/diracmagic/supercon-research-notes/contents/');
    if (privateRead && [403, 404].includes(response.status) && response.headers.get('x-ratelimit-remaining') !== '0') {
      await response.body?.cancel(); throw new AuthError('memo_access_revoked', 403);
    }
    if (!response.ok) { await response.body?.cancel(); throw new AuthError('upstream_unavailable', 503); }
    return boundedJson(response, maximum);
  }
  async function githubUser(token) {
    const user = await github('/user', token);
    demand(plainObject(user) && Number.isSafeInteger(user.id) && user.id > 0 && typeof user.login === 'string' && /^[a-z\d][a-z\d-]{0,38}$/i.test(user.login), 'invalid_identity', 401);
    return { id: user.id, login: user.login };
  }
  async function getSession(request, env, key) {
    const token = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(request.headers.get('authorization') || '')?.[1];
    demand(token, 'invalid_session', 401);
    const record = await stateAccess(env, 'session', token, 'get', now());
    demand(record && record.kind === 'session', 'invalid_session', 401);
    try {
      const githubToken = await decryptToken(record.encrypted, key, 'session:' + await sha256(token));
      const user = await githubUser(githubToken);
      demand(user.id === record.user.id, 'invalid_session', 401);
      demand(await stateAccess(env, 'session', token, 'get', now()), 'invalid_session', 401);
      return { token, record: { ...record, user }, githubToken };
    } catch (error) {
      if (error instanceof AuthError && error.status === 401) await stateAccess(env, 'session', token, 'delete', now());
      throw error;
    }
  }
  return {
    async fetch(request, env) {
      const origin = request.headers.get('origin');
      let url;
      try {
        url = new URL(request.url);
        demand(url.protocol === 'https:' && request.url.length <= 4096);
        demand(!origin || origin === APP_ORIGIN, 'origin_denied', 403);
        demand(ROUTES.has(url.pathname), 'not_found', 404);
        if (request.method === 'OPTIONS') {
          demand(origin === APP_ORIGIN && request.headers.get('access-control-request-method') === ROUTES.get(url.pathname), 'origin_denied', 403);
          const requested = (request.headers.get('access-control-request-headers') || '').toLowerCase().split(',').map(value => value.trim()).filter(Boolean);
          demand(requested.every(value => ['authorization', 'content-type'].includes(value)), 'origin_denied', 403);
          const headers = securityHeaders(origin);
          headers.set('Access-Control-Allow-Methods', ROUTES.get(url.pathname));
          headers.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
          return new Response(null, { status: 204, headers });
        }
        demand(request.method === ROUTES.get(url.pathname), 'method_not_allowed', 405);
        demand(typeof env.GITHUB_CLIENT_ID === 'string' && /^[A-Za-z0-9_.-]{3,128}$/.test(env.GITHUB_CLIENT_ID) && typeof env.GITHUB_CLIENT_SECRET === 'string' && env.GITHUB_CLIENT_SECRET.length >= 16 && env.GITHUB_CLIENT_SECRET.length <= 1024 && env.AUTH_STATE, 'not_configured', 503);
        const key = await encryptionKey(env);
        if (url.pathname === '/health') {
          parameters(url, []);
          return jsonResponse({ status: 'ready', configured: true }, 200, origin);
        }
        if (url.pathname === '/auth/start') {
          parameters(url, ['challenge', 'state']);
          const challenge = url.searchParams.get('challenge'), clientState = url.searchParams.get('state');
          demand(TOKEN_PATTERN.test(challenge) && TOKEN_PATTERN.test(clientState));
          const serverState = randomToken(), browserCookie = randomToken(), verifier = randomToken();
          const callback = url.origin + '/auth/github/callback';
          const record = { kind: 'transaction', expiresAt: now() + TEN_MINUTES, clientChallenge: challenge, clientState,
            cookieHash: await sha256(browserCookie), verifier, callback };
          demand(await stateAccess(env, 'transaction', serverState, 'create', now(), { record }), 'storage_unavailable', 503);
          const authorize = new URL('https://github.com/login/oauth/authorize');
          authorize.search = new URLSearchParams({ client_id: env.GITHUB_CLIENT_ID, redirect_uri: callback, state: serverState,
            code_challenge: await sha256(verifier), code_challenge_method: 'S256', allow_signup: 'false' });
          return redirect(authorize.href, origin, cookie(browserCookie));
        }
        if (url.pathname === '/auth/github/callback') {
          let clientState, stage = 'callback_parameters';
          try {
            callbackParameters(url);
            stage = 'callback_state';
            const serverState = url.searchParams.get('state'), browserCookie = cookieValue(request);
            demand(TOKEN_PATTERN.test(serverState || '') && TOKEN_PATTERN.test(browserCookie), 'oauth_state_invalid');
            stage = 'transaction_storage';
            const transaction = await stateAccess(env, 'transaction', serverState, 'consume', now(), { checks: { cookieHash: await sha256(browserCookie), callback: url.origin + '/auth/github/callback' } });
            stage = 'callback_state';
            demand(transaction?.kind === 'transaction', 'oauth_state_invalid');
            clientState = transaction.clientState;
            stage = 'provider_denied';
            demand(!url.searchParams.has('error'), 'oauth_denied');
            stage = 'code_invalid';
            const code = url.searchParams.get('code');
            // OAuth codes are opaque VSCHAR strings (RFC 6749), not our base64url tickets.
            demand(typeof code === 'string' && /^[\x20-\x7e]{1,2048}$/.test(code), 'oauth_failed');
            let response;
            stage = 'provider_transport';
            try {
              response = await fetchImpl('https://github.com/login/oauth/access_token', { method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(10000), headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'supercon-team-auth' },
                body: new URLSearchParams({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code, redirect_uri: transaction.callback, code_verifier: transaction.verifier, repository_id: String(REPOSITORY_ID) }) });
            } catch { throw new AuthError('oauth_exchange_unavailable'); }
            stage = httpDiagnostic(response.status);
            // Reject before parsing: a 307 must never forward the code/client secret.
            if (response.status >= 300 && response.status < 400) { await response.body?.cancel(); throw new AuthError('oauth_exchange_unavailable'); }
            stage = 'provider_response_json';
            const grant = await boundedJson(response, 16384, 'oauth_exchange_unavailable');
            demand(plainObject(grant), 'oauth_exchange_unavailable');
            // Only fixed categories cross the callback boundary, never provider text or credentials.
            if (Object.hasOwn(grant, 'error')) {
              stage = 'provider_grant_error_unknown';
              if (grant.error === 'bad_verification_code') stage = 'provider_bad_code';
              else if (grant.error === 'incorrect_client_credentials') stage = 'provider_credentials';
              else if (grant.error === 'redirect_uri_mismatch') stage = 'provider_redirect';
              else if (grant.error === 'unverified_user_email') stage = 'provider_email_unverified';
              throw new AuthError(PROVIDER_ERRORS.get(grant.error) || 'oauth_exchange_unavailable');
            }
            stage = httpDiagnostic(response.status);
            demand(response.ok, 'oauth_exchange_unavailable');
            // RFC 6750 b64token permits punctuation and trailing padding, but no header controls.
            stage = 'provider_token_format';
            demand(typeof grant.access_token === 'string' && grant.access_token.length <= 2048 && /^[A-Za-z0-9._~+/-]+=*$/.test(grant.access_token), 'oauth_exchange_unavailable');
            stage = 'provider_token_type';
            demand(typeof grant.token_type === 'string' && grant.token_type.toLowerCase() === 'bearer', 'oauth_exchange_unavailable');
            stage = 'provider_expiry';
            const lifetime = grant.expires_in === undefined ? ONE_HOUR : Number(grant.expires_in) * 1000;
            demand(Number.isSafeInteger(lifetime) && lifetime > 0, 'oauth_exchange_unavailable');
            const tokenExpiresAt = now() + Math.min(ONE_HOUR, lifetime);
            let user;
            stage = 'provider_identity';
            try { user = await githubUser(grant.access_token); }
            catch { throw new AuthError('oauth_identity_unavailable'); }
            stage = 'ticket_encryption';
            const ticket = randomToken();
            const record = { kind: 'ticket', expiresAt: Math.min(now() + FIVE_MINUTES, tokenExpiresAt), tokenExpiresAt,
              clientChallenge: transaction.clientChallenge, clientState, user,
              encrypted: await encryptToken(grant.access_token, key, 'ticket:' + await sha256(ticket)) };
            stage = 'ticket_storage';
            demand(await stateAccess(env, 'ticket', ticket, 'create', now(), { record }), 'storage_unavailable', 503);
            // Ignore refresh_token entirely. Only an encrypted short-lived access token persists.
            return returnToApp({ team_ticket: ticket, team_state: clientState }, origin);
          } catch (error) {
            const code = error instanceof AuthError && OAUTH_ERRORS.has(error.code) ? error.code : 'oauth_failed';
            return returnToApp({ team_error: code, ...(clientState ? { team_state: clientState } : {}) }, origin, stage);
          }
        }
        // Cross-site APIs deliberately use bearer sessions without cookies.
        demand(origin === APP_ORIGIN, 'origin_denied', 403);
        parameters(url, []);
        if (url.pathname === '/auth/exchange') {
          demand(/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') || ''));
          const body = await boundedJson(request, 4096, 'invalid_request');
          demand(plainObject(body) && Object.keys(body).length === 3 && ['ticket', 'verifier', 'state'].every(field => typeof body[field] === 'string' && TOKEN_PATTERN.test(body[field])));
          const record = await stateAccess(env, 'ticket', body.ticket, 'consume', now(), { checks: { clientChallenge: await sha256(body.verifier), clientState: body.state } });
          demand(record?.kind === 'ticket', 'invalid_ticket');
          const githubToken = await decryptToken(record.encrypted, key, 'ticket:' + await sha256(body.ticket));
          const user = await githubUser(githubToken);
          demand(user.id === record.user.id, 'invalid_identity', 401);
          const session = randomToken();
          const sessionRecord = { kind: 'session', expiresAt: Math.min(now() + ONE_HOUR, record.tokenExpiresAt), user,
            encrypted: await encryptToken(githubToken, key, 'session:' + await sha256(session)) };
          demand(sessionRecord.expiresAt > now(), 'invalid_ticket');
          demand(await stateAccess(env, 'session', session, 'create', now(), { record: sessionRecord }), 'storage_unavailable', 503);
          return jsonResponse({ session_token: session, ...presentation(sessionRecord) }, 200, origin);
        }
        if (url.pathname === '/auth/logout') {
          const token = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(request.headers.get('authorization') || '')?.[1];
          demand(token, 'invalid_session', 401);
          await stateAccess(env, 'session', token, 'delete', now());
          return jsonResponse({ logged_out: true }, 200, origin);
        }
        const session = await getSession(request, env, key);
        if (url.pathname === '/api/session') {
          if (session.record.user.id === OWNER_ID) await verifyMemoAccess(github, session.githubToken);
          demand(await stateAccess(env, 'session', session.token, 'get', now()), 'invalid_session', 401);
          return jsonResponse(presentation(session.record), 200, origin);
        }
        demand(session.record.user.id === OWNER_ID, 'owner_only', 403);
        const memo = await readMemo(github, session.githubToken);
        demand(await stateAccess(env, 'session', session.token, 'get', now()), 'invalid_session', 401);
        return jsonResponse(memo, 200, origin);
      } catch (error) {
        const known = error instanceof AuthError;
        return jsonResponse({ error: known ? error.code : 'unavailable' }, known ? error.status : 503, origin);
      }
    },
  };
}
export default createHandler();
