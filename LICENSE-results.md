# Licence for results and curated content

Copyright (c) 2026 Yantao Li

The code in this repository is under the MIT licence (see [`LICENSE`](LICENSE)). The following are licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0; [legal code](https://creativecommons.org/licenses/by/4.0/legalcode)):

- `results/`: the models' out-of-fold predictions, scores, leaderboards and design specs.
- `progress/progress.json`: the project's stages, activity log, results and model descriptions.
- `progress/content.json`: the curated list of recent advances, that is, the text we wrote about each one. The papers it cites belong to their authors and publishers.
- `data/experiments.json` and `data/hurricane_anchors.json`: our graded compilation of measured T<sub>c</sub>. The measured values themselves are facts reported in the papers cited in each file.

**Attribution.** Please cite *Yantao Li, supercon-ml (Hello Super), https://github.com/diracmagic/supercon-ml* and, for results built on them, the datasets listed in the README (Alexandria, JARVIS-DFT, and 3DSC with SuperCon and the Materials Project), which keep their own licences.

**Not covered.** `progress/papers.json` holds bibliographic metadata and short excerpts from arXiv, Crossref, journals and news feeds, which remain with their owners. The training datasets are downloaded when the models train and are not stored here. The third-party software in the desktop app is listed in `THIRD-PARTY-NOTICES.txt` with its own licences.
