# Licence for results and curated content

Copyright (c) 2026 The supercon-ml project

The code in this repository is under the MIT licence (see [`LICENSE`](LICENSE)). The following are licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0; [legal code](https://creativecommons.org/licenses/by/4.0/legalcode)):

- `results/`: the models' out-of-fold predictions, scores, leaderboards and design specs.
- `progress/progress.json`: the project's stages, activity log, results and model descriptions.
- `progress/content.json`: the curated list of recent advances, that is, the text we wrote about each one. The papers it cites belong to their authors and publishers.
- `data/experiments.json` and `data/hurricane_anchors.json`: our graded compilation of measured T<sub>c</sub>. The measured values themselves are facts reported in the papers cited in each file.

**Attribution.** Please cite *The supercon-ml project, supercon-ml: finding superconductors with AI-designed models, https://github.com/diracmagic/supercon-ml* and, for results built on them, the datasets listed in the README (Alexandria, JARVIS-DFT, the Materials Project, the Crystallography Open Database, and 3DSC with SuperCon), which keep their own licences.

**Not covered.** `progress/papers.json` holds bibliographic metadata and short excerpts from arXiv, Crossref, journals and news feeds, which remain with their owners. The training datasets are downloaded when the models train and are not stored here. `results/screen_round7_cod.csv.gz` holds rows of the Crystallography Open Database's own table, as read once for screening round 7; they are in the public domain, as the COD publishes them. The crystal structures of candidates that come from the Materials Project or Alexandria, in `progress/progress.json` and `results/`, are those databases' data under CC BY 4.0; each candidate names the entry it comes from. The third-party software in the desktop app is listed in `THIRD-PARTY-NOTICES.txt` with its own licences.
