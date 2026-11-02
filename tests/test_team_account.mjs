import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../app/dist/team-account.js', import.meta.url), 'utf8');
const module = {exports: {}};
vm.runInNewContext(source, {module, URL, URLSearchParams, AbortController});
const account = module.exports;
const CONFIG = {apiKey: 'Public_test_key_12345678901234567890', projectId: 'test-project'};
const CODE = 'C'.repeat(40), MEMBER = 'M'.repeat(43);
const json = (value, status = 200) => ({ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(value)});
const flush = async () => { for (let i = 0; i < 12; i++) await new Promise(setImmediate); };
const flatten = node => [node, ...node.children.flatMap(flatten)];
class Element {
  constructor(tag, doc) { this.tagName = tag.toUpperCase(); this.doc = doc; this.children = []; this.parentNode = null; this.attributes = {}; this.events = {}; this._text = ''; this.open = false; this.disabled = false; this.value = ''; }
  get firstChild() { return this.children[0] || null; }
  get isConnected() { return this === this.doc.body || !!this.parentNode?.isConnected; }
  get textContent() { return this._text + this.children.map(node => node.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach(node => { node.parentNode = null; }); this.children = []; }
  set innerHTML(_) { throw new Error('Account content must never use innerHTML'); }
  appendChild(node) { this.children.push(node); node.parentNode = this; return node; }
  removeChild(node) { this.children.splice(this.children.indexOf(node), 1); node.parentNode = null; return node; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(kind, handler) { (this.events[kind] ||= []).push(handler); }
  dispatch(kind) { for (const handler of this.events[kind] || []) handler({target: this, preventDefault() {}}); }
  querySelectorAll(selector) { const tags = selector.split(',').map(tag => tag.toUpperCase()); return flatten(this).slice(1).filter(node => tags.includes(node.tagName)); }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}
function harness(options = {}) {
  const doc = {activeElement: null, createElement: tag => new Element(tag, doc)};
  doc.body = doc.createElement('body');
  const opener = doc.body.appendChild(doc.createElement('button')); opener.focus();
  const requests = [], exchanges = [], teamRequests = [], history = [], timers = new Map();
  let nextTimer = 1, authenticated = 0, github = 0, emailActions = 0, admin = options.admin === true;
  const win = {location: {pathname: '/supercon-ml/', search: options.search || '', hash: options.hash || ''},
    history: {replaceState(_state, _title, value) {history.push(value); const url = new URL(value, 'https://diracmagic.github.io'); Object.assign(win.location, {pathname: url.pathname, search: url.search, hash: url.hash});}}};
  for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(win, name, {get() {throw new Error('No account data may use storage');}});
  const ui = account.createAccountUI({document: doc, window: win, config: options.config === undefined ? CONFIG : options.config,
    fetch: async (url, settings) => {
      requests.push({url, settings});
      if (options.fetch) return options.fetch(url, settings, requests.length);
      if (url.includes('signInWithPassword')) return json({idToken: 'synthetic-id-token', refreshToken: 'must-not-be-used'});
      if (url.includes('lookup')) return json({users: [{localId: 'fake-uid', email: 'member@example.org', emailVerified: true}]});
      if (url.includes('resetPassword')) return json({email: 'member@example.org', requestType: 'PASSWORD_RESET'});
      if (url.includes('accounts:update')) return json({emailVerified: true, email: 'member@example.org'});
      if (url.includes('sendOobCode')) return json({email: 'member@example.org'});
      throw new Error('Unexpected Google operation');
    },
    exchangeFirebase: async token => {exchanges.push(token); if (options.exchange) return options.exchange(token);},
    onAuthenticated: async () => {authenticated++;}, onEmailAction: () => {emailActions++;}, signInGithub: () => {github++;}, canManageTeam: () => admin,
    teamRequest: async (path, method, payload) => {
      teamRequests.push({path, method, payload});
      return options.team ? options.team(path, method, payload) : {members: [{member_id: MEMBER, email: 'member@example.org', status: 'invited', delivery_status: 'accepted'}]};
    },
    setTimeout(handler, ms) {const id = nextTimer++; timers.set(id, {handler, ms}); return id;}, clearTimeout(id) {timers.delete(id);}
  });
  const nodes = () => flatten(doc.body);
  const get = id => nodes().find(node => node.attributes.id === id);
  const click = text => {const button = nodes().find(node => node.tagName === 'BUTTON' && node.textContent === text); assert.ok(button, text); button.dispatch('click');};
  const submit = id => {let target = get(id); while (target && target.tagName !== 'FORM') target = target.parentNode; assert.ok(target); target.dispatch('submit');};
  return {ui, doc, win, opener, requests, exchanges, teamRequests, history, timers, get, click, submit,
    setAdmin(value) {admin = value;}, get authenticated() {return authenticated;}, get github() {return github;}, get emailActions() {return emailActions;},
    fireTimeout() {for (const [id, timer] of [...timers]) {timers.delete(id); timer.handler();}}};
}

test('public Firebase configuration and member shapes fail closed', () => {
  assert.equal(account.configuration(CONFIG).projectId, 'test-project');
  for (const config of [null, {}, {...CONFIG, apiKey: 'https://evil.example'}, {...CONFIG, projectId: '../other'}]) assert.equal(account.configuration(config), null);
  assert.equal(account.email('person@example.org'), true);
  for (const value of ['', 'x@y', '<a>@example.org', 'x\n@example.org']) assert.equal(account.email(value), false);
  assert.throws(() => account.members({members: [{member_id: MEMBER, email: 'x@example.org', status: 'admin'}]}));
  assert.throws(() => account.members({members: [{member_id: '../member', email: 'x@example.org', status: 'active'}]}));
  assert.match(account.safeError({code: '<script>secret</script>'}), /could not complete/);
  assert.doesNotMatch(account.safeError({code: '<script>secret</script>'}), /secret|script/);
});

test('early head loading strips bridge action codes before DOM or network use', () => {
  const writes = [];
  const win = {location: {pathname: '/supercon-ml/', search: '?view=news', hash: '#team_email_mode=resetPassword&team_email_code=' + CODE},
    history: {replaceState(_a, _b, url) {writes.push(url);}}};
  vm.runInNewContext(source, {window: win, URLSearchParams, AbortController});
  assert.deepEqual(writes, ['/supercon-ml/?view=news']);
  assert.ok(win.SuperconAccountUI);
  const html = fs.readFileSync(new URL('../app/dist/index.html', import.meta.url), 'utf8');
  assert.ok(html.indexOf('name="referrer" content="no-referrer"') < html.indexOf('<script src="team-account.js"'));
  assert.equal([...html.matchAll(/<script\b[^>]*src="([^"]+)"/g)][0][1], 'team-account.js');
});

test('legacy action queries are stripped and URL project keys and return targets are never trusted', async () => {
  const h = harness({search: '?mode=resetPassword&oobCode=' + CODE + '&apiKey=evil&continueUrl=https%3A%2F%2Fevil.example&lang=zz&keep=yes'});
  assert.deepEqual(h.history, ['/supercon-ml/?keep=yes']);
  await h.ui.handleEmailAction();
  assert.equal(h.requests.length, 1);
  assert.ok(h.requests[0].url.endsWith('?key=' + CONFIG.apiKey));
  assert.deepEqual(JSON.parse(h.requests[0].settings.body), {oobCode: CODE});
  assert.equal(h.get('team-new-password').getAttribute('minlength'), '8');
  assert.equal(h.get('team-confirm-password').getAttribute('minlength'), '8');
  assert.equal(h.get('team-new-password').getAttribute('maxlength'), '128');
});

test('duplicate, mixed and unsupported action callbacks cause no Google call', async () => {
  for (const options of [
    {search: '?mode=resetPassword&mode=verifyEmail&oobCode=' + CODE},
    {hash: '#team_email_mode=resetPassword&team_email_code=' + CODE + '&team_email_code=' + CODE},
    {search: '?mode=resetPassword&oobCode=' + CODE, hash: '#team_email_mode=verifyEmail&team_email_code=' + CODE},
    {hash: '#team_email_mode=verifyEmail&team_email_code=' + CODE + '&team_ticket=' + 'T'.repeat(43)},
    {hash: '#team_email_mode=unsupported&team_email_code=' + CODE}
  ]) {
    const h = harness(options); await h.ui.handleEmailAction();
    assert.equal(h.requests.length, 0); assert.match(h.doc.body.textContent, /invalid/);
    assert.doesNotMatch(h.win.location.search + h.win.location.hash, /oobCode|team_email_code|team_ticket/);
  }
});

test('recovering an email clears the old identity, requires confirmation, and returns to sign-in without a session', async () => {
  const h = harness({hash: '#team_email_mode=recoverEmail&team_email_code=' + CODE});
  await h.ui.handleEmailAction();
  assert.equal(h.emailActions, 1); assert.equal(h.requests.length, 0);
  assert.equal(h.win.location.hash, ''); assert.match(h.doc.body.textContent, /reset your password/);
  h.click('Restore email address'); await flush();
  assert.equal(h.requests.length, 1);
  assert.match(h.requests[0].url, /accounts:update\?key=/);
  assert.deepEqual(JSON.parse(h.requests[0].settings.body), {oobCode: CODE});
  assert.match(h.doc.body.textContent, /Email address restored/);
  assert.equal(h.get('team-account-email').value, 'member@example.org');
  assert.equal(h.authenticated, 0); assert.equal(h.exchanges.length, 0);
});

test('login uses Google only for the password and passes only an ID token to the Worker adapter', async () => {
  const h = harness(); h.ui.openLogin();
  h.get('team-account-email').value = 'member@example.org'; h.get('team-account-password').value = ' long private password ';
  h.submit('team-account-password');
  assert.equal(h.get('team-account-password').value, ''); await flush();
  assert.equal(h.requests.length, 2); assert.equal(h.exchanges.length, 1); assert.equal(h.exchanges[0], 'synthetic-id-token');
  assert.equal(h.authenticated, 1); assert.equal(h.get('team-account-dialog').open, false);
  assert.deepEqual(JSON.parse(h.requests[0].settings.body), {email: 'member@example.org', password: ' long private password ', returnSecureToken: true});
  for (const request of h.requests) {
    assert.equal(new URL(request.url).origin, 'https://identitytoolkit.googleapis.com');
    assert.equal(request.settings.credentials, 'omit'); assert.equal(request.settings.cache, 'no-store');
    assert.equal(request.settings.referrerPolicy, 'no-referrer'); assert.equal(request.settings.redirect, 'error');
    assert.equal(request.settings.headers.Authorization, undefined);
    assert.doesNotMatch(request.settings.body, /must-not-be-used/);
  }
});

test('unverified email cannot exchange a session and verification email requires an explicit click', async () => {
  const h = harness({fetch: (url) => url.includes('signInWithPassword') ? json({idToken: 'unverified-id', refreshToken: 'discard'}) :
    url.includes('lookup') ? json({users: [{emailVerified: false}]}) : json({})});
  h.ui.openLogin('member@example.org'); h.get('team-account-password').value = 'secret password here'; h.submit('team-account-password'); await flush();
  assert.equal(h.exchanges.length, 0); assert.equal(h.requests.length, 2); assert.match(h.doc.body.textContent, /Verify your email/);
  h.click('Send verification email'); await flush();
  assert.equal(h.requests.length, 3);
  assert.deepEqual(JSON.parse(h.requests[2].settings.body), {requestType: 'VERIFY_EMAIL', idToken: 'unverified-id', continueUrl: 'https://diracmagic.github.io/supercon-ml/'});
  h.click('Send verification email'); await flush(); assert.equal(h.requests.length, 3, 'The temporary verification token is consumed');
});

test('uninvited but valid Google credentials never make an authenticated Notes session', async () => {
  const h = harness({exchange: () => {throw Object.assign(new Error('server private detail'), {code: 'member_required'});}});
  h.ui.openLogin('member@example.org'); h.get('team-account-password').value = 'secret password here'; h.submit('team-account-password'); await flush();
  assert.equal(h.authenticated, 0); assert.match(h.doc.body.textContent, /not been invited/); assert.doesNotMatch(h.doc.body.textContent, /server private detail/);
});

test('unknown errors never reflect provider descriptions, passwords or HTML', async () => {
  const h = harness({fetch: () => json({error: {message: '<img src=x onerror=secret_password>'}}, 400)});
  h.ui.openLogin('member@example.org'); h.get('team-account-password').value = 'secret_password'; h.submit('team-account-password'); await flush();
  assert.match(h.doc.body.textContent, /could not complete/); assert.doesNotMatch(h.doc.body.textContent, /secret_password|<img/);
  assert.equal(h.exchanges.length, 0);
});

test('reset requests give the same visible result for unknown and eligible email accounts', async () => {
  const messages = [];
  for (const unknown of [false, true]) {
    const h = harness({fetch: () => unknown ? json({error: {message: 'EMAIL_NOT_FOUND'}}, 400) : json({})});
    h.ui.openLogin('member@example.org'); h.click('Forgot password?'); h.submit('team-reset-email'); await flush();
    messages.push(h.get('team-account-status').textContent);
    assert.deepEqual(JSON.parse(h.requests[0].settings.body), {requestType: 'PASSWORD_RESET', email: 'member@example.org', continueUrl: 'https://diracmagic.github.io/supercon-ml/'});
  }
  assert.equal(messages[0], messages[1]);
});

test('reset validates a code, applies only a matching 8–128 character password and requires a fresh login', async () => {
  const h = harness({hash: '#team_email_mode=resetPassword&team_email_code=' + CODE}); await h.ui.handleEmailAction();
  assert.match(h.doc.body.textContent, /at least 8 characters/); assert.doesNotMatch(h.doc.body.textContent, /15 characters/);
  h.get('team-new-password').value = 'short 7'; h.get('team-confirm-password').value = 'short 7'; h.submit('team-new-password'); await flush();
  assert.equal(h.requests.length, 1);
  assert.match(h.doc.body.textContent, /between 8 and 128 characters/);
  h.get('team-new-password').value = 'x'.repeat(129); h.get('team-confirm-password').value = 'x'.repeat(129); h.submit('team-new-password'); await flush();
  assert.equal(h.requests.length, 1);
  h.get('team-new-password').value = 'a good long passphrase'; h.get('team-confirm-password').value = 'different password'; h.submit('team-new-password'); await flush();
  assert.equal(h.requests.length, 1);
  h.get('team-new-password').value = 'eight888'; h.get('team-confirm-password').value = 'eight888'; h.submit('team-new-password'); await flush();
  assert.equal(h.requests.length, 2); assert.deepEqual(JSON.parse(h.requests[1].settings.body), {oobCode: CODE, newPassword: 'eight888'});
  assert.equal(h.authenticated, 0); assert.equal(h.exchanges.length, 0); assert.match(h.doc.body.textContent, /Password saved. Sign in/);
});

test('password setup accepts the unchanged 128-character upper bound and preserves spaces', async () => {
  const h = harness({hash: '#team_email_mode=resetPassword&team_email_code=' + CODE}); await h.ui.handleEmailAction();
  const password = ' ' + 'x'.repeat(126) + ' ';
  h.get('team-new-password').value = password; h.get('team-confirm-password').value = password; h.submit('team-new-password'); await flush();
  assert.deepEqual(JSON.parse(h.requests[1].settings.body), {oobCode: CODE, newPassword: password});
  assert.equal(h.authenticated, 0); assert.equal(h.exchanges.length, 0);
});

test('email verification requires confirmation and never grants Notes or signs in automatically', async () => {
  const h = harness({hash: '#team_email_mode=verifyEmail&team_email_code=' + CODE}); await h.ui.handleEmailAction();
  assert.equal(h.requests.length, 0); h.click('Confirm email address'); await flush();
  assert.equal(h.requests.length, 1); assert.deepEqual(JSON.parse(h.requests[0].settings.body), {oobCode: CODE});
  assert.match(h.doc.body.textContent, /Email verified. Sign in/); assert.equal(h.exchanges.length, 0); assert.equal(h.authenticated, 0);
});

test('closing the dialog clears secrets, restores focus and ignores a late login response', async () => {
  let resolve;
  const h = harness({fetch: () => new Promise(done => {resolve = done;})}); h.ui.openLogin('member@example.org');
  const input = h.get('team-account-password'); input.value = 'a secret passphrase'; h.submit('team-account-password');
  h.ui.close(); assert.equal(input.value, ''); assert.equal(h.doc.activeElement, h.opener);
  resolve(json({idToken: 'late-token'})); await flush();
  assert.equal(h.requests.length, 1); assert.equal(h.exchanges.length, 0); assert.equal(h.authenticated, 0);
  assert.equal(h.get('team-account-dialog').open, false); assert.equal(h.requests[0].settings.signal.aborted, true);
});

test('deadline includes a stalled Google response body', async () => {
  const h = harness({fetch: () => ({ok: true, text: () => new Promise(() => {})})}); h.ui.openLogin('member@example.org');
  h.get('team-account-password').value = 'a secret passphrase'; h.submit('team-account-password'); await flush();
  h.fireTimeout(); await flush(); assert.match(h.doc.body.textContent, /could not complete/);
  assert.equal(h.requests[0].settings.signal.aborted, true); assert.equal(h.exchanges.length, 0);
});

test('GitHub remains available without Firebase configuration and no public signup is offered', () => {
  const h = harness({config: {}}); h.ui.openLogin();
  assert.equal(h.get('team-account-email').disabled, true); assert.equal(h.get('team-account-password').disabled, true);
  assert.doesNotMatch(h.doc.body.textContent, /Create account|Sign up/); h.click('Continue with GitHub'); assert.equal(h.github, 1);
  assert.equal(h.get('team-account-dialog').open, false); assert.equal(h.requests.length, 0);
});

test('only a current administrator may list, invite or revoke members', async () => {
  const denied = harness(); assert.equal(await denied.ui.openAdmin(), false); assert.equal(denied.teamRequests.length, 0);
  let status = 'invited';
  const h = harness({admin: true, team: (path) => {
    if (path.endsWith('/revoke')) status = 'revoked';
    return {members: [{member_id: MEMBER, email: 'member@example.org', status, delivery_status: 'accepted'}]};
  }});
  await h.ui.openAdmin(); assert.match(h.doc.body.textContent, /delivery is not confirmed/);
  h.get('team-invite-email').value = 'another@example.org'; h.submit('team-invite-email'); await flush();
  const invite = h.teamRequests.find(request => request.path.endsWith('/invite'));
  assert.deepEqual({...invite.payload}, {email: 'another@example.org'});
  h.click('Revoke access'); assert.equal(h.teamRequests.some(request => request.path.endsWith('/revoke')), false);
  h.click('Confirm revoke'); await flush();
  assert.equal(h.teamRequests.filter(request => request.path.endsWith('/revoke')).length, 1);
  assert.match(h.doc.body.textContent, /Member access revoked/);
  assert.doesNotMatch(h.doc.body.textContent, /member@example.org/);
  h.setAdmin(false); h.get('team-invite-email').value = 'nope@example.org'; h.submit('team-invite-email'); await flush();
  assert.equal(h.teamRequests.filter(request => request.path.endsWith('/invite')).length, 1);
});

test('pending invitations can be resent and active memberships do not advertise resend', async () => {
  const h = harness({admin: true}); await h.ui.openAdmin();
  h.click('Resend invitation'); await flush();
  assert.deepEqual({...h.teamRequests.find(row => row.method === 'POST').payload}, {email: 'member@example.org'});
  assert.match(h.doc.body.textContent, /Delivery is not confirmed/);
  const active = harness({admin: true, team: () => ({members: [{member_id: MEMBER, email: 'active@example.org', status: 'active', name: 'Alice'}]})});
  await active.ui.openAdmin(); assert.doesNotMatch(active.doc.body.textContent, /Resend invitation/);
  assert.match(active.doc.body.textContent, /Alice · active@example.org/);
});

test('name editing sends only a name update and displays literal text before the email', async () => {
  let name = '';
  const h = harness({admin: true, team: (path, method, payload) => {
    if (path.endsWith('/name')) name = payload.name;
    return {members: [{member_id: MEMBER, email: 'member@example.org', status: 'invited', name}]};
  }});
  await h.ui.openAdmin(); h.click('Edit name');
  h.get('team-name-' + MEMBER).value = '<Alice & Bob>';
  h.submit('team-name-' + MEMBER); await flush();
  assert.match(h.doc.body.textContent, /<Alice & Bob> · member@example.org/);
  assert.deepEqual({...h.teamRequests.find(row => row.method === 'POST').payload}, {member_id: MEMBER, name: '<Alice & Bob>'});
  assert.equal(h.teamRequests.some(row => row.path.endsWith('/invite')), false);
  h.get('team-invite-name').value = 'Carol'; h.get('team-invite-email').value = 'carol@example.org';
  h.submit('team-invite-email'); await flush();
  assert.deepEqual({...h.teamRequests.find(row => row.path.endsWith('/invite')).payload}, {email: 'carol@example.org', name: 'Carol'});
});

test('resend failures remain visible and do not claim an email was sent', async () => {
  const h = harness({admin: true, team: (path) => {
    if (path.endsWith('/invite')) throw Object.assign(new Error('private detail'), {code: 'rate_limited'});
    return {members: [{member_id: MEMBER, email: 'member@example.org', status: 'invited'}]};
  }});
  await h.ui.openAdmin(); h.click('Resend invitation'); await flush();
  assert.match(h.doc.body.textContent, /Too many attempts/);
  assert.doesNotMatch(h.doc.body.textContent, /requested again|private detail/);
});

test('forgot-password and invitation setup have distinct entries without signing in or granting membership', async () => {
  for (const [label, title] of [['Forgot password?', 'Reset your password'], ['Set password for an invitation', 'Set up your team password']]) {
    const h = harness(); h.ui.openLogin('member@example.org'); h.click(label);
    assert.equal(h.get('team-account-title').textContent, title);
    assert.equal(h.get('team-reset-email').value, 'member@example.org');
    h.submit('team-reset-email'); await flush();
    assert.equal(JSON.parse(h.requests[0].settings.body).requestType, 'PASSWORD_RESET');
    assert.equal(h.authenticated, 0); assert.equal(h.teamRequests.length, 0); assert.equal(h.exchanges.length, 0);
  }
});
