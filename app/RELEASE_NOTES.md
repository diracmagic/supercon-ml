Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.1 adds:

- **Authors**: a new view next to Progress with the people behind the project and how to reach them. The project contact is Yantao Li (liyant@iu.edu). Each author has an animated pencil-sketch portrait.
- **Our models**: Storm for conventional superconductors, Hurricane for unconventional ones (cuprates, nickelates, iron-based, heavy-fermion and more) and Radar, which decides which model a material goes to. Hurricane will learn from measured T<sub>c</sub>, with every measurement graded from replicated to retracted.
- **Classic high-T<sub>c</sub> mechanisms**: eight ideas for how the cuprates superconduct, from the Mott insulator, RVB and the t–J model to stripes, phase fluctuations, bipolarons and the strange metal. Each one is animated on the copper-oxide phase diagram, with the original papers and what is still open.
- **A drawing for every news story**, matched to its topic.
- **New-version prompt**: the desktop app tells you when a new version is out and opens the right installer; the phone version refreshes itself.
- **Installer icon**: the Windows installer now shows the app's icon instead of a generic one.
- **Storm 2.0, experimental**: in its second design round the AI agent tried eight designs. The best one, which adds an Allen–Dynes stage, is not better than Storm 1.0 in enough test folds, so Storm 1.0 stays in use. A new check against replicated T<sub>c</sub> measurements shows that most of Storm's remaining error comes from its DFT training labels, which sets the goal for round 3.
- **Corrections**: references and wording checked against the papers, and each card's *Latest* list now holds results on that card's topic.

Version 0.3.0 added Storm, the News & papers view, an animation on every Theory & materials card and the Nobel Prizes for superconductivity.

Version 0.2.0 added the *Hello Super* tour, the physics demos, the Theory & materials view and the phone and iPad version.

### Download

- **Windows 10/11:** `SuperconProgress-windows-x64-setup.exe` (or the `.msi`)
- **macOS, Apple Silicon and Intel:** `SuperconProgress-macos-universal.dmg`

### First launch

The installers aren't code-signed yet, so the operating system asks you to confirm once.

- **Windows:** if SmartScreen says "Windows protected your PC", click **More info**, then **Run anyway**.
- **macOS:** open the `.dmg` and drag **Supercon Progress** into Applications. If macOS says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.
