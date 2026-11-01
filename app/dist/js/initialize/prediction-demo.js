'use strict';
// prediction-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconPredictionDemo = function initializeSuperconPredictionDemo() {


  /* ---------- Predict Tc: the Allen–Dynes formula, and how Storm and Hurricane predict, step by step ----------
     The two walk-throughs use only numbers the models computed: the worked examples that Storm round 5 writes into
     progress.json (ai_model.uncertainty.worked, out of fold) and the anchors of the Hurricane in use (each with the two
     parts of its prediction). A new training round therefore updates them without a new app. */
  PRED_MODES = [['formula', 'Formula'], ['storm', 'Storm'], ['hurricane', 'Hurricane']];

};
