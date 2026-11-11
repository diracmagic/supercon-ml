# Hurricane 9.0, the release run: declaration before the run (R-007), version 1

Date: 2026-11-11. Committed before the release module was run on any real data. Until this file is on the branch, the
module refuses to read any data: python ml/pipeline.py hurricane9 stops unless the protocol hash below is written here.

## 1. What is declared

- Protocol: hurricane9-release-protocol-v1, SHA-256 87694b5845afb729f2f1ede376e194a48db8c65dd7d800f169af34521b1a1fdf
  (the canonical JSON of PROTOCOL in ml/hurricane9_release.py; printed by: python ml/hurricane9_release.py --protocol).
  It binds the fit protocol hurricane9-protocol-v1, SHA-256
  37478fec876263854a3286539aac92820039d8f5a37a5bc87cd8844d40654987, declared on 2026-11-10 in
  results/validation/hurricane9-r007-declaration-v1.md.
- Code: commit 24cc19b457788008b5c7c509529df85d35705eee on claude/hurricane9.

| File | SHA-256 |
| --- | --- |
| ml/hurricane9_release.py | 1d503a63db75ad1a37805a28a564e95568ccc11cd5c5161edd049bcac97361d3 |
| ml/hurricane9.py (unchanged since the first declaration) | 4edc1aa43b99f1b6141dae4d714195690e0ed85ee22036c11c6f7cd0fd1c8cf1 |
| ml/hurricane9_data.py (v0.4, unchanged) | 61695fcbb78e02168f64c9e4505079fa54ea9fb08af53f7fdc628c73ea4870c6 |
| ml/hurricane.py | c08672379cbf43f4e2be91aebe43984db3a0dbf5db4e5d75e5abcb27b99960fb |
| ml/hurricane2.py | 962d65e311bb1f1dcdd108f9fec7e751f30d0b77dfd17fea1d2efac6e419008d |
| ml/hurricane3.py | add5b2f15689dfdf75e8479cc58fb6912900e63d9626eec2a3db565418c1f960 |
| ml/screen.py | 42b74504c6cd2d5cbc365504d76b4dba752f3a3df7ff0fc842f02ae7867d8242 |
| ml/radar.py | c5664c7c19d6eb18f1598e7f5ce7baef1fb169a7f11004dd3987ff56e8474d57 |
| ml/pipeline.py | d5cfabe670869521ab629ed5b02944d0ec753d8a9573fddd457281d4d41f081b |
| data/hurricane_anchors.json | e58a2e82b434c1e2520ac1853c60922405a3abb9911ec4c3afdaf67b90c589f3 |
| tests/test_hurricane9_release.py | 3c47f035689e19ad816262e7790bfa1170f00b0b5bc69f0793abcd0ee2b73b3f |
| tests/test_hurricane9.py | f61dab7d0e72d07f257b208e0794368f61df07872907818f58c6c8a0de213eec |
| .github/workflows/train.yml | 11f365f87e8cac23d31534b219eaee3fccf58e1584974b3598dbb39b5459c94c |

- Data for the model: MDR SuperCon Datasheet Ver.220808, file 220808_MDR_OAndM.txt, 18,227,757 bytes, SHA-256
  a874ab2472c960ace275b2f97e6b97fae8fae2420513fc94d919d0037f202ff7 (NIMS, https://doi.org/10.48505/nims.3837,
  CC BY 4.0); 3DSC_MP.csv at commit 8d69ca9c94b83d387378549225d3b7c3af85ca42, 9,457,406 bytes, SHA-256
  353b86f9c60505d11a3e25df8312da02ff88fd8e27af05b632dec4739d52eb24 (only to mark the units the previous model's data
  hold). Both are verified by size and hash before parsing.
- Data for the guard: JARVIS-DFT 3D as jarvis-tools downloads it, the lists of known superconductors and claims that
  ml/screen.py loads, and Radar refitted on its 3DSC rows, all exactly as the screening rounds and Hurricane rounds 3
  and 4 use them. These downloads are not pinned by a hash; the run writes the number of compounds after every step.
