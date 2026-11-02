import { stateAccess } from './state.mjs';

const MAXIMUM_MS = 86400000, FALLBACK_MS = 60000;
const HTTP_DATE = /^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4} \d{2}:\d{2}:\d{2} GMT$/;
const unsigned = value => typeof value === 'string' && /^\d{1,15}$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null;

// Called only for a 429 from the fixed GitHub token endpoint. Its quota scope is
// unknown, so a conservative application-wide pause protects every device.
export function providerCooldownUntil(headers, now) {
  const waits = [], retry = headers.get('retry-after');
  const seconds = unsigned(retry);
  if (seconds !== null && seconds > 0) waits.push(Math.min(seconds, 86400) * 1000);
  else if (retry && HTTP_DATE.test(retry)) {
    const date = Date.parse(retry);
    if (Number.isFinite(date) && new Date(date).toUTCString() === retry && date > now) waits.push(date - now);
  }
  // A primary-quota reset is relevant only when that quota is exhausted.
  // Secondary throttles may carry a later primary reset while quota remains.
  const reset = headers.get('x-ratelimit-remaining') === '0' ? unsigned(headers.get('x-ratelimit-reset')) : null;
  if (reset !== null && reset <= Number.MAX_SAFE_INTEGER / 1000 && reset * 1000 > now) waits.push(reset * 1000 - now);
  return now + Math.min(MAXIMUM_MS, waits.length ? Math.max(...waits) : FALLBACK_MS);
}

export function githubCooldown(env, now, until) {
  return stateAccess(env, 'provider-cooldown', 'github-token-endpoint', 'cooldown', now, until === undefined ? {} : { until });
}

export function cooldownSeconds(until, now) {
  return until > now ? Math.min(86400, Math.max(1, Math.ceil((until - now) / 1000))) : 0;
}
