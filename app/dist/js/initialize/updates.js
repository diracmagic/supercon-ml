'use strict';
// updates: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconUpdates = function initializeSuperconUpdates() {


  /* ---------- new-version prompt ----------
     Desktop app: checks the latest release on startup and return. The native app
     independently verifies and downloads the installer; installation requires confirmation.
     Phone and web app: check the published application version at startup and on return,
     keeping service-worker cache revisions separate. Reload only when the user chooses it. */
  UPD = { info: null, busy: false, note: '', noteTimer: 0, web: '', dismissed: false, badged: null,
    download: null, downloading: false, downloadAttempted: '', downloadError: '', installing: false, installError: '', installConfirm: false, launched: false };

  UPD_EVERY = 15 * 60 * 1000;
  UPD_LATER = 3 * 24 * 3600 * 1000;

  if (window.__TAURI__ || window.__TAURI_INTERNALS__) {
    // OAuth can leave a native window on the public web APP. Its bridge object
    // is not authorization: only the bundled local origin may invoke updates.
    if (!isDesktop()) { UPD.returnToApp = true; renderUpdate(); return; }
    var lastDesktop = 0;
    function pollDesktop() {
      if (UPD.busy || document.visibilityState !== 'visible' || navigator.onLine === false || Date.now() - lastDesktop < UPD_EVERY) return;
      lastDesktop = Date.now(); checkUpdate(false, true);
    }
    setTimeout(pollDesktop, 3000);
    setInterval(pollDesktop, UPD_EVERY);
    document.addEventListener('visibilitychange', pollDesktop);
    window.addEventListener('online', pollDesktop);
  }

  (function registerWorker() {
    if (!('serviceWorker' in navigator) || location.protocol !== 'https:' || isDesktop()) return;
    var sw = navigator.serviceWorker, had = !!sw.controller, last = 0, reading = null;
    function checkVersion() {
      if (reading) return reading;
      if (navigator.onLine === false) return Promise.resolve();
      reading = fetch('sw.js', { cache: 'no-store', redirect: 'error' }).then(function (response) {
        if (!response.ok) throw new Error('Version unavailable');
        return response.text();
      }).then(function (text) {
        var version = webReleaseVersion(text);
        if (version && verNewer(version, APP_VERSION) && (!UPD.web || verNewer(version, UPD.web))) {
          UPD.web = version; UPD.dismissed = false; renderUpdate();
        }
      }).catch(function () { /* Offline or unverified version: keep quiet. */ }).then(function () { reading = null; });
      return reading;
    }
    sw.register('sw.js').then(function (reg) {
      var polling = false;
      function poll() {
        if (!had || polling || document.visibilityState !== 'visible' || navigator.onLine === false || Date.now() - last < 60000) return;
        last = Date.now();
        polling = true;
        Promise.resolve().then(function () { return reg.update(); }).then(checkVersion)
          .catch(function () { /* Offline checks never create an update notice. */ })
          .then(function () { polling = false; });
      }
      poll();
      setInterval(poll, 15 * 60 * 1000);
      document.addEventListener('visibilitychange', poll);
      window.addEventListener('online', poll);
    }).catch(function () { /* offline support is optional */ });
    sw.addEventListener('controllerchange', function () {
      if (!had) { had = true; return; }   // the first install, not an update
      checkVersion();
    });
  })();

};