- The runs. Stage hurricane9 of .github/workflows/train.yml calls python ml/pipeline.py hurricane9. It is run twice
  with the same code, data and rule: first by hand on the branch claude/hurricane9, where the workflow commits
  nothing and the results stay in the job log and the workflow artifact; then, after the merge, by hand on main,
  where the workflow commits results/ and progress/. The second run writes the entry of Hurricane 9.0 in
  progress/progress.json, as released or as experimental, as the rule decides. The first run exists to find
  failures of the plumbing that no local test can reach (JARVIS, Radar and the element properties are not available
  where the module was written) before anything is merged.
- A change to PROTOCOL changes the hash. A code fix that leaves PROTOCOL untouched is recorded as an amendment to
  this file before a rerun, with the commit and the reason.

## 2. What had been looked at when this was frozen

- The declared run of hurricane9-protocol-v1 (run 42904179317, repeated unchanged in run 42907151258; every one of
  the 2,318 numbers of the report agrees to 13 decimals). Claims C0 to C3 are about the units of new cuprate
  parents in the windows after 1990, 1995, 2000 and 2005 (1,103 units in 472 parent clusters); C4 is about the two
  windows in which a family was new (cuprates after 1985, iron-based after 2005):

| Claim | Contrast | Pooled difference in rank correlation, 95% interval | Result |
| --- | --- | --- | --- |
| C0 | measured minus previous | +0.292 [0.196, 0.381] | met |
| C1 | data minus previous | +0.306 [0.212, 0.390] | met |
| C2 | measured minus names, units with a c axis | +0.005 [-0.027, 0.033] | not met |
| C3 | data minus the nearest known compound | +0.049 [-0.023, 0.129] | not met |
| C4 | transfer, AUC of the 30 K event in a new family | 0.648 [0.541, 0.759] cuprates; 0.728 [0.610, 0.835] iron-based | met |

  Rank correlations: previous 0.315, data 0.621, names 0.617, measured 0.607, nearest known compound 0.571. Mean
  error on the same units: 28.4, 19.4, 19.6, 19.8 and 21.5 K. An independent recomputation from the saved
  predictions (ml/hurricane9_audit.py) agrees with the report on the cuprate lines of C0 to C3, largest difference
  3.6e-15. Its first version could not read the event column, so the two AUCs of C4 have not been recomputed
  independently; version 2 reads it and has not been run yet. C4 is not part of the rule below.
- So the first half of the rule below is already known: the release run repeats the declared evaluation unchanged,
  and C1 is expected to come out as in the table. That half is a check that the released code path reproduces the
  declared result, not a new test. A difference beyond rounding would be an error to find, not a result.
- The second half is not known. No classifier with background compounds has been fitted on datasheet rows, no
  JARVIS compound has been scored by a model trained on the datasheet, and no share of false alarms has been
  computed. The release module has run only on invented rows (its --smoke and the tests in
  tests/test_hurricane9_release.py: an invented table, invented background compounds, no JARVIS and no Radar).
- What was chosen knowing the declared results: the released design is the one called data. It is the simplest
  design of the declared ladder that carries the claim that was met (C1). The designs with structure names and
  with measured lattice lengths brought no gain (C2), and the measured quantities do not exist for a compound nobody
  has made. No setting of the design was changed after the declared run: the learner, its parameters, the inputs
  and the seed are those of that run, and a test holds the released code path to the same predictions bit for bit.
- The three numbers of the guard (weight 0.3, radius 1, no chance beyond 1) and the limit of 5% false alarms are
  those of Hurricane 4.0, taken over unchanged. None was tuned on datasheet rows.

## 3. The model, the guard and the rule (the protocol JSON is authoritative)

