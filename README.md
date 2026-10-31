# supercon-ml

Finding high-T<sub>c</sub> superconductors with AI-designed models. The project predicts the critical temperature T<sub>c</sub> of conventional (electron–phonon) and unconventional superconductors from crystal structure, screens open databases for high-T<sub>c</sub> candidates, and then asks what the models have learned about pairing mechanisms. An AI agent (Claude) designs the models: **Storm** for conventional superconductors, **Hurricane** for unconventional ones and **Radar** to decide which of the two a material goes to.

[![Progress](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiracmagic%2Fsupercon-ml%2Fmain%2Fprogress%2Fprogress.json&query=%24.badge&label=progress&color=2a78d6)](progress/progress.json)
[![Desktop app](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml/badge.svg)](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml)

Questions, ideas, collaborations and offers to measure one of our candidates are welcome: write to us with the message form in the app's **Cite** view, which goes straight to the project's inbox.

## Follow the progress

The app shows every stage, the training results, our three models and the GitHub Actions runs as they happen, with the details of each model's latest round. It also has six other views:

- **Candidates**: the candidate superconductors found by our AI models, in two lists: conventional ones ranked by Storm and unconventional ones ranked by Hurricane. Each has its predicted T<sub>c</sub> with a 90% range, the chance that it superconducts, its crystal structure turning in 3D, the date we first listed it and remarks on how far to trust it, and all are published before any calculation or experiment checks them. Only our own finds are listed (see *High-T<sub>c</sub> screening* below).
- **Physics demos**, starting with *Hello Super*, a 90-second animated tour of the project, and *Our AI model: Storm*, *Our AI model: Hurricane* and *Our AI model: Radar*, animations of the versions in use of the three models our AI agent designed, drawn from their own results. *Baselines* shows the simple model each of them must beat. *Predict T<sub>c</sub>* has the Allen–Dynes formula with sliders and, step by step, how Storm and Hurricane predict T<sub>c</sub> for real materials, with the numbers they computed. Demos of zero resistance, the Meissner effect and Cooper pairs follow.
- **Theory & materials**: the main theories of superconductivity, the classic ideas for high-T<sub>c</sub> superconductivity in the cuprates and the materials behind today's headlines, each with an animation, the original papers and the latest results, plus the Nobel Prizes for superconductivity.
- **News & papers**: superconductivity news, each story with a drawing of its topic, and new papers from arXiv, Nature, Science, Physical Review and the Nature-family journals, refreshed every three hours, plus a curated list of recent advances in experiment, theory and AI for superconductivity.
- **AI × superconductors**: new papers and news on machine learning, AI agents and autonomous labs for superconductors, newest first and checked again every ten minutes while the view is open, with new AI predictions and new AI-guided experiments tagged automatically. It also lists our AI-designed models, every superconductor that an AI or machine-learning model pointed to and an experiment then confirmed, notable AI predictions still waiting for an experiment, and a curated list of AI advances, each with its paper.
- **Cite**: how to cite the project and our candidates (as text or BibTeX), the published work that cites supercon-ml, and where the data come from.

New results, papers and curated advances reach the app without an update, because it reads `progress/progress.json`, `progress/papers.json` and `progress/content.json` from this repository. The desktop app tells you when a new version is out, and the phone version updates itself.

