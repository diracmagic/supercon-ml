import { AuthError, TOKEN_PATTERN, boundedJson, demand, jsonResponse, plainObject, sha256 } from './security.mjs';

const HOUR = 3600000;
const actorPattern = /^(?:github:[1-9][0-9]{0,15}|firebase:[A-Za-z0-9_-]{1,128})$/;
const messageKey = id => 'message:' + String(id).padStart(16, '0');
export function normalizeBoardBody(value) {
  demand(typeof value === 'string' && !/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/.test(value), 'invalid_message');
  const body = value.trim();
  demand(body.length > 0 && body.length <= 2000, 'invalid_message');
  return body;
}
function validateActor(actor) {
  demand(plainObject(actor) && typeof actor.id === 'string' && actorPattern.test(actor.id) &&
    typeof actor.name === 'string' && actor.name.length > 0 && actor.name.length <= 80 && !/[\u0000-\u001f\u007f-\u009f]/.test(actor.name));
  if (actor.id.startsWith('firebase:')) demand(typeof actor.memberId === 'string' && TOKEN_PATTERN.test(actor.memberId) && Number.isSafeInteger(actor.memberVersion) && actor.memberVersion >= 1);
}
function present(message, actorId) {
  return { id: message.id, body: message.body, created_at: message.createdAt,
    author: { name: message.authorName, is_self: message.actorId === actorId } };
}

// This object has no public route. The Worker authenticates the request and
// supplies the actor; client bodies are never forwarded as actor metadata.
// Messages have individual keys and no expiry/alarm or automatic retention limit.
export class TeamBoardDO {
  constructor(state) { this.storage = state.storage; }
  async fetch(request) {
    try {
      demand(request.method === 'POST');
      const input = await boundedJson(request, 12288, 'invalid_request');
      demand(plainObject(input) && Number.isSafeInteger(input.now) && input.now > 0);
      const operation = new URL(request.url).pathname;
      demand(operation === '/read' || operation === '/post' || operation === '/revoke', 'not_found', 404);
      if (operation === '/revoke') demand(typeof input.memberId === 'string' && TOKEN_PATTERN.test(input.memberId) && Number.isSafeInteger(input.version) && input.version >= 1);
      else validateActor(input.actor);
      const body = operation === '/post' ? normalizeBoardBody(input.body) : null;
      const rateKey = operation === '/post' ? 'rate:' + await sha256(input.actor.id) : null;
      const memberId = operation === '/revoke' ? input.memberId : input.actor.memberId;
      const fenceKey = memberId ? 'revoked:' + await sha256(memberId) : null;
      const result = await this.storage.transaction(async transaction => {
        // Revoke acknowledgements and appends share this durable transaction
        // boundary. An old in-flight request cannot append after its revoke has
        // completed, including across object restarts or reordered old revokes.
        if (fenceKey) {
          const throughVersion = await transaction.get(fenceKey) || 0;
          demand(Number.isSafeInteger(throughVersion) && throughVersion >= 0, 'board_unavailable', 503);
          if (operation === '/revoke') {
            await transaction.put(fenceKey, Math.max(throughVersion, input.version));
            return { revoked: true };
          }
          demand(input.actor.memberVersion > throughVersion, 'membership_revoked', 403);
        }
        const latest = await transaction.get('latest') || 0;
        demand(Number.isSafeInteger(latest) && latest >= 0, 'board_unavailable', 503);
        if (operation === '/post') {
          demand(latest < Number.MAX_SAFE_INTEGER, 'board_capacity', 409);
          const stored = await transaction.get(rateKey) || [];
          demand(Array.isArray(stored) && stored.length <= 20 && stored.every(Number.isSafeInteger), 'board_unavailable', 503);
          const times = stored.filter(time => input.now - time < HOUR);
          demand(times.length < 20 && (!times.length || input.now - times[times.length - 1] >= 3000), 'rate_limited', 429);
          const message = { id: latest + 1, body, createdAt: input.now, actorId: input.actor.id, authorName: input.actor.name };
          await transaction.put(messageKey(message.id), message);
          await transaction.put(rateKey, [...times, input.now]);
          await transaction.put('latest', message.id);
          return { message: present(message, input.actor.id), latest_id: message.id };
        }
        demand(Number.isSafeInteger(input.limit) && input.limit >= 1 && input.limit <= 50 &&
          Number.isSafeInteger(input.after) && input.after >= 0 &&
          (input.before === null || Number.isSafeInteger(input.before) && input.before >= 1) &&
          !(input.after && input.before !== null));
        let first, last, hasMore;
        if (input.after > 0) {
          first = input.after < latest ? input.after + 1 : latest + 1;
          last = Math.min(latest, first + input.limit - 1);
          hasMore = last < latest;
        } else {
          last = input.before === null ? latest : Math.min(latest, input.before - 1);
          first = Math.max(1, last - input.limit + 1); hasMore = first > 1;
        }
        const messages = [];
        // IDs are contiguous, so a bounded range reads at most 50 separate keys.
        // Read in the same transaction as the cursor for a consistent page.
        for (let id = first; id <= last; id++) {
          const message = await transaction.get(messageKey(id));
          demand(message && message.id === id, 'board_unavailable', 503);
          messages.push(present(message, input.actor.id));
        }
        return { messages, latest_id: latest, has_more: hasMore };
      });
      return jsonResponse({ result }, 200, null);
    } catch (error) {
      return jsonResponse({ error: error instanceof AuthError ? error.code : 'board_unavailable' }, error instanceof AuthError ? error.status : 503, null);
    }
  }
}

export async function boardAccess(env, operation, now, values) {
  demand(env.TEAM_BOARD, 'board_not_configured', 503);
  demand(operation === 'read' || operation === 'post' || operation === 'revoke');
  const object = env.TEAM_BOARD.get(env.TEAM_BOARD.idFromName('supercon-team-board-v1'));
  const response = await object.fetch(new Request('https://internal/' + operation, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ now, ...values }) }));
  const data = await boundedJson(response, 524288, 'board_unavailable');
  if (!response.ok) {
    const known = new Set(['rate_limited', 'board_capacity', 'invalid_message', 'invalid_request', 'membership_revoked']);
    throw new AuthError(known.has(data.error) ? data.error : 'board_unavailable', known.has(data.error) ? response.status : 503);
  }
  demand(plainObject(data.result), 'board_unavailable', 503);
  return data.result;
}
