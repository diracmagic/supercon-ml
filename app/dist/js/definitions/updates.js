'use strict';
// updates: shared lexical function definitions; no startup side effects.

  const isDesktop = function isDesktop() { return !!(window.__TAURI__ || window.__TAURI_INTERNALS__); };

  const verParts = function verParts(s) { var m = /(\d+)\.(\d+)\.(\d+)/.exec(String(s || '')); return m ? [+m[1], +m[2], +m[3]] : null; };

  const verNewer = function verNewer(a, b) {
    a = verParts(a); b = verParts(b);
    if (!a || !b) return false;
    for (var i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i];
    return false;
  };

  // Public release identity is explicit; cache names are implementation revisions.
  const webReleaseVersion = function webReleaseVersion(source) {
    if (typeof source !== 'string' || source.length > 65536) return '';
    var match = /(?:^|\n)\s*const\s+APP_VERSION\s*=\s*(['"])(\d{1,6}\.\d{1,6}\.\d{1,6})\1\s*;/.exec(source);
    return match ? match[2] : '';
  };

  const updateWebBadge = function updateWebBadge(available) {
    try {
      var standalone = navigator.standalone === true || (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
      if (!standalone || UPD.badged === available) return;
      UPD.badged = available;
      var operation = available ? navigator.setAppBadge : navigator.clearAppBadge;
      if (typeof operation === 'function') Promise.resolve(operation.call(navigator, ...(available ? [1] : []))).catch(function () {});
    } catch (_) { /* Optional badges need no permission prompt or update dependency. */ }
  };

  const installerName = function installerName() {
    var ua = navigator.userAgent || '', pf = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '';
    if (/win/i.test(pf) || /Windows/.test(ua)) return 'SuperconProgress-windows-x64-setup.exe';
    if (/mac/i.test(pf) || /Mac OS X|Macintosh/.test(ua)) return 'SuperconProgress-macos-universal.dmg';
    return '';
  };

  // The bold titles of the "Version X adds:" bullets in the release notes.
  const releaseHighlights = function releaseHighlights(body, v) {
    var lines = String(body || '').split(/\r?\n/), out = [], on = false;
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i].trim();
      if (!on) { if (ln.indexOf('Version ' + v) === 0) on = true; continue; }
      if (!ln) { if (out.length) break; continue; }
      if (ln.charAt(0) !== '-') { if (out.length) break; continue; }
      var m = /\*\*(.+?)\*\*/.exec(ln);
      if (m) out.push(m[1].replace(/<[^>]+>/g, ''));
    }
    return out.slice(0, 4);
  };

  const updRead = function updRead(key) { try { return JSON.parse(store.get(key) || 'null'); } catch (e) { return null; } };

  const updAvailable = function updAvailable() {
    var info = UPD.info;
    return !!(isDesktop() && info && info.url && verNewer(info.v, APP_VERSION));
  };

  const checkUpdate = function checkUpdate(manual, fresh) {
    if (!isDesktop() || UPD.busy) return;
    var cached = updRead('update');
    if (!manual && !fresh && cached && cached.t && Date.now() - cached.t < UPD_EVERY) { UPD.info = cached; renderUpdate(); downloadUpdate(false); return; }
    UPD.busy = true;
    if (manual) { store.set('updateLater', ''); UPD.dismissed = false; flashNote('Checking for updates…', 0); }
    getJSON(API + '/releases/latest', { headers: { Accept: 'application/vnd.github+json' }, timeout: 12000 })
      .then(function (rel) {
        var v = (verParts(rel && rel.tag_name) || []).join('.'), want = installerName(), url = '';
        (rel && rel.assets || []).forEach(function (a) { if (a && a.name === want && /^https:\/\//.test(a.browser_download_url || '')) url = a.browser_download_url; });
        var page = rel && /^https:\/\//.test(rel.html_url || '') ? rel.html_url : REPO_URL + '/releases/latest';
        // An unknown computer gets the release page; a known one waits until its installer is uploaded.
        UPD.info = { t: Date.now(), v: v, page: page, url: want ? url : page, news: releaseHighlights(rel && rel.body, v) };
        store.set('update', JSON.stringify(UPD.info));
        if (manual) flashNote(updAvailable() ? '' : 'You have the latest version.', 6000);
      }, function () {
        if (manual) flashNote('Couldn’t reach GitHub to check for updates. Try again later.', 8000);
      })
      .then(function () { UPD.busy = false; renderUpdate(); downloadUpdate(false); });
  };

  const nativeUpdateCall = function nativeUpdateCall(command, args) {
    var invoke = window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke;
    if (typeof invoke !== 'function') invoke = window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke;
    if (typeof invoke !== 'function') return Promise.reject(new Error('update_native_unavailable'));
    return Promise.resolve().then(function () { return invoke(command, args); });
  };

  const updateFailureText = function updateFailureText(error) {
    var code = typeof error === 'string' ? error : error && error.message;
    var messages = {
      update_busy: 'An update is already being prepared. Try again shortly.',
      update_not_newer: 'This installed app is already current. Check again for the latest release.',
      update_release_changed: 'The published version changed. Check again before downloading.',
      update_asset_unavailable: 'The installer for this computer is not available yet.',
      update_digest_unavailable: 'The installer has no verified checksum yet. Try again later.',
      update_integrity_failed: 'The installer failed its integrity check and will not be opened. Retry the download.',
      update_not_downloaded: 'Download the update again before installing it.',
      update_launch_failed: 'The installer could not be opened. Try again.',
      update_unsupported_platform: 'In-app installation is available on Windows and macOS.',
      update_native_unavailable: 'This installed build needs a one-time upgrade to version 0.3.10 or later before it can install updates inside the app.',
      update_origin_denied: 'Updates must be opened from the installed app.'
    };
    return Object.hasOwn(messages, code) ? messages[code] : 'The update could not be completed. Check your connection and try again.';
  };

  const downloadUpdate = function downloadUpdate(retry) {
    if (!updAvailable() || UPD.downloading || UPD.installing) return;
    var version = UPD.info.v;
    if (UPD.download && UPD.download.version === version) return;
    if (!retry && UPD.downloadAttempted === version) return;
    UPD.downloadAttempted = version; UPD.downloading = true; UPD.downloadError = ''; UPD.installError = '';
    UPD.download = null; UPD.installConfirm = false; UPD.launched = false; renderUpdate();
    return nativeUpdateCall('download_app_update', { expectedVersion: version }).then(function (artifact) {
      if (!artifact || artifact.version !== version || !['windows', 'macos'].includes(artifact.platform) ||
        !Number.isSafeInteger(artifact.size) || artifact.size < 1 || artifact.size > 1073741824 ||
        typeof artifact.downloadId !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(artifact.downloadId)) throw new Error('update_integrity_failed');
      if (UPD.info && UPD.info.v === version) UPD.download = artifact;
    }).catch(function (error) {
      if (UPD.info && UPD.info.v === version) UPD.downloadError = updateFailureText(error);
    }).then(function () {
      UPD.downloading = false; renderUpdate();
      if (UPD.info && UPD.info.v !== version) downloadUpdate(false);
    });
  };

  const installUpdate = function installUpdate() {
    if (!UPD.installConfirm || UPD.installing || !UPD.download || !UPD.info || UPD.download.version !== UPD.info.v) return;
    var artifact = UPD.download;
    UPD.installing = true; UPD.installConfirm = false; UPD.installError = ''; renderUpdate();
    return nativeUpdateCall('install_app_update', { downloadId: artifact.downloadId }).then(function (result) {
      if (!result || result.launched !== true || result.version !== artifact.version || result.platform !== artifact.platform) throw new Error('update_launch_failed');
      UPD.launched = true;
    }).catch(function (error) {
      var code = typeof error === 'string' ? error : error && error.message;
      if (code === 'update_integrity_failed' || code === 'update_not_downloaded') {
        // A missing or changed artifact must be downloaded and verified again.
        // Keep downloadAttempted set so retries require an explicit user action.
        UPD.download = null; UPD.installConfirm = false; UPD.downloadError = updateFailureText(error); UPD.installError = '';
      } else UPD.installError = updateFailureText(error);
    }).then(function () { UPD.installing = false; renderUpdate(); });
  };

  const flashNote = function flashNote(msg, ms) {
    UPD.note = msg;
    clearTimeout(UPD.noteTimer);
    renderUpdateFoot();
    if (msg && ms) UPD.noteTimer = setTimeout(function () { UPD.note = ''; renderUpdateFoot(); }, ms);
  };

  const renderUpdate = function renderUpdate() {
    var el = $('#update');
    if (!el) return;
    clear(el);
    var info = UPD.info, kind = '';
    if (UPD.web && !UPD.dismissed) kind = 'web';
    else if (updAvailable() && !UPD.dismissed) {
      var later = updRead('updateLater');
      if (!(later && later.v === info.v && Date.now() < later.until)) kind = 'desktop';
    }
    el.hidden = !kind;
    updateWebBadge(kind === 'web');
    if (kind === 'web') {
      append(el, [glyph('refresh', 'upd-glyph'), h('div', { class: 'upd-body' },
        h('p', { class: 'upd-title', text: UPD.web === 'new' ? 'A new version of Supercon Progress is available.' : 'Supercon Progress ' + UPD.web + ' is available.' }),
        h('div', { class: 'upd-actions' },
          h('button', { class: 'btn primary', type: 'button', onclick: function () { window.location.reload(); } }, 'Reload now'),
          h('button', { class: 'btn', type: 'button', onclick: function () { UPD.dismissed = true; renderUpdate(); } }, 'Later')))]);
    } else if (kind === 'desktop') {
      var artifact = UPD.download && UPD.download.version === info.v ? UPD.download : null;
      var actions = h('div', { class: 'upd-actions' }), status = '';
      if (UPD.downloading) status = 'Downloading and verifying the update inside the app…';
      else if (UPD.installing) status = 'Opening the installer…';
      else if (UPD.launched) status = artifact && artifact.platform === 'macos'
        ? 'The installer is open. Drag Supercon Progress into Applications to replace it, then reopen the app.'
        : 'The installer is open. Follow its prompts to finish, then reopen the app.';
      else if (artifact) {
        status = 'Update downloaded and verified. Installation starts only after you confirm.';
        if (UPD.installConfirm) {
          actions.appendChild(h('button', { class: 'btn primary', type: 'button', onclick: installUpdate }, 'Confirm installation'));
          actions.appendChild(h('button', { class: 'btn', type: 'button', onclick: function () { UPD.installConfirm = false; renderUpdate(); } }, 'Cancel'));
        } else actions.appendChild(h('button', { class: 'btn primary', type: 'button', onclick: function () { UPD.installConfirm = true; renderUpdate(); } }, 'Install update'));
      } else actions.appendChild(h('button', { class: 'btn primary', type: 'button', onclick: function () { UPD.downloadAttempted = ''; checkUpdate(true, true); } }, UPD.downloadError ? 'Retry download' : 'Download update'));
      actions.appendChild(h('button', { class: 'btn', type: 'button', onclick: function () { store.set('updateLater', JSON.stringify({ v: info.v, until: Date.now() + UPD_LATER })); renderUpdate(); } }, 'Later'));
      append(el, [glyph('download', 'upd-glyph'), h('div', { class: 'upd-body' },
        h('p', { class: 'upd-title', text: 'Supercon Progress ' + info.v + ' is available. You have ' + APP_VERSION + '.' }),
        info.news && info.news.length ? h('p', { class: 'upd-news', text: 'New: ' + info.news.join(' · ') }) : null,
        actions, h('p', { class: 'upd-hint', role: 'status', text: UPD.downloadError || UPD.installError || status }))]);
    }
    renderUpdateFoot();
  };

  const renderUpdateFoot = function renderUpdateFoot() {
    var el = $('#upd-foot');
    if (!el) return;
    clear(el);
    if (!isDesktop()) return;
    el.appendChild(document.createTextNode(' · '));
    if (UPD.note) { el.appendChild(h('span', { class: 'upd-note', role: 'status', text: UPD.note })); return; }
    if (updAvailable()) {
      el.appendChild(h('button', { class: 'linklike', type: 'button', onclick: function () {
        store.set('updateLater', ''); UPD.dismissed = false; renderUpdate(); window.scrollTo(0, 0);
      } }, 'Update to ' + UPD.info.v));
      return;
    }
    el.appendChild(h('button', { class: 'linklike', type: 'button', onclick: function () { checkUpdate(true); } }, 'Check for updates'));
  };


  const render = function render() {
    renderChrome();
    var d = state.data;
    $('#main').hidden = !d || view !== 'progress';
    $('#candidates').hidden = !d || view !== 'candidates';
    if (!d) return;
    renderPipeline(d);
    renderCandidates(d);
    renderKpis(d);
    renderModels(d);
    renderStages(d);
    renderResults(d);
    renderActivity(d);
    renderGitHub();
    renderDetails(d);
    if (demo.built && view === 'demos') { syncControls(); kick(); }
    if (view === 'authors') renderAuthors();
    if (aiState.built) renderAIOurs();
  };


  const applyTheme = function applyTheme() {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
  };
