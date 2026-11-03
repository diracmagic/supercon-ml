Desktop app that shows the live progress of [supercon-ml](https://github.com/diracmagic/supercon-ml): every stage, training results and GitHub Actions runs, refreshed every few minutes.

Version 0.3.21 adds:

- **Testable predictions:** Candidates gains a second, lower tier below the 40 K benchmark. A candidate is marked a testable prediction when its predicted Tc is at least 2 K (within reach of a standard 1.8 K cryostat), its superconductivity model score is at least 0.5, it lies near the training data, it has an ICSD-linked structure, no experimental check is recorded yet, and no matching DFT check reports no superconductivity or a Tc below 2 K (such a check withdraws the recommendation; it is not an experimental result). A candidate predicted above 40 K that misses the full 40 K criteria is described as such, not as below 40 K. The 40 K tier, the lists, the models and the results are unchanged.

Version 0.3.20 adds:

- **Fewer GitHub requests:** GitHub runs and commits now refresh every 15 minutes (every 5 while a run is active) instead of every 3, and not while the app is in the background. GitHub allows 60 such requests per hour for each network address, and two open copies of the app used them all. Progress data still refreshes every few minutes, and the refresh button always fetches everything.

Version 0.3.19 adds:

- **Animated unsupervised results:** replaces the highlight-only view with a step-by-step animation of the audited Storm 7 and Hurricane 8 results. The underlying audited values remain fixed during animation. No new model was adopted.

Version 0.3.18 adds:

- **Unsupervised results:** Physics demos now presents the audited Storm 7 and Hurricane 8 experiment results. Neither experiment established a substantive improvement. No new model was adopted, and Hurricane 4.0 remains in use.

Version 0.3.17 adds:

- **Compact News & papers animations:** small animations appear directly on article cards, without a separate expanded drawing view. Original-source links remain available.
- **Model methods and references:** model explanations cite the research they draw on and distinguish our inputs, training and validation from the cited methods.

Version 0.3.16 adds:

- **Desktop sign-in returns automatically:** after GitHub or email sign-in, the app hands the verified team session back to its installed home screen. Notes, Messages and Team remain available there alongside native updates. Credentials stay in process memory; closing the desktop process or signing out ends the local session. Cancellation and expired or revoked membership cannot restore private access.
- **Consistent mobile navigation:** Physics demos, Theory & materials and News & papers now use the same full titles on phones, in a compact two-row navigation bar.
- **Article-specific illustrations:** every displayed news item, paper and selected advance gets a diagram driven by its available material, method and research question, with an original-source link and an explanation of the evidence used. These are labelled schematics, not reconstructed crystal coordinates or measured traces. Existing concept animations remain available in the drawing details.
- **Branded Windows uninstaller:** new installations use the Supercon icon for the uninstaller as well as the installer. An upgrade may still briefly open the previous version's old uninstaller.

Version 0.3.15 fixes:

- **Desktop team sign-in:** the installed APP opens the fixed hosted sign-in form in the same window before starting GitHub or email authentication. GitHub verification is now stored at the same address that receives the callback, preventing the missing pending-request error. Credentials never move between the bundled and hosted origins; existing PKCE, membership and native-updater checks remain in force.

Version 0.3.14 adds:

- **Team presence:** approved members can open Team to see names with authenticated activity in the last 2½ minutes. Existing checks refresh this private list; leaving or closing the APP may take a short time to disappear. Sign-out and revocation clear access.
- **Clearer email sign-in:** after setting a password in the APP, the same account dialog returns to sign-in with the invited email address. New password emails also return from Firebase’s hosted page to the APP’s email form. No separate username is needed; returning to the form does not sign anyone in automatically.

Version 0.3.13 adds:

- **Responsive update retries:** Retry download immediately starts the verified download inside the APP, even when a background release check is active. Checking, download failures and installers still being prepared have visible status messages; installation still requires confirmation.
- **Return after web sign-in:** if sign-in leaves a desktop window on the hosted web APP, a clear button returns to the installed home screen before updating. Remote pages do not gain native updater permissions.
- **GitHub sign-in retry guidance:** temporary GitHub rate limits have bounded waiting guidance, and the sign-in service observes a cooldown before requesting another exchange. Account permissions remain unchanged.
- **Distinct News illustrations:** restores animated material and method motifs instead of repeated placeholders. Literature extraction, graph models, candidate searches, spectroscopy, pressure, layered materials and model uncertainty use separate labelled schematics; no measured data or unverified crystal structure is invented.

Version 0.3.12 adds:

- **Notes by update date:** newest substantive updates appear first, grouped by day; publication dates and review dates remain separate. Experimental evidence is highlighted with its conditions and limitations. Daily literature review continues at 09:00 America/Chicago.
- **Private team messages:** a message board beside Notes with an in-app new-message indicator, visible only to authenticated, approved team members. While the APP is visible it checks about once a minute; this is not a background push service. Logging out clears private content and notifications.
- **Correct model explanations:** Hurricane 4.0 displays its own 2,123-entry training cohort; later experimental versions keep separate cohorts. Chemical-system groups, catalogued zero labels and abstentions are described accurately.
- **Evidence-based illustrations:** source-supported octahedral, copper–oxygen, nickel–oxygen and kagome motifs replace broad family-based guesses. Idealised structures and proposed mechanisms are labelled explicitly, with experimental conditions and references retained.
- **Careful screening claims:** 40 K is a screening benchmark, not a universal physical limit. DFT stability is no longer treated as proof of synthesis, and model scores are distinguished from demonstrated discovery probabilities.

Version 0.3.11 adds:

- **Team password setup:** new passwords can contain 8–128 characters. Existing passwords remain unchanged.

Version 0.3.10 added:

- **Team access on the web:** invited email/password accounts, administrator-managed display names, resend controls, and hidden revoked members. Membership invitations remain valid until revoked; Firebase password-setting links still expire and can be requested again. Password recovery and invitation setup have separate entries.
- **Private Notes:** material or research-method illustrations alongside the existing research walkthroughs, source-based team introductions, progress, evidence limits and references. Illustrations are schematic, not verified crystal structures or experimental measurements. Private content stays behind team authentication.
- **Phone updates:** the installed web app checks for updates when opened or resumed and offers an update banner without automatically reloading. Home-screen badges depend on browser support.
- **Desktop updates inside the APP:** after this first installation, future versions are checked and downloaded automatically. The APP verifies the installer against its GitHub release checksum and starts installation only after confirmation, without opening a GitHub download page. Existing 0.3.9 installations need this one-time upgrade. The installers are not code-signed; operating-system confirmation may still be required.
- **News and papers:** separate AI-for-superconductors and general-superconductivity sections with their existing animations.

Use [the hosted APP](https://diracmagic.github.io/supercon-ml/) for team sign-in and private Notes. Native-installer authentication has not been verified.

Candidate-screening and validation updates included in this release:

- Candidate scores exclude each candidate's own background labels in every ensemble member; model disagreement is labelled separately from confidence intervals.
- Storm training-domain priority, exploration and B/C-containing metallic sublists, with optional bounded MACE/ASE sampled-phonon triage.
- Condition-specific literature checks, including unknown outcomes when the source does not establish a superconductivity null.
- Ordered, reviewable frontend resources with AST extraction checks and a complete offline asset manifest; other applications' caches are preserved.

Version 0.3.9 added:

- **Hurricane 4.0, “not known” instead of “unlikely”**: far from everything it learned from, Hurricane now answers “not known” and gives no chance, and its classifier keeps only the 218 compounds with no superconductivity record that lie near its training data. Trained without a whole family, Hurricane 3.0 called 88% of that family’s superconductors unlikely and Hurricane 4.0 calls 28% unlikely, still with no false alarms and an error on measured T<sub>c</sub> of 10.4 K (Hurricane 3.0: 10.3 K). It does not find a new family either: it answers “not known” for most of one (64%) and gives at least an even chance to 8% (Hurricane 2.0: 47%). The model details show, for every family left out, how much it found, left open and called unlikely, and where the distance falls short: most cuprates look like the families it learned from, so a model that never saw one still calls 69% of them unlikely, and the refuted LK-99 now gets a 94% chance (Hurricane 3.0: 78%).
- **Screening round 4**: Hurricane judges only the compounds near its training data, 75 of the 354 that Radar sends it; the other 279 get no chance and are counted, not listed. The list says which numbers come from cross-validation and which from the model trained on all of its data: in cross-validation none of the held-out compounds with no record reached an even chance, while on the list one compound does (61%). It is a prediction that nothing has checked.
- **Model details on phones**: the tables fit the screen, with column heads that wrap instead of scrolling sideways, and a chance just under one half reads 49.9% instead of 50%.

Version 0.3.8 added:

- **Hurricane 3.0, fewer false alarms**: Hurricane now also learns from 1,714 compounds that nobody has reported as superconducting, counted as probably not superconducting, as Konno et al. did in 2021 (Phys. Rev. B 103, 014509). Of the compounds of that kind that it never saw, Hurricane 2.0 gave 39% at least an even chance of superconducting and Hurricane 3.0 gives none, with the same error on measured T<sub>c</sub> (10.3 K). The model details show the price as well: it is now slow to recognize a family of superconductors it has never seen.
- **Screening round 3**: the unconventional list is ranked by Hurricane 3.0, and no compound on it is more likely than not to superconduct. The materials Hurricane is checked against, such as UTe<sub>2</sub> and CsV<sub>3</sub>Sb<sub>5</sub>, now count as known too, so they can never appear among our finds.
- **What decided the release**: for Hurricane 3.0 the model details list the false alarms of every design the AI agent proposed, whether each passed the release rule fixed before the run, what the new caution costs on a family left out of training, and how the chance of each later discovery changed. The Hurricane demo compares the designs by their false alarms.

Version 0.3.7 added:

- **Two candidate lists**: conventional candidates ranked by Storm and unconventional ones ranked by Hurricane, which gives the chance that a compound superconducts and its T<sub>c</sub> if it does. A candidate made of exactly the elements of a known superconductor is now left out too, so every one is in a chemical system where no superconductor has been reported.
- **What to make of each candidate**: every candidate shows the chance that it superconducts and, in the viewer, remarks on how far to trust it: whether its structure has ever been made or is hypothetical, how wide its 90% range is, how its chance was calibrated, the most similar material its model learned from and whether it lies outside the training data, whether anything has checked it, and the date we first listed it, which the repository's history records. All candidates are predictions that no calculation or experiment has checked yet.
- **Worth an experiment**: a candidate is highlighted only when its predicted T<sub>c</sub> is above the McMillan limit of about 40 K and it passes every test we set before suggesting a measurement: more likely than not to superconduct, inside its model's training data and made before. None does yet. Highlighted candidates come with an invitation to experimental groups.
- **Cite**: the Authors view is now Cite, with how to cite the project (as text or BibTeX, with copy buttons) and one of our candidate superconductors, and the published work that cites supercon-ml as soon as there is any. A message form sends questions, reports and offers to measure a candidate straight to the project's inbox, and every "tell us" link in the app leads to it.

Version 0.3.6 added:

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

- **Phone / iPad:** open [the web APP](https://diracmagic.github.io/supercon-ml/) and add it to the Home Screen. It keeps the same icon across updates.
- **Windows 10/11:** `SuperconProgress-windows-x64-setup.exe` (or the `.msi`)
- **macOS, Apple Silicon and Intel:** `SuperconProgress-macos-universal.dmg`

### First launch

The installers aren't code-signed yet, so the operating system asks you to confirm once.

- **Windows:** if SmartScreen says "Windows protected your PC", click **More info**, then **Run anyway**.
- **macOS:** open the `.dmg` and drag **Supercon Progress** into Applications. If macOS says it can't verify the developer, open **System Settings → Privacy & Security** and click **Open Anyway**.
