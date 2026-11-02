import { APP_RETURN, AuthError, boundedJson, demand, plainObject, randomToken } from './security.mjs';

const API = 'https://identitytoolkit.googleapis.com/v1/accounts:';
export const UID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;
export function normalizeEmail(value) {
  demand(typeof value === 'string' && value.length <= 254 && value === value.trim() && /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}$/.test(value), 'invalid_email');
  return value.toLowerCase();
}
export function firebaseConfigured(env) {
  try { configuration(env); return true; } catch { return false; }
}
function configuration(env) {
  demand(typeof env.FIREBASE_PROJECT_ID === 'string' && /^[a-z][a-z0-9-]{4,62}$/.test(env.FIREBASE_PROJECT_ID) && typeof env.FIREBASE_API_KEY === 'string' && /^[A-Za-z0-9_-]{20,128}$/.test(env.FIREBASE_API_KEY), 'email_not_configured', 503);
  return { project: env.FIREBASE_PROJECT_ID, apiKey: env.FIREBASE_API_KEY };
}
function claimsOf(token, project, now) {
  try {
    demand(typeof token === 'string' && token.length <= 16384 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token));
    const segment = token.split('.')[1];
    const bytes = Uint8Array.from(atob(segment.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - segment.length % 4) % 4)), c => c.charCodeAt(0));
    const claims = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    demand(plainObject(claims) && claims.aud === project && claims.iss === 'https://securetoken.google.com/' + project && UID_PATTERN.test(claims.sub || '') && Number.isSafeInteger(claims.exp) && claims.exp * 1000 > now && claims.exp * 1000 <= now + 3660000 && Number.isSafeInteger(claims.iat) && claims.iat * 1000 <= now + 60000 && Number.isSafeInteger(claims.auth_time) && claims.auth_time >= 0 && claims.auth_time <= claims.iat && claims.email_verified === true && claims.firebase?.sign_in_provider === 'password');
    normalizeEmail(claims.email);
    return claims;
  } catch { throw new AuthError('invalid_email_identity', 401); }
}

// User-chosen passwords and refresh tokens stay between the browser and Firebase.
// Public Firebase registration does not grant application membership.
export function createFirebaseClient({ fetchImpl = (...args) => fetch(...args), now = () => Date.now() } = {}) {
  async function request(env, method, body, { identity = false, allowExisting = false } = {}) {
    const config = configuration(env);
    demand(['lookup', 'signUp', 'sendOobCode'].includes(method), 'identity_unavailable', 503);
    let response;
    try {
      response = await fetchImpl(API + method + '?key=' + encodeURIComponent(config.apiKey), { method: 'POST', redirect: 'manual', signal: AbortSignal.timeout(12000), headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch { throw new AuthError('identity_unavailable', 503); }
    if (!response.ok) {
      if (allowExisting && response.status === 400) {
        const result = await boundedJson(response, 16384, 'identity_unavailable');
        if (result?.error?.message === 'EMAIL_EXISTS') return { exists: true };
      } else await response.body?.cancel();
      throw new AuthError(identity && [400, 401, 403].includes(response.status) ? 'invalid_email_identity' : 'identity_unavailable', identity && [400, 401, 403].includes(response.status) ? 401 : 503);
    }
    const result = await boundedJson(response, 131072, 'identity_unavailable');
    demand(plainObject(result) && !result.error, 'identity_unavailable', 503);
    return result;
  }
  return {
    async invite(env, email) {
      email = normalizeEmail(email);
      // An unshared, discarded random password creates only a provider placeholder.
      // The recipient sets their own password through Firebase's email action.
      const result = await request(env, 'signUp', { email, password: randomToken() + '!Aa9' + randomToken(), returnSecureToken: false }, { allowExisting: true });
      if (result.exists) return { uid: null, email };
      demand(UID_PATTERN.test(result.localId || '') && normalizeEmail(result.email) === email, 'identity_unavailable', 503);
      // Any idToken/refreshToken returned by Firebase is deliberately discarded.
      return { uid: result.localId, email };
    },
    async sendInvitation(env, email, userIp) {
      email = normalizeEmail(email);
      demand(typeof userIp === 'string' && /^[0-9a-fA-F:.]{3,64}$/.test(userIp), 'invitation_unavailable', 503);
      await request(env, 'sendOobCode', { requestType: 'PASSWORD_RESET', email, continueUrl: APP_RETURN + '?team_login=email', canHandleCodeInApp: false, userIp });
    },
    async verify(env, idToken) {
      const config = configuration(env), claims = claimsOf(idToken, config.project, now());
      // Decoded JWT claims are NOT trusted until Google validates this exact token.
      // This online lookup checks its signature/expiry and returns current account data.
      const result = await request(env, 'lookup', { idToken }, { identity: true });
      demand(Array.isArray(result.users) && result.users.length === 1, 'invalid_email_identity', 401);
      const current = result.users[0];
      demand(plainObject(current) && current.localId === claims.sub, 'invalid_email_identity', 401);
      const email = normalizeEmail(current.email);
      demand(typeof current.validSince === 'string' && /^\d+$/.test(current.validSince) && typeof current.passwordUpdatedAt === 'number', 'invalid_email_identity', 401);
      const validSince = Number(current.validSince), passwordUpdatedAt = current.passwordUpdatedAt;
      demand(current.disabled !== true && current.emailVerified === true && email === normalizeEmail(claims.email) && Number.isSafeInteger(validSince) && validSince >= 0 && Number.isFinite(passwordUpdatedAt) && passwordUpdatedAt > 0 && claims.auth_time >= validSince && claims.auth_time >= Math.floor(passwordUpdatedAt / 1000), 'invalid_email_identity', 401);
      return { uid: claims.sub, email, expiresAt: claims.exp * 1000, authTime: claims.auth_time * 1000, passwordUpdatedAt };
    },
  };
}
