# supercon-ml

Finding high-T<sub>c</sub> superconductors with AI-designed models. The project predicts the critical temperature T<sub>c</sub> of conventional (electron–phonon) and unconventional superconductors from crystal structure, screens open databases for high-T<sub>c</sub> candidates, and then asks what the models have learned about pairing mechanisms. An AI agent (Claude) designs the models: **Storm** for conventional superconductors, **Hurricane** for unconventional ones and **Radar** to decide which of the two a material goes to.

[![Progress](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiracmagic%2Fsupercon-ml%2Fmain%2Fprogress%2Fprogress.json&query=%24.badge&label=progress&color=2a78d6)](progress/progress.json)
[![Desktop app](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml/badge.svg)](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml)

## Authors

| Name | Contact |
|---|---|
| Yantao Li | [liyant@iu.edu](mailto:liyant@iu.edu) (project contact) |

Questions, ideas and collaboration are welcome by email; bugs and feature requests can also go to [GitHub Issues](https://github.com/diracmagic/supercon-ml/issues).

## Follow the progress

The app shows every stage, the training results, our three models and the GitHub Actions runs as they happen, with the details of each model's latest round. It also has five other views:

- **AI × superconductors**: new papers and news on machine learning, AI agents and autonomous labs for superconductors, newest first and checked again every ten minutes while the view is open, plus our AI-designed models and a curated list of AI advances.
- **Physics demos**, starting with *Hello Super*, a 90-second animated tour of the project, and *Our AI model: Storm* and *Our AI model: Hurricane*, animations of the two models our AI agent designed, drawn from their own results. Demos of zero resistance, the Meissner effect, Cooper pairs and the Allen–Dynes formula follow.
- **Theory & materials**: the main theories of superconductivity, the classic ideas for high-T<sub>c</sub> superconductivity in the cuprates and the materials behind today's headlines, each with an animation, the original papers and the latest results, plus the Nobel Prizes for superconductivity.
- **News & papers**: superconductivity news, each story with a drawing of its topic, and new papers from arXiv, Nature, Science, Physical Review and the Nature-family journals, refreshed every three hours, plus a curated list of recent advances in experiment, theory and AI for superconductivity.
- **Authors**: who is behind the project, how to reach us, and where the data come from.

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
| **Storm** | Conventional superconductors, paired by phonons | About 7,600 materials whose electron–phonon coupling λ and ω<sub>log</sub> have been computed (Alexandria), calibrated to the measured T<sub>c</sub> of 298 of them (3DSC) | Storm 3.0 in use |
| **Hurricane** | Unconventional superconductors: cuprates, nickelates, iron-based, heavy-fermion and more | 2,123 measured T<sub>c</sub> values (3DSC: SuperCon with Materials Project structures); later discoveries graded as replicated, single report, preprint, retracted or refuted | Hurricane 1.0 in use |
| **Radar** | Deciding which model to ask | Composition and structure, to estimate whether phonons can account for a material's pairing | Planned |

Where Storm and Hurricane disagree about a material is itself a clue to its pairing mechanism.

## Storm, the model for conventional superconductors

An AI agent (Claude) designs the project's T<sub>c</sub> models. In each of Storm's search rounds it proposes new feature sets, physics features and settings. Every candidate is trained and scored with the same composition-grouped five-fold cross-validation, and a design is released as a new version of **Storm** only if it beats the current best on average and in at least 4 of the 5 folds. The locked JARVIS test set is never used to pick a design.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Baseline |
|---|---|---|---|
| Storm 1.0 | Hand-made features + 11 AI-proposed physics features, deeper boosted trees | 0.969 K, better than the baseline in 5 of 5 folds | 1.045 K |
| Storm 2.0 (experimental) | Storm 1.0 + an Allen–Dynes stage (predicted λ, ω<sub>log</sub> and their Allen–Dynes T<sub>c</sub> as extra inputs) | 0.966 K, better than Storm 1.0 in only 2 of 5 folds, so not released | 1.045 K |

From round 2 on, every candidate is also compared with graded measured T<sub>c</sub> (`data/experiments.json`): only replicated, ambient-pressure, phonon-mediated superconductors are scored, and single reports, preprints and retracted claims are listed with their status but never scored. A new version may not be more than 0.5 K worse than the current one on these measurements. On the 18 scored materials, Storm 1.0 is off by 7.6 K on average and the best round-2 design by 6.9 K, while the DFT labels they learn from are themselves off by 7.0 K (MgB<sub>2</sub>, for example, is 8 K in the DFT data and 39 K in experiment). Most of the remaining error therefore comes from the labels, not the model.

**Round 3, Storm 3.0: calibrated to measured T<sub>c</sub>.** 3DSC lists 298 conventional materials (168 of them superconducting) that are also in Storm's training data. The AI agent proposed five maps from Storm's predictions to the measured value, from a linear map and an Allen–Dynes map with a rescaled λ and an effective μ* to a small gradient-boosting correction. Their inputs are Storm 1.0's predictions for materials it never saw, never the DFT labels, and they were scored with the same grouped cross-validation. The gradient-boosting correction is off by 1.61 K on average, against 2.24 K for uncalibrated Storm 1.0 and 2.48 K for the DFT labels themselves, better in 5 of 5 folds, and was released as Storm 3.0. The largest shortfalls, such as AlV<sub>3</sub>, V<sub>3</sub>Ga and the borocarbides, are leads for the mechanism study.

Each release writes its structure and scores to `progress/progress.json` (`ai_model`), and the app animates that spec. Details of every candidate are in `results/model_search.json` (round 1), `results/model_search_round2.json` (round 2) and `results/storm_round3.json` (round 3).

## Hurricane, the model for unconventional superconductors

No first-principles theory gives T<sub>c</sub> for the cuprates, iron-based or heavy-fermion superconductors, so Hurricane learns from measurements: 2,123 compounds from 3DSC, which matches measured T<sub>c</sub> from the SuperCon database to Materials Project crystal structures. They are 874 cuprates, 517 iron- and nickel-based compounds, 422 heavy-fermion compounds and 310 other oxides, and 728 of them were reported as not superconducting, which shows the model where T<sub>c</sub> falls to zero. Cross-validation holds out whole parent compounds (the Materials Project chemical system), so every score is for compounds whose relatives the model never saw.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Baseline |
|---|---|---|---|
| Hurricane 1.0 | Composition statistics + measurable crystal structure + 15 AI-proposed physics features + element shares | 12.7 K, better than the baseline in 5 of 5 folds | 15.0 K (composition only) |

The AI agent proposed nine designs in round 1. The physics features come from what is known about these families: charge balance gives the holes per copper p, which sets where a cuprate sits on its T<sub>c</sub> dome (Presland and Tallon), and the d-electron count of the metal layer; others count CuO<sub>2</sub> planes, heavy-metal charge reservoirs, FeAs- or FeSe-type layers and f electrons. The holes per copper and the d count turned out to be the model's two most important inputs. A harder test leaves out a whole family: trained without any cuprate, Hurricane never predicts more than 9.8 K for one, while cuprates reach 133 K, and its error is no better than always guessing the median. Materials reported after the 2018 SuperCon snapshot are graded and predicted but never used for training or for choosing a design (`data/hurricane_anchors.json`); Hg-1223, the 133 K ambient-pressure record, which is not in the training data, is predicted at 156 K. Details are in `results/hurricane_round1.json`.

## What the project does

**Conventional superconductors (electron–phonon).** The models predict the electron–phonon coupling λ, the logarithmic phonon frequency ω<sub>log</sub> and the Allen–Dynes T<sub>c</sub>, recomputed with a single μ* = 0.10. Training data are about 8,250 Alexandria electron–phonon calculations and 1,058 from JARVIS, split by composition so that near-duplicates never straddle train and test. The 626 dynamically stable JARVIS materials form a locked test set that is evaluated once.

**Unconventional superconductors (measured T<sub>c</sub>): Hurricane.** Experimental T<sub>c</sub> for cuprates, nickelates, iron-based, heavy-fermion and other families comes from 3DSC, a SuperCon-derived dataset that includes crystal structures, and later discoveries are graded for reliability. No first-principles theory supplies labels here, so Hurricane learns empirical trends, and leave-one-family-out tests measure how far it transfers to families it hasn't seen.

**High-T<sub>c</sub> screening.** Radar sends each candidate structure from open databases to Storm or Hurricane. Candidates with high predicted T<sub>c</sub> and low uncertainty go on a shortlist for DFT or experimental follow-up.

**Mechanism analysis.** Comparing the electron–phonon T<sub>c</sub> with the measured T<sub>c</sub> flags materials whose superconductivity phonons can't explain. Within each family, feature attributions test whether the models recover known structure–T<sub>c</sub> correlations.

Hydrides are excluded from the electron–phonon track.

## Data and licences

The training data are downloaded when the models train and are not stored in this repository. We filter and match them and compute features from them; the models, predictions and scores in `results/` and `progress/` are our own. None of the data providers endorses this project.

| Data | Used for | Licence | Please cite |
|---|---|---|---|
| [Alexandria](https://alexandria.icams.rub.de/) electron–phonon calculations | Storm's training data | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | T. F. T. Cerqueira, A. Sanna & M. A. L. Marques, Adv. Mater. 36, 2307085 (2024), [doi:10.1002/adma.202307085](https://doi.org/10.1002/adma.202307085); T. Cavignac et al., J. Phys. Mater. 9, 025014 (2026), [doi:10.1088/2515-7639/ae6620](https://doi.org/10.1088/2515-7639/ae6620) |
| [JARVIS-DFT](https://jarvis.nist.gov/) superconductors | Storm's locked test set | [NIST open licence](https://www.nist.gov/open/license) | K. Choudhary & K. Garrity, npj Comput. Mater. 8, 244 (2022), [doi:10.1038/s41524-022-00933-1](https://doi.org/10.1038/s41524-022-00933-1); K. Choudhary et al., npj Comput. Mater. 6, 173 (2020), [doi:10.1038/s41524-020-00440-1](https://doi.org/10.1038/s41524-020-00440-1) |
| [3DSC](https://github.com/aimat-lab/3DSC): measured T<sub>c</sub> from the SuperCon database (NIMS) matched to [Materials Project](https://materialsproject.org/) structures | Hurricane; Storm 3.0's calibration | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | T. Sommer et al., Sci. Data 10, 816 (2023), [doi:10.1038/s41597-023-02721-y](https://doi.org/10.1038/s41597-023-02721-y); A. Jain et al., APL Mater. 1, 011002 (2013), [doi:10.1063/1.4812323](https://doi.org/10.1063/1.4812323) |
| Graded measurements in `data/experiments.json` and `data/hurricane_anchors.json` | Checks only, never training | Facts from the papers cited in each file | The papers listed in each file |
| [arXiv API](https://info.arxiv.org/help/api/tou.html) | The paper feed | Metadata under CC0 1.0 | |
| [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/) and journal feeds | Journal papers in the feed | Bibliographic metadata; abstracts remain the publishers' or authors' copyright, so the feed keeps only their first sentence and links to the paper | |
| News feeds: Nature News, ScienceDaily, Phys.org, Physics World, APS Physics, Quanta Magazine | The news list | Headlines and a short summary from each public feed, always linked to the story | |

The desktop app is built with [Tauri](https://tauri.app/) and other open-source Rust crates under MIT, Apache-2.0 and similar licences. `app/scripts/third-party-notices.mjs` lists them with their licence texts and copyright notices; the list ships inside the installers and with every release as `THIRD-PARTY-NOTICES.txt`. The app's own interface, `app/dist/index.html`, contains no third-party code.

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
- `ml/pipeline.py`: downloads the data, trains the models and updates the progress file; `ml/storm3.py` is Storm's calibration round and `ml/hurricane.py` is Hurricane. `.github/workflows/train.yml` runs them on GitHub Actions.
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
