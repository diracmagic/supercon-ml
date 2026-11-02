(function (root) {
  'use strict';
  const POLL_MS = 60000, EVENT_GAP_MS = 5000, PAGE_SIZE = 50, MAX_VISIBLE = 500;
  const SAFE_ERRORS = Object.freeze({
    rate_limited: 'Please wait a moment before posting again.',
    invalid_message: 'Enter a message of 1 to 2,000 characters.',
    board_full: 'The message board is full. Please contact the administrator.'
  });
  function sequence(value) { return Number.isSafeInteger(value) && value >= 0; }
  function message(value) {
    if (!value || !sequence(value.id) || value.id === 0 || typeof value.body !== 'string' ||
        !value.body.trim() || value.body.length > 2000 || !sequence(value.created_at) || value.created_at === 0 ||
        !Number.isFinite(new Date(value.created_at).getTime()) ||
        !value.author || typeof value.author.name !== 'string' || value.author.name.length > 80 ||
        typeof value.author.is_self !== 'boolean') throw new Error('Invalid board response');
    return {id: value.id, body: value.body, created_at: value.created_at,
      author: {name: value.author.name || 'Team member', is_self: value.author.is_self}};
  }
  function page(value) {
    if (!value || !Array.isArray(value.messages) || value.messages.length > PAGE_SIZE ||
        !sequence(value.latest_id) || typeof value.has_more !== 'boolean') throw new Error('Invalid board response');
    const rows = value.messages.map(message);
    if (rows.some((row, i) => row.id > value.latest_id || (i > 0 && row.id <= rows[i - 1].id))) throw new Error('Invalid board order');
    return {messages: rows, latest_id: value.latest_id, has_more: value.has_more};
  }
  function createTeamBoard(env) {
    const doc = env.document, win = env.window;
    const later = env.setTimeout || win.setTimeout.bind(win), cancel = env.clearTimeout || win.clearTimeout.bind(win);
    const now = env.now || Date.now;
    const storageKey = typeof env.storageKey === 'string' && /^[A-Za-z0-9_-]{20,128}$/.test(env.storageKey) ? 'supercon-board-seen:' + env.storageKey : '';
    let active = false, destroyed = false, generation = 0, timer = null, lastAttempt = -Infinity;
    let dialog, list, status, input, postButton, counter, olderButton, focusBefore;
    let fetching = false, posting = false, loadingOlder = false, hasOlder = false, snapshotPending = false, loaded = false, cursor = 0, seen = 0;
    const rows = new Map(), unread = new Set(), controllers = new Set();
    function node(tag, attrs, children) {
      const result = doc.createElement(tag);
      Object.entries(attrs || {}).forEach(([key, value]) => {
        if (key === 'text') result.textContent = String(value);
        else if (key === 'class') result.className = value;
        else result.setAttribute(key, String(value));
      });
      (children || []).forEach(child => result.appendChild(child));
      return result;
    }
    function empty(element) { if (element) while (element.firstChild) element.removeChild(element.firstChild); }
    function visible() { return !doc.hidden && doc.visibilityState !== 'hidden'; }
    function online() { return !win.navigator || win.navigator.onLine !== false; }
    function displayed() { return active && dialog && dialog.open && visible(); }
    function notify() { if (typeof env.onUnread === 'function') env.onUnread(active ? unread.size : 0); }
    function say(text) { if (status) status.textContent = text; }
    function readSeen() {
      if (!storageKey) return 0;
      try { const value = win.localStorage.getItem(storageKey); return /^(?:0|[1-9]\d{0,15})$/.test(value || '') && sequence(Number(value)) ? Number(value) : 0; }
      catch (_) { return 0; }
    }
    function markSeen() {
      if (!displayed() || !loaded) return;
      seen = Math.max(seen, readSeen());
      // A new own post can leap over unseen concurrent posts; only GET advances this cursor.
      const latestDisplayed = Math.max(seen, cursor);
      if (latestDisplayed > seen) {
        seen = latestDisplayed;
        if (storageKey) { try { win.localStorage.setItem(storageKey, String(seen)); } catch (_) { /* Memory-only unread state remains usable. */ } }
      }
      for (const id of unread) if (id <= seen) unread.delete(id);
      notify();
    }
    function controls() {
      if (!input) return;
      input.disabled = !active || posting;
      postButton.disabled = !active || posting || !input.value.trim() || input.value.trim().length > 2000;
      counter.textContent = input.value.length + ' / 2,000';
      olderButton.hidden = !hasOlder;
      olderButton.disabled = !active || loadingOlder;
    }
    function render() {
      if (!list || !dialog.open) return;
      empty(list);
      const messages = [...rows.values()].sort((a, b) => a.id - b.id);
      if (!messages.length && loaded) list.appendChild(node('li', {class: 'team-board-empty', text: 'No messages yet. Start a conversation with your team.'}));
      messages.forEach(item => {
        const time = node('time', {datetime: new Date(item.created_at).toISOString(), text: new Date(item.created_at).toLocaleString()});
        list.appendChild(node('li', {class: 'team-board-message' + (item.author.is_self ? ' is-self' : ''), 'data-message-id': item.id}, [
          node('div', {class: 'team-board-meta'}, [node('strong', {text: item.author.name + (item.author.is_self ? ' · You' : '')}), time]),
          node('p', {class: 'team-board-text', text: item.body})]));
      });
      markSeen();
    }
    function close() {
      if (dialog && dialog.open) dialog.close();
      if (input) input.value = '';
      if (focusBefore && focusBefore.isConnected && focusBefore.focus) focusBefore.focus();
      focusBefore = null;
    }
    function ensureDialog() {
      if (dialog) return;
      const closeButton = node('button', {type: 'button', class: 'btn small', text: 'Close', 'aria-label': 'Close team message board'});
      closeButton.addEventListener('click', close);
      status = node('p', {id: 'team-board-status', class: 'team-board-status', role: 'status', 'aria-live': 'polite'});
      const historyHint = node('p', {class: 'team-board-hint', text: 'Messages are visible only to signed-in team members. Opening the board shows the latest 50 messages.'});
      olderButton = node('button', {type: 'button', class: 'btn small', text: 'Load older messages'});
      olderButton.addEventListener('click', loadOlder);
      list = node('ol', {class: 'team-board-list', 'aria-label': 'Team messages'});
      input = node('textarea', {id: 'team-board-message', rows: '4', maxlength: '2000', placeholder: 'Share an update or ask the team a question…', 'aria-describedby': 'team-board-count'});
      input.value = '';
      input.addEventListener('input', controls);
      counter = node('span', {id: 'team-board-count', class: 'team-board-count', text: '0 / 2,000'});
      postButton = node('button', {type: 'submit', class: 'btn', text: 'Post message'});
      const form = node('form', {class: 'team-board-form'}, [node('label', {for: 'team-board-message', text: 'Message to the team'}), input,
        node('div', {class: 'team-board-compose-actions'}, [counter, postButton])]);
      form.addEventListener('submit', event => { event.preventDefault(); post(); });
      dialog = node('dialog', {id: 'team-board-dialog', class: 'team-board-dialog', 'aria-labelledby': 'team-board-title'}, [
        node('header', {class: 'team-board-header'}, [node('h2', {id: 'team-board-title', text: 'Team board'}), closeButton]),
        node('div', {class: 'team-board-body'}, [historyHint, status, olderButton, list, form])]);
      dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
      dialog.addEventListener('close', () => { if (input) input.value = ''; controls(); });
      doc.body.appendChild(dialog); controls();
    }
    function current(expected) { return active && !destroyed && generation === expected; }
    async function call(path, method, body) {
      const controller = new AbortController(); controllers.add(controller);
      try { return await env.request(path, method, body, {signal: controller.signal}); }
      finally { controllers.delete(controller); }
    }
    function failure(error, expected, postingError) {
      if (!current(expected)) return;
      if (error && (error.status === 401 || error.status === 403)) {
        deactivate();
        if (typeof env.onUnauthorized === 'function') env.onUnauthorized();
        return;
      }
      if (dialog && dialog.open) say(error && Object.hasOwn(SAFE_ERRORS, error.code) ? SAFE_ERRORS[error.code] :
        postingError ? 'The post could not be confirmed. Your draft is kept; refresh the board before trying again to avoid a duplicate.' :
          'Messages could not be refreshed. They will be checked again when your connection is available.');
    }
    function schedule() {
      cancel(timer); timer = null;
      if (active && !destroyed && visible() && online()) timer = later(() => { timer = null; refresh(false); }, POLL_MS);
    }
    function ingest(items) {
      items.forEach(item => {
        rows.set(item.id, item);
        if (item.id > seen && !item.author.is_self) unread.add(item.id);
      });
      const ids = [...rows.keys()].sort((a, b) => a - b);
      ids.slice(0, Math.max(0, ids.length - MAX_VISIBLE)).forEach(id => rows.delete(id));
    }
    async function refresh(snapshot, forced) {
      if (!active || destroyed || !visible() || !online()) { schedule(); return; }
      if (fetching) { snapshotPending = snapshotPending || !!snapshot; return; }
      if (!forced && now() - lastAttempt < EVENT_GAP_MS) {
        cancel(timer); timer = later(() => { timer = null; refresh(snapshot, true); }, EVENT_GAP_MS - (now() - lastAttempt)); return;
      }
      fetching = true; lastAttempt = now();
      const expected = generation;
      try {
        let after = snapshot ? 0 : cursor;
        for (let count = 0; count < 4; count++) {
          const result = page(await call('/api/board?after=' + after + '&limit=' + PAGE_SIZE, 'GET'));
          if (!current(expected)) return;
          if (after > 0 && result.messages.some(item => item.id <= after)) throw new Error('Invalid board cursor');
          if (snapshot && count === 0) { rows.clear(); hasOlder = result.has_more; }
          else if (after === 0) hasOlder = result.has_more;
          ingest(result.messages); loaded = true;
          const next = result.messages.length ? result.messages[result.messages.length - 1].id : after;
          cursor = Math.max(cursor, next);
          render(); controls(); notify();
          if (dialog && dialog.open) say('');
          if (!result.has_more || next <= after || snapshot || after === 0 || !visible()) break;
          after = next;
        }
      } catch (error) { failure(error, expected, false); }
      finally {
        if (current(expected)) {
          fetching = false;
          if (snapshotPending) { snapshotPending = false; refresh(true, false); }
          else schedule();
        }
      }
    }
    async function loadOlder() {
      if (!displayed() || loadingOlder || !hasOlder || !rows.size || !online()) return;
      if (rows.size >= MAX_VISIBLE) { say('Up to 500 messages can be viewed at once. Reopen the board to return to the latest messages.'); return; }
      const expected = generation, before = Math.min(...rows.keys());
      loadingOlder = true; controls(); say('Loading older messages…');
      try {
        const result = page(await call('/api/board?before=' + before + '&limit=' + PAGE_SIZE, 'GET'));
        if (!current(expected)) return;
        if (result.messages.some(item => item.id >= before)) throw new Error('Invalid history cursor');
        result.messages.forEach(item => rows.set(item.id, item));
        hasOlder = result.has_more; render(); say('');
      } catch (error) { failure(error, expected, false); }
      finally { if (current(expected)) { loadingOlder = false; controls(); } }
    }
    async function post() {
      if (!displayed() || posting || !input) return;
      const body = input.value.trim();
      if (!body || body.length > 2000 || /[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/.test(body)) { say(SAFE_ERRORS.invalid_message); return; }
      const expected = generation; posting = true; controls(); say('Posting…');
      try {
        const result = await call('/api/board', 'POST', {body});
        if (!current(expected)) return;
        const item = message(result && result.message);
        if (!item.author.is_self || !sequence(result.latest_id) || result.latest_id < item.id) throw new Error('Invalid post response');
        ingest([item]); loaded = true; input.value = ''; render(); say('Message posted.');
        // Do not move the read cursor past concurrent messages from other members.
        refresh(false, true);
      } catch (error) { failure(error, expected, true); }
      finally { if (current(expected)) { posting = false; controls(); } }
    }
    function activate() {
      if (active || destroyed) return;
      active = true; generation++; seen = readSeen(); cursor = seen; lastAttempt = -Infinity;
      notify(); refresh(false, true);
    }
    function open() {
      if (!active || destroyed) return;
      ensureDialog();
      if (!dialog.open) { focusBefore = doc.activeElement; dialog.showModal(); }
      render(); controls(); say(online() ? 'Refreshing messages…' : 'You are offline. Messages will refresh when you reconnect.');
      refresh(true, false);
    }
    function deactivate() {
      active = false; generation++; cancel(timer); timer = null;
      controllers.forEach(controller => controller.abort()); controllers.clear();
      fetching = false; posting = false; loadingOlder = false; hasOlder = false; snapshotPending = false; loaded = false; cursor = 0; seen = 0;
      rows.clear(); unread.clear(); close(); empty(list); say(''); controls(); notify();
    }
    function resume() {
      if (!active || destroyed) return;
      if (visible() && online()) { markSeen(); refresh(false); }
      else { cancel(timer); timer = null; }
    }
    function storageChanged(event) {
      if (!active || !storageKey || event.key !== storageKey) return;
      seen = Math.max(seen, readSeen());
      for (const id of unread) if (id <= seen) unread.delete(id);
      notify();
    }
    doc.addEventListener('visibilitychange', resume);
    win.addEventListener('online', resume);
    win.addEventListener('offline', resume);
    win.addEventListener('storage', storageChanged);
    function destroy() {
      if (destroyed) return;
      deactivate(); destroyed = true;
      doc.removeEventListener('visibilitychange', resume);
      win.removeEventListener('online', resume); win.removeEventListener('offline', resume);
      win.removeEventListener('storage', storageChanged);
      if (dialog && dialog.parentNode) dialog.parentNode.removeChild(dialog);
      dialog = null;
    }
    return {open, activate, deactivate, destroy};
  }
  const api = {createTeamBoard};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.SuperconTeamBoard = api;
})(typeof window !== 'undefined' ? window : null);
