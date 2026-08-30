# CLAUDE.md

## About this project
Analysis of Brazilian domestic airfares (ANAC, 2002-present), deflated by IPCA, with explicit
handling of the 2010 ANAC methodology break (Resolution 140/2010, ~65 trunk routes -> 2,000+
routes). Entry point is `airline_prices.ipynb`; the cleaning/aggregation pipeline lives in
`files_processor.py` (`FilesProcessor`).

Full context on this project and the sibling repos it's part of: see PLANNING.md.

## What this repo does
- Normalizes ANAC's monthly fare CSVs (schema/encoding varies across years) onto a canonical
  schema and concatenates them (`FilesProcessor.read_files`).
- Computes seats-weighted average fare, weighted standard deviation and coefficient of variation
  per route/month (`create_metrics_file`).
- Deflates fares to constant purchasing power via IPCA, fetched live from the BCB SGS API through
  the shared `br_economic_indicators` package (`deflate_metrics`).
- Tests whether real fares show a statistically significant trend over time in the notebook,
  accounting for the 2010 methodology break and route-mix composition effects.

## Conventions
- Code, docstrings, README and notebook prose are in English; conversation with the user may be
  in Portuguese.
- Seats are treated as frequency weights (each seat = a repeated observation of that fare), so
  `weighted_std` uses the unbiased frequency-weighted estimator — except for a single-seat sample,
  which has no variance by definition and is defined as `0.0` rather than left undefined.
- Deflation logic (building the price index, deflating a series to a base date) lives in
  `br_economic_indicators`, not duplicated here — see `PLANNING.md` for the shared-package
  rationale.
- No formal test suite here (notebook + a single pipeline module) — `br_economic_indicators`,
  the shared dependency, is where deflation/conversion logic is tested.

## Useful commands
```bash
pip install -r requirements.txt
pip install -e /path/to/br-economic-indicators   # shared deflation/indicators package
```

## Don't
- Don't duplicate deflation or minimum-wage-conversion logic here — it belongs in
  `br_economic_indicators` and gets consumed via `import`.
- Don't silently handle an unrecognized ANAC column-header schema — `read_files` should keep
  raising a clear error instead of misaligning columns.
