import { TOKEN_PATTERN, demand, plainObject } from './security.mjs';

export const PRESENCE_WINDOW_MS = 150000;
const SESSION_MAX_MS = 3600000;
export function validateActivity(activity, now) {
  demand(plainObject(activity) && TOKEN_PATTERN.test(activity.sessionKey || '') && Number.isSafeInteger(activity.expiresAt) && activity.expiresAt > now && activity.expiresAt <= now + SESSION_MAX_MS);
}

// Called inside TeamBoard's existing transaction: activity, logout and member
// revocation have the same ordering boundary. Session hashes never leave it.
export async function updatePresence(transaction, input, operation) {
  const saved = await transaction.get('presence') || { sessions: {}, signedOut: {} };
  demand(plainObject(saved.sessions) && plainObject(saved.signedOut), 'board_unavailable', 503);
  const sessions = Object.fromEntries(Object.entries(saved.sessions).filter(([, row]) => row.expiresAt > input.now && row.lastSeen + PRESENCE_WINDOW_MS > input.now));
  const signedOut = Object.fromEntries(Object.entries(saved.signedOut).filter(([, until]) => until > input.now));
  if (operation === '/revoke') {
    for (const [key, row] of Object.entries(sessions)) if (row.memberId === input.memberId && row.memberVersion <= input.version) delete sessions[key];
  } else if (operation === '/signout') {
    const until = Math.max(signedOut[input.sessionKey] || 0, sessions[input.sessionKey]?.expiresAt || 0, input.expiresAt || 0);
    if (until > input.now) {
      demand(signedOut[input.sessionKey] !== undefined || Object.keys(signedOut).length < 4096, 'presence_capacity', 503);
      signedOut[input.sessionKey] = until;
    }
    delete sessions[input.sessionKey];
  } else if (input.activity) {
    validateActivity(input.activity, input.now);
    demand(!signedOut[input.activity.sessionKey], 'invalid_session', 401);
    demand(sessions[input.activity.sessionKey] !== undefined || Object.keys(sessions).length < 1024, 'presence_capacity', 503);
    for (const row of Object.values(sessions)) if (row.actorId === input.actor.id) row.name = input.actor.name;
    sessions[input.activity.sessionKey] = { actorId: input.actor.id, name: input.actor.name,
      ...(input.actor.memberId ? { memberId: input.actor.memberId, memberVersion: input.actor.memberVersion } : {}),
      expiresAt: input.activity.expiresAt, lastSeen: input.now };
  }
  await transaction.put('presence', { sessions, signedOut });
  const people = new Map();
  for (const row of Object.values(sessions)) if (!people.has(row.actorId) || people.get(row.actorId).lastSeen < row.lastSeen) people.set(row.actorId, row);
  return { members: [...people.values()].sort((a, b) => a.name.localeCompare(b.name) || a.actorId.localeCompare(b.actorId)).map(row => ({ name: row.name, is_self: row.actorId === input.actor?.id, online: true })),
    window_seconds: PRESENCE_WINDOW_MS / 1000, observed_at: input.now };
}
