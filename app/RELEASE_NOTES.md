Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.0 adds:

- **Storm, our AI-designed model**: an AI agent (Claude) designs the models, and Storm 1.0 is its first release, with an average T<sub>c</sub> error of 0.97 K against 1.05 K for the hand-made baseline, better in all five test folds. The new *Our AI model: Storm* demo animates the design round, inputs, learner, predictions, fold-by-fold check and what changed. It is drawn from the model's own spec, so every new version explains itself.
- **News & papers**: superconductivity news, new arXiv papers and new papers in Nature, Science, PRL and PRX, refreshed every three hours. It also has a curated list of recent advances in experiment, theory and AI for superconductivity.
- **Theory & materials**: an animation and the latest results on every theory and material card, plus the Nobel Prizes for superconductivity, each illustrated and linked to NobelPrize.org.

Version 0.2.0 added the *Hello Super* tour, the physics demos, the Theory & materials view and the phone and iPad version.

### Download

- **Windows 10/11:** `SuperconProgress-windows-x64-setup.exe` (or the `.msi`)
- **macOS, Apple Silicon and Intel:** `SuperconProgress-macos-universal.dmg`

### First launch

The installers aren't code-signed yet, so the operating system asks you to confirm once.

- **Windows:** if SmartScreen says "Windows protected your PC", click **More info**, then **Run anyway**.
- **macOS:** open the `.dmg` and drag **Supercon Progress** into Applications. If macOS says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.
