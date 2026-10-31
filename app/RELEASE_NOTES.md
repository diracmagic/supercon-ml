Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.5 adds:

- **Hurricane 2.0**: our AI agent's second round for unconventional superconductors predicts in two parts, whether a compound superconducts and its T<sub>c</sub> if it does, with 19 structure types read from the formula. It is off by 10.3 K for compounds whose parent it never saw, against 12.7 K for Hurricane 1.0 on the same folds. The model details compare it with Hurricane 1.0 and list every design of the round, and the Hurricane demo explains the two-part prediction.
- **Storm 5.0, a 90% range for every prediction**: round 5 tells how sure Storm is. For materials it never saw, the range held the computed T<sub>c</sub> 90% of the time, and half of the ranges are narrower than 1.8 K. A new block in the model details shows the designs our AI agent proposed, the highest predictions with their ranges and how the ranges hold up against measured T<sub>c</sub>.
- **Fixes**: clearer names for the inputs a model relies on (for example "spread of electronegativity"), the structure types by name, tables that fit phone screens, and the licences card now says that the code is under the MIT licence and our results under CC BY 4.0.

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