| Platform | Get it |
|---|---|
| Windows 10/11 | [SuperconProgress-windows-x64-setup.exe](https://github.com/diracmagic/supercon-ml/releases/latest/download/SuperconProgress-windows-x64-setup.exe) |
| macOS, Apple Silicon and Intel | [SuperconProgress-macos-universal.dmg](https://github.com/diracmagic/supercon-ml/releases/latest/download/SuperconProgress-macos-universal.dmg) |
| iPhone, iPad and Android | Open [diracmagic.github.io/supercon-ml](https://diracmagic.github.io/supercon-ml/) and add it to your home screen (iPhone and iPad: **Share → Add to Home Screen**; Android: **⋮ → Install app**). |

The installers aren't code-signed yet. On Windows, click **More info → Run anyway** if SmartScreen appears. On macOS, if it says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.

## Our models

| Model | For | Learns from | Status |
|---|---|---|---|
| **Storm** | Conventional superconductors, paired by phonons | About 7,600 materials whose electron–phonon coupling λ and ω<sub>log</sub> have been computed (Alexandria), calibrated to the measured T<sub>c</sub> of 298 of them (3DSC); since Storm 4.0 its boosted trees work together with a crystal-graph network, and since Storm 5.0 every prediction comes with a 90% range | Storm 5.0 in use |
| **Hurricane** | Unconventional superconductors: cuprates, nickelates, iron-based, heavy-fermion and more | 2,123 measured T<sub>c</sub> values (3DSC: SuperCon with Materials Project structures); later discoveries graded as replicated, single report, preprint, retracted or refuted | Hurricane 2.0 in use |
| **Radar** | Deciding which model to ask | 5,751 SuperCon entries in 3DSC labelled by chemical class: 2,123 in Hurricane's families and 3,628 conventional ones for Storm | Radar 1.0 in use |

Where Storm and Hurricane disagree about a material is itself a clue to its pairing mechanism.

## Storm, the model for conventional superconductors

An AI agent (Claude) designs the project's T<sub>c</sub> models. In each of Storm's search rounds it proposes new feature sets, physics features and settings. Every candidate is trained and scored with the same composition-grouped five-fold cross-validation, and a design is released as a new version of **Storm** only if it beats the current best on average and in at least 4 of the 5 folds. The locked JARVIS test set is never used to pick a design.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Baseline |
|---|---|---|---|
| Storm 1.0 | Hand-made features + 11 AI-proposed physics features, deeper boosted trees | 0.969 K, better than the baseline in 5 of 5 folds | 1.045 K |
| Storm 2.0 (experimental) | Storm 1.0 + an Allen–Dynes stage (predicted λ, ω<sub>log</sub> and their Allen–Dynes T<sub>c</sub> as extra inputs) | 0.966 K, better than Storm 1.0 in only 2 of 5 folds, so not released | 1.045 K |
| Storm 3.0 | Storm 1.0 calibrated to measured T<sub>c</sub> (round 3, below) | 0.969 K against computed T<sub>c</sub>; 1.61 K against measured T<sub>c</sub> | 1.045 K |
| Storm 4.0 | Storm 1.0, the graph network 2.0 and the network's Allen–Dynes route, averaged, then calibrated as in round 3 (round 4, below) | 0.898 K, better than Storm 1.0 in 5 of 5 folds; 1.56 K against measured T<sub>c</sub> | 1.045 K |
| Storm 5.0 | Storm 4.0 with a 90% range for every prediction: one width on log(1 + T<sub>c</sub>), set by conformal prediction (round 5, below) | 0.898 K; the range held the computed T<sub>c</sub> of 90% of held-out materials and of 84% of the tenth with the highest T<sub>c</sub> | 1.045 K |

From round 2 on, every candidate is also compared with graded measured T<sub>c</sub> (`data/experiments.json`): only replicated, ambient-pressure, phonon-mediated superconductors are scored, and single reports, preprints and retracted claims are listed with their status but never scored. A new version may not be more than 0.5 K worse than the current one on these measurements. On the 18 scored materials, Storm 1.0 is off by 7.6 K on average and the best round-2 design by 6.9 K, while the DFT labels they learn from are themselves off by 7.0 K (MgB<sub>2</sub>, for example, is 8 K in the DFT data and 39 K in experiment). Most of the remaining error therefore comes from the labels, not the model.

**Round 3, Storm 3.0: calibrated to measured T<sub>c</sub>.** 3DSC lists 298 conventional materials (168 of them superconducting) that are also in Storm's training data. The AI agent proposed five maps from Storm's predictions to the measured value, from a linear map and an Allen–Dynes map with a rescaled λ and an effective μ* to a small gradient-boosting correction. Their inputs are Storm 1.0's predictions for materials it never saw, never the DFT labels, and they were scored with the same grouped cross-validation. The gradient-boosting correction is off by 1.61 K on average, against 2.24 K for uncalibrated Storm 1.0 and 2.48 K for the DFT labels themselves, better in 5 of 5 folds, and was released as Storm 3.0. The largest shortfalls, such as AlV<sub>3</sub>, V<sub>3</sub>Ga and the borocarbides, are leads for the mechanism study.

**Round 4, Storm 4.0: boosted trees and a crystal-graph network together.** Storm 1.0's trees and the graph network (below) learn from different inputs, and their mistakes only partly overlap. The AI agent proposed three ways to combine them, all scored on the same folds: a plain average, an average on log(1 + T<sub>c</sub>) and a three-way average that adds the network's Allen–Dynes route from its predicted λ and ω<sub>log</sub>. All three beat Storm 1.0 in 5 of 5 folds; the three-way average is off by 0.898 K against 0.969 K for Storm 1.0, and by 6.7 K against 7.6 K on the 18 graded measurements. Calibrated with round 3's maps on the same 298 matched materials, it is off by 1.56 K against measured T<sub>c</sub>, against 1.61 K for Storm 3.0 (better in 3 of 5 folds), and was released as Storm 4.0.

**Round 5, Storm 5.0: how sure is Storm?** To pick materials for a calculation or an experiment, the range matters as much as the number. The AI agent proposed six ways to put a 90% range around Storm 4.0's prediction, which itself does not change. Every range is set by conformal prediction from the out-of-fold errors in the other four folds, so it never uses its own fold's answers, and the designs are scored by the interval score (the width plus 20 times any miss, lower is better) and by how often the range holds the computed T<sub>c</sub>. One width for every material holds 90% of the held-out materials but only 54% of the tenth with the highest T<sub>c</sub>, where screening looks. The same width on log(1 + T<sub>c</sub>), so that the range grows with T<sub>c</sub>, holds 90% overall and 84% of that tenth, half of its ranges are narrower than 1.8 K, and its interval score is 7.47 K against 8.02 K, better in 5 of 5 folds; it was released as Storm 5.0. Conformalised gradient-boosted quantiles scored better on the interval score (6.0 K) but held only 72% of the highest-T<sub>c</sub> tenth, below the 80% the rule asks for. A range is for the computed T<sub>c</sub> that Storm learns; against measured T<sub>c</sub>, after round 3's calibration, the same kind of range holds 90% of the 298 matched materials with a median width of 3.5 K.

Each release writes its structure and scores to `progress/progress.json` (`ai_model`), and the app animates that spec. Details of every candidate are in `results/model_search.json` (round 1), `results/model_search_round2.json` (round 2), `results/storm_round3.json` (round 3), `results/storm_round4.json` (round 4) and `results/storm_round5.json` (round 5, with every material's range in `results/storm_round5_ranges.csv`).

## The graph neural network

A crystal-graph network learns T<sub>c</sub>, λ and ω<sub>log</sub> straight from the atoms and their neighbours: each atom is a node joined to its 12 nearest neighbours within 8 Å, and gated message passing turns the graph into the three targets (CGCNN-style, written in JAX). It is scored on the same five folds as Storm, grouped by chemical system, and the epoch is picked on 10% of each training fold's chemical systems, never on the test fold.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Storm 1.0 on the same folds |
|---|---|---|---|
| 1.0 | 3 message-passing layers of width 64, two seeds averaged, 200 epochs | 0.983 K; averaged with Storm 1.0, 0.915 K, better than Storm 1.0 in 5 of 5 folds | 0.969 K |
| 2.0 | + weight averaging (an exponential moving average of the weights) + an Allen–Dynes head (T<sub>c</sub> computed inside the network from its λ and ω<sub>log</sub>) + Storm 1.0's 54 crystal descriptors in the readout | 0.936 K, better than version 1.0 in 4 of 5 folds and than Storm 1.0 in 4 of 5; averaged with Storm 1.0, 0.898 K | 0.969 K |

In round 2 the AI agent proposed six changes and combinations, each trained with one seed for 150 epochs next to the round-1 design trained the same way (1.053 K). Weight averaging (1.028 K) and the crystal descriptors (1.035 K) each helped a little, a wider and deeper network more (1.004 K), and all three of weight averaging, the Allen–Dynes head and the descriptors together the most (0.977 K, better in 5 of 5 folds). One seed is not how version 1.0 was trained, so the selected design was retrained exactly like it, two seeds averaged and 200 epochs, before it could be released. Details are in `results/gnn_round1.json`, `results/gnn_round2.json` and `results/gnn_round2_final.json`.

## Hurricane, the model for unconventional superconductors

No first-principles theory gives T<sub>c</sub> for the cuprates, iron-based or heavy-fermion superconductors, so Hurricane learns from measurements: 2,123 compounds from 3DSC, which matches measured T<sub>c</sub> from the SuperCon database to Materials Project crystal structures. They are 874 cuprates, 517 iron- and nickel-based compounds, 422 heavy-fermion compounds and 310 other oxides, and 728 of them were reported as not superconducting, which shows the model where T<sub>c</sub> falls to zero. Cross-validation holds out whole parent compounds (the Materials Project chemical system), so every score is for compounds whose relatives the model never saw.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Baseline |
|---|---|---|---|
| Hurricane 1.0 | Composition statistics + measurable crystal structure + 15 AI-proposed physics features + element shares | 12.7 K, better than the baseline in 5 of 5 folds | 15.0 K (composition only) |
| Hurricane 2.0 | Hurricane 1.0 + 19 AI-proposed structure types, predicting in two parts: the probability that the compound superconducts times its T<sub>c</sub> if it does | 10.3 K, better than Hurricane 1.0 (retrained on the same folds: 12.7 K) in 5 of 5 folds | 15.0 K (composition only) |

The AI agent proposed nine designs in round 1. The physics features come from what is known about these families: charge balance gives the holes per copper p, which sets where a cuprate sits on its T<sub>c</sub> dome (Presland and Tallon), and the d-electron count of the metal layer; others count CuO<sub>2</sub> planes, heavy-metal charge reservoirs, FeAs- or FeSe-type layers and f electrons. The holes per copper and the d count turned out to be the model's two most important inputs. A harder test leaves out a whole family: trained without any cuprate, Hurricane never predicts more than 9.8 K for one, while cuprates reach 133 K, and its error is no better than always guessing the median. Materials reported after the 2018 SuperCon snapshot are graded and predicted but never used for training or for choosing a design (`data/hurricane_anchors.json`); Hg-1223, the 133 K ambient-pressure record, which is not in the training data, is predicted at 156 K. Details are in `results/hurricane_round1.json`.

**Round 2, Hurricane 2.0: structure types and a prediction in two parts.** The AI agent proposed seven designs on top of Hurricane 1.0, which was retrained on the same folds as the yardstick. Nineteen structure types read from the stoichiometry (123, 214, electron-doped, Bi-, Tl- and Hg-based and infinite-layer cuprates; 1111, 122, 111 and 11 iron-based compounds and nickel pnictides; 115 and 122 heavy-fermion compounds; nickelates, bismuthates, ruthenates and cobaltates) help a little on their own (12.4 K). Predicting in two parts helps much more: a classifier gives the probability that a compound superconducts at all, a regressor trained on the superconductors gives its T<sub>c</sub>, and the prediction is their product (10.4 K). Both together are best: 10.3 K, better than Hurricane 1.0 in all five folds, 12.3 K against 17.8 K on the superconducting entries and 24 K against 38 K for T<sub>c</sub> ≥ 30 K. Cuprates improve most (18 K against 24 K), while heavy-fermion compounds, whose T<sub>c</sub> is small, get slightly worse (1.3 K against 1.0 K); one model per family (13.0 K) and averaging five seeds of the structure-type design (12.6 K) did not help. A family left out is still out of reach: trained without any cuprate, Hurricane 2.0 never predicts more than 11 K for one. On the five scored later measurements it does worse than 1.0 (9.7 K against 5.3 K), mostly because the product shrinks the highest predictions: Hg-1223 is now predicted at 91 K. Five measurements are too few to choose a design, so they are shown and not used, but keeping high-T<sub>c</sub> predictions from shrinking is the next thing to try. Details are in `results/hurricane_round2.json`. From this round on, the training runs fix Python's string hashing and the features no longer depend on the order of a set, so every run gives the same numbers; Hurricane 1.0 retrained this way scores as it did in round 1, fold by fold.

## Radar, the router between Storm and Hurricane

Radar decides which model a material goes to. From its composition and crystal structure it gives the probability that the material belongs to one of Hurricane's unconventional families, and sends it to Hurricane when that probability is at least one half, to Storm otherwise. It learns from the SuperCon chemical classes of 5,751 entries in 3DSC: 874 cuprates, 517 iron- and nickel-based compounds, 422 heavy-fermion compounds and 310 other oxides for Hurricane, and 3,524 other conventional superconductors, 74 Chevrel phases and 30 carbon-based ones for Storm. These labels are SuperCon's chemical classes, a proxy for the pairing mechanism rather than a measurement of it. Cross-validation holds out whole parent compounds, as for Hurricane.

| Version | Design | Log loss (grouped CV) | Right model (balanced accuracy) | Baseline |
|---|---|---|---|---|
| Radar 1.0 | Composition statistics + measurable crystal structure + Hurricane's physics features + element shares, gradient-boosted classifier | 0.022, better than the baseline in 5 of 5 folds | 99.5% | 0.054 and 98.2% (composition only) |

The AI agent proposed eight designs in round 1, from Hurricane's physics features and the crystal structure to balanced classes, a five-seed average and calibrated probabilities, and ranked them by the log loss, which punishes confident mistakes. Radar 1.0's probabilities are well calibrated (calibration error 0.4 percentage points), and its most important inputs are the oxygen share, the FeAs- or FeSe-type layer and the f-electron count. The harder test leaves out a whole family. Trained without any cuprate, Radar still sends every cuprate to Hurricane; trained without heavy-fermion compounds, it sends only 1% of them there, and only 33% of the iron- and nickel-based compounds, because these families look like ordinary intermetallics in their chemistry. Radar can route a new material of a known kind, but a new family needs physics, not only a classifier. Graded materials are scored by a Radar that never saw them (those also in 3DSC out of fold): UTe<sub>2</sub>, CeRh<sub>2</sub>As<sub>2</sub>, the nickelates and Hg-1223 go to Hurricane and the 36 graded conventional superconductors and hydrides to Storm, as do the kagome metals CsV<sub>3</sub>Sb<sub>5</sub> and KV<sub>3</sub>Sb<sub>5</sub>, whose pairing is still debated. Details are in `results/radar_round1.json`.

## When is a model done?

An AI agent can always propose another round, so each model follows the same rules:

1. **Release only what wins.** A round is released only if it beats the version in use on average and in at least 4 of 5 held-out folds. Everything else stays experimental.
2. **Two empty rounds freeze a model.** After two rounds in a row with no release, the model stays as it is until new data or a new kind of input arrive.
3. **A gain smaller than the noise doesn't count.** An improvement smaller than the fold-to-fold scatter of the difference between two designs is not progress, even if it passes rule 1.
4. **No model beats its labels.** Storm learns computed T<sub>c</sub>, and Hurricane learns measured T<sub>c</sub>, which scatters between repeated measurements of the same compound. 3DSC averages repeated SuperCon reports into one value per formula, so Hurricane's floor still has to be measured from another source.
5. **Done means fit for its job.** Radar's job is routing; Storm's is ranking candidates for DFT checks, with honest uncertainty; Hurricane's is pointing to high-T<sub>c</sub> compounds in known families.

| Model | Status |
|---|---|
| Radar 1.0 | Fit for routing materials of known families: it picks the right model for 99.5% of parent compounds it never saw (a whole family it never saw is harder, see above). Frozen; re-run only to confirm that it reproduces, or when new data arrive. |
| Storm 5.0 | In use and still improving. Its ranges hold 90.0% overall but 84.1% for the tenth with the highest T<sub>c</sub>. The next step is screening: rank untested materials and check the top ones with DFT. |
| Hurricane 2.0 | In use and still improving. It pulls the highest T<sub>c</sub> values down (Hg-1223: 91 K predicted, 133 K measured) and misses a family it never saw by tens of kelvin (34 K for cuprates). Round 3 works on both. |

## What the project does

**Conventional superconductors (electron–phonon).** The models predict the electron–phonon coupling λ, the logarithmic phonon frequency ω<sub>log</sub> and the Allen–Dynes T<sub>c</sub>, recomputed with a single μ* = 0.10. They learn from about 8,250 Alexandria electron–phonon calculations (7,582 after cleaning), and cross-validation holds out whole chemical systems so that near-duplicates never straddle train and test. The 1,058 JARVIS calculations are kept out of training: the 626 dynamically stable ones form a locked test set that is evaluated once.

**Unconventional superconductors (measured T<sub>c</sub>): Hurricane.** Experimental T<sub>c</sub> for cuprates, nickelates, iron-based, heavy-fermion and other families comes from 3DSC, a SuperCon-derived dataset that includes crystal structures, and later discoveries are graded for reliability. No first-principles theory supplies labels here, so Hurricane learns empirical trends, and leave-one-family-out tests measure how far it transfers to families it hasn't seen.

**High-T<sub>c</sub> screening.** Radar sends each candidate structure from open databases to Storm or Hurricane, and each model publishes its own list (`ml/screen.py`): Storm ranks the metals in JARVIS-DFT that look conventional by their DFT T<sub>c</sub>, and Hurricane ranks the compounds that look like the unconventional families (narrow-gap and magnetic ones included) by the chance that each superconducts times its T<sub>c</sub> if it does. The top 50 of each list, one per chemical system, go into `progress/progress.json` (`screen`) with their structures; every scored material is in `results/screen_roundN_ranked.csv` and `results/screen_roundN_hurricane.csv`, and every one left out, with the reason, in `results/screen_roundN_excluded.csv`.

The lists hold only our own finds: a material is left out if its composition is in SuperCon or 3DSC, already has a computed T<sub>c</sub> in the Alexandria or JARVIS electron–phonon data, or is in `data/prior_claims.json`, the superconductors reported or predicted by others that we track, and from round 2 also if it is made of exactly the elements of a known superconductor (tell us of any we missed). Every candidate is a prediction until a calculation and an experiment check it, and each comes with what is needed to judge it: whether its structure has ever been made (ICSD) or is hypothetical, its 90% range, the chance that it superconducts with how that chance was calibrated, the most similar material its model learned from and whether it lies outside the training data, any check, and the date of the screening round that first listed it, which the history of `results/` records. A candidate is highlighted as worth an experiment only when its predicted T<sub>c</sub> is above the McMillan limit of about 40 K and it passes every test: more likely than not to superconduct, inside its model's training data and made before (a Storm candidate also needs the low end of its range, or a full DFT calculation, above 40 K); we then suggest it to experimental groups.

**Mechanism analysis.** Comparing the electron–phonon T<sub>c</sub> with the measured T<sub>c</sub> flags materials whose superconductivity phonons can't explain. Within each family, feature attributions test whether the models recover known structure–T<sub>c</sub> correlations.

Hydrides are excluded from the electron–phonon track.

## Data and licences

The training data are downloaded when the models train and are not stored in this repository. We filter and match them and compute features from them; the models, predictions and scores in `results/` and `progress/` are our own. None of the data providers endorses this project.

| Data | Used for | Licence | Please cite |
|---|---|---|---|
| [Alexandria](https://alexandria.icams.rub.de/) electron–phonon calculations | Storm's training data | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | T. F. T. Cerqueira, A. Sanna & M. A. L. Marques, Adv. Mater. 36, 2307085 (2024), [doi:10.1002/adma.202307085](https://doi.org/10.1002/adma.202307085); T. Cavignac et al., J. Phys. Mater. 9, 025014 (2026), [doi:10.1088/2515-7639/ae6620](https://doi.org/10.1088/2515-7639/ae6620) |
| [JARVIS-DFT](https://jarvis.nist.gov/) superconductors | Storm's locked test set | [NIST open licence](https://www.nist.gov/open/license) | K. Choudhary & K. Garrity, npj Comput. Mater. 8, 244 (2022), [doi:10.1038/s41524-022-00933-1](https://doi.org/10.1038/s41524-022-00933-1); K. Choudhary et al., npj Comput. Mater. 6, 173 (2020), [doi:10.1038/s41524-020-00440-1](https://doi.org/10.1038/s41524-020-00440-1) |
| [3DSC](https://github.com/aimat-lab/3DSC): measured T<sub>c</sub> from the SuperCon database (NIMS) matched to [Materials Project](https://materialsproject.org/) structures | Hurricane; Storm 3.0's calibration | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | T. Sommer et al., Sci. Data 10, 816 (2023), [doi:10.1038/s41597-023-02721-y](https://doi.org/10.1038/s41597-023-02721-y); A. Jain et al., APL Mater. 1, 011002 (2013), [doi:10.1063/1.4812323](https://doi.org/10.1063/1.4812323) |
| [JARVIS-DFT](https://jarvis.nist.gov/) 3D materials (OptB88vdW) | The pool that the screening rounds score; the candidates' structures | [NIST open licence](https://www.nist.gov/open/license) | K. Choudhary et al., npj Comput. Mater. 6, 173 (2020), [doi:10.1038/s41524-020-00440-1](https://doi.org/10.1038/s41524-020-00440-1) |
| SuperCon formulas: JARVIS's copy (`supercon_chem`) and the extract of K. Hamidieh on the [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/464/superconductivty+data) | Leaving known superconductors out of the candidate list, never training | JARVIS: [NIST open licence](https://www.nist.gov/open/license); UCI: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | V. Stanev et al., npj Comput. Mater. 4, 29 (2018), [doi:10.1038/s41524-018-0085-8](https://doi.org/10.1038/s41524-018-0085-8); K. Hamidieh, Comput. Mater. Sci. 154, 346 (2018), [doi:10.1016/j.commatsci.2018.07.052](https://doi.org/10.1016/j.commatsci.2018.07.052) |
| Graded measurements in `data/experiments.json` and `data/hurricane_anchors.json` | Checks only, never training | Facts from the papers cited in each file | The papers listed in each file |
| Others' finds and predictions in `data/prior_claims.json` | Leaving them out of the candidate list | Facts from the papers cited in the file | The papers listed in the file |
| [arXiv API](https://info.arxiv.org/help/api/tou.html) | The paper feed | Metadata under CC0 1.0 | |
| [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/) and journal feeds | Journal papers in the feed | Bibliographic metadata; abstracts remain the publishers' or authors' copyright, so the feed keeps only their first sentence and links to the paper | |
| News feeds: Nature News, ScienceDaily, Phys.org, Physics World, APS Physics, Quanta Magazine | The news list | Headlines and a short summary from each public feed, always linked to the story | |

**Licence of this repository.** The code is under the [MIT licence](LICENSE). Our own results, that is, the models' predictions, scores and specs in `results/` and `progress/progress.json`, the curated text in `progress/content.json` and the graded compilations in `data/`, are under [CC BY 4.0](LICENSE-results.md); please cite the repository. The training data and the paper feed keep their providers' terms in the table above, and `progress/papers.json` is not covered by our licences.

The desktop app is built with [Tauri](https://tauri.app/) and other open-source Rust crates under MIT, Apache-2.0, MPL-2.0 and similar licences. `app/scripts/third-party-notices.mjs` lists them with their licence texts and copyright notices; the list ships inside the installers and with every release as `THIRD-PARTY-NOTICES.txt`. The app's own interface, `app/dist/index.html`, contains no third-party code.

## Published baselines

| Model | Target | MAE | Inputs | Source |
|---|---|---|---|---|
| ALIGNN 2.0 | T<sub>c</sub> | 0.864 K | Structure | [arXiv 2609.19487](https://arxiv.org/abs/2609.19487) |
| ALIGNN 2.0 | λ | 0.068 | Structure | [arXiv 2609.19487](https://arxiv.org/abs/2609.19487) |
| ALIGNN 2.0 | ω<sub>log</sub> | 20.1 K | Structure | [arXiv 2609.19487](https://arxiv.org/abs/2609.19487) |
| BEE-NET | T<sub>c</sub> | 1.20 K | Structure | [arXiv 2503.20005](https://arxiv.org/abs/2503.20005) |
| BEE-NET | T<sub>c</sub> | 0.87 K | Structure + DFT phonon DOS | [arXiv 2503.20005](https://arxiv.org/abs/2503.20005) |

Each paper uses its own data split, so these numbers are a reference point rather than a head-to-head comparison.

## Repository layout

- `progress/progress.json`: stages, activity log and results. The desktop app and the progress badge read this file.
- `progress/content.json`: curated recent advances with their papers, which the app adds to its own list without an update.
- `ml/pipeline.py`: downloads the data, trains the models and updates the progress file; `ml/storm3.py`, `ml/storm4.py` and `ml/storm5.py` are Storm's rounds 3 to 5, `ml/hurricane.py` and `ml/hurricane2.py` are Hurricane's rounds 1 and 2, `ml/radar.py` is Radar, and `ml/gnn.py` and `ml/gnn2.py` are the graph neural network's rounds 1 and 2. `.github/workflows/train.yml` runs them on GitHub Actions, with Python's string hashing fixed so that every run is reproducible.
- `data/`: graded measured T<sub>c</sub> used only for checks (`experiments.json` for Storm, `hurricane_anchors.json` for Hurricane).
- `feed/papers.py`: collects new superconductivity papers and news, and the AI × superconductors list, into `progress/papers.json`; `.github/workflows/papers.yml` runs it every three hours.
- `results/`: metrics and predictions from the latest training run.
- `app/`: the desktop app (Tauri). `app/dist/index.html` is the whole interface; `manifest.webmanifest` and `sw.js` make the same page installable on phones. `app/scripts/third-party-notices.mjs` writes the licence notices for the installers.
- `.github/workflows/app.yml`: builds the Windows and macOS installers and publishes them as a release.
- `.github/workflows/pages.yml`: publishes the phone version to GitHub Pages.

## Build the app yourself

You need Node.js 20 or later and Rust.

```bash
cd app
npm install
npm run icon
npm run notices
cp ../progress/progress.json dist/
npx tauri build
```
