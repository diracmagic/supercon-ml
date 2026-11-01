(function () {
  'use strict';

  const OWNER_ID = '350433501';
  const PENDING_KEY = 'supercon.github.pending.v1';
  const PROOF_TTL = 10 * 60 * 1000;
  const REQUEST_TIMEOUT = 12000;
  const SESSION_CHECK = 60 * 1000;
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
    if (!(typeof id === 'number' && Number.isSafeInteger(id) && id > 0) && !(typeof id === 'string' && /^[1-9]\d*$/.test(id))) return null;
    if (typeof value.user.login !== 'string' || !/^[A-Za-z0-9-]{1,39}$/.test(value.user.login)) return null;
    if (typeof value.can_read_memo !== 'boolean') return null;
    return { user: { id: String(id), login: value.user.login }, expires_at: value.expires_at,
      can_read_memo: String(id) === OWNER_ID && value.can_read_memo === true };
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
    let token = '', session = null, privateMemo = null, generation = 0;
    let expiryTimer = 0, checkTimer = 0, busy = false, initialized = false;
    let loginButton, controls, status, notesButton, logoutButton, dialog, memoBody, memoStatus;
    let searchInput, categoryInput, memoList, returnFocus, callback;

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
      loginButton.textContent = session ? '@' + session.user.login : busy ? 'Signing in…' : 'Login for team';
      loginButton.disabled = busy || !!session || !origin;
      loginButton.setAttribute('title', session ? 'Signed in with GitHub' : origin ? 'Sign in securely with GitHub' : 'Team sign-in is not configured yet');
      notesButton.hidden = !session || !session.can_read_memo;
      logoutButton.hidden = !session;
    }

    function clearMemo() {
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
      token = ''; session = null; busy = false;
      clearMemo(); renderAccount(); say(message || '');
      if (wasOpen && loginButton) loginButton.focus();
    }

    async function request(path, method, bearer, body) {
      if (!origin || !/^\/(?:auth\/(?:exchange|logout)|api\/(?:session|memo))$/.test(path)) throw new Error('Request unavailable');
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
            if (!response.ok) { const error = new Error('Request failed'); error.status = response.status; throw error; }
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
        session = verified;
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
        el('details', {}, [el('summary', { text: 'Evidence, conditions and sources' }), body])
      ]);
    }

    function renderMemoRows() {
      if (!privateMemo || !session || !session.can_read_memo || !memoList) return;
      const query = searchInput.value.trim().toLowerCase(), category = categoryInput.value;
      const rows = privateMemo.entries.filter(function (entry) {
        return (category === 'all' || category === entry.category) && (!query ||
          [entry.heading, entry.short, entry.title, entry.team, entry.year, entry.doi, entry.result, entry.boundary].join(' ').toLowerCase().includes(query));
      });
      empty(memoList);
      rows.forEach(function (entry) { memoList.appendChild(memoCard(entry)); });
      memoStatus.textContent = rows.length + ' of ' + privateMemo.entries.length + ' private entries' +
        (privateMemo.reviewed_on ? ' · reviewed ' + privateMemo.reviewed_on : '');
      if (!rows.length) memoList.appendChild(el('p', { class: 'team-notes-empty', text: 'No entries match this search.' }));
    }

    function renderMemo() {
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
      privateMemo = null; empty(memoBody); memoStatus.textContent = 'Loading private notes…';
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
        else { privateMemo = null; empty(memoBody); memoStatus.textContent = 'Private notes could not be loaded. Close and try again.'; }
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
      logoutButton = el('button', { id: 'team-logout', type: 'button', class: 'btn small', text: 'Sign out' });
      notesButton.hidden = logoutButton.hidden = true;
      controls.appendChild(notesButton); controls.appendChild(logoutButton);
      status = el('span', { class: 'team-auth-status', role: 'status', 'aria-live': 'polite' });
      loginButton.parentNode.appendChild(controls); loginButton.parentNode.appendChild(status);
      loginButton.addEventListener('click', function (event) { event.preventDefault(); signIn(); });
      notesButton.addEventListener('click', openNotes); logoutButton.addEventListener('click', logout);
      doc.addEventListener('visibilitychange', function () { if (!doc.hidden && token) validateSession(); });
      win.addEventListener('pagehide', function () { reset(''); });
      renderAccount();
      if (callback) finishSignIn();
      else {
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
      safeSourceUrl: safeSourceUrl, memoEntries: memoEntries, createController: createController, PENDING_KEY: PENDING_KEY };
  } else if (typeof document !== 'undefined' && typeof window !== 'undefined') {
    const controller = createController({ window: window, document: document });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', controller.init, { once: true });
    else controller.init();
  }
})();
