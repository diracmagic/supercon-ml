'use strict';
// model-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconModelDemo = function initializeSuperconModelDemo() {


  /* ---------- Our model: animated walk through the real pipeline ---------- */
  MODEL_STAGE_DUR = 6;

  MODEL_STAGES = {
    baseline: [
      { node: 'Crystal', short: 'Crystal', title: 'Input: one crystal',
        text: 'The model sees only the crystal: which atoms sit where in the unit cell. Training data are the 7,582 crystals of the Alexandria superconductivity set with computed λ, ω_log and Tc (hydrides removed), spread over 4,288 chemical systems.' },
      { node: 'Features', short: 'Features', title: '43 numbers per crystal',
        text: 'The baseline turns each crystal into 43 hand-made features: the mean, spread, minimum and maximum of eight element properties (atomic number, mass, electronegativity, row, group, radius, Mendeleev number, valence), the number of elements and sites, and the cell size and shape, density and nearest-neighbour distances.' },
      { node: 'Gradient boosting', short: 'Boosting', title: 'Gradient-boosted trees',
        text: 'Histogram gradient boosting adds up to 800 small decision trees one at a time; each tree corrects a small part of the remaining error (learning rate 0.04, at most 31 leaves per tree). Separate models learn λ, ω_log and log(1 + Tc).' },
      { node: 'λ, ω_log → Tc', short: 'λ, ω → Tc', title: 'From λ and ω_log to Tc',
        text: 'The predicted λ and ω_log go into the Allen–Dynes formula with μ* = 0.10. A separate model also predicts Tc directly, and both routes are scored.' },
      { node: 'Score', short: 'Score', title: 'Honest scoring',
        text: 'Five-fold cross-validation grouped by chemical system: all compounds of a system, such as every Mo–W phase, are held out together, so the score shows how the model handles chemistry it has never seen.' }
    ],
    foundation: [
      { node: 'Crystal', short: 'Crystal', title: 'Input: one crystal',
        text: 'The same 7,582 Alexandria crystals and the same input: atom types and positions in the unit cell.' },
      { node: 'MACE-MP-0', short: 'MACE', title: 'A foundation model reads the crystal',
        text: 'MACE-MP-0 (medium), pre-trained on about 1.6 million DFT calculations from the Materials Project and kept frozen, passes messages between atoms within a 6 Å cutoff in two layers. Each atom ends with a vector of invariant features, pooled over the crystal by mean, standard deviation and maximum into one fingerprint.' },
      { node: '3 boosted models', short: '3 models', title: 'An ensemble for error bars',
        text: 'Three gradient-boosted models (up to 1,000 trees each, with early stopping) are trained on bootstrap resamples of the training set. Their average is the prediction and their spread is an error bar.' },
      { node: 'λ, ω_log → Tc ± σ', short: 'Tc ± σ', title: 'Tc with an uncertainty',
        text: 'Allen–Dynes turns the predicted λ and ω_log into Tc, and the spread of the three models gives a range. Error bars tell us which candidates are worth a full calculation.' },
      { node: 'Score', short: 'Score', title: 'Same honest scoring',
        text: 'The same grouped five-fold cross-validation as the baseline, so the two models compare fairly, plus a check that larger error bars really go with larger errors (rank correlation).' }
    ]
  };

  CHEMSYS = ['Sc–Zr', 'Re–Tc', 'Pt–Rh', 'Sc–Y', 'Al–Zn', 'Ti–Zr', 'Mo–V–W', 'Al–Li', 'La–Y', 'Nb–Ta–W', 'Mo–W', 'Al–Sc', 'Hf–Zr', 'Os–Tc', 'Ta–W', 'Mo–Nb', 'Al–Mg', 'Li–Mg', 'Al–Co–V', 'Ti–Zn–Zr'];

  FEATURE_GROUPS = [['count', 2], ['Z', 4], ['mass', 4], ['electroneg.', 4], ['row', 4], ['group', 4], ['radius', 4], ['Mendeleev', 4], ['valence', 4], ['cell', 6], ['neighbours', 3]];

};
