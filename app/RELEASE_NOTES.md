Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.6 adds:

- **Candidates**: a new view, right after Progress, for the candidate superconductors found by our AI models: Radar keeps the metals that look conventional and Storm predicts their T<sub>c</sub>, each with a 90% range, published before any calculation or experiment checks them. Only our own finds are listed: anything already in SuperCon or 3DSC, with a computed T<sub>c</sub>, or reported or predicted by others is left out. Every candidate's crystal structure turns in 3D; drag it to look from any side. Every check will be added, hits and misses alike.
- **Superconductors found with AI**: the AI view lists every new superconductor that an AI or machine-learning model pointed to and an experiment then confirmed, each with its paper, and the AI predictions still waiting for an experiment. Its live list now tags new AI predictions and new AI-guided experiments.
- **Predict T<sub>c</sub>, step by step**: the Predict T<sub>c</sub> demo shows how Storm and Hurricane predict T<sub>c</sub> for real materials, with the numbers they computed, from Nb₃Sn and MgB₂ to Hg-1223 and UTe₂.
- **The models in use**: the Storm demo shows only the Storm in use and the five rounds that built it, and the Baselines demo now has the simple model that each of Storm, Hurricane and Radar must beat.
- **Hurricane 2.0 and Storm 5.0**: Hurricane predicts in two parts, whether a compound superconducts and its T<sub>c</sub> if it does, and is off by 10.3 K for compounds whose parent it never saw (Hurricane 1.0: 12.7 K). Storm gives every prediction a 90% range, which held the computed T<sub>c</sub> 90% of the time for materials it never saw.
- **Fixes**: filter buttons in News & papers no longer lose their selection after you filter the materials in Theory & materials, the Predict T<sub>c</sub> switch shows which view is on, every material in the walk-throughs can be reached with reduced motion, and model inputs have clearer names. Tables fit phone screens, and the licences card says that the code is under the MIT licence and our results under CC BY 4.0.

Version 0.3.5 came out on the web only; everything it added is listed above.

Version 0.3.4 added Radar and its demo, Storm 4.0 with the graph network, and model cards that follow each model's own results.

Version 0.3.3 fixed the Storm version shown everywhere, Hurricane in Our models and the licence notices.

Version 0.3.2 added the AI × superconductors view, the Hurricane demo and tour step, model details, live content, the data and licences card and more journals.

Version 0.3.1 added the Authors view, our three models, the classic high-T<sub>c</sub> mechanisms, a drawing for every news story and the new-version prompt.

Version 0.3.0 added Storm, the News & papers view, an animation on every Theory & materials card and the Nobel Prizes for superconductivity.

Version 0.2.0 added the *Hello Super* tour, the physics demos, the Theory & materials view and the phone and iPad version.

### Download

- **Windows 10/11:** `SuperconProgress-windows-x64-setup.exe` (or the `.msi`)
- **macOS, Apple Silicon and Intel:** `SuperconProgress-macos-universal.dmg`

### First launch

The installers aren't code-signed yet, so the operating system asks you to confirm once.

- **Windows:** if SmartScreen says "Windows protected your PC", click **More info**, then **Run anyway**.
- **macOS:** open the `.dmg` and drag **Supercon Progress** into Applications. If macOS says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.
