# Candidate acquisition inventory

This frozen metadata package covers all 152 candidates in screening round 5:
102 Storm 5.0 candidates and 50 Hurricane 4.0 candidates. Five previously listed
IDs are retained separately as retired history. The executed ranking source is
commit `57434fb`, in research artifact run
[41263644864](https://github.com/diracmagic/supercon-ml/actions/runs/41263644864).
Later exploratory Storm 6 and Hurricane 6/7 experiments did not replace that
candidate ranking. The older `progress/progress.json` is not the authority for
this inventory.

Each candidate has its exact JARVIS ID, formula, recorded structure hash,
original audit record hash, source references and model outputs. Predictions
live under `prediction_summary` with explicit names. They are not experimental
labels. The structure hash identifies the stored lattice/elements/fractional
coordinates; it is representation sensitive and does not prove an experimental
phase or specimen match. Feature-distance acceptance is also separate from
exact training-set membership, which remains unverified.

`manifest.json` gives source byte hashes, file hashes, counts and common
collection requirements. Candidate and literature records are split into files
smaller than 70 KB. Source access failures, different phases, computational
studies and condition limits remain visible. A paper reporting magnetism,
structure or no superconductivity report supplies no automatic negative label.
Storm and Hurricane collection/testing eligibility proceeds independently.

## Primary data leads

`primary-data-leads.json` records five checked acquisition leads. One public
numeric workbook was downloaded and inspected: the CeCoIn5/YbCoIn5/YbRhIn5
heterostructure source data. Its zero-field resistance data span 0.06–3.5 K;
they do not cover the frozen 150–300 K pilot window and cannot be assigned to a
standalone YbRhIn5 or YbCoIn5 candidate. The other four leads still require
numeric curves or authorized source access. Five leads do not mean five
trainable datasets.

The source workbook, PDFs, ZIP files, full curve arrays and ledger are excluded
from this package. Source URLs and hashes allow separate acquisition. A local
attachment path in lead metadata identifies the separately held work file, not
a bundled download. New experimental records still require primary source,
specimen/trace, composition quality, target criterion, units, pressure, field,
doping and state provenance. Unknown conditions remain unknown.

## MDR review crosswalk

The separate MDR SuperCon 240322 source is a secondary curated literature
datasheet ([dataset DOI](https://doi.org/10.48505/nims.4487),
[readme DOI](https://doi.org/10.48505/nims.4488)). Exact rational formula parsing
found zero exact reduced-composition matches among these 152 candidates. The
20 same-element-system records linked to 17 candidates have different
compositions and remain manual review leads. They do not establish candidate
samples, structures or labels. Unresolved oxygen/occupancy variables are
preserved in the full work audit, never assigned a value to force a match.

The crosswalk summary retains source numbers, references and row locators.
`mdr-ingestion-risk-audit.json` explains why recommended Tc is not necessarily
midpoint Tc, Hall field is not every measurement's field, maximum pressure is
not each observation's pressure, and RT/sparse scalar resistivities are not a
150–300 K curve. Full figure/text archives require primary/point provenance
review before observations can be exported. No primary DOI is fabricated from
MDR reference abbreviations.

## Validate and reproduce

Only Python's standard library is needed for this compact-package validation:

```text
python tools/normal_state_collection/batch3/inventory/validate.py
```

The full private inventory is intentionally excluded. Its SHA256 is
`4654712cd80084b4329d06bea47eddfd0cda88d7d4c65ad9c5a420de9db26fee`.
With the separately retained audited work directory, reproduce the compact
package in a temporary directory and compare hashes:

```text
python tools/normal_state_collection/batch3/inventory/build.py --data-root <inventory-work-directory> --output-dir <temporary-output-directory>
python tools/normal_state_collection/batch3/inventory/validate.py --bundle-root <temporary-output-directory> --data-root <inventory-work-directory>
```

`build.py` consumes the full private inventory, primary-lead review, MDR
crosswalk and MDR risk audit. It checks the frozen full-inventory hash and writes
only compact metadata in the requested output directory. It never downloads,
fits a model, extracts curves, accesses a ledger or edits input files. The
original private replay independently rehashed 11 ranking/audit input files and
checked 1,891 unchanged prediction fields. This package contains zero new
training labels and zero model fits.
