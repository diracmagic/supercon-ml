'use strict';
// tour: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconTour = function initializeSuperconTour() {


  /* ---------- Hello Super: animated tour of the project ---------- */
  // 200 materials held out by 5-fold grouped CV, as [computed Tc, predicted Tc] pairs in K,
  // sampled from results/model_search_predictions.csv (out-of-fold predictions of Storm 1.0, the AI-designed model).
  PARITY = [1.49,2.08,2.38,0.62,1.59,0.11,0.5,0.3,0.01,0.07,0,0.03,2.02,0.55,2.65,3.34,0,0.3,0.08,0.07,0,0.09,0,0.2,1.95,1.07,0.02,0,0.31,0.14,1.39,0.87,1.16,1.98,0.25,0.19,0.36,0.62,0.94,0.37,1.51,0.68,2.54,1.49,0.02,0,0,0.15,0.03,0.3,0.26,0.3,0.09,0.38,1.8,1.04,8.64,3.88,5.72,5.17,1.46,1.51,10.22,7.06,0.58,1.01,0,0.48,0,0.11,0.57,1.11,0,0.52,0,0.69,0,0.24,0.24,1.66,0,0.2,0,0,0.02,0.13,0.01,0.86,0,0.35,8.74,5.58,1.19,0.7,0.03,1.18,0.35,0.93,0,0.12,0.72,1.17,5.88,5.81,3.92,2.8,6.53,11.33,0.39,0.44,0.6,0.29,1.78,2.01,0.46,1.77,2.36,1.43,1.66,2.18,0.4,0.35,0.26,0.11,0,0.03,0.04,0.01,0,0,0,0.03,0,0.16,0,0.03,0.12,0.07,5.65,7,0,0,0.25,0.81,0,0.01,5.54,4.58,0.56,1.5,1.26,0.76,0.92,0.58,0,0.03,0.78,0.47,1.56,0.84,0.11,0.26,2.53,6.6,0.76,0.52,0.02,0.33,0.52,0.42,0.72,0.58,0,0,0.02,0.07,3.41,0.72,0.31,0.2,0.14,0.62,12.58,5.49,3.25,1.97,0.15,0.33,0.02,0.53,2.22,0.92,0.09,0.17,0.08,0.26,0.05,1.24,0.01,0.16,0.21,0.71,4.96,1.82,0.05,0.07,7.75,8.55,0,0.14,0.62,0.89,0,0.17,0.81,2.34,1.18,0.58,0.09,0.27,0.18,0.44,0.96,1.06,0.59,1.46,2.04,0.88,2.44,1.59,0.06,0.33,0.99,0.69,1.29,3.21,8.3,1.52,0.06,0.39,0.4,1.87,6.58,5.22,0,0,8.59,6.74,0.01,0,0.14,0.91,0,0,0,0.13,0.88,0.44,0,0.07,0.87,2.51,0.46,0.83,0.06,0.59,0.49,1.36,0,0,0.78,0.89,4.83,3.68,1.41,0.18,0.06,0,0.4,2.69,0.03,0.08,1.57,1.09,0.02,0.15,0.22,1.11,0.2,0.32,1.92,1.56,0.13,0.03,0.51,0.46,0,0.01,5.96,3.36,0.01,0.11,0.02,0.2,0.25,0.25,1.6,1.57,0,0,0,0,0.83,4.09,0,0.06,0.01,0.38,0.36,0.31,1.81,3.13,0,0,1.85,0.11,0.2,0.26,0.48,0.49,1.02,0.78,0.03,0.45,0.29,1.75,0,0.35,2.73,1.09,0,0.08,0.1,0.27,1.25,1.87,0.03,0.99,0.03,2.01,10.1,1.53,10.24,8.68,11.53,1.15,6.3,6.55,8.18,9.37,11.2,9.72,9.35,8.42,16.43,14.38,5.76,2.64,12.5,8.57,11.14,10.02,7.3,6.64,9.06,6.67,8.11,7.22,7.67,6.15,3.72,3.5,0,1.33,8.49,8.68,1.81,2.41,12.76,5.83,4.04,4.6,7.15,2.61,6.84,5.82,3.66,5.62,9.31,10.15];

  PARITY_MEAN = 2.23;
   // mean computed Tc of the 7,582 training materials (K)
  MAE_GUESS = 2.64;
     // error from predicting that mean for every material (K)
  MAE_BASELINE = 1.05;
  // gradient-boosting baseline, 5-fold grouped CV (K)
  MAE_STORM = 0.97;


  WHY_ITEMS = [
    { name: 'Mercury', T: 4.2, year: 1911, kind: 'conv' },
    { name: 'Niobium', T: 9.3, year: 1930, kind: 'conv' },
    { name: 'YBCO', T: 92, year: 1987, kind: 'unconv' },
    { name: 'Hg-1223', T: 133, year: 1993, kind: 'unconv' },
    { name: 'MgB₂', T: 39, year: 2001, kind: 'conv' },
    { name: 'LaH₁₀', T: 250, year: 2019, kind: 'pressure' },
    { name: 'Hg-1223, quenched', T: 151, year: 2026, kind: 'unconv' }
  ];

  WHY_REFS = [
    { name: 'Liquid helium', short: 'Liquid He', T: 4.2, val: '4.2 K' },
    { name: 'Liquid nitrogen', short: 'Liquid N₂', T: 77, val: '77 K' },
    { name: 'Room temperature', short: 'Room temp.', T: 295, val: '295 K' }
  ];


  STORY = [
    { title: 'Hello Super', bare: true, dur: 6, draw: drawStoryIntro,
      caption: 'Hello Super is an open project that uses machine learning to predict the critical temperature Tc of superconductors from their crystal structure, to screen materials databases for high-Tc candidates, and to look for clues about what drives superconductivity. This 90-second tour walks through the idea in ten steps.',
      refs: [] },
    { title: 'Why it matters', dur: 9, draw: drawStoryWhy,
      sub: 'Zero resistance, but only when cold enough. Can we find warmer superconductors?',
      caption: 'A superconductor carries electric current with no resistance at all, but only below its critical temperature Tc. Most need liquid helium (4.2 K). Copper-oxide "cuprates" work in liquid nitrogen (77 K); their ambient-pressure record of 133 K stood from 1993 until 2026, when a pressure-quenched Hg-1223 sample kept superconductivity up to 151 K. Hydrides reach about 250 K, but only when squeezed to 1.7 million atmospheres, and a 2025 preprint reports signs of superconductivity near room temperature in LaSc₂H₂₄ at over 2 million atmospheres. A superconductor that works warm, at everyday pressure, could carry power without loss and make MRI scanners and strong magnets far cheaper to run.',
      refs: ['onnes1911', 'bednorz1986', 'schilling1993', 'deng2026', 'drozdov2019', 'song2025'] },
    { title: 'What sets Tc', dur: 8, draw: drawStoryPhysics,
      sub: 'Electrons pair up through lattice vibrations; λ and ω_log decide how high Tc goes.',
      caption: 'In conventional superconductors a moving electron pulls the positive ions toward it and leaves a wake that attracts a second electron, binding the two into a Cooper pair (BCS theory). The strength of this electron–phonon coupling is λ, and ω_log is a typical vibration energy of the lattice. Eliashberg theory and the Allen–Dynes formula turn the two into Tc: here, raising λ from 0.3 to 1.0 at ω_log = 300 K lifts Tc from about 0.1 K to about 21 K.',
      refs: ['bcs1957', 'eliashberg1960', 'allendynes1975'] },
    { title: 'The slow way', dur: 9, draw: drawStorySlow,
      sub: 'Computing λ and ω_log from quantum mechanics takes hours to days per material.',
      caption: 'λ and ω_log can be computed from first principles with density-functional theory (DFT) and density-functional perturbation theory for the phonons. The results are reliable, but every material costs hours to days of supercomputer time, and open databases list millions of known and predicted crystals: far too many to compute one by one.',
      refs: ['baroni2001', 'giustino2017'] },
    { title: 'Our AI model', dur: 9, draw: drawStoryShortcut,
      sub: 'Storm, the model our AI agent designed, predicts Tc from the crystal in under a second.',
      caption: storyShortcutCaption,
      refs: ['alexandria2024', 'matthias1955', 'friedman2001', 'allendynes1975', 'macemp2023'] },
    { title: 'Many models', dur: 8, draw: drawStoryModels,
      sub: 'We try many kinds of AI models, and let an AI agent design new ones.',
      caption: storyModelsCaption,
      refs: ['friedman2001', 'alignn2021', 'macemp2023', 'nas2017'] },
    { title: 'How accurate?', dur: 8, draw: drawStoryAccuracy,
      sub: 'We test predictions on materials the model never saw during training.',
      caption: storyAccuracyCaption,
      refs: ['sklearn2011', 'jarvis2022'] },
    { title: 'Screening', dur: 8, draw: drawStoryScreen,
      sub: 'Rank thousands of candidates by predicted Tc, then verify only the best few.',
      caption: 'With a fast model we can scan large crystal databases, rank every candidate by its predicted Tc, and spend supercomputer time only on the most promising few, where the full calculation confirms or rejects the prediction. The squares here are an illustration, not real candidates.',
      refs: ['jarvis2022', 'alexandria2024'] },
    { title: 'Beyond phonons', dur: 8, draw: drawStoryBeyond,
      sub: 'Cuprates and iron-based superconductors pair up through a different glue.',
      caption: function () {
        var ri = radInfo();
        return 'Cuprates and iron-based superconductors do not follow the phonon recipe, and what binds their electron pairs is still debated; magnetic spin fluctuations are a leading candidate. So our second AI-designed model, Hurricane, learns directly from measured Tc values, each graded by how well it has been confirmed, and a third, ' +
          (ri ? radTitle(ri) + ', decides which of the two each material goes to, picking the right one ' + radPct(ri.v.scores.balanced_accuracy) + ' of the time for compounds it never saw.'
            : 'Radar, will decide which of the two each material goes to.') +
          ' Comparing what Storm and Hurricane rely on can give clues about the pairing mechanism.';
      },
      refs: ['bednorz1986', 'kamihara2008', 'tsuei2000', 'scalapino2012'] },
    { title: 'Our second AI model', dur: 10, draw: drawStoryHurricane,
      sub: 'Hurricane, also designed by our AI agent, learns unconventional Tc from measurements.',
      caption: hurStoryCaption,
      refs: ['sommer2023', 'presland1991', 'friedman2001'] },
    { title: 'The loop', dur: 7, draw: drawStoryLoop,
      sub: 'Predict, screen, verify, learn: every confirmed result makes the next round better.',
      caption: 'Each confirmed calculation becomes new training data, so the models improve with every round. All code and data are public on GitHub, and every training run updates the Progress page of this app.',
      refs: [] }
  ];


  /* 7 · screening */
  SCREEN_CACHE = null;

};