- Model: the recipe of Hurricane 4.0 without its Materials Project structure block (composition statistics, 15
  physics features, element shares, 19 structure types read from the stoichiometry; the same gradient-boosting
  learner), trained on every usable unit of the four modelled families in the datasheet, all years. Two parts: a
  classifier for the family event (superconducting at or above 4.2 K; 1 K for a heavy-fermion compound) on the units
  with an event of 0 or 1, and a regressor for log(1 + Tc) on the units with a Tc value. The answer is the chance,
  the Tc if the compound superconducts, and their product.
- Guard: the compounds of Hurricane's screening pool with no superconductivity record, without those whose
  composition the datasheet lists, join the classifier as event 0 at weight 0.3 when they lie within the training
  data (distance ratio up to 1); a compound further away than that gets no chance but the answer not known.
- The check of the guard: the background compounds are split into five folds by a hash of their chemical system,
  and each gets its chance from a classifier that learned from no background compound of its fold. A false alarm
  is a held-out background compound that Radar sends to Hurricane, lies inside the training data and gets a chance
  of at least one half.
- Rule: Hurricane 9.0 is released if, in this run, claim C1 of hurricane9-protocol-v1 is met and the false alarms
  are at most 5% of the held-out background compounds that Radar sends to Hurricane. Then the entry is written as
  adopted and becomes the version in use. Otherwise the entry is written as experimental, Hurricane 4.0 stays in
  use, and nothing is tuned and rerun under this protocol: another design would need a new protocol, a new
  declaration, and the statement that its guard check is no longer a first look.
- Reported without a limit: what the released behaviour, guard included, answers for the new-parent units of the
  declared windows (the shares given a chance, found, called unlikely and not known), for the family windows and
  for the two windows in which a family was new; the width of a 90% range on log(1 + Tc); the importance of the
  inputs; the graded anchors, where an anchor whose composition the training rows hold is shown and not scored.

## 4. How this stands to the standing rules of the repository

- The standing rule asks a release to beat the version in use on average and in at least four of five held-out
  folds. It cannot be applied to this data. The count-only audits of the datasheet found that under the full
  isolation graph one connected component, the cuprates, holds 8,546 of the 13,329 modelled units, so folds that
  keep related compounds apart cannot be built for the family that carries the claim. The time-window claim C1,
  declared before the first fit, takes the place of the fold rule for this release, and the README will say so.
- Of the conditions of round 4, only the limit on false alarms is kept as a limit. The others compare a design with
  earlier Hurricane versions on the folds of the 3DSC rows, which this model does not use; the share of compounds
  that get an answer is reported without a limit.
- The comparison is with a stand-in for Hurricane 4.0 (its recipe on the units its data hold), not with the released
  file: that model was trained on rows from every year and needs a structure block no datasheet row carries.
- Hurricane has had rounds without a release; the standing rule lets a model move again when new data arrive. The
  datasheet is new data: about six times the measurements, and measured non-superconductors.

## 5. Review

R-007 asks for the other side's no-objection to the frozen hash before a fit on real data. The other agent has been
paused by the project owner since 2026-11-06. On 2026-11-11 the project owner asked for the release of the new model
if it had really improved, chose the full replacement of Hurricane 4.0 with a new screening round to follow, and
waived the review for the release fits (answer to the question how to handle it: approve directly), on these terms:
the protocol is frozen and published with its hash before the run; the rule is fixed in advance and a model that
fails it is not put in use; the results, one prediction row per test unit and one row per background compound are
kept in results/ for a later audit. The waiver covers this protocol hash only.

## 6. What this run cannot show

- It does not show that Hurricane 9.0 beats the Tc of the nearest known compound: claim C3 was not met. The gain
  over the previous model comes from the larger data, not from a new kind of input.
- The background compounds have no superconductivity record, which is not a measurement of zero. A low share of
  false alarms says the model does not give ordinary compounds a chance; it does not say they do not superconduct.
- The model reads the composition only. Two compounds with one formula and different structures get one answer.
- One database, one way of dating reports (the year field of the datasheet) and one parent rule. A parent that is
  new in the datasheet may have been known in the literature earlier.
- The screening list of candidates is not part of this run. It follows in its own round, with the released model.
