'use strict';
// storm-demo: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconStormDemo = function initializeSuperconStormDemo() {


  /* ---------- Storm: the AI-designed model, animated from its own spec ----------
     Every release writes a machine-readable spec into progress.json (ai_model.versions[]):
     inputs, learner settings, scores and the list of changes. This demo draws only from that
     spec, so each new version of Storm explains itself without new drawing code. */
  STORM_STAGES = [
    { node: 'AI designs', short: 'Design' },
    { node: 'Inputs', short: 'Inputs' },
    { node: 'Learner', short: 'Learner' },
    { node: 'Prediction', short: 'Predict' },
    { node: 'Validation', short: 'Check' },
    { node: 'What’s new', short: 'New' }
  ];

  STORM_DUR = 7;

  PHYS_LABELS = {
    vec: 'valence electrons per atom', matthias_d47: 'distance to Matthias peak 4.7', matthias_d65: 'distance to Matthias peak 6.5',
    d_fraction: 'd-block share', p_fraction: 'p-block share', light_fraction: 'light-atom share',
    inv_sqrt_mass: 'M^−½ phonon scale', omega_proxy: 'stiffness over mass', mass_ratio: 'heaviest / lightest mass',
    x_diff: 'electronegativity spread', packing_fraction: 'packing fraction',
    theta_lindemann: 'Lindemann Debye scale', theta_lindemann_min: 'softest-atom Debye scale', sound_omega: 'sound-speed frequency',
    bulk_mean: 'mean bulk modulus', omega_bulk: 'stiffness-over-mass frequency'
  };

  STORM_BASE = { trees: 800, leaves: 31, learning_rate: 0.04, min_leaf: 20, l2: 1, features_per_split: 1 };

};
