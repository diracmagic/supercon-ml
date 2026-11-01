'use strict';
// crystal-viewer: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconCrystalViewer = function initializeSuperconCrystalViewer() {


  /* ---------- turning crystal structures ----------
     One requestAnimationFrame loop draws the structure canvases that are on screen while the Candidates view is open.
     The c axis points up; each cell turns about it and is seen from 24° above, with the far side faded. */
  XT = { items: [], raf: 0, last: 0, t: 0, obs: null, play: true };

  XT_SPEED = 2 * Math.PI / 24;
   // one turn in 24 s
  XT_YAW0 = 0.6;
  XT_PITCH0 = 0.42;

  window.addEventListener('resize', function () { if (xtOn()) { xtDirty(); xtKick(); } });

  document.addEventListener('visibilitychange', function () { if (!document.hidden) xtKick(); });

};
