# Validation record

Validated locally on Windows with Python 3.12 on 2026-09-15.
Only synthetic data was used. This record distinguishes automated checks,
actual browser interaction and checks that have not run.

## Automated checks

`python -m pytest -q -W error`: **89 passed**, no warnings (final run: 2.92 seconds).
The count includes parameterized cases, not 89 separate features.

Coverage includes:
- UTF-8/BOM, four CSV delimiters, quoting, leading zeros, literal NA text,
  empty/corrupt/binary input, missing sheets, upload/expansion/row/column limits.
- Duplicate/blank headers and streaming XLSX without dimension metadata,
  including shorter rows, trailing empty columns and blank rows.
- Finite numeric statistics, text statistics, date/native boolean types and empty input.
- Missingness, duplicates, whitespace, empty/constant columns, category variants,
  mixed types, IQR outliers, infinity, explicit date/numeric/range/identifier rules.
- Exact score arithmetic, overlapping issue deduplication, boundaries and determinism.
- Cleaning order, unchanged source, every supported action, rejected invalid plans,
  all-missing fill errors, new nulls and per-step/net counts.
- JSON structure and row-position caps, CSV formula protection, XLSX literal formulas,
  large integers and rejection of unsupported Excel text.
- Streamlit AppTest: every workspace view, clean demo, workbook sheets, preview/apply,
  analysis-setting invalidation and mandatory fresh acknowledgement after a new preview.

## Browser scenarios actually exercised

The actual Streamlit app was launched through Start_DataTriage.bat on port 8502.

| Scenario | Observed result |
| --- | --- |
| Dirty customer demo | 62 rows, 8 columns, 65 missing cells, 2 duplicate rows, score 91.4 with visible demo rules |
| Clean inventory demo | 20 rows, 4 columns, no missing cells, score 100.0 |
| Issues and severity filter | 16 findings; HIGH filter reduced to 5; invalid-date rows 11, 12, 17 shown |
| Numeric column explorer | spend histogram, one finite IQR outlier, infinity reported separately; fences −70.5 to 285.5 |
| CSV upload | Synthetic customer CSV loaded through the browser file chooser |
| XLSX upload and sheet change | Synthetic workbook loaded; Customers and Inventory selectable, correct data and report after switching |
| Invalid CSV upload | Helpful inconsistent-width message, no traceback |
| Empty file upload | Helpful empty-file message, no traceback |
| Duplicate cleanup preview/apply | 62 → 60 rows, 2 → 0 duplicates, 65 → 63 missing cells, 0 surviving cells modified; apply gated by acknowledgement |
| Whitespace cleanup preview/apply | Trimming name modified exactly 1 cell, retained 62 rows |
| CSV download | Browser download obtained; bytes exactly matched engine export of the duplicate-removal result (60 × 8) |
| XLSX download | Browser download obtained; reloaded values matched all 62 × 8 cells of the trim result |
| JSON download | Browser download parsed; Inventory dimensions 20 × 4, score 100, no applied result, explicit settings |
| Layout | Inspected narrow 340-pixel layout and desktop 1366-pixel layout; real screenshots saved in assets |

Header-only dataframes, corrupt XLSX, high-risk conversion/removal and less common
fill operations were tested at engine/AppTest level, not all repeated through the
browser. Source immutability and stale-result invalidation have explicit automated tests.

## Defects found and fixed

1. Object-series comparisons involving pd.NA could raise an ambiguous-boolean error
   during whitespace detection. Replaced them with explicit string-only masks.
2. Excel would silently truncate long strings and lose long integer precision.
   Unsupported text is rejected before writing; integers above 15 digits are literal text.
3. Rejecting invalid Excel strings after starting a streaming writer left an open
   generator and caused cleanup warnings. Pre-validation now occurs before workbook creation.
4. A fresh preview could retain an earlier acknowledgement. Every preview now
   clears acknowledgement; a regression test checks that Apply is disabled again.
5. Actual XLSX download verification uncovered missing trailing cells in dimensionless
   streaming workbooks. The loader now pads shorter rows and preserves later wider rows.
   Regression tests cover both cases; the actual downloaded file was rechecked successfully.

## Performance observation

One direct engine analysis of a synthetic 50,000 × 40 numeric dataframe
(2,000,000 cells, the configured cell limit) took **3.58 seconds** on this machine.
All 40 columns held the same increasing sequence: 39 matching-column INFO findings,
score 100.0. This measures analysis only, not file upload, Excel serialization or UI
rendering. It is not a general benchmark or a promise for arbitrary datasets.

## Runtime notes and remaining scope

The prior local server had stopped between sessions; the launcher restarted it.
Browser logs recorded connection errors while that server was down, and later
Streamlit tooltip warnings about preventOverflow/hide. No application traceback
was observed during the completed browser scenarios after restart.

Start_DataTriage.bat was used to start the actual app successfully, including a
second launch after the previous server had stopped. Its missing-environment
message was inspected in code, not exercised by deleting/renaming the environment.

Screenshots are real browser captures of synthetic data. Some text softness comes
from the in-app browser capture; no generated UI artwork or artificial data overlays
were used.

At the initial validation checkpoint, publication was explicitly deferred and no
hosted CI run had occurred. Consult the repository Actions page for subsequent
publication checks and per-commit results.

## Final publication audit

The complete 89-test suite passed again with warnings treated as errors. All 38
tracked files were reviewed; screenshots decode, demo workbook XML contains no
credential/local-path pattern matches, and all six declared dependencies are used.
Ignore rules exclude the environment, caches, uploads, downloads and temporary files.
The launcher uses project-relative paths. The README opening was shortened and its
clone URL updated for the verified account. Application functionality was unchanged.
