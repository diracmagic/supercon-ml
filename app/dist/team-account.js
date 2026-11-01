(function () {
  'use strict';
  const APP_URL = 'https://diracmagic.github.io/supercon-ml/';
  const GOOGLE_API = 'https://identitytoolkit.googleapis.com/v1/accounts:';
  const GOOGLE_ACTIONS = new Set(['signInWithPassword', 'lookup', 'sendOobCode', 'resetPassword', 'update']);
  const ACTION_KEYS = ['mode', 'oobCode', 'apiKey', 'continueUrl', 'lang'];
  let earlyAction = null;
  const SAFE_ERRORS = Object.freeze({
    INVALID_LOGIN_CREDENTIALS: 'The email or password is incorrect.', INVALID_PASSWORD: 'The email or password is incorrect.',
    EMAIL_NOT_FOUND: 'The email or password is incorrect.', USER_DISABLED: 'Sign-in is unavailable for this account. Contact the administrator.',
    TOO_MANY_ATTEMPTS_TRY_LATER: 'Too many attempts. Please wait and try again.',
    EXPIRED_OOB_CODE: 'This email link has expired. Request a new one.', INVALID_OOB_CODE: 'This email link is invalid or has already been used.',
    WEAK_PASSWORD: 'Choose a stronger password and try again.', PASSWORD_DOES_NOT_MEET_REQUIREMENTS: 'This password does not meet the account security requirements.',
    OPERATION_NOT_ALLOWED: 'Email sign-in is not available yet.', not_configured: 'Email sign-in is not available yet.',
    member_required: 'This account has not been invited to the team. Contact the administrator.',
    membership_required: 'This account has not been invited to the team. Contact the administrator.',
    not_invited: 'This account has not been invited to the team. Contact the administrator.',
    invitation_expired: 'This invitation has expired. Ask the administrator to invite you again.',
    membership_conflict: 'This account does not match the invitation. Contact the administrator.',
    membership_revoked: 'Team access has been revoked. Contact the administrator.',
    invalid_email_identity: 'Your email identity could not be confirmed. Verify your email, then sign in again.',
    invalid_email: 'Enter a valid email address.', admin_only: 'Only the team administrator can manage invitations.',
    team_capacity: 'The team has reached its member limit. Contact the administrator.',
    invitation_delivery_failed: 'The invitation was recorded, but the email request failed. Try the invitation again shortly.',
    email_not_configured: 'Email sign-in is not available yet.',
    member_revoked: 'Team access has been revoked. Contact the administrator.',
    email_unverified: 'Verify your email address, then sign in again.',
    recent_signin_required: 'Sign out and sign in again before continuing.',
    owner_only: 'Only the team administrator can manage invitations.', invalid_session: 'Your session expired. Sign in again.',
    rate_limited: 'Too many attempts. Please wait and try again.'
  });
  function configuration(value) {
    if (!value || typeof value.apiKey !== 'string' || !/^[A-Za-z0-9_-]{20,100}$/.test(value.apiKey) ||
        typeof value.projectId !== 'string' || !/^[a-z][a-z0-9-]{4,61}[a-z0-9]$/.test(value.projectId)) return null;
    return { apiKey: value.apiKey, projectId: value.projectId };
  }
  function email(value) { return typeof value === 'string' && value.length <= 254 && /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(value); }
  function safeError(error) {
    const code = error && typeof error.code === 'string' ? error.code.split(' : ')[0] : '';
    return Object.hasOwn(SAFE_ERRORS, code) ? SAFE_ERRORS[code] : 'The account service could not complete this request. Please try again.';
  }
  function consumeEmailAction(win) {
    const params = new URLSearchParams(win.location.search || '');
    const fragment = new URLSearchParams((win.location.hash || '').replace(/^#/, ''));
    const legacy = params.has('mode') || params.has('oobCode');
    const bridged = fragment.has('team_email_mode') || fragment.has('team_email_code');
    if (!legacy && !bridged) return null;
    const oauth = ['team_ticket', 'team_state', 'team_error'];
    const mixedOAuth = oauth.some(key => fragment.has(key));
    const invalid = (legacy && bridged) || mixedOAuth || ACTION_KEYS.some(key => params.getAll(key).length > 1) ||
      ['team_email_mode', 'team_email_code'].some(key => fragment.getAll(key).length > 1);
    const mode = bridged ? fragment.get('team_email_mode') || '' : params.get('mode') || '';
    const code = bridged ? fragment.get('team_email_code') || '' : params.get('oobCode') || '';
    ACTION_KEYS.forEach(key => params.delete(key));
    ['team_email_mode', 'team_email_code'].forEach(key => fragment.delete(key));
    if (mixedOAuth) oauth.forEach(key => fragment.delete(key));
    const query = params.toString(), remainingHash = bridged || mixedOAuth ? fragment.toString() : (win.location.hash || '').replace(/^#/, '');
    win.history.replaceState(null, '', win.location.pathname + (query ? '?' + query : '') + (remainingHash ? '#' + remainingHash : ''));
    return { mode, code, invalid: invalid || !['resetPassword', 'verifyEmail', 'recoverEmail'].includes(mode) || !/^[\x21-\x7e]{1,2048}$/.test(code) };
  }
  function members(value) {
    if (!value || !Array.isArray(value.members) || value.members.length > 500) throw new Error('Invalid team response');
    const seen = new Set();
    return value.members.map(row => {
      if (!row || typeof row.member_id !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(row.member_id) || seen.has(row.member_id) ||
          !email(row.email) || !['invited', 'active', 'revoked'].includes(row.status)) throw new Error('Invalid team member');
      seen.add(row.member_id);
      return { member_id: row.member_id, email: row.email, status: row.status,
        delivery_status: typeof row.delivery_status === 'string' && /^[a-z_-]{1,40}$/.test(row.delivery_status) ? row.delivery_status : 'unknown' };
    });
  }
  function createAccountUI(env) {
    const doc = env.document, win = env.window, config = configuration(env.config || (win.SuperconTeamConfig || {}).firebase);
    const fetcher = env.fetch || win.fetch.bind(win);
    const later = env.setTimeout || win.setTimeout.bind(win), cancel = env.clearTimeout || win.clearTimeout.bind(win);
    const active = new Set();
    let dialog, body, heading, status, closeButton, focusBefore, generation = 0, busy = false;
    let verificationToken = '', pendingAction = earlyAction || consumeEmailAction(win), destroyed = false;
    earlyAction = null;
    function node(tag, attrs, children) {
      const result = doc.createElement(tag);
      Object.entries(attrs || {}).forEach(([key, value]) => {
        if (key === 'text') result.textContent = String(value);
        else if (key === 'class') result.className = value;
        else if (key === 'value') result.value = String(value);
        else result.setAttribute(key, String(value));
      });
      (children || []).forEach(child => result.appendChild(child));
      return result;
    }
    function empty(element) { if (element) while (element.firstChild) element.removeChild(element.firstChild); }
    function say(text) { if (status) status.textContent = text; }
    function button(text, handler, attrs) {
      const item = node('button', { type: 'button', class: 'btn', text, ...(attrs || {}) });
      item.addEventListener('click', handler); return item;
    }
    function field(form, label, id, type, autocomplete, value) {
      const input = node('input', { id, name: id, type, autocomplete, required: '', value: value || '' });
      if (type === 'email') { input.setAttribute('maxlength', '254'); input.setAttribute('autocapitalize', 'none'); input.setAttribute('spellcheck', 'false'); }
      if (type === 'password') input.setAttribute('maxlength', '128');
      form.appendChild(node('label', { for: id }, [node('span', { text: label }), input]));
      return input;
    }
    function wipe() {
      if (body) for (const input of body.querySelectorAll('input')) input.value = '';
      verificationToken = ''; pendingAction = null;
    }
    function invalidate() {
      generation++; busy = false;
      active.forEach(controller => controller.abort()); active.clear();
      wipe();
    }
    function ensureDialog() {
      if (dialog) return;
      heading = node('h2', { id: 'team-account-title', text: 'Team sign in' });
      closeButton = button('Close', () => close(), { class: 'btn small', 'aria-label': 'Close account window' });
      status = node('p', { id: 'team-account-status', class: 'team-account-status', role: 'status', 'aria-live': 'polite' });
      body = node('div', { class: 'team-account-body' });
      dialog = node('dialog', { id: 'team-account-dialog', class: 'team-account-dialog', 'aria-labelledby': 'team-account-title' }, [
        node('div', { class: 'team-account-header' }, [heading, closeButton]), status, body]);
      dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
      dialog.addEventListener('close', () => { invalidate(); empty(body); say(''); });
      doc.body.appendChild(dialog);
    }
    function open(title) {
      if (destroyed) return false;
      ensureDialog(); invalidate(); empty(body); heading.textContent = title; say('');
      if (!dialog.open) { focusBefore = doc.activeElement; dialog.showModal(); }
      return true;
    }
    function close(restoreFocus = true) {
      invalidate();
      if (typeof env.onDismiss === 'function') env.onDismiss();
      if (dialog && dialog.open) dialog.close();
      empty(body); say('');
      if (restoreFocus && focusBefore && focusBefore.isConnected && focusBefore.focus) focusBefore.focus();
      focusBefore = null;
    }
    function setBusy(value) {
      busy = value;
      if (body) body.querySelectorAll('button,input').forEach(item => { item.disabled = value; });
    }
    async function run(work) {
      if (busy || destroyed || !dialog || !dialog.open) return;
      const expected = generation; setBusy(true); say('Working…');
      try { await work(expected); }
      catch (error) { if (generation === expected && dialog.open) say(safeError(error)); }
      finally { if (generation === expected && dialog.open) setBusy(false); }
    }
    function current(expected) { return generation === expected && !destroyed && dialog && dialog.open; }
    async function google(action, payload) {
      if (!config || !GOOGLE_ACTIONS.has(action)) throw Object.assign(new Error('Unavailable'), {code: 'not_configured'});
      const controller = new AbortController(); active.add(controller); let timer;
      try {
        return await Promise.race([
          (async () => {
            const response = await fetcher(GOOGLE_API + action + '?key=' + encodeURIComponent(config.apiKey), {
              method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Firebase-Locale': 'en' },
              body: JSON.stringify(payload), credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', redirect: 'error', signal: controller.signal
            });
            const text = await response.text();
            if (text.length > 200000) throw new Error('Response too large');
            const value = JSON.parse(text);
            if (!response.ok) throw Object.assign(new Error('Account request failed'), {code: typeof value?.error?.message === 'string' ? value.error.message.split(' : ')[0] : ''});
            return value;
          })(),
          new Promise((_, reject) => { timer = later(() => { controller.abort(); reject(new Error('Request timed out')); }, 12000); })
        ]);
      } finally { cancel(timer); active.delete(controller); }
    }
    function addBack() { body.appendChild(button('Back to sign in', () => openLogin(), {class: 'btn small'})); }
    function openLogin(initialEmail = '', message = '') {
      if (!open('Team sign in')) return;
      body.appendChild(node('p', { class: 'team-account-intro', text: 'Invited members can sign in with email and password. GitHub sign-in remains available.' }));
      const form = node('form', { class: 'team-account-form', autocomplete: 'on' });
      const address = field(form, 'Email', 'team-account-email', 'email', 'username', initialEmail);
      const password = field(form, 'Password', 'team-account-password', 'password', 'current-password');
      form.appendChild(node('button', { type: 'submit', class: 'btn primary', text: 'Sign in' }));
      form.addEventListener('submit', event => {
        event.preventDefault(); const userEmail = address.value.trim(), secret = password.value; password.value = '';
        if (!email(userEmail) || !secret || secret.length > 128) { say('Enter your email and password.'); return; }
        run(async expected => {
          let grant = await google('signInWithPassword', { email: userEmail, password: secret, returnSecureToken: true });
          if (!current(expected)) { grant = null; return; }
          const idToken = grant && grant.idToken; grant = null; // Never retain or persist a refresh token.
          if (typeof idToken !== 'string' || idToken.length > 16384 || !idToken) throw new Error('Invalid identity token');
          const identity = await google('lookup', { idToken });
          if (!current(expected)) return;
          const account = Array.isArray(identity.users) && identity.users.length === 1 ? identity.users[0] : null;
          if (!account || typeof account.emailVerified !== 'boolean') throw new Error('Invalid account response');
          if (!account.emailVerified) { openVerification(idToken, userEmail); return; }
          if (typeof env.exchangeFirebase !== 'function') throw new Error('Session exchange unavailable');
          await env.exchangeFirebase(idToken);
          if (!current(expected)) return;
          close(false);
          if (typeof env.onAuthenticated === 'function') await env.onAuthenticated();
        });
      });
      body.appendChild(form);
      body.appendChild(button('Forgot password or setting up an invitation?', () => openResetRequest(address.value), {class: 'team-account-link'}));
      body.appendChild(node('div', { class: 'team-account-divider', text: 'or' }));
      body.appendChild(button('Continue with GitHub', () => {
        if (busy || typeof env.signInGithub !== 'function') return;
        close(false); env.signInGithub();
      }, {class: 'btn team-account-github'}));
      if (!config) { form.querySelectorAll('button,input').forEach(item => { item.disabled = true; }); say('Email sign-in is being configured. You can continue with GitHub.'); }
      else say(message);
      address.focus();
    }
    function openResetRequest(initialEmail) {
      if (!open('Set or reset your password')) return;
      body.appendChild(node('p', {text: 'Use the email address invited by your administrator. If an account is eligible, the account service will send a link.'}));
      const form = node('form', {class: 'team-account-form'});
      const address = field(form, 'Email', 'team-reset-email', 'email', 'username', initialEmail);
      form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Send password link'}));
      form.addEventListener('submit', event => {
        event.preventDefault(); const target = address.value.trim();
        if (!email(target)) { say('Enter a valid email address.'); return; }
        run(async expected => {
          try { await google('sendOobCode', {requestType: 'PASSWORD_RESET', email: target, continueUrl: APP_URL}); }
          catch (error) { if (error.code !== 'EMAIL_NOT_FOUND') throw error; }
          if (current(expected)) say('If this account is eligible, a password link has been sent. Check your inbox and spam folder.');
        });
      });
      body.appendChild(form); addBack(); address.focus();
    }
    function openVerification(idToken, userEmail) {
      if (!open('Verify your email')) return;
      verificationToken = idToken;
      body.appendChild(node('p', {text: 'Verify ' + userEmail + ' before accessing team notes. After following the email link, sign in again.'}));
      body.appendChild(button('Send verification email', () => run(async expected => {
        const proof = verificationToken; verificationToken = '';
        if (!proof) { say('Sign in again to request another verification email.'); return; }
        await google('sendOobCode', {requestType: 'VERIFY_EMAIL', idToken: proof, continueUrl: APP_URL});
        if (current(expected)) say('Verification email requested. Follow the link, then sign in again.');
      }), {class: 'btn primary'}));
      addBack();
    }
    async function handleEmailAction() {
      if (!pendingAction) return false;
      const action = pendingAction; pendingAction = null;
      if (typeof env.onEmailAction === 'function') env.onEmailAction();
      const titles = {verifyEmail: 'Verify your email', recoverEmail: 'Restore your email address', resetPassword: 'Set your password'};
      if (!open(titles[action.mode] || 'Email action')) return true;
      if (action.invalid || !config) { say(action.invalid ? 'This email action link is invalid. Request a new link.' : 'Email sign-in is not available yet.'); addBack(); return true; }
      if (action.mode === 'recoverEmail') {
        body.appendChild(node('p', {text: 'Undo the email address change associated with this link. You will need to sign in again afterward. If you did not request that change, reset your password as well.'}));
        body.appendChild(button('Restore email address', () => run(async expected => {
          const result = await google('update', {oobCode: action.code}); action.code = '';
          if (!current(expected)) return;
          if (!email(result.email)) throw new Error('Email recovery unconfirmed');
          openLogin(result.email, 'Email address restored. Sign in again. If the change was not yours, use the password reset link below.');
        }), {class: 'btn primary'}));
        addBack(); return true;
      }
      if (action.mode === 'verifyEmail') {
        body.appendChild(node('p', {text: 'Confirm your email address, then sign in to check your team invitation.'}));
        body.appendChild(button('Confirm email address', () => run(async expected => {
          const result = await google('update', {oobCode: action.code}); action.code = '';
          if (!current(expected)) return;
          if (result.emailVerified !== true) throw new Error('Email verification unconfirmed');
          openLogin('', 'Email verified. Sign in to continue.');
        }), {class: 'btn primary'}));
        addBack(); return true;
      }
      await run(async expected => {
        const checked = await google('resetPassword', {oobCode: action.code});
        if (!current(expected)) return;
        if (checked.requestType !== 'PASSWORD_RESET' || !email(checked.email)) throw new Error('Invalid reset response');
        say('Choose a new password for ' + checked.email + '.');
        const form = node('form', {class: 'team-account-form'});
        const password = field(form, 'New password', 'team-new-password', 'password', 'new-password');
        const confirmation = field(form, 'Confirm password', 'team-confirm-password', 'password', 'new-password');
        password.setAttribute('minlength', '15'); confirmation.setAttribute('minlength', '15');
        form.appendChild(node('p', {class: 'team-account-hint', text: 'Use at least 15 characters. Spaces and pasted passwords are allowed.'}));
        form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Save password'}));
        form.addEventListener('submit', event => {
          event.preventDefault(); const secret = password.value, repeat = confirmation.value;
          password.value = ''; confirmation.value = '';
          if (secret.length < 15 || secret.length > 128) { say('Use a password between 15 and 128 characters.'); return; }
          if (secret !== repeat) { say('The passwords did not match. Enter them again.'); return; }
          run(async version => {
            await google('resetPassword', {oobCode: action.code, newPassword: secret}); action.code = '';
            if (current(version)) openLogin(checked.email, 'Password saved. Sign in with your new password.');
          });
        });
        body.appendChild(form); addBack(); password.focus();
      });
      return true;
    }
    function isAdmin() { return typeof env.canManageTeam === 'function' && env.canManageTeam() === true; }
    async function team(path, method, payload) {
      if (!isAdmin() || typeof env.teamRequest !== 'function') throw Object.assign(new Error('Not authorized'), {code: 'owner_only'});
      if (!['/api/team', '/api/team/invite', '/api/team/revoke'].includes(path)) throw new Error('Invalid team operation');
      return env.teamRequest(path, method, payload);
    }
    async function openAdmin() {
      if (!isAdmin()) return false;
      if (!open('Manage team')) return false;
      body.appendChild(node('p', {text: 'Invite members to read research notes. Invitations do not grant administrator access or access to the private GitHub repository.'}));
      const form = node('form', {class: 'team-account-form team-account-invite'});
      const address = field(form, 'Member email', 'team-invite-email', 'email', 'off');
      form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Invite member'}));
      const list = node('div', {id: 'team-member-list', class: 'team-member-list'});
      async function refresh(expected) {
        const rows = members(await team('/api/team', 'GET'));
        if (!current(expected) || !isAdmin()) return;
        empty(list);
        if (!rows.length) list.appendChild(node('p', {text: 'No invited members yet.'}));
        rows.forEach(row => {
          const delivery = {pending: 'Email request pending', accepted: 'Email request accepted by the provider; delivery is not confirmed', failed: 'Email request failed'};
          const card = node('article', {class: 'team-member'}, [node('p', {class: 'team-member-email', text: row.email}),
            node('p', {class: 'team-member-status', text: row.status + ' · ' + (delivery[row.delivery_status] || 'Email request status unknown')})]);
          if (row.status !== 'revoked') card.appendChild(button('Revoke access', () => {
            const confirmation = button('Confirm revoke', () => run(async version => {
              await team('/api/team/revoke', 'POST', {member_id: row.member_id});
              if (!current(version)) return;
              await refresh(version); if (current(version)) say('Member access revoked.');
            }), {class: 'btn small'});
            card.appendChild(node('p', {text: 'Revoke access for ' + row.email + '?'})); card.appendChild(confirmation);
          }, {class: 'btn small'}));
          list.appendChild(card);
        });
      }
      form.addEventListener('submit', event => {
        event.preventDefault(); const target = address.value.trim();
        if (!email(target)) { say('Enter a valid email address.'); return; }
        run(async expected => {
          await team('/api/team/invite', 'POST', {email: target});
          if (!current(expected)) return;
          address.value = ''; await refresh(expected);
          if (current(expected)) say('Invitation updated. Check its delivery status below.');
        });
      });
      body.appendChild(form); body.appendChild(list);
      await run(async expected => { await refresh(expected); if (current(expected)) say('Only the administrator can manage this list.'); });
      return true;
    }
    return Object.freeze({openLogin, openAdmin, handleEmailAction, close,
      reset() { close(false); }, destroy() { close(false); destroyed = true; if (dialog && dialog.parentNode) dialog.parentNode.removeChild(dialog); }});
  }
  const api = Object.freeze({configuration, email, safeError, consumeEmailAction, members, createAccountUI});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (typeof window !== 'undefined') {
    // This script is the first resource in <head>: erase action capabilities
    // before loading any stylesheet or other app resource. No network starts here.
    earlyAction = consumeEmailAction(window);
    window.SuperconAccountUI = api;
  }
})();
