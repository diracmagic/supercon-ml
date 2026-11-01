import { AuthError, OWNER_ID, REPOSITORY_ID, base64url, boundedJson, demand, encoder, plainObject } from './security.mjs';

// This deployment is deliberately limited to the existing read-only notes App.
export const APP_ID = 5570777;
export const INSTALLATION_ID = 177619503;
const API = 'https://api.github.com';

function derLength(length) {
  if (length < 128) return Uint8Array.of(length);
  const bytes = []; while (length) { bytes.unshift(length & 255); length >>>= 8; }
  return Uint8Array.of(128 | bytes.length, ...bytes);
}
function join(...arrays) {
  const out = new Uint8Array(arrays.reduce((sum, value) => sum + value.length, 0));
  let offset = 0; for (const value of arrays) { out.set(value, offset); offset += value.length; }
  return out;
}
function der(tag, bytes) { return join(Uint8Array.of(tag), derLength(bytes.length), bytes); }

export async function importAppKey(pem) {
  try {
    demand(typeof pem === 'string' && pem.length <= 16384, 'team_not_configured', 503);
    const match = /^\s*-----BEGIN (RSA PRIVATE KEY|PRIVATE KEY)-----\s*([A-Za-z0-9+/=\r\n]+)\s*-----END \1-----\s*$/.exec(pem);
    demand(match, 'team_not_configured', 503);
    const body = match[2].replace(/\s/g, '');
    demand(/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(body), 'team_not_configured', 503);
    let bytes = Uint8Array.from(atob(body), c => c.charCodeAt(0));
    demand(bytes.length >= 1024 && bytes.length <= 8192, 'team_not_configured', 503);
    if (match[1] === 'RSA PRIVATE KEY') {
      // GitHub's downloaded PEM uses PKCS#1; WebCrypto imports PKCS#8.
      const rsaAlgorithm = Uint8Array.of(0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00);
      bytes = der(0x30, join(Uint8Array.of(0x02, 0x01, 0x00), rsaAlgorithm, der(0x04, bytes)));
    }
    const key = await crypto.subtle.importKey('pkcs8', bytes, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']);
    demand(key.algorithm.modulusLength >= 2048, 'team_not_configured', 503);
    return key;
  } catch { throw new AuthError('team_not_configured', 503); }
}

export async function appJwt(pem, now = Date.now()) {
  const key = await importAppKey(pem);
  const header = base64url(encoder.encode(JSON.stringify({ alg: 'RS256', typ: 'JWT' })));
  const payload = base64url(encoder.encode(JSON.stringify({ iss: String(APP_ID), iat: Math.floor(now / 1000) - 60, exp: Math.floor(now / 1000) + 300 })));
  const message = header + '.' + payload;
  return message + '.' + base64url(await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, encoder.encode(message)));
}

export function createInstallationReader({ fetchImpl = (...args) => fetch(...args), now = () => Date.now() } = {}) {
  async function request(path, jwt, body) {
    let response;
    try {
      response = await fetchImpl(API + path, { method: body ? 'POST' : 'GET', redirect: 'manual', signal: AbortSignal.timeout(10000),
        headers: { Accept: 'application/vnd.github+json', Authorization: 'Bearer ' + jwt, 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'supercon-team-auth', ...(body ? { 'Content-Type': 'application/json' } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {}) });
    } catch { throw new AuthError('memo_service_unavailable', 503); }
    if (!response.ok || response.status >= 300) { await response.body?.cancel(); throw new AuthError('memo_service_unavailable', 503); }
    return boundedJson(response, 65536, 'memo_service_unavailable');
  }
  return async function installationToken(env) {
    const jwt = await appJwt(env.GITHUB_APP_PRIVATE_KEY, now());
    // Revalidate on every private read. A removed/suspended/widened installation
    // must not be hidden by a cached installation token.
    const installation = await request('/app/installations/' + INSTALLATION_ID, jwt);
    demand(installation.id === INSTALLATION_ID && installation.app_id === APP_ID && installation.account?.id === OWNER_ID &&
      installation.suspended_at === null && installation.repository_selection === 'selected' &&
      installation.permissions?.contents === 'read' && Object.values(installation.permissions).every(value => value === 'read'), 'memo_service_unavailable', 503);
    const grant = await request('/app/installations/' + INSTALLATION_ID + '/access_tokens', jwt,
      { repository_ids: [REPOSITORY_ID], permissions: { contents: 'read', metadata: 'read' } });
    demand(plainObject(grant) && typeof grant.token === 'string' && grant.token.length <= 2048 && /^[A-Za-z0-9._~+/-]+=*$/.test(grant.token) &&
      grant.permissions?.contents === 'read' && Object.values(grant.permissions).every(value => value === 'read') &&
      Number.isFinite(Date.parse(grant.expires_at)) && Date.parse(grant.expires_at) > now() && Date.parse(grant.expires_at) <= now() + 3660000 &&
      Array.isArray(grant.repositories) && grant.repositories.length === 1 && grant.repositories[0].id === REPOSITORY_ID &&
      grant.repositories[0].private === true && grant.repositories[0].owner?.id === OWNER_ID &&
      grant.repositories[0].full_name === 'diracmagic/supercon-research-notes', 'memo_service_unavailable', 503);
    // Never persisted, returned to a browser, or logged. Caller uses it only
    // with the existing fixed-path, byte-verified private memo reader.
    return grant.token;
  };
}
