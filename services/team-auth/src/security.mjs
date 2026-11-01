// Runtime secrets and OAuth tokens never belong in this source tree.
export const APP_ORIGIN = 'https://diracmagic.github.io';
export const APP_RETURN = APP_ORIGIN + '/supercon-ml/';
export const OWNER_ID = 350433501;
export const REPOSITORY_ID = 1442131882;
export const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;
export const encoder = new TextEncoder();

export class AuthError extends Error {
  constructor(code, status = 400) { super(code); this.code = code; this.status = status; }
}
export function demand(condition, code = 'invalid_request', status = 400) {
  if (!condition) throw new AuthError(code, status);
}
export const plainObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export function base64url(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}
export function unbase64url(value) {
  demand(typeof value === 'string' && /^[A-Za-z0-9_-]+$/.test(value), 'not_configured', 503);
  const bytes = Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)), c => c.charCodeAt(0));
  demand(base64url(bytes) === value, 'not_configured', 503);
  return bytes;
}
export const randomToken = () => base64url(crypto.getRandomValues(new Uint8Array(32)));
export const sha256 = async value => base64url(await crypto.subtle.digest('SHA-256', typeof value === 'string' ? encoder.encode(value) : value));
export async function hexHash(value, algorithm = 'SHA-256') {
  return Array.from(new Uint8Array(await crypto.subtle.digest(algorithm, value)), byte => byte.toString(16).padStart(2, '0')).join('');
}
export function equalSecret(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string' || left.length !== right.length) return false;
  let difference = 0;
  for (let i = 0; i < left.length; i++) difference |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return difference === 0;
}
export async function encryptionKey(env) {
  demand(typeof env.SESSION_KEY === 'string' && TOKEN_PATTERN.test(env.SESSION_KEY), 'not_configured', 503);
  const raw = unbase64url(env.SESSION_KEY);
  demand(raw.byteLength === 32, 'not_configured', 503);
  return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']);
}
export async function encryptToken(token, key, binding) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: encoder.encode(binding) }, key, encoder.encode(token));
  return { iv: base64url(iv), ciphertext: base64url(ciphertext) };
}
export async function decryptToken(encrypted, key, binding) {
  try {
    const clear = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unbase64url(encrypted.iv), additionalData: encoder.encode(binding) }, key, unbase64url(encrypted.ciphertext));
    return new TextDecoder('utf-8', { fatal: true }).decode(clear);
  } catch { throw new AuthError('invalid_session', 401); }
}
export async function boundedBytes(response, maximum, code = 'upstream_unavailable') {
  const size = response.headers.get('content-length');
  if (size !== null) demand(/^\d+$/.test(size) && Number(size) <= maximum, code, 502);
  demand(response.body, code, 502);
  const reader = response.body.getReader();
  const pieces = []; let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      demand(length <= maximum, code, 502);
      pieces.push(value);
    }
  } catch (error) { await reader.cancel().catch(() => {}); throw error; }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const piece of pieces) { bytes.set(piece, offset); offset += piece.length; }
  return bytes;
}
export async function boundedJson(response, maximum, code = 'upstream_unavailable') {
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(await boundedBytes(response, maximum, code)));
  } catch (error) {
    if (error instanceof AuthError) throw error;
    throw new AuthError(code, code === 'invalid_request' ? 400 : 502);
  }
}
export function securityHeaders(origin) {
  const headers = new Headers({
    'Cache-Control': 'private, no-store', Pragma: 'no-cache',
    'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
    'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'",
    Vary: 'Origin',
  });
  if (origin === APP_ORIGIN) headers.set('Access-Control-Allow-Origin', APP_ORIGIN);
  return headers;
}
export function jsonResponse(value, status, origin) {
  const headers = securityHeaders(origin);
  headers.set('Content-Type', 'application/json; charset=utf-8');
  return new Response(JSON.stringify(value), { status, headers });
}
