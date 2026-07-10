# Brazilian Airline Historical Fares Analysis

#### Frederico Horst

Analysis of Brazilian domestic airfares (2002–present), based on ANAC's (Brazil's civil aviation
regulator) historical fare series, adjusted for inflation using IBGE's IPCA index.

> **Methodology note**: [ANAC Resolution 140/2010](https://www.gov.br/anac/pt-br/assuntos/regulados/empresas-aereas/Instrucoes-para-a-elaboracao-e-apresentacao-das-demonstracoes-contabeis/base-de-dados-estatisticos-do-transporte-aereo)
> took effect in July 2010 and expanded ANAC's fare monitoring from a narrow panel of ~65 trunk
> routes (the "Fare Yield Report", Jan 2002–Sep 2009) to the full domestic network (2,000+ routes).
> Any analysis spanning both eras is comparing two different sampling methodologies, not a clean
> price signal over time — see the trend analysis in `airline_prices.ipynb` for how this is handled.

## Data Sources

- **Historical air fares** by origin, destination and airline: [ANAC downloads](https://sistemas.anac.gov.br/sas/downloads/view/frmDownload.aspx)
- **IPCA historical series** (Brazilian consumer price index, used to deflate fares to real values): [IBGE](https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html?=&t=series-historicas)
- More context on the fare data: [ANAC air transport market statistics](https://www.anac.gov.br/assuntos/dados-e-estatisticas/mercado-do-transporte-aereo)

## Goals

- Build a metrics database: weighted average fare, standard deviation and coefficient of
  variation, by route and month.
- Adjust historical fares for inflation (IPCA) so prices are comparable across years.
- Summarize how much real fares actually varied over the full historical period, per route.
- Test whether real fares show a statistically significant trend over time, accounting for the
  2010 methodology break and route-mix composition effects.

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
They're expected as `;`-delimited `.CSV` files, one per month (e.g. `200201.CSV`). ANAC has changed
the column header names and file encoding several times over the years (see `FilesProcessor.COLUMN_ALIASES`
in `files_processor.py`); `read_files()` normalizes all known variants automatically and raises a
clear error if it encounters an unrecognized header schema, rather than silently misaligning columns.

## Usage

```python
from files_processor import FilesProcessor

df, metrics, route_variability = FilesProcessor().process_files()
```

`process_files()` runs the full pipeline:

1. **`read_files`** — reads every monthly CSV in `csv_files_from_anac/`, normalizes each file's
   columns onto a canonical schema regardless of which header variant or encoding ANAC used that
   month, then concatenates them.
2. **`clean_dataframe`** — builds a `YearMonth` key and enriches origin/destination with airport
   names via `airports.json`; `Route` is built from the ICAO code, falling back to the airport's
   IATA code where `airports.json` has one, so routes to/from airports missing from that lookup
   are still included (just without a friendly 3-letter code).
3. **`route_agg_column`** — adds `RouteAgg`, a canonical (direction-independent) route key so
   `A >> B` and `B >> A` are treated as the same route.
4. **`convert_fare_to_numeric`** — parses `Fare` into a numeric column, handling both
   comma-decimal strings (most files) and already-numeric values (some months use period decimals
   or plain integers instead).
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
