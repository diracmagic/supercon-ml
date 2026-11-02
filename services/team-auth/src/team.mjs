import { AuthError, boundedJson, demand, jsonResponse, plainObject, randomToken } from './security.mjs';
import { normalizeEmail, UID_PATTERN } from './firebase.mjs';
import { boardAccess } from './board.mjs';

export function normalizeMemberName(value) {
  demand(typeof value === 'string' && value.length <= 80 && !/[\u0000-\u001f\u007f-\u009f]/.test(value), 'invalid_member_name');
  return value.trim().replace(/\s+/g, ' ');
}
const publicMember = member => ({ member_id: member.id, name: member.name || '', email: member.email, status: member.status, invited_at: member.invitedAt, activated_at: member.activatedAt || null, version: member.version, delivery_status: member.deliveryStatus });
export class TeamDirectory {
  constructor(state, env = {}) { this.storage = state.storage; this.env = env; }
  async fetch(request) {
    try {
      demand(request.method === 'POST');
      const body = await boundedJson(request, 8192, 'invalid_request');
      demand(plainObject(body) && Number.isSafeInteger(body.now));
      const operation = new URL(request.url).pathname;
      const result = await this.storage.transaction(async transaction => {
        if (operation === '/limit') {
          demand(typeof body.key === 'string' && /^[A-Za-z0-9:_-]{1,160}$/.test(body.key) && Number.isSafeInteger(body.window) && body.window >= 60000 && body.window <= 86400000 && Number.isSafeInteger(body.maximum) && body.maximum >= 1 && body.maximum <= 2000);
          const rates = await transaction.get('rates') || {};
          for (const [key, rate] of Object.entries(rates)) if (rate.until <= body.now) delete rates[key];
          const rate = rates[body.key] || { count: 0, until: body.now + body.window };
          demand(rate.count < body.maximum && (rates[body.key] || Object.keys(rates).length < 512), 'rate_limited', 429);
          rate.count++; rates[body.key] = rate; await transaction.put('rates', rates); return true;
        }
        const members = await transaction.get('members') || [];
        demand(Array.isArray(members) && members.length <= 100, 'team_unavailable', 503);
        if (operation === '/list') return members.filter(member => member.status !== 'revoked').map(publicMember).sort((a, b) => b.invited_at - a.invited_at);
        // Only the Worker uses this internal lookup; revoked records remain as
        // tombstones so an old in-flight invitation cannot restore access.
        if (operation === '/lookup') {
          const member = members.find(item => item.email === normalizeEmail(body.email));
          return member ? publicMember(member) : null;
        }
        if (operation === '/name') {
          const member = members.find(item => item.id === body.memberId);
          demand(member && ['invited', 'active'].includes(member.status), 'member_not_found', 404);
          member.name = normalizeMemberName(body.name);
          await transaction.put('members', members); return publicMember(member);
        }
        if (operation === '/invite') {
          const email = normalizeEmail(body.email);
          const name = Object.hasOwn(body, 'name') ? normalizeMemberName(body.name) : undefined;
          demand(body.uid === null || (typeof body.uid === 'string' && UID_PATTERN.test(body.uid)));
          let member = members.find(item => item.email === email);
          // An invitation that began before a revoke/reinvite must not overwrite it
          // after a slow provider request completes. The snapshot is compared atomically.
          demand(member ? body.expectedMemberId === member.id && body.expectedVersion === member.version : body.expectedMemberId === null && body.expectedVersion === null, 'membership_changed', 409);
          if (member?.status === 'active') return publicMember(member);
          if (!member) {
            demand(members.length < 100, 'team_capacity', 409);
            member = { id: randomToken(), email, version: 0 }; members.push(member);
          }
          const resending = member.status === 'invited';
          demand(!member.uid || !body.uid || member.uid === body.uid, 'membership_conflict', 409);
          const uid = member.uid || body.uid;
          demand(!members.some(item => item !== member && uid && item.uid === uid), 'membership_conflict', 409);
          // A retry must not unbind an existing UID (Firebase returns EMAIL_EXISTS)
          // or invalidate a previous accepted invitation if the retry fails.
          member.deliveryAccepted = resending && (member.deliveryAccepted === true || member.deliveryStatus === 'accepted');
          member.uid = uid; member.status = 'invited'; member.version++;
          if (name !== undefined) member.name = name;
          else if (!Object.hasOwn(member, 'name')) member.name = '';
          if (!resending) member.invitedAt = body.now;
          delete member.expiresAt;
          member.deliveryStatus = 'pending'; member.activatedAt = null;
          await transaction.put('members', members); return publicMember(member);
        }
        if (operation === '/delivery' || operation === '/revoke') {
          const member = members.find(item => item.id === body.memberId);
          demand(member, 'member_not_found', 404);
          if (operation === '/delivery') {
            demand(['accepted', 'failed'].includes(body.status) && member.version === body.version, 'membership_changed', 409);
            member.deliveryStatus = body.status;
            if (body.status === 'accepted') member.deliveryAccepted = true;
          } else { member.status = 'revoked'; member.version++; }
          await transaction.put('members', members); return publicMember(member);
        }
        if (operation === '/claim') {
          demand(UID_PATTERN.test(body.uid || '') && Number.isSafeInteger(body.authTime));
          const email = normalizeEmail(body.email), member = members.find(item => item.email === email);
          demand(member && member.status !== 'revoked', 'not_invited', 403);
          demand(!member.uid || member.uid === body.uid, 'membership_conflict', 403);
          demand(!members.some(item => item !== member && item.uid === body.uid), 'membership_conflict', 403);
          if (member.status === 'invited') {
            // Membership invitations do not expire. Legacy expiresAt values are
            // ignored; Firebase still enforces its own one-use email-link expiry.
            demand(member.deliveryAccepted === true || member.deliveryStatus === 'accepted', 'invitation_not_ready', 403);
            demand(body.authTime >= Math.floor(member.invitedAt / 1000) * 1000, 'fresh_login_required', 403);
            member.uid = body.uid; member.status = 'active'; member.activatedAt = body.now; await transaction.put('members', members);
          }
          return { id: member.id, uid: member.uid, email: member.email, version: member.version };
        }
        if (operation === '/check' || operation === '/board-identity') {
          const member = members.find(item => item.id === body.memberId);
          demand(member && member.status === 'active' && member.uid === body.uid && member.email === body.email && member.version === body.version, 'membership_revoked', 403);
          return operation === '/board-identity' ? { name: member.name || 'Team member' } : true;
        }
        throw new AuthError('not_found', 404);
      });
      // Persist the board fence before acknowledging a completed revocation.
      // If this RPC fails, membership is already revoked and a retry is safe;
      // never return a successful revoke while old in-flight posts can commit.
      if (operation === '/revoke' && this.env.TEAM_BOARD) await boardAccess(this.env, 'revoke', body.now, { memberId: result.member_id, version: result.version });
      return jsonResponse({ result }, 200, null);
    } catch (error) { return jsonResponse({ error: error instanceof AuthError ? error.code : 'team_unavailable' }, error instanceof AuthError ? error.status : 503, null); }
  }
}
export async function teamAccess(env, operation, now, values = {}) {
  demand(env.TEAM_DIRECTORY, 'team_not_configured', 503);
  const object = env.TEAM_DIRECTORY.get(env.TEAM_DIRECTORY.idFromName('supercon-team-v1'));
  const response = await object.fetch(new Request('https://internal/' + operation, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ now, ...values }) }));
  // At the 100-record cap, bounded UTF-8 names and email addresses can exceed 64 KiB.
  const data = await boundedJson(response, 131072, 'team_unavailable');
  if (!response.ok) {
    const known = new Set(['rate_limited', 'team_capacity', 'member_not_found', 'membership_changed', 'membership_conflict', 'not_invited', 'invitation_not_ready', 'fresh_login_required', 'membership_revoked', 'invalid_member_name']);
    throw new AuthError(known.has(data.error) ? data.error : 'team_unavailable', known.has(data.error) ? response.status : 503);
  }
  return data.result;
}
