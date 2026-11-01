'use strict';
// updates: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconUpdates = function initializeSuperconUpdates() {


  /* ---------- new-version prompt ----------
     Desktop app: asks GitHub at most every 6 hours for the latest release (tag app-vX.Y.Z). When it is newer
     than this build and already has the installer for this computer, a banner offers the download.
     Phone and web app: the service worker fetches new versions by itself; once a new one has taken over,
     the banner offers a reload. */
  UPD = { info: null, busy: false, note: '', noteTimer: 0, web: '', dismissed: false, downloaded: false };

  UPD_EVERY = 6 * 3600 * 1000;
  UPD_LATER = 3 * 24 * 3600 * 1000;

  if (isDesktop()) {
    setTimeout(function () { checkUpdate(false); }, 3000);
    setInterval(function () { checkUpdate(false); }, 3600 * 1000);
  }

  (function registerWorker() {
    if (!('serviceWorker' in navigator) || location.protocol !== 'https:' || isDesktop()) return;
    var sw = navigator.serviceWorker, had = !!sw.controller, last = Date.now();
    sw.register('sw.js').then(function (reg) {
      function poll() {
        if (document.visibilityState !== 'visible' || Date.now() - last < 10 * 60 * 1000) return;
        last = Date.now();
        reg.update().catch(function () { /* offline */ });
      }
      setInterval(poll, 15 * 60 * 1000);
      document.addEventListener('visibilitychange', poll);
    }).catch(function () { /* offline support is optional */ });
    sw.addEventListener('controllerchange', function () {
      if (!had) { had = true; return; }   // the first install, not an update
      fetch('sw.js', { cache: 'no-store' }).then(function (r) { return r.text(); }).then(function (txt) {
        var m = /supercon-(\d+\.\d+\.\d+)/.exec(txt);
        if (m && !verNewer(m[1], APP_VERSION)) return;   // the same version deployed again
        UPD.web = m ? m[1] : 'new'; UPD.dismissed = false; renderUpdate();
      }).catch(function () { UPD.web = 'new'; renderUpdate(); });
    });
  })();

};
