# Reviewed external AI superconductivity research

This registry drives the native **Superconductors found with AI by other groups**
cards. The app does not embed the separate Word memo or redistribute papers.

`../external_research_memo.json` holds the manifest and daily search metadata;
`part-*.json` holds reviewed entries. Each entry retains its primary references,
version and review date, pressure, Tc criterion, evidence category, result,
limitations, and the steps actually reported. Predictions, calculations,
experimental results, retrospective tests and funded plans are distinct.

Daily review is scheduled at 09:00 America/Chicago in the Codex automation
`ai`. This repository records that schedule; it does not itself run the scheduler.
The separate automatic news feed is not a reviewed source registry. A scheduled
search is not evidence that a review completed or that the app was deployed.

## Daily update

1. Search primary papers, author versions, repositories and official programme
   announcements. Check follow-up experiments, corrections and retractions.
2. Deduplicate by DOI and version. Record what was accessible; keep a preliminary
   claim qualified if the necessary full text or sample information is unavailable.
3. Update the relevant entry, its review date and references. Keep negative results,
   failed synthesis, phase attribution and conflicting Tc criteria. Do not copy
   article text or figures. Dataset reuse requires its own permission review.
4. Set each explanation step to `completed`, `current` or `not_reported` from the
   source. Animation only moves the explanation focus; it never changes evidence.
5. Run `python tools/build_external_research.py`, then its `--check` mode and the
   Python/Node checks in `.github/workflows/checks.yml`. Keep each reviewable file
   below 70 KB; split the bundle if growth requires it. Update the asset/cache
   manifests for changed resource structure and verify desktop, mobile and offline.
6. Commit to a review branch and update its open PR. After that PR is merged,
   start a new review branch/PR for later findings. Merge or deploy only within
   the user's explicit authorization for that release; do not retrain a model
   or change a frozen protocol as a side effect of literature maintenance.

The initial source digest is the independently reviewed memo-record JSON, not the
DOCX's layout bytes. Later changes live in version control and must identify their
primary evidence. The separate source snapshot and review dates must stay honest.

## Candidate ordering and earlier reports

Storm lists sort by predicted DFT Tc. Hurricane lists sort by explicit `tc_sc`
(Tc conditional on superconductivity), retaining the probability and five-fold
disagreement. A missing conditional Tc stays unknown and sorts last.

Earlier experimental superconductivity reports move a candidate to a visible
archive only with an exact candidate ID, reviewed composition/structure/phase/
pressure/doping/sample-form matches, a source locator and sample context, and a
publication date preceding a sourced frozen prediction. Unknown conditions,
theory alone and formula mentions do not establish priority. Existing pool
exclusions remain historical; the app does not reconstruct absent candidates.

The current 152-row snapshot has no record satisfying all priority requirements,
so none was moved. This does not establish that any retained candidate is novel.
Measured negative and unknown outcomes remain visible with their conditions and
citations; an unmodified sample's negative result is not a parent-wide label.
