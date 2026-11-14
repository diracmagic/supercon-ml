# Hurricane round 10: declaration before the run, version 1

Date: 2026-11-13. Committed with the module, before it was run on any real data. Until this file is on the branch, the
module refuses to read any data: python ml/pipeline.py hurricane10 stops unless the protocol hash below is written here.

## 1. What is declared

- Protocol: hurricane10-protocol-v1, SHA-256 571e49bd68ee5ee76e3d358262f36256b68245c6898cb96d8b48a7e8da71acbd
  (the canonical JSON of PROTOCOL in ml/hurricane10.py; printed by: python ml/hurricane10.py --protocol). It binds the
  release protocol of Hurricane 9.0, hurricane9-release-protocol-v1, SHA-256
  87694b5845afb729f2f1ede376e194a48db8c65dd7d800f169af34521b1a1fdf, and the pool protocol of screening round 7,
  hurricane9-screen7-protocol-v1, SHA-256 46c955b68e68a52a291eba5398757125a22fbcd44f4a47db08c330d0f1eecfd2.
- Code: the files below, committed together with this declaration on the branch claude/hurricane10.

| File | SHA-256 |
| --- | --- |
| ml/hurricane10.py | 4b679f657804e3b15872ce39c22189bee3110047349fa5cf62025a4a2b7da7ce |
| ml/hurricane9_screen7.py (as on the branch claude/screen-round7, unchanged) | 231060e9b1971d31323696de618a05aed0e4fd4f880f62cd36c7874569dbf9ad |
| results/screen_round7_cod.csv.gz (the COD rows read once for screening round 7, unchanged) | 891622279ff2379b30974d284775d0a2d9507243355592b26388dfea36e4e14e |
| results/screen_round7_cod.json (unchanged) | b7e69d967566f97a3dcfef7fa413a5535ac05b68632b5800367c2508f016d64b |
| ml/hurricane9_release.py (unchanged) | 6b13d19af83ef958cb5897725f825d55d83de10983077513bd163e95807b31a5 |
| ml/hurricane9_screen.py (unchanged) | 8903b5254376d11df59194e2a6271890912dbacca1642dd88c7eaf8f8309fc3e |
| ml/hurricane9.py (unchanged) | 4edc1aa43b99f1b6141dae4d714195690e0ed85ee22036c11c6f7cd0fd1c8cf1 |
| ml/hurricane9_data.py (unchanged) | 61695fcbb78e02168f64c9e4505079fa54ea9fb08af53f7fdc628c73ea4870c6 |
| ml/hurricane3.py (unchanged) | add5b2f15689dfdf75e8479cc58fb6912900e63d9626eec2a3db565418c1f960 |
| ml/screen.py (unchanged) | 42b74504c6cd2d5cbc365504d76b4dba752f3a3df7ff0fc842f02ae7867d8242 |
| ml/radar.py (unchanged) | c5664c7c19d6eb18f1598e7f5ce7baef1fb169a7f11004dd3987ff56e8474d57 |
| ml/pipeline.py | ff94864d8166fb571efa2722c8ea942368c797772f3ef59821ea5cd6f313cbf8 |
| ml/requirements.txt | 52acb53bb759b840fde16cffb48d6a57be3c8b9dd2ef44a8d80bd06d77fff1e8 |
| tests/test_hurricane10.py | 553c4e042a02e14d92b8755fe1597a1cc712b5496761d91be9f4d4e8cd40e84d |
| .github/workflows/train.yml | 61a9c85b30f86ea387f6453b493a7171f94d8a3450fc415c4aca74e1090a723b |

## 2. Why this round

Screening round 7 (run on the branch claude/screen-round7, not published) put Hurricane 9.0 to 118,750 compounds with no
superconductivity record from JARVIS-DFT, the Materials Project, Alexandria and the Crystallography Open Database. It
gave at least an even chance to 1,956 of the 9,456 compounds it judged (21%), and all 100 compounds it would have
listed were copper oxides: substituted variants of known cuprate superconductors, and copper oxysalts and other copper
oxides that are not layered cuprates. The record is section 6 of results/validation/screening-pools-hull-correction.md.

Hurricane reads the composition only. Its classifier learned from 158 background compounds as weak negatives: those of
3,881 JARVIS-DFT compounds that lie near its training rows, and those 3,881 were selected with JARVIS-DFT's ehull field,
which does not follow the convex hull. This round asks one question: does a wide background, selected correctly and
without the variants of measured compounds, teach the classifier that a copper oxide is not a cuprate superconductor by
its composition alone, without losing the superconductors it finds?

## 3. What changes and what does not

- Changes: the background of the classifier only. It becomes the pool of screening round 7, assembled by
  ml/hurricane9_screen7.py with its sources, files, tracks, rules and exclusions, without every compound whose parent
  compound by the datasheet's coefficient rule is a parent of the datasheet. Such a compound is a variant of a measured
  compound and may well superconduct (rank 1 of round 7's list, Ba1.888Na0.094YCu3Cl0.057O6.961, has the parent of
  YBa2Cu3O7). Variants are neither background nor scored.
- Unchanged: the training rows, the inputs, the regressor (so every Tc is Hurricane 9.0's), the classifier's settings and
  seeds, the guard's weight (0.3), radius (1.0) and abstention (1.0), the five background folds by a hash of the
  chemical system, and the declared time windows.

## 4. The test, fixed before the run

Both designs are computed in the run, with the same code, on the same compounds.

- A. Of the compounds of the new background that Radar sends to Hurricane and that lie inside the training data, the
  share given a chance of at least one half, each by a classifier that learned from no background compound of its fold,
  is at most half the share that Hurricane 9.0 gives the same compounds.
- B. In the family windows of hurricane9-protocol-v1, pooled by units, the share of new-parent superconductors given a
  chance of at least one half inside the training data is at least Hurricane 9.0's share minus 0.05.

The design is adopted as Hurricane 10.0 when A and B hold. Otherwise the round is reported and Hurricane 9.0 stays.

Reported without a limit: the share of new parents measured not to superconduct that get at least an even chance (9.0:
0.385 in its release run), the new-family windows, both guards' summaries, each design's alarms by Hurricane's family
rule, the variants left out (counts, and those 9.0 would have called likely), and the 25 compounds of each track that
the new design ranks highest, with 9.0's chance beside each. That last table is not a list of candidates.

The run must reproduce Hurricane 9.0: its released background table (results/hurricane_round9_background.csv) and the
chances of its guard; it stops and writes nothing otherwise.

## 5. Order of work

1. This declaration and the code are committed on the branch claude/hurricane10.
2. The run is made once on the branch (Train, stage hurricane10). On a branch the workflow commits nothing; the
   block the module prints is read from the job log and checked against the hash printed with it.
3. The result is reported to the user whatever it is. A release of Hurricane 10.0, its app version and a screening round
   with it are later steps, each published only after the user's explicit go-ahead.

Limits known before the run: the background compounds carry no date, so inside a time window the classifier learns from
compounds that may have been made after the window's cutoff (as in Hurricane 9.0); test B can only show that the found
share holds, not that new superconductors in the pool would be found; and a composition-only classifier cannot see CuO2
planes, so test A can be met while layered copper oxides that do not superconduct still get high chances.
