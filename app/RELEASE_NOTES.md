Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.4 adds:

- **Radar, our third AI-designed model**: a new demo, *Our AI model: Radar*, animates how it decides whether a material goes to Storm or Hurricane, from its data and the eight designs our AI agent proposed to where new materials go, how often it picks the right model and what happens when a whole family is left out of training. Radar also appears with its own results in Our models, the AI × superconductors view and the model details.
- **Storm 4.0 and the graph network**: Storm 1.0's boosted trees and our crystal-graph network together, off by 0.90 K against computed T<sub>c</sub> and 1.56 K against measured T<sub>c</sub>. The app names Storm 4.0 wherever it shows the Storm in use, and the model details show the graph network's AI-designed round 2 and the final check that released version 2.0.
- **Fixes**: the model cards follow each model's own results, so an older status line can no longer name a version that is not in use; *Best Tc error so far* counts released models only; percentages near 100% keep one decimal; the Radar demo fits phone screens.

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
