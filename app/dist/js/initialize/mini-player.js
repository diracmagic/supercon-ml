'use strict';
// mini-player: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconMiniPlayer = function initializeSuperconMiniPlayer() {


  /* ---------- mini animations on the Theory & materials cards and the news ----------
     One requestAnimationFrame loop draws only the canvases on screen, and only while their view is open. */
  MINI = { items: [], raf: 0, last: 0, obs: null };

  window.addEventListener('resize', function () { if (miniOn()) { MINI.items.forEach(function (it) { it.W = 0; }); miniKick(); } });

  document.addEventListener('visibilitychange', function () { if (!document.hidden) miniKick(); });

};
