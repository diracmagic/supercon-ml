# supercon-ml

Machine learning for superconductors. The project predicts the critical temperature T<sub>c</sub> of conventional (electron–phonon) and unconventional superconductors from crystal structure with open materials foundation models, screens open databases for high-T<sub>c</sub> candidates, and then asks what the models have learned about pairing mechanisms.

[![Progress](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdiracmagic%2Fsupercon-ml%2Fmain%2Fprogress%2Fprogress.json&query=%24.badge&label=progress&color=2a78d6)](progress/progress.json)
[![Desktop app](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml/badge.svg)](https://github.com/diracmagic/supercon-ml/actions/workflows/app.yml)

## Follow the progress

The app shows every stage, the training results and the GitHub Actions runs as they happen. It also has four other views:

- **Physics demos**, starting with *Hello Super*, a 90-second animated tour of the project, and *Our AI model: Storm*, an animation of the model our AI agent designed. Demos of zero resistance, the Meissner effect, Cooper pairs and the Allen–Dynes formula follow.
- **Theory & materials**: the main theories of superconductivity and the materials behind today's headlines, each with an animation, the original papers and the latest results, plus the Nobel Prizes for superconductivity.
- **News & papers**: superconductivity news and new papers from arXiv, Nature, Science, PRL and PRX, refreshed every three hours, plus a curated list of recent advances in experiment, theory and AI for superconductivity.

| Platform | Get it |
|---|---|
| Windows 10/11 | [SuperconProgress-windows-x64-setup.exe](https://github.com/diracmagic/supercon-ml/releases/latest/download/SuperconProgress-windows-x64-setup.exe) |
| macOS, Apple Silicon and Intel | [SuperconProgress-macos-universal.dmg](https://github.com/diracmagic/supercon-ml/releases/latest/download/SuperconProgress-macos-universal.dmg) |
| iPhone, iPad and Android | Open [diracmagic.github.io/supercon-ml](https://diracmagic.github.io/supercon-ml/) and add it to your home screen (iPhone and iPad: **Share → Add to Home Screen**; Android: **⋮ → Install app**). |

The installers aren't code-signed yet. On Windows, click **More info → Run anyway** if SmartScreen appears. On macOS, if it says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.

## Storm, the AI-designed model

An AI agent (Claude) designs the project's T<sub>c</sub> models. In each search round it proposes new feature sets, physics features and settings. Every candidate is trained and scored with the same composition-grouped five-fold cross-validation, and a design is released as a new version of **Storm** only if it beats the current best on average and in at least 4 of the 5 folds. The locked JARVIS test set is never used to pick a design.

| Version | Design | T<sub>c</sub> MAE (grouped CV) | Baseline |
|---|---|---|---|
| Storm 1.0 | Hand-made features + 11 AI-proposed physics features, deeper boosted trees | 0.97 K, better in 5 of 5 folds | 1.05 K |

Each release writes its structure and scores to `progress/progress.json` (`ai_model`), and the app animates that spec. Details of every candidate are in `results/model_search.json`.

## What the project does

**Conventional superconductors (electron–phonon).** The models predict the electron–phonon coupling λ, the logarithmic phonon frequency ω<sub>log</sub> and the Allen–Dynes T<sub>c</sub>, recomputed with a single μ* = 0.10. Training data are about 8,250 Alexandria electron–phonon calculations and 1,058 from JARVIS, split by composition so that near-duplicates never straddle train and test. The 626 dynamically stable JARVIS materials form a locked test set that is evaluated once.

**Unconventional superconductors (measured T<sub>c</sub>).** Experimental T<sub>c</sub> for cuprates, iron-based, heavy-fermion and other families comes from SuperCon-derived datasets that include crystal structures. No first-principles theory supplies labels here, so the model learns empirical trends, and leave-one-family-out tests measure how far it transfers to families it hasn't seen.

**High-T<sub>c</sub> screening.** Both models score candidate structures from open databases. Candidates with high predicted T<sub>c</sub> and low uncertainty go on a shortlist for DFT or experimental follow-up.

**Mechanism analysis.** Comparing the electron–phonon T<sub>c</sub> with the measured T<sub>c</sub> flags materials whose superconductivity phonons can't explain. Within each family, feature attributions test whether the models recover known structure–T<sub>c</sub> correlations.

Hydrides are excluded from the electron–phonon track.

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
- `ml/pipeline.py`: downloads the data, trains the models and updates the progress file. `.github/workflows/train.yml` runs it on GitHub Actions.
- `feed/papers.py`: collects new superconductivity papers and news into `progress/papers.json`; `.github/workflows/papers.yml` runs it every three hours.
- `results/`: metrics and predictions from the latest training run.
- `app/`: the desktop app (Tauri). `app/dist/index.html` is the whole interface; `manifest.webmanifest` and `sw.js` make the same page installable on phones.
- `.github/workflows/app.yml`: builds the Windows and macOS installers and publishes them as a release.
- `.github/workflows/pages.yml`: publishes the phone version to GitHub Pages.

## Build the app yourself

You need Node.js 20 or later and Rust.

```bash
cd app
npm install
npm run icon
cp ../progress/progress.json dist/
npx tauri build
```
