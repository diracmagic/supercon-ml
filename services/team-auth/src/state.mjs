import { AuthError, boundedJson, demand, equalSecret, plainObject, sha256 } from './security.mjs';

// One unguessable transaction, ticket or session per DO. These methods are only
// reachable through the binding; the public Worker never forwards paths here.
export class AuthState {
  constructor(state) { this.storage = state.storage; }
  async fetch(request) {
    demand(request.method === 'POST', 'invalid_request');
    const input = await boundedJson(request, 16384, 'invalid_request');
    demand(plainObject(input) && Number.isSafeInteger(input.now), 'invalid_request');
    const operation = new URL(request.url).pathname;
    let result;
    if (operation === '/create') {
      demand(plainObject(input.record) && Number.isSafeInteger(input.record.expiresAt) && input.record.expiresAt > input.now, 'invalid_request');
      result = await this.storage.transaction(async transaction => {
        if (await transaction.get('record')) return false;
        await transaction.put('record', input.record); return true;
      });
      if (result) await this.storage.setAlarm(input.record.expiresAt);
    } else if (operation === '/get' || operation === '/consume') {
      result = await this.storage.transaction(async transaction => {
        const record = await transaction.get('record');
        if (!record) return null;
        if (record.expiresAt <= input.now) { await transaction.delete('record'); return null; }
        if (operation === '/consume') {
          demand(plainObject(input.checks), 'invalid_request');
          if (!Object.entries(input.checks).every(([key, value]) => equalSecret(record[key], value))) return null;
          // The verification and deletion are one atomic transaction, including
          // concurrent callback or exchange requests in different Worker isolates.
          await transaction.delete('record');
        }
        return record;
      });
    } else if (operation === '/delete') {
      await this.storage.deleteAll(); await this.storage.deleteAlarm(); result = true;
    } else throw new AuthError('not_found', 404);
    return Response.json({ result });
  }
  async alarm() { await this.storage.deleteAll(); await this.storage.deleteAlarm(); }
}

export async function stateAccess(env, kind, opaque, operation, now, values = {}) {
  const id = env.AUTH_STATE.idFromName(kind + ':' + await sha256(opaque));
  const response = await env.AUTH_STATE.get(id).fetch(new Request('https://internal/' + operation, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ now, ...values }),
  }));
  demand(response.ok, 'storage_unavailable', 503);
  return (await response.json()).result;
}
