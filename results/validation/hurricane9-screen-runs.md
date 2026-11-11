# Screening round 6, the candidates of Hurricane 9.0: the two runs

Written after the run on main, 2026-11-11. The protocol of both runs was declared before either of them:
hurricane9-screen-protocol-v1, SHA-256 e0d088da29803a7a40f07b43683d34f1e87460e65bf6bfc6358ff12117dc2dcf
(results/validation/hurricane9-screen-declaration-v1.md). The declaration said that the run would be made twice with
the same code: first by hand on the branch, where the workflow commits nothing, then by hand on main.

## 1. The run on the branch

- Train run #74 (GitHub Actions run 43075974830), dispatched by hand on 2026-11-11 at 18:15 UTC on commit fcb0844 of
  the branch claude/hurricane9-screen, stages `hurricane9screen`. It succeeded in 3 min 34 s. On a branch the
  workflow commits nothing; the block that the module prints was read from the job log and checked against the hash
  printed with it.
- The block: 37,706 characters, SHA-256 4fc84666421c71babc437ab05ad3af3dd6653766f9e062db79d197c828b2bf1b.
- It reproduced the table of the release run (results/hurricane_round9_background.csv, SHA-256
  e2575e5481cf6734f0e03b9b9741ba6fbba168d460a20589ccbc34a279c12500): 3,881 rows, largest difference 5e-05, against a
  tolerance of 5.1e-05 (the table is rounded to four decimals).
- Counts: a pool of 3,881 compounds; 591 sent to Hurricane by Radar; 537 not known; 54 judged, in 42 chemical systems;
  42 listed; 1 with at least an even chance; 3 with a recorded check; 20 with a literature record; 23 listed in an
  earlier round. The table of every compound sent had SHA-256
  18564f826284a5a041a87a6c8831f510c6c287444a39226fec5bc554c3f7b14b.
- The list was checked before it was published: every listed compound is sent and inside the training data in the
  release run's table, with the same chance to within 6e-4; one compound per chemical system and every judged system
  covered; the order is the chance times the Tc if it superconducts. The app was checked with the block in place.

## 2. What was done between the runs

- The result of the branch run was shown to the project owner, who gave the go-ahead to publish it.
- The screening code was merged (pull request #46, merge e778576), and APP 0.3.31, which describes a list screened by
  a version trained on the NIMS datasheet, was released (pull request #47, merge 8516751), so that the web app never
  showed this list with the wording written for the earlier version. A desktop app of an earlier version shows the
  list with that wording until it is updated.

## 3. The run on main

- Train run #76 (run 43086259505), dispatched by hand on 2026-11-11 at 19:20 UTC on main at 8516751, stages
  `hurricane9screen`. It succeeded in 4 min 34 s and committed results/screen_round6.json,
  results/screen_round6_hurricane.csv and progress/progress.json in 42940c3 ("Update training results (run 76)").
- The block it printed differs from that of the branch run only in the duration of the run (1.9 minutes against
  1.5): the same counts, the same reproduction of the release run's table (largest difference 5e-05), the same 42
  candidates with the same values and first-listing records, and the same table of every compound sent (SHA-256
  18564f826284a5a041a87a6c8831f510c6c287444a39226fec5bc554c3f7b14b). The list it wrote into progress/progress.json is
  that block.
- results/screen_round6.json: SHA-256 9aa28e4020f59d7b6eaf88ca015304ee3c757e7f38447290c41705fcba92a80a.

## 4. Review

As section 5 of the declaration says, the runs were made without a review by the other AI agent, which the project
owner has paused since 2026-11-06. The owner was told so before the branch run and approved the publication after
seeing its result.
