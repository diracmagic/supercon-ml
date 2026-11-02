(function () {
  'use strict';
  const APP_URL = 'https://diracmagic.github.io/supercon-ml/';
  const EMAIL_LOGIN_URL = APP_URL + '?team_login=email';
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
    invitation_not_ready: 'The invitation email has not been accepted by the mail service. Ask the administrator to resend it.',
    fresh_login_required: 'Sign out and sign in again to accept the latest invitation.',
    invalid_member_name: 'Use a name of up to 80 characters, without control characters.',
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
    const oauth = ['team_ticket', 'team_state', 'team_error'];
    const mixedOAuth = oauth.some(key => fragment.has(key));
    const loginIntent = params.getAll('team_login').length === 1 && params.get('team_login') === 'email';
    if (!legacy && !bridged) {
      if (!params.has('team_login')) return null;
      params.delete('team_login');
      const query = params.toString();
      win.history.replaceState(null, '', win.location.pathname + (query ? '?' + query : '') + (win.location.hash || ''));
      return loginIntent && !mixedOAuth ? {mode: 'login'} : null;
    }
    const invalid = (legacy && bridged) || mixedOAuth || ACTION_KEYS.some(key => params.getAll(key).length > 1) ||
      ['team_email_mode', 'team_email_code'].some(key => fragment.getAll(key).length > 1);
    const mode = bridged ? fragment.get('team_email_mode') || '' : params.get('mode') || '';
    const code = bridged ? fragment.get('team_email_code') || '' : params.get('oobCode') || '';
    ACTION_KEYS.forEach(key => params.delete(key));
    params.delete('team_login');
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
      if (row.name !== undefined && (typeof row.name !== 'string' || row.name.length > 80 || /[\u0000-\u001f\u007f-\u009f]/.test(row.name))) throw new Error('Invalid member name');
      return { member_id: row.member_id, name: row.name || '', email: row.email, status: row.status,
        delivery_status: typeof row.delivery_status === 'string' && /^[a-z_-]{1,40}$/.test(row.delivery_status) ? row.delivery_status : 'unknown' };
    });
  }
  function presence(value) {
    if (!value || !Array.isArray(value.members) || value.members.length > 501 || value.window_seconds !== 150 ||
        !Number.isSafeInteger(value.observed_at) || value.observed_at < 1) throw new Error('Invalid presence response');
    return {observed_at: value.observed_at, window_seconds: 150, members: value.members.map(row => {
      if (!row || typeof row.name !== 'string' || !row.name.trim() || row.name.length > 80 ||
          /[\u0000-\u001f\u007f-\u009f]/.test(row.name) || typeof row.is_self !== 'boolean' || row.online !== true) throw new Error('Invalid presence member');
      return {name: row.name, is_self: row.is_self, online: true};
    })};
  }
  function createAccountUI(env) {
    const doc = env.document, win = env.window, config = configuration(env.config || (win.SuperconTeamConfig || {}).firebase);
    const fetcher = env.fetch || win.fetch.bind(win);
    const later = env.setTimeout || win.setTimeout.bind(win), cancel = env.clearTimeout || win.clearTimeout.bind(win);
    const now = env.now || Date.now;
    const active = new Set();
    let dialog, body, heading, status, closeButton, focusBefore, generation = 0, busy = false;
    let verificationToken = '', pendingAction = earlyAction || consumeEmailAction(win), destroyed = false;
    let onlineSnapshot = null, presenceTimer = 0, teamView = false, presenceList = null;
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
      teamView = false; presenceList = null;
      ensureDialog(); invalidate(); empty(body); heading.textContent = title; say('');
      if (!dialog.open) { focusBefore = doc.activeElement; dialog.showModal(); }
      return true;
    }
    function close(restoreFocus = true) {
      teamView = false; presenceList = null; clearPresence();
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
      body.appendChild(node('p', { class: 'team-account-intro', text: 'Sign in with the email address your administrator invited and your own password. No separate username is needed.' }));
      const form = node('form', { class: 'team-account-form', autocomplete: 'on' });
      const address = field(form, 'Email address', 'team-account-email', 'email', 'username', initialEmail);
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
      body.appendChild(button('Forgot password?', () => openResetRequest(address.value), {class: 'team-account-link'}));
      body.appendChild(node('p', {class: 'team-account-setup'}, [button('Set password for an invitation', () => openResetRequest(address.value, true), {class: 'team-account-link'})]));
      body.appendChild(node('div', { class: 'team-account-divider', text: 'or' }));
      body.appendChild(button('Continue with GitHub', () => {
        if (busy || typeof env.signInGithub !== 'function') return;
        close(false); env.signInGithub();
      }, {class: 'btn team-account-github'}));
      if (!config) { form.querySelectorAll('button,input').forEach(item => { item.disabled = true; }); say('Email sign-in is being configured. You can continue with GitHub.'); }
      else say(message);
      if (email(initialEmail) && config) password.focus(); else address.focus();
    }
    function openResetRequest(initialEmail, invitation = false) {
      if (!open(invitation ? 'Set up your team password' : 'Reset your password')) return;
      body.appendChild(node('p', {text: invitation ? 'Use the email address invited by your administrator. Firebase currently labels the setup email as a password reset; use it to choose your own password.' : 'Enter your team email address to request a password reset. If an account is eligible, the account service will send a link.'}));
      const form = node('form', {class: 'team-account-form'});
      const address = field(form, 'Email address', 'team-reset-email', 'email', 'username', initialEmail);
      form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Send password link'}));
      form.addEventListener('submit', event => {
        event.preventDefault(); const target = address.value.trim();
        if (!email(target)) { say('Enter a valid email address.'); return; }
        run(async expected => {
          try { await google('sendOobCode', {requestType: 'PASSWORD_RESET', email: target, continueUrl: EMAIL_LOGIN_URL}); }
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
      // This first-party return hint opens a form only. It never verifies an
      // email, consumes a password action, or starts an authentication request.
      if (action.mode === 'login') { openLogin('', 'Sign in with your invited email address and password.'); return true; }
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
        password.setAttribute('minlength', '8'); confirmation.setAttribute('minlength', '8');
        form.appendChild(node('p', {class: 'team-account-hint', text: 'Use at least 8 characters. Spaces and pasted passwords are allowed.'}));
        form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Save password'}));
        form.addEventListener('submit', event => {
          event.preventDefault(); const secret = password.value, repeat = confirmation.value;
          password.value = ''; confirmation.value = '';
          if (secret.length < 8 || secret.length > 128) { say('Use a password between 8 and 128 characters.'); return; }
          if (secret !== repeat) { say('The passwords did not match. Enter them again.'); return; }
          run(async version => {
            await google('resetPassword', {oobCode: action.code, newPassword: secret}); action.code = '';
            if (current(version)) openLogin(checked.email, 'Password saved. Sign in below with your email address and new password.');
          });
        });
        body.appendChild(form); addBack(); password.focus();
      });
      return true;
    }
    function isAdmin() { return typeof env.canManageTeam === 'function' && env.canManageTeam() === true; }
    function isTeam() { return typeof env.canReadTeam === 'function' && env.canReadTeam() === true; }
    function clearPresence() {
      if (presenceTimer) cancel(presenceTimer);
      presenceTimer = 0; onlineSnapshot = null;
    }
    function renderPresence() {
      if (!teamView || !presenceList || !dialog || !dialog.open) return;
      empty(presenceList);
      if (!isTeam()) return;
      if (!onlineSnapshot || onlineSnapshot.observed_at + 150000 <= now()) {
        presenceList.appendChild(node('p', {text: 'Online status is not current. Select Refresh to check again.'})); return;
      }
      if (!onlineSnapshot.members.length) presenceList.appendChild(node('p', {text: 'No team members were recently active at the latest check.'}));
      onlineSnapshot.members.forEach(row => {
        presenceList.appendChild(node('article', {class: 'team-member team-presence-member'}, [
          node('p', {class: 'team-member-email', text: row.name + (row.is_self ? ' (you)' : '')}),
          node('p', {class: 'team-member-status', text: 'Online'})]));
      });
    }
    function setPresence(value) {
      if (destroyed || !isTeam()) { clearPresence(); renderPresence(); return false; }
      try {
        const checked = presence(value), remaining = checked.observed_at + 150000 - now();
        if (checked.observed_at > now() + 60000 || remaining <= 0) throw new Error('Stale presence response');
        // Session, board and manual refreshes can finish out of order. An older
        // response must not restore names removed by a fresher snapshot.
        if (onlineSnapshot && onlineSnapshot.observed_at + 150000 > now() && checked.observed_at < onlineSnapshot.observed_at) return true;
        clearPresence();
        onlineSnapshot = checked;
        presenceTimer = later(() => { clearPresence(); renderPresence(); }, Math.min(remaining, 150000));
      } catch (_) { clearPresence(); renderPresence(); return false; }
      renderPresence(); return true;
    }
    async function openTeam() {
      if (!isTeam() || !open('Team')) return false;
      teamView = true;
      body.appendChild(node('p', {text: 'Online means authenticated activity within the last 2½ minutes at the latest check. Background or closed apps may remain listed briefly.'}));
      presenceList = node('div', {id: 'team-presence-list', class: 'team-member-list', 'aria-live': 'polite'});
      body.appendChild(presenceList); renderPresence();
      async function refresh(expected) {
        if (!isTeam() || typeof env.presenceRequest !== 'function') throw new Error('Presence unavailable');
        const value = await env.presenceRequest();
        if (!current(expected) || !isTeam()) return;
        if (!setPresence(value && value.presence)) throw new Error('Presence unavailable');
        say('Online status updated.');
      }
      body.appendChild(button('Refresh', () => run(refresh), {class: 'btn small'}));
      if (isAdmin()) body.appendChild(button('Manage team', openAdmin, {class: 'btn small'}));
      await run(refresh); return true;
    }
    async function team(path, method, payload) {
      if (!isAdmin() || typeof env.teamRequest !== 'function') throw Object.assign(new Error('Not authorized'), {code: 'owner_only'});
      if (!['/api/team', '/api/team/invite', '/api/team/revoke', '/api/team/name'].includes(path)) throw new Error('Invalid team operation');
      return env.teamRequest(path, method, payload);
    }
    async function openAdmin() {
      if (!isAdmin()) return false;
      if (!open('Manage team')) return false;
      if (isTeam()) body.appendChild(button('Back to Team', openTeam, {class: 'btn small'}));
      body.appendChild(node('p', {text: 'Invite members to read research notes. Invitations do not grant administrator access or access to the private GitHub repository.'}));
      body.appendChild(node('p', {class: 'team-account-hint', text: 'Invitations stay valid until revoked. Password-setting links expire; resend an invitation for a fresh link. If a message is missing, check spam.'}));
      const form = node('form', {class: 'team-account-form team-account-invite'});
      const name = field(form, 'Name (optional)', 'team-invite-name', 'text', 'off');
      name.removeAttribute('required'); name.setAttribute('maxlength', '80');
      const address = field(form, 'Member email', 'team-invite-email', 'email', 'off');
      form.appendChild(node('button', {type: 'submit', class: 'btn primary', text: 'Invite member'}));
      const list = node('div', {id: 'team-member-list', class: 'team-member-list'});
      async function refresh(expected) {
        const rows = members(await team('/api/team', 'GET')).filter(row => row.status !== 'revoked');
        if (!current(expected) || !isAdmin()) return;
        empty(list);
        if (!rows.length) list.appendChild(node('p', {text: 'No invited members yet.'}));
        rows.forEach(row => {
          const delivery = {pending: 'Email request pending', accepted: 'Email request accepted by the provider; delivery is not confirmed', failed: 'Email request failed'};
          const card = node('article', {class: 'team-member'}, [node('p', {class: 'team-member-email', text: row.name ? row.name + ' · ' + row.email : row.email}),
            node('p', {class: 'team-member-status', text: row.status + ' · ' + (delivery[row.delivery_status] || 'Email request status unknown')})]);
          if (row.status === 'invited') card.appendChild(button('Resend invitation', () => run(async version => {
            const result = await team('/api/team/invite', 'POST', {email: row.email});
            if (!current(version)) return;
            await refresh(version);
            if (current(version)) say(result.email_request === 'not_sent_active' ? 'This member has already joined. No invitation email was sent.' : 'Invitation email requested again. Delivery is not confirmed; check spam too. Wait at least one minute before resending.');
          }), {class: 'btn small'}));
          const editName = button('Edit name', () => {
            editName.disabled = true;
            const editor = node('form', {class: 'team-account-form'});
            const input = field(editor, 'Member name', 'team-name-' + row.member_id, 'text', 'off', row.name);
            input.removeAttribute('required'); input.setAttribute('maxlength', '80');
            editor.appendChild(node('button', {type: 'submit', class: 'btn small', text: 'Save name'}));
            editor.appendChild(button('Cancel', () => { card.removeChild(editor); editName.disabled = false; }, {class: 'btn small'}));
            editor.addEventListener('submit', event => {
              event.preventDefault();
              run(async version => {
                await team('/api/team/name', 'POST', {member_id: row.member_id, name: input.value.trim()});
                if (!current(version)) return;
                await refresh(version); if (current(version)) say('Member name updated.');
              });
            });
            card.appendChild(editor); input.focus();
          }, {class: 'btn small'});
          card.appendChild(editName);
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
          const payload = {email: target}; if (name.value.trim()) payload.name = name.value.trim();
          const result = await team('/api/team/invite', 'POST', payload);
          if (!current(expected)) return;
          address.value = ''; name.value = ''; await refresh(expected);
          if (current(expected)) say(result.email_request === 'not_sent_active' ? 'This member has already joined. No invitation email was sent.' : 'Invitation updated. Check its delivery status below.');
        });
      });
      body.appendChild(form); body.appendChild(list);
      await run(async expected => { await refresh(expected); if (current(expected)) say('Only the administrator can manage this list.'); });
      return true;
    }
    return Object.freeze({openLogin, openAdmin, openTeam, setPresence, handleEmailAction, close,
      reset() { close(false); }, destroy() { close(false); destroyed = true; if (dialog && dialog.parentNode) dialog.parentNode.removeChild(dialog); }});
  }
  const api = Object.freeze({configuration, email, safeError, consumeEmailAction, members, presence, createAccountUI});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (typeof window !== 'undefined') {
    // This script is the first resource in <head>: erase action capabilities
    // before loading any stylesheet or other app resource. No network starts here.
    earlyAction = consumeEmailAction(window);
    window.SuperconAccountUI = api;
  }
})();
