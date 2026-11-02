(function () {
  'use strict';

  const OWNER_ID = '350433501';
  const PENDING_KEY = 'supercon.github.pending.v1';
  const PROOF_TTL = 10 * 60 * 1000;
  const REQUEST_TIMEOUT = 12000;
  const SESSION_CHECK = 60 * 1000;
  const ACCOUNT_ERRORS = new Set(['admin_only', 'not_invited', 'invitation_expired', 'membership_conflict', 'membership_revoked',
    'invalid_email_identity', 'invalid_email', 'rate_limited', 'team_capacity', 'invitation_delivery_failed',
    'email_not_configured', 'identity_unavailable', 'invalid_session']);
  const CATEGORY = Object.freeze({ '计算预测': 'Computational prediction', '回溯验证': 'Retrospective validation',
    '实验研究': 'Experimental research', '数据与工具': 'Data and tools', '研究计划': 'Research programme' });
  const STEP_STATUS = Object.freeze({ completed: 'Reported', current: 'Current evidence', not_reported: 'Not reported' });
  const CALLBACK_ERRORS = Object.freeze({
    oauth_state_invalid: 'The sign-in service could not verify the callback. Start again in this tab and allow cookies for the sign-in service.',
    oauth_denied: 'GitHub authorization was cancelled or denied. Start again when you are ready.',
    oauth_failed: 'GitHub sign-in failed at the authorization service. Please try again.',
    oauth_credentials_invalid: 'GitHub rejected the app credentials. The app administrator needs to check the sign-in configuration.',
    oauth_redirect_invalid: 'GitHub rejected the callback address. The app administrator needs to check the registered sign-in URL.',
    oauth_exchange_unavailable: 'The sign-in service could not complete the GitHub exchange. Please try again shortly.',
    oauth_identity_unavailable: 'The sign-in service could not verify your GitHub account. Please try again shortly.'
  });

  function apiOrigin(value) {
    if (typeof value !== 'string' || !value || /\s|\\|[?#]/.test(value)) return '';
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') return '';
      if (!url.hostname.includes('.') || url.hostname === 'localhost') return '';
      return url.origin;
    } catch (_) { return ''; }
  }

  function base64url(bytes, encode) {
    return encode(String.fromCharCode.apply(null, Array.from(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async function makeProof(crypto, encode, now) {
    const random = function () { return base64url(crypto.getRandomValues(new Uint8Array(32)), encode); };
    const verifier = random(), state = random();
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
    return { verifier: verifier, state: state, created_at: now, challenge: base64url(new Uint8Array(digest), encode) };
  }

  function validProof(proof, state, now) {
    return !!proof && typeof proof.verifier === 'string' && typeof proof.state === 'string' &&
      /^[A-Za-z0-9_-]{43}$/.test(proof.verifier) && /^[A-Za-z0-9_-]{43}$/.test(proof.state) &&
      proof.state === state && Number.isFinite(proof.created_at) && proof.created_at <= now && now - proof.created_at < PROOF_TTL;
  }

  function callbackFailure(received, proof, now) {
    if (!received || received.invalid) return 'The sign-in callback was malformed. Start sign-in again from this tab.';
    // Never reflect an arbitrary provider error, description, ticket or proof.
    if (received.error) return Object.hasOwn(CALLBACK_ERRORS, received.error) ? CALLBACK_ERRORS[received.error] :
      'The sign-in service returned an unrecognized error. Please start sign-in again.';
    if (!/^[A-Za-z0-9_-]{43}$/.test(received.ticket)) return 'The sign-in callback did not include a valid login ticket. Start sign-in again.';
    if (!proof || typeof proof.verifier !== 'string' || typeof proof.state !== 'string' ||
      !/^[A-Za-z0-9_-]{43}$/.test(proof.verifier) || !/^[A-Za-z0-9_-]{43}$/.test(proof.state)) {
      return 'The browser could not find a valid pending sign-in request. Start again in this tab with session storage available.';
    }
    if (!Number.isFinite(proof.created_at) || proof.created_at > now) return 'The saved sign-in time is invalid. Check your device clock and start again.';
    if (now - proof.created_at >= PROOF_TTL) return 'This sign-in request expired after 10 minutes. Start sign-in again.';
    if (!validProof(proof, received.state, now)) return 'This sign-in response does not match the request started in this tab. Start sign-in again.';
    return '';
  }

  function sessionMetadata(value, now) {
    if (!value || !value.user || !Number.isSafeInteger(value.expires_at) || value.expires_at <= now) return null;
    const id = value.user.id;
    if (value.user.provider === 'firebase') {
      if (typeof id !== 'string' || !/^firebase:[A-Za-z0-9_-]{1,128}$/.test(id) ||
          typeof value.user.email !== 'string' || value.user.email.length > 254 || !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(value.user.email) ||
          value.user.login !== value.user.email || typeof value.can_read_memo !== 'boolean' || value.can_manage_team !== false) return null;
      return {user: {id: id, login: value.user.login, provider: 'firebase', email: value.user.email}, expires_at: value.expires_at,
        can_read_memo: value.can_read_memo, can_manage_team: false};
    }
    if (value.user.provider !== undefined && value.user.provider !== 'github') return null;
    if (!(typeof id === 'number' && Number.isSafeInteger(id) && id > 0) && !(typeof id === 'string' && /^[1-9]\d*$/.test(id))) return null;
    if (typeof value.user.login !== 'string' || !/^[A-Za-z0-9-]{1,39}$/.test(value.user.login)) return null;
    if (typeof value.can_read_memo !== 'boolean') return null;
    return { user: { id: String(id), login: value.user.login }, expires_at: value.expires_at,
      can_read_memo: String(id) === OWNER_ID && value.can_read_memo === true,
      can_manage_team: String(id) === OWNER_ID && value.can_manage_team === true };
  }

  function safeSourceUrl(value) {
    if (typeof value !== 'string' || /[\s\\\u0000-\u001f]/.test(value)) return '';
    try {
      if (/[\u0000-\u001f]/.test(decodeURIComponent(value))) return '';
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password ? url.href : '';
    } catch (_) { return ''; }
  }

  function memoEntries(value) {
    if (!value || !Array.isArray(value.entries) || !value.entries.length || value.entries.length > 250 || value.entry_count !== value.entries.length) return null;
    const seen = new Set();
    for (const entry of value.entries) {
      if (!entry || typeof entry.id !== 'string' || !/^[A-Za-z0-9_-]{1,40}$/.test(entry.id) || seen.has(entry.id)) return null;
      if (typeof entry.heading !== 'string' || typeof entry.result !== 'string' || typeof entry.boundary !== 'string') return null;
      seen.add(entry.id);
    }
    return value.entries;
  }

  function createNoteAnimation(options) {
    const doc = options.document, win = options.window, details = options.details;
    const steps = (Array.isArray(options.steps) ? options.steps : []).slice(0, 12).filter(function (step) {
      return step && typeof step.label === 'string' && typeof step.detail === 'string' && Object.hasOwn(STEP_STATUS, step.status);
    }).map(function (step) { return { label: step.label, detail: step.detail, status: step.status }; });
    if (!steps.length) return null;
    const duration = 3600, subscriptions = [], nodes = [];
    const frame = typeof win.requestAnimationFrame === 'function' ? win.requestAnimationFrame.bind(win) : null;
    const cancelFrame = typeof win.cancelAnimationFrame === 'function' ? win.cancelAnimationFrame.bind(win) : function () {};
    const motion = typeof win.matchMedia === 'function' ? win.matchMedia('(prefers-reduced-motion: reduce)') : null;
    let reduced = !!motion && motion.matches, visible = typeof win.IntersectionObserver !== 'function';
    let position = 0, elapsed = 0, previousTime = null, frameId = 0, playing = false, disposed = false, finished = false, observer;
    function node(tag, attrs, text, svg) {
      const value = svg && doc.createElementNS ? doc.createElementNS('http://www.w3.org/2000/svg', tag) : doc.createElement(tag);
      Object.keys(attrs || {}).forEach(function (key) { value.setAttribute(key, String(attrs[key])); });
      if (text !== undefined) value.textContent = text;
      return value;
    }
    function listen(target, event, callback) {
      target.addEventListener(event, callback); subscriptions.push(function () { if (target.removeEventListener) target.removeEventListener(event, callback); });
    }
    const root = node('section', { class: 'team-note-animation', 'aria-label': 'Research walkthrough' });
    const heading = node('h4', {}, 'Research walkthrough'); root.appendChild(heading);
    root.appendChild(node('p', { class: 'team-note-animation-intro' }, 'Follow the study’s recorded steps. Evidence labels stay attached to each step.'));
    const diagram = node('svg', { class: 'team-note-diagram', viewBox: '0 0 640 105', 'aria-hidden': 'true', focusable: 'false' }, undefined, true);
    const x = function (index) { return steps.length === 1 ? 320 : 80 + index * 480 / (steps.length - 1); };
    for (let index = 1; index < steps.length; index++) {
      diagram.appendChild(node('line', { x1: x(index - 1) + 22, y1: 42, x2: x(index) - 22, y2: 42,
        class: 'team-note-connector' }, undefined, true));
    }
    steps.forEach(function (step, index) {
      const group = node('g', { transform: 'translate(' + x(index) + ',42)', class: 'team-note-node' }, undefined, true);
      group.appendChild(node('circle', { r: 20, class: 'team-note-node-ring' }, undefined, true));
      group.appendChild(node('text', { y: 5, 'text-anchor': 'middle', class: 'team-note-node-number' }, String(index + 1), true));
      group.appendChild(node('title', {}, step.label + ' — ' + STEP_STATUS[step.status], true));
      if (steps.length <= 5) group.appendChild(node('text', { y: 45, 'text-anchor': 'middle', class: 'team-note-node-label' },
        step.label.length > 19 ? step.label.slice(0, 18) + '…' : step.label, true));
      diagram.appendChild(group); nodes.push(group);
    });
    const pulse = node('circle', { cx: x(0), cy: 42, r: 5, class: 'team-note-pulse', visibility: 'hidden' }, undefined, true);
    diagram.appendChild(pulse); root.appendChild(diagram);
    const counter = node('p', { class: 'team-note-counter', 'aria-live': 'polite', 'aria-atomic': 'true' });
    const title = node('h5', { class: 'team-note-step-title' });
    const evidence = node('span', { class: 'team-note-evidence' });
    const description = node('p', { class: 'team-note-step-detail' });
    const stage = node('div', { class: 'team-note-stage' });
    [counter, title, evidence, description].forEach(function (child) { stage.appendChild(child); }); root.appendChild(stage);
    const controls = node('div', { class: 'team-note-animation-controls' });
    const previous = node('button', { type: 'button', class: 'btn small', 'aria-label': 'Previous research step' }, 'Previous');
    const play = node('button', { type: 'button', class: 'btn small' }, 'Play');
    const next = node('button', { type: 'button', class: 'btn small', 'aria-label': 'Next research step' }, 'Next');
    [previous, play, next].forEach(function (child) { controls.appendChild(child); }); root.appendChild(controls);
    const state = node('p', { class: 'team-note-play-state' }); root.appendChild(state);
    function updateControls() {
      previous.disabled = position === 0; next.disabled = position === steps.length - 1;
      play.hidden = reduced || !frame;
      play.disabled = !visible || !details.open || doc.hidden;
      play.textContent = playing ? 'Pause' : finished ? 'Replay' : elapsed || position ? 'Resume' : 'Play';
      play.setAttribute('aria-label', playing ? 'Pause research walkthrough' : finished ? 'Replay research walkthrough' : 'Play research walkthrough');
      state.textContent = reduced || !frame ? 'Static walkthrough. Use Previous and Next.' : playing ? 'Playing the recorded sequence' : finished ? 'End of the recorded sequence' : 'Paused · use Play or inspect one step at a time';
    }
    function draw() {
      if (disposed) return;
      const step = steps[position];
      counter.textContent = 'Step ' + (position + 1) + ' of ' + steps.length;
      title.textContent = step.label; description.textContent = step.detail; evidence.textContent = STEP_STATUS[step.status];
      evidence.setAttribute('class', 'team-note-evidence' + (step.status === 'not_reported' ? ' is-unreported' : ''));
      nodes.forEach(function (group, index) {
        group.setAttribute('class', 'team-note-node' + (index === position ? ' is-active' : '') +
          (steps[index].status === 'not_reported' ? ' is-unreported' : ''));
      });
      pulse.setAttribute('visibility', playing && position < steps.length - 1 ? 'visible' : 'hidden');
      pulse.setAttribute('cx', String(x(position))); updateControls();
    }
    function pause() {
      if (disposed) return;
      playing = false; previousTime = null;
      if (frameId) cancelFrame(frameId); frameId = 0;
      pulse.setAttribute('visibility', 'hidden'); updateControls();
    }
    function tick(time) {
      frameId = 0;
      if (disposed || !playing) return;
      if (reduced || !visible || doc.hidden || !details.open) { pause(); return; }
      if (previousTime !== null) elapsed += Math.min(Math.max(0, time - previousTime), 100);
      previousTime = time;
      if (elapsed >= duration) {
        if (position === steps.length - 1) { finished = true; elapsed = 0; pause(); return; }
        position++; elapsed = 0; draw();
      }
      if (position < steps.length - 1) pulse.setAttribute('cx', String(x(position) + (x(position + 1) - x(position)) * elapsed / duration));
      frameId = frame(tick);
    }
    function togglePlay() {
      if (disposed) return;
      if (playing) { pause(); return; }
      if (reduced || !frame || !visible || doc.hidden || !details.open) return;
      if (finished) { position = 0; elapsed = 0; finished = false; }
      playing = true; previousTime = null; draw(); frameId = frame(tick);
    }
    function move(delta) {
      if (disposed) return;
      pause(); position = Math.max(0, Math.min(steps.length - 1, position + delta)); elapsed = 0; finished = false; draw();
    }
    listen(previous, 'click', function () { move(-1); }); listen(next, 'click', function () { move(1); }); listen(play, 'click', togglePlay);
    listen(details, 'toggle', function () { if (!details.open) pause(); else updateControls(); });
    listen(doc, 'visibilitychange', function () { if (doc.hidden) pause(); else updateControls(); });
    if (motion) {
      const onMotion = function () { reduced = motion.matches; if (reduced) pause(); updateControls(); };
      if (motion.addEventListener) listen(motion, 'change', onMotion);
      else if (motion.addListener) { motion.addListener(onMotion); subscriptions.push(function () { motion.removeListener(onMotion); }); }
    }
    if (typeof win.IntersectionObserver === 'function') {
      observer = new win.IntersectionObserver(function (entries) {
        if (disposed) return;
        const entry = entries.find(function (item) { return item.target === root; });
        if (!entry) return;
        visible = entry.isIntersecting && entry.intersectionRatio >= .1;
        if (!visible) pause(); else updateControls();
      }, { threshold: [.1] }); observer.observe(root);
    }
    draw();
    return { node: root, pause: pause, destroy: function () {
      if (disposed) return;
      pause(); disposed = true;
      if (observer) observer.disconnect();
      subscriptions.splice(0).forEach(function (unsubscribe) { unsubscribe(); });
      root.textContent = ''; steps.length = 0; nodes.length = 0;
    } };
  }

  function createController(env) {
    const win = env.window, doc = env.document;
    const now = env.now || Date.now;
    const later = env.setTimeout || win.setTimeout.bind(win);
    const cancel = env.clearTimeout || win.clearTimeout.bind(win);
    const fetcher = env.fetch || win.fetch.bind(win);
    const crypto = env.crypto || win.crypto;
    const encode = env.btoa || win.btoa.bind(win);
    const origin = apiOrigin((env.config || win.SuperconTeamConfig || {}).apiBase);
    const activeRequests = new Set();
    const noteAnimations = new Set();
    let token = '', session = null, privateMemo = null, generation = 0;
    let expiryTimer = 0, checkTimer = 0, busy = false, initialized = false;
    let loginButton, controls, status, notesButton, logoutButton, teamButton, dialog, memoBody, memoStatus;
    let searchInput, categoryInput, memoList, returnFocus, callback;
    let accountUI = null, emailSignInPending = false;

    function el(tag, attributes, children) {
      const node = doc.createElement(tag);
      Object.keys(attributes || {}).forEach(function (key) {
        const value = attributes[key];
        if (key === 'text') node.textContent = String(value);
        else if (key === 'class') node.className = value;
        else node.setAttribute(key, String(value));
      });
      (children || []).forEach(function (child) { if (child) node.appendChild(child); });
      return node;
    }
    function empty(node) { if (node) while (node.firstChild) node.removeChild(node.firstChild); }
    function say(message) { if (status) status.textContent = message; }
    function removePending() { try { win.sessionStorage.removeItem(PENDING_KEY); } catch (_) { /* no persisted auth */ } }
    function pauseAnimations() { noteAnimations.forEach(function (animation) { animation.pause(); }); }
    function clearAnimations() { noteAnimations.forEach(function (animation) { animation.destroy(); }); noteAnimations.clear(); }

    // Consume callback data before waiting for DOM initialization. Ticket/proof
    // material never appears in app links, logs, or persistent session state.
    function consumeFragment() {
      const params = new URLSearchParams(win.location.hash.replace(/^#/, ''));
      if (!['team_ticket', 'team_state', 'team_error'].some(function (key) { return params.has(key); })) return null;
      win.history.replaceState(null, '', win.location.pathname + win.location.search);
      const duplicate = ['team_ticket', 'team_state', 'team_error'].some(function (key) { return params.getAll(key).length > 1; });
      return { ticket: params.get('team_ticket') || '', state: params.get('team_state') || '',
        error: params.get('team_error') || '', invalid: duplicate || (params.has('team_ticket') && params.has('team_error')) };
    }
    callback = consumeFragment();

    function renderAccount() {
      if (!loginButton) return;
      loginButton.textContent = session ? (session.user.provider === 'firebase' ? session.user.email : '@' + session.user.login) : busy ? 'Signing in…' : 'Login for team';
      loginButton.disabled = busy || !!session || !origin;
      loginButton.setAttribute('title', session ? (session.user.provider === 'firebase' ? 'Signed in with email' : 'Signed in with GitHub') : origin ? 'Sign in to the team' : 'Team sign-in is not configured yet');
      notesButton.hidden = !session || !session.can_read_memo;
      logoutButton.hidden = !session;
      if (teamButton) teamButton.hidden = !session || !session.can_manage_team;
    }

    function clearMemo() {
      clearAnimations();
      privateMemo = null;
      if (dialog && dialog.open) dialog.close();
      empty(memoBody);
      if (memoStatus) memoStatus.textContent = '';
      searchInput = null; categoryInput = null; memoList = null;
    }

    function reset(message) {
      const wasOpen = !!dialog && dialog.open;
      generation++;
      activeRequests.forEach(function (controller) { controller.abort(); });
      activeRequests.clear();
      cancel(expiryTimer); cancel(checkTimer); expiryTimer = checkTimer = 0;
      token = ''; session = null; busy = false; emailSignInPending = false;
      if (accountUI) accountUI.reset();
      clearMemo(); renderAccount(); say(message || '');
      if (wasOpen && loginButton) loginButton.focus();
    }

    async function request(path, method, bearer, body) {
      if (!origin || !/^\/(?:auth\/(?:exchange|logout|firebase)|api\/(?:session|memo|team(?:\/(?:invite|revoke|name))?))$/.test(path)) throw new Error('Request unavailable');
      const controller = new AbortController();
      activeRequests.add(controller);
      let timeout;
      const headers = { Accept: 'application/json' };
      if (bearer) headers.Authorization = 'Bearer ' + bearer;
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      try {
        return await Promise.race([
          (async function () {
            const response = await fetcher(origin + path, { method: method, headers: headers, credentials: 'omit', cache: 'no-store',
              referrerPolicy: 'no-referrer', redirect: 'error', signal: controller.signal,
              ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
            if (!response.ok) {
              const error = new Error('Request failed'); error.status = response.status;
              try {
                const text = await response.text();
                if (text.length <= 4096) { const data = JSON.parse(text); if (ACCOUNT_ERRORS.has(data.error)) error.code = data.error; }
              } catch (_) { /* Never reflect raw service errors or response bodies. */ }
              throw error;
            }
            if (response.status === 204) return {};
            const text = await response.text();
            if (text.length > 1500000) throw new Error('Response too large');
            return JSON.parse(text);
          })(),
          new Promise(function (_, reject) { timeout = later(function () { controller.abort(); reject(new Error('Request timed out')); }, REQUEST_TIMEOUT); })
        ]);
      } finally { cancel(timeout); activeRequests.delete(controller); }
    }

    function armSessionChecks() {
      cancel(expiryTimer); cancel(checkTimer);
      if (!session || !token) return;
      const remaining = session.expires_at - now();
      if (remaining <= 0) { reset('Your session expired. Sign in again.'); return; }
      expiryTimer = later(function () { reset('Your session expired. Sign in again.'); }, Math.min(remaining, 2147483647));
      checkTimer = later(function () {
        if (doc.hidden) armSessionChecks();
        else validateSession();
      }, SESSION_CHECK);
    }

    async function validateSession() {
      if (!token || !session) return false;
      if (session.expires_at <= now()) { reset('Your session expired. Sign in again.'); return false; }
      const expected = generation, bearer = token;
      try {
        const value = await request('/api/session', 'GET', bearer);
        if (generation !== expected || token !== bearer) return false;
        const verified = sessionMetadata(value, now());
        if (!verified || verified.user.id !== session.user.id) throw new Error('Session unavailable');
        const lostAdmin = session.can_manage_team && !verified.can_manage_team;
        session = verified;
        if (lostAdmin && accountUI) accountUI.reset();
        if (!session.can_read_memo) clearMemo();
        renderAccount(); armSessionChecks();
        return true;
      } catch (_) {
        if (generation === expected) reset('Your session could not be confirmed. Sign in again.');
        return false;
      }
    }

    async function signIn() {
      if (!origin || busy || session) return;
      const expected = generation;
      busy = true; renderAccount(); say('Opening GitHub sign-in…');
      try {
        if (!crypto || !crypto.subtle) throw new Error('Secure browser required');
        const proof = await makeProof(crypto, encode, now());
        if (generation !== expected) return;
        win.sessionStorage.setItem(PENDING_KEY, JSON.stringify({ verifier: proof.verifier, state: proof.state, created_at: proof.created_at }));
        const start = new URL('/auth/start', origin);
        start.searchParams.set('challenge', proof.challenge);
        start.searchParams.set('state', proof.state);
        win.location.assign(start.href);
      } catch (_) {
        if (generation !== expected) return;
        removePending(); busy = false; renderAccount();
        say('Sign-in could not start. Use a secure browser with session storage available.');
      }
    }

    async function exchangeFirebase(idToken) {
      if (!origin || busy || session || typeof idToken !== 'string' || !idToken || idToken.length > 16384) throw new Error('Email sign-in unavailable');
      const expected = generation;
      emailSignInPending = true; busy = true; renderAccount(); say('Confirming team access…');
      try {
        const value = await request('/auth/firebase', 'POST', '', {id_token: idToken});
        if (generation !== expected) throw new Error('Sign-in cancelled');
        const verified = sessionMetadata(value, now());
        if (!verified || verified.user.provider !== 'firebase' || typeof value.session_token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(value.session_token)) throw new Error('Invalid email session');
        token = value.session_token; session = verified;
        if (!await validateSession()) throw Object.assign(new Error('Session unavailable'), {code: 'invalid_session'});
        emailSignInPending = false; busy = false; renderAccount(); say('Signed in with email.');
      } catch (error) {
        if (generation === expected) {
          emailSignInPending = false; busy = false; token = ''; session = null;
          clearMemo(); renderAccount(); say('');
        }
        throw error;
      }
    }

    async function teamRequest(path, method, payload) {
      const methods = {'/api/team': 'GET', '/api/team/invite': 'POST', '/api/team/revoke': 'POST', '/api/team/name': 'POST'};
      if (methods[path] !== method || !session || !session.can_manage_team || !token || !await validateSession() || !session || !session.can_manage_team) {
        throw Object.assign(new Error('Team management unavailable'), {code: 'admin_only'});
      }
      try { return await request(path, method, token, payload); }
      catch (error) {
        if (error.status === 401 || error.status === 403) reset('Team access could not be confirmed. Sign in again.');
        throw error;
      }
    }

    async function finishSignIn() {
      if (!callback) return;
      let proof = null;
      try { proof = JSON.parse(win.sessionStorage.getItem(PENDING_KEY) || 'null'); } catch (_) { /* invalid proof */ }
      removePending();
      const received = callback; callback = null;
      if (!origin) { say('Team sign-in is not available yet.'); return; }
      const failure = callbackFailure(received, proof, now());
      if (failure) { proof = null; say(failure); return; }
      busy = true; renderAccount(); say('Confirming your GitHub account…');
      const expected = generation;
      try {
        const value = await request('/auth/exchange', 'POST', '', { ticket: received.ticket, verifier: proof.verifier, state: received.state });
        proof = null;
        if (generation !== expected) return;
        const verified = sessionMetadata(value, now());
        if (!verified || typeof value.session_token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(value.session_token)) throw new Error('Invalid session');
        token = value.session_token; session = verified;
        if (!await validateSession()) return;
        busy = false; renderAccount(); say('Signed in with GitHub.');
        if (session && session.can_read_memo) await openNotes();
      } catch (_) {
        proof = null;
        if (generation === expected) reset('GitHub sign-in could not be completed. Please try again.');
      }
    }

    async function logout() {
      const bearer = token;
      reset('Signed out.');
      removePending();
      if (loginButton) loginButton.focus();
      if (bearer && origin) {
        try { await request('/auth/logout', 'POST', bearer); } catch (_) { /* local private state is already gone */ }
      }
    }

    function createDialog() {
      if (dialog) return;
      const title = el('h2', { id: 'team-notes-title', text: 'Private research notes' });
      const close = el('button', { type: 'button', class: 'btn small', text: 'Close', 'aria-label': 'Close private notes' });
      close.addEventListener('click', function () { dialog.close(); });
      memoStatus = el('p', { class: 'team-notes-status', role: 'status', 'aria-live': 'polite' });
      memoBody = el('div', { class: 'team-notes-body' });
      dialog = el('dialog', { id: 'team-notes-dialog', class: 'team-notes-dialog', 'aria-labelledby': 'team-notes-title' }, [
        el('header', { class: 'team-notes-header' }, [el('div', {}, [el('p', { class: 'team-notes-eyebrow', text: 'Account access verified' }), title]), close]),
        memoStatus, memoBody
      ]);
      dialog.addEventListener('close', function () {
        pauseAnimations();
        const target = returnFocus && returnFocus.isConnected && !returnFocus.hidden && !returnFocus.disabled ? returnFocus :
          logoutButton && !logoutButton.hidden ? logoutButton : loginButton;
        if (target) target.focus();
      });
      doc.body.appendChild(dialog);
    }

    function sourceLinks(entry) {
      const rows = [{ label: entry.title || 'Primary source', url: entry.url }]
        .concat(Array.isArray(entry.primary_refs) ? entry.primary_refs : [])
        .concat((Array.isArray(entry.extra) ? entry.extra : []).map(function (r) { return Array.isArray(r) ? { label: r[0], url: r[1] } : r; }));
      const list = el('ul', { class: 'team-notes-sources' }), seen = new Set();
      rows.forEach(function (row) {
        if (!row) return;
        const url = safeSourceUrl(row.url);
        if (!url || seen.has(url)) return;
        seen.add(url);
        list.appendChild(el('li', {}, [el('a', { href: url, target: '_blank', rel: 'noopener noreferrer', referrerpolicy: 'no-referrer', text: row.title || row.label || 'Primary source' })]));
      });
      return list;
    }

    function memoCard(entry) {
      const body = el('div', { class: 'team-notes-detail' });
      const details = el('details', {}, [el('summary', { text: 'Evidence, conditions and sources' }), body]);
      const animation = createNoteAnimation({ document: doc, window: win, details: details, steps: entry.progress_steps });
      if (animation) { body.appendChild(animation.node); noteAnimations.add(animation); }
      [['Result', entry.result], ['Evidence limits', entry.boundary], ['What we can learn', entry.reference_point]].forEach(function (item) {
        if (typeof item[1] === 'string' && item[1]) { body.appendChild(el('h4', { text: item[0] })); body.appendChild(el('p', { text: item[1] })); }
      });
      const facts = el('dl', { class: 'team-notes-facts' });
      [['Team', entry.team], ['Publication', entry.publication], ['Evidence', entry.evidence_type], ['Pressure / conditions', entry.pressure],
        ['Tc criterion', entry.tc_criterion], ['Version checked', entry.verified_version], ['Reviewed', entry.reviewed_on]].forEach(function (item) {
        if (typeof item[1] === 'string' && item[1]) { facts.appendChild(el('dt', { text: item[0] })); facts.appendChild(el('dd', { text: item[1] })); }
      });
      body.appendChild(facts);
      if (Array.isArray(entry.progress_steps)) {
        body.appendChild(el('h4', { text: 'Research route' }));
        const route = el('ol', { class: 'team-notes-route' });
        entry.progress_steps.forEach(function (step) {
          if (!step || typeof step.label !== 'string') return;
          route.appendChild(el('li', {}, [el('b', { text: step.label }), el('span', { class: 'team-notes-step-status', text: STEP_STATUS[step.status] || 'Not specified' }), el('p', { text: step.detail || '' })]));
        });
        body.appendChild(route);
      }
      body.appendChild(el('h4', { text: 'Primary sources' })); body.appendChild(sourceLinks(entry));
      return el('article', { class: 'team-notes-card' }, [
        el('p', { class: 'team-notes-meta', text: '#' + entry.id + ' · ' + (entry.year || '') + ' · ' + (CATEGORY[entry.category] || entry.category || '') }),
        el('h3', { text: entry.heading }), el('p', { class: 'team-notes-headline', text: entry.headline || '' }),
        el('p', { class: 'team-notes-stage', text: entry.stage || '' }),
        details
      ]);
    }

    function renderMemoRows() {
      if (!privateMemo || !session || !session.can_read_memo || !memoList) return;
      const query = searchInput.value.trim().toLowerCase(), category = categoryInput.value;
      const rows = privateMemo.entries.filter(function (entry) {
        return (category === 'all' || category === entry.category) && (!query ||
          [entry.heading, entry.short, entry.title, entry.team, entry.year, entry.doi, entry.result, entry.boundary].join(' ').toLowerCase().includes(query));
      });
      clearAnimations(); empty(memoList);
      rows.forEach(function (entry) { memoList.appendChild(memoCard(entry)); });
      memoStatus.textContent = rows.length + ' of ' + privateMemo.entries.length + ' private entries' +
        (privateMemo.reviewed_on ? ' · reviewed ' + privateMemo.reviewed_on : '');
      if (!rows.length) memoList.appendChild(el('p', { class: 'team-notes-empty', text: 'No entries match this search.' }));
    }

    function renderMemo() {
      clearAnimations();
      empty(memoBody);
      searchInput = el('input', { id: 'team-notes-search', type: 'search', placeholder: 'Material, author, method or DOI', autocomplete: 'off' });
      categoryInput = el('select', { id: 'team-notes-category' });
      categoryInput.appendChild(el('option', { value: 'all', text: 'All evidence' }));
      const categories = new Set(privateMemo.entries.map(function (entry) { return entry.category; }).filter(Boolean));
      categories.forEach(function (category) { categoryInput.appendChild(el('option', { value: category, text: CATEGORY[category] || category })); });
      categoryInput.value = 'all';
      searchInput.addEventListener('input', renderMemoRows); categoryInput.addEventListener('change', renderMemoRows);
      memoList = el('div', { class: 'team-notes-list' });
      memoBody.appendChild(el('div', { class: 'team-notes-filters' }, [
        el('label', { for: 'team-notes-search' }, [el('span', { text: 'Search notes' }), searchInput]),
        el('label', { for: 'team-notes-category' }, [el('span', { text: 'Evidence category' }), categoryInput])
      ]));
      memoBody.appendChild(memoList);
      renderMemoRows();
    }

    async function openNotes() {
      if (!session || !session.can_read_memo || !token) return;
      if (!await validateSession() || !session || !session.can_read_memo) return;
      createDialog();
      if (typeof dialog.showModal !== 'function') { say('Private notes require a browser with dialog support.'); return; }
      returnFocus = notesButton;
      clearAnimations(); privateMemo = null; empty(memoBody); memoStatus.textContent = 'Loading private notes…';
      if (!dialog.open) dialog.showModal();
      const expected = generation, bearer = token;
      try {
        const value = await request('/api/memo', 'GET', bearer);
        if (generation !== expected || token !== bearer || !session || !session.can_read_memo) return;
        if (session.expires_at <= now()) { reset('Your session expired. Sign in again.'); return; }
        if (!memoEntries(value)) throw new Error('Invalid private records');
        privateMemo = value; renderMemo();
      } catch (error) {
        if (generation !== expected) return;
        if (error.status === 401 || error.status === 403) reset('Access to private notes is no longer available. Sign in again.');
        else { clearAnimations(); privateMemo = null; empty(memoBody); memoStatus.textContent = 'Private notes could not be loaded. Close and try again.'; }
      }
    }

    function init() {
      if (initialized) return;
      loginButton = doc.getElementById('team-login');
      if (!loginButton) return;
      initialized = true;
      // The HTML uses a button; remove old link attributes during upgrades too.
      ['href', 'target', 'rel'].forEach(function (name) { loginButton.removeAttribute(name); });
      controls = el('span', { class: 'team-auth-controls' });
      notesButton = el('button', { id: 'team-notes', type: 'button', class: 'btn small', text: 'Notes' });
      teamButton = el('button', { id: 'team-manage', type: 'button', class: 'btn small', text: 'Team' });
      logoutButton = el('button', { id: 'team-logout', type: 'button', class: 'btn small', text: 'Sign out' });
      notesButton.hidden = teamButton.hidden = logoutButton.hidden = true;
      controls.appendChild(notesButton); controls.appendChild(teamButton); controls.appendChild(logoutButton);
      status = el('span', { class: 'team-auth-status', role: 'status', 'aria-live': 'polite' });
      loginButton.parentNode.appendChild(controls); loginButton.parentNode.appendChild(status);
      const accountModule = env.accountUI || win.SuperconAccountUI;
      if (accountModule && typeof accountModule.createAccountUI === 'function') {
        accountUI = accountModule.createAccountUI({window: win, document: doc, config: (env.config || win.SuperconTeamConfig || {}).firebase,
          fetch: fetcher, setTimeout: later, clearTimeout: cancel, signInGithub: signIn, exchangeFirebase: exchangeFirebase,
          canManageTeam: function () { return !!session && session.can_manage_team === true; }, teamRequest: teamRequest,
          onAuthenticated: openNotes, onEmailAction: function () { logout(); },
          onDismiss: function () { if (emailSignInPending) { emailSignInPending = false; reset(''); } }});
      }
      loginButton.addEventListener('click', function (event) { event.preventDefault(); if (accountUI) accountUI.openLogin(); else signIn(); });
      notesButton.addEventListener('click', openNotes); logoutButton.addEventListener('click', logout);
      teamButton.addEventListener('click', function () { if (accountUI && session && session.can_manage_team) accountUI.openAdmin(); });
      doc.addEventListener('visibilitychange', function () { if (!doc.hidden && token) validateSession(); });
      win.addEventListener('pagehide', function () { reset(''); });
      renderAccount();
      if (callback) finishSignIn();
      else {
        if (accountUI) accountUI.handleEmailAction();
        try {
          const pending = JSON.parse(win.sessionStorage.getItem(PENDING_KEY) || 'null');
          if (pending && !validProof(pending, pending.state, now())) removePending();
        } catch (_) { removePending(); }
        if (!origin) say('Team sign-in is not available yet.');
      }
    }
    return Object.freeze({ init: init, signIn: signIn, logout: logout, openNotes: openNotes });
  }

  // No browser secrets are exported. The CommonJS branch is for isolated tests.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { apiOrigin: apiOrigin, makeProof: makeProof, validProof: validProof, sessionMetadata: sessionMetadata,
      safeSourceUrl: safeSourceUrl, memoEntries: memoEntries, createNoteAnimation: createNoteAnimation, createController: createController, PENDING_KEY: PENDING_KEY };
  } else if (typeof document !== 'undefined' && typeof window !== 'undefined') {
    const controller = createController({ window: window, document: document });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', controller.init, { once: true });
    else controller.init();
  }
})();
