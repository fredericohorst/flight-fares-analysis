# Brazilian Airline Historical Fares Analysis

#### Frederico Horst

Analysis of Brazilian domestic airfares (2002–2019), based on ANAC's (Brazil's civil aviation
regulator) historical fare series, adjusted for inflation using IBGE's IPCA index.

## Data Sources

- **Historical air fares** by origin, destination and airline: [ANAC downloads](https://sistemas.anac.gov.br/sas/downloads/view/frmDownload.aspx)
- **IPCA historical series** (Brazilian consumer price index, used to deflate fares to real values): [IBGE](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html?=&t=series-historicas)
- More context on the fare data: [ANAC air transport market statistics](https://www.anac.gov.br/assuntos/dados-e-estatisticas/mercado-do-transporte-aereo)

## Goals

- Build a metrics database: weighted average fare, standard deviation and coefficient of
  variation, by route and month.
- Adjust historical fares for inflation (IPCA) so prices are comparable across years.
- Summarize how much real fares actually varied over the full 2002–2019 period, per route.

## Project structure

```
files_processor.py        # FilesProcessor: the full cleaning/aggregation pipeline
airline_prices.ipynb       # notebook entry point that runs the pipeline and explores results
airports.json               # ICAO/IATA/city lookup used to enrich routes with names
ipca_historico.csv           # IBGE IPCA historical index (inflation)
csv_files_from_anac/          # raw monthly ANAC fare CSVs (not versioned, see Setup)
metrics_files/                  # generated output CSVs (not versioned, see Output files)
```

## Setup

```bash
pip install -r requirements.txt
```

Download the monthly historical fare CSVs from ANAC and place them in `csv_files_from_anac/`.
They're expected as `;`-delimited, `latin-1`-encoded `.CSV` files, one per month (e.g. `200201.CSV`).

## Usage

```python
from files_processor import FilesProcessor

df, metrics, route_variability = FilesProcessor().process_files()
```

`process_files()` runs the full pipeline:

1. **`read_files`** — concatenates every monthly CSV in `csv_files_from_anac/`.
2. **`clean_dataframe`** — renames columns, builds a `YearMonth` key, and enriches origin/destination
   with airport names via `airports.json`.
3. **`route_agg_column`** — adds `RouteAgg`, a canonical (direction-independent) route key so
   `A >> B` and `B >> A` are treated as the same route.
4. **`convert_fare_to_numeric`** — parses `Fare` (Brazilian comma-decimal) into a numeric column.
5. **`create_metrics_file`** — computes the seats-weighted average fare, weighted standard
   deviation and coefficient of variation per route/month; saves `fare_metrics_by_year.csv`.
6. **`deflate_metrics`** — joins the IPCA index and expresses fares in constant (most recent
   month's) purchasing power; saves `fare_metrics_by_year_deflated.csv`.
7. **`summarize_route_variability`** — aggregates across the whole period, per route, to show
   how much real fares actually moved over time; saves `route_fare_variability.csv`.

## Output files (`metrics_files/`)

- **`fare_metrics_by_year.csv`** — one row per route/month: `WeightedAverageFare`, `FareStdDev`,
  `TotalSeats`, `CoefficientVariation` (within-month fare dispersion).
- **`fare_metrics_by_year_deflated.csv`** — same as above, plus `WeightedAverageFareReal` and
  `FareStdDevReal`, adjusted for inflation via IPCA.
- **`route_fare_variability.csv`** — one row per route (both directions merged): average real
  fare, real fare std dev, min/max, months of data available, total seats, and coefficient of
  variation — i.e. how volatile that route's pricing has been across the whole period.

> Note on methodology: seats are treated as frequency weights (each seat represents a repeated
> observation of that fare), so standard deviations use the unbiased frequency-weighted
> estimator, not a population-weighted one. Confidence intervals were considered but ruled out
> for measuring fare variability — they describe uncertainty around the *mean* and shrink with
> sample size (seat count), rather than describing the actual spread of fares, which is what
> `FareStdDev`/`CoefficientVariation` capture directly.
