##################################################################
# objetivo: limpar e ajustar os arquivos necessários para análise
##################################################################

import glob
import os
import unicodedata
# import numpy
import pandas

class FilesProcessor:
    CANONICAL_COLUMNS = ["Year", "Month", "Airline", "OriginICAO", "DestinationICAO", "Fare", "Seats"]

    # ANAC has changed the CSV header schema several times across the historical series
    # (e.g. ANO vs. "Ano de Referência" vs. nr_ano_referencia); every known variant is
    # mapped onto CANONICAL_COLUMNS here, keyed by an accent-stripped, lowercased header.
    COLUMN_ALIASES = {
        'ano': 'Year', 'ano de referencia': 'Year', 'nr_ano_referencia': 'Year',
        'mes': 'Month', 'mes de referencia': 'Month', 'nr_mes_referencia': 'Month',
        'empresa': 'Airline', 'icao empresa aerea': 'Airline', 'sg_empresa_icao': 'Airline',
        'origem': 'OriginICAO', 'icao aerodromo origem': 'OriginICAO', 'sg_icao_origem': 'OriginICAO',
        'destino': 'DestinationICAO', 'icao aerodromo destino': 'DestinationICAO', 'sg_icao_destino': 'DestinationICAO',
        'tarifa': 'Fare', 'tarifa-n': 'Fare', 'nr_tarifa': 'Fare',
        'assentos': 'Seats', 'assentos comercializados': 'Seats', 'nr_assentos': 'Seats',
    }

    def __init__(self):
        import json
        self.path = os.getcwd() + "/csv_files_from_anac/"
        self.dict_airports = json.load(open("airports.json", encoding='utf-8'))
        self.dict_airports = pandas.DataFrame(self.dict_airports)

    @staticmethod
    def _strip_accents(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

    @classmethod
    def _normalize_columns(cls, df, source_file):
        """Renames a raw ANAC file's columns to CANONICAL_COLUMNS regardless of which
        header schema it was downloaded with, and drops any stray extra columns (e.g. a
        leftover row-index column present in a few files)."""
        rename = {}
        for col in df.columns:
            key = cls._strip_accents(str(col)).strip().strip('"').lower()
            if key in cls.COLUMN_ALIASES:
                rename[col] = cls.COLUMN_ALIASES[key]
        if sorted(rename.values()) != sorted(cls.CANONICAL_COLUMNS):
            raise ValueError(f"{source_file}: unrecognized column schema {list(df.columns)}")
        return df.rename(columns=rename)[cls.CANONICAL_COLUMNS]

    @staticmethod
    def _read_single_file(path):
        # most files are Latin-1; a few were re-exported as UTF-8 with a BOM
        try:
            return pandas.read_csv(path, delimiter=';', encoding='utf-8-sig')
        except UnicodeDecodeError:
            return pandas.read_csv(path, delimiter=';', encoding='latin-1')

    def read_files(self):
        frames = []
        for f in sorted(glob.glob(self.path + "*.CSV")):
            frame = self._read_single_file(f)
            frames.append(self._normalize_columns(frame, f))
        df = pandas.concat(frames, ignore_index=True)
        return df

    def clean_dataframe(self, df):
        """Cleans the dataframe by creating a YearMonth column and enriching with airport names."""
        # create a YearMonth column for easier time series analysis
        df["YearMonth"] = df["Year"].astype(str) + "-" + df["Month"].astype(str).str.zfill(2)
        # merge with airports data to get city names (airports.json only covers a subset of
        # the ICAO codes seen in the fare data, so this enrichment can be NaN for a given row)
        df = df.merge(self.dict_airports[['ICAO', 'Nome do Aeroporto', "IATA"]], left_on='OriginICAO', right_on='ICAO', how='left')
        df = df.rename(columns={'Nome do Aeroporto': 'OriginCity', "IATA": "Origin"})
        df = df.merge(self.dict_airports[['ICAO', 'Nome do Aeroporto', "IATA"]], left_on='DestinationICAO', right_on='ICAO', how='left')
        df = df.rename(columns={'Nome do Aeroporto': 'DestinationCity', "IATA": "Destination"})
        df = df.drop(columns=['ICAO_x', 'ICAO_y'])
        # build Route from the IATA code where airports.json has it, falling back to the ICAO
        # code otherwise, so route identity never depends on airports.json's coverage and no
        # fare data is silently dropped for airports it doesn't list
        df["Route"] = df["Origin"].fillna(df["OriginICAO"]) + " >> " + df["Destination"].fillna(df["DestinationICAO"])
        # order dataframe by Year and Month
        df = df.sort_values(by=["Year", "Month"]).reset_index(drop=True)
        return df
    
    def route_agg_column(self, df):
        """Creates a RouteAgg column that aggregates routes in both directions using a canonical, order-independent key."""
        routes = df["Route"].unique()
        dict_RouteAgg = []
        for route in routes:
            x = str(route).split(" >> ")
            if x != ['nan', 'nan'] and x != ['nan']:
                route_agg = " >> ".join(sorted(x))
                dict_RouteAgg.append({"Route": route, "RouteAgg": route_agg})
        df_RouteAgg = pandas.DataFrame(dict_RouteAgg)
        df = df.merge(df_RouteAgg, left_on='Route', right_on='Route', how='left')
        return df

    def convert_fare_to_numeric(self, df):
        """Converts the Fare column to numeric, handling comma-decimal strings (most files)
        as well as already-numeric values (some months' files use period decimals or plain
        integers instead of commas, which makes pandas infer that single file's Fare column
        as numeric before concatenation)."""
        df["Fare"] = df["Fare"].astype(str).str.replace(",", ".")  # Replace comma with dot for decimal
        df["Fare"] = pandas.to_numeric(df["Fare"], errors='coerce')
        return df
    
    @staticmethod
    def weighted_average(values, weights):
        """Returns the average of values weighted by weights (e.g. Seats)."""
        return (values * weights).sum() / weights.sum()

    @staticmethod
    def weighted_std(values, weights):
        """
        Returns the standard deviation of values weighted by weights, treating
        weights as frequency weights (e.g. Seats represents repeated observations
        of the same fare), using the unbiased frequency-weights estimator.
        """
        average = FilesProcessor.weighted_average(values, weights)
        variance = (weights * (values - average) ** 2).sum() / (weights.sum() - 1)
        return variance ** 0.5

    def create_metrics_file(self, df, filename="fare_metrics_by_year.csv"):
        """
        Calculates the weighted average fare, weighted standard deviation and total seats for each route and month
        considering seats as weights for the average fare and standard deviation, and saves the result to a CSV file.
        """
        metrics = df.groupby(['RouteAgg', 'Route', 'YearMonth']).apply(lambda x: pandas.Series({
            'WeightedAverageFare': self.weighted_average(x['Fare'], x['Seats']),
            'FareStdDev': self.weighted_std(x['Fare'], x['Seats']),
            'TotalSeats': x['Seats'].sum()
        })).reset_index()
        # scale-invariant, so it's the same whether computed on nominal or deflated fares
        metrics['CoefficientVariation'] = metrics['FareStdDev'] / metrics['WeightedAverageFare']

        path_to_file = os.getcwd() + "/metrics_files/" + filename
        metrics.to_csv(path_to_file, index=False)
        return metrics

    def read_ipca(self, path="ipca_historico.csv"):
        """Reads the IPCA historical series and returns it as YearMonth + Index columns."""
        ipca = pandas.read_csv(path, delimiter=';', encoding='utf-8')
        ipca = ipca.rename(columns={
            "Período": "YearMonth",
            "Número Índice (Dez/93 = 100)": "IPCAIndex"
        })
        ipca["YearMonth"] = ipca["YearMonth"].astype(str).str[:4] + "-" + ipca["YearMonth"].astype(str).str[4:]
        return ipca[["YearMonth", "IPCAIndex"]]

    def deflate_metrics(self, metrics, base_yearmonth=None, filename="fare_metrics_by_year_deflated.csv"):
        """
        Deflates WeightedAverageFare and FareStdDev to constant prices using the IPCA index,
        expressing every fare in terms of the purchasing power of base_yearmonth (defaults to
        the most recent month present in metrics). FareStdDev is deflated by the same factor
        as the average since it shares the same currency units; TotalSeats is left untouched.
        """
        ipca = self.read_ipca()
        if base_yearmonth is None:
            base_yearmonth = metrics["YearMonth"].max()
        base_index = ipca.loc[ipca["YearMonth"] == base_yearmonth, "IPCAIndex"].iloc[0]

        metrics = metrics.merge(ipca, on="YearMonth", how="left")
        deflation_factor = base_index / metrics["IPCAIndex"]
        metrics["WeightedAverageFareReal"] = metrics["WeightedAverageFare"] * deflation_factor
        metrics["FareStdDevReal"] = metrics["FareStdDev"] * deflation_factor

        path_to_file = os.getcwd() + "/metrics_files/" + filename
        metrics.to_csv(path_to_file, index=False)
        return metrics

    def summarize_route_variability(self, metrics, filename="route_fare_variability.csv"):
        """
        Summarizes real (inflation-adjusted) fare variability per route across the whole
        period available, weighting each month's fare by its seat volume. This captures how
        much fares actually moved over time for a route, as opposed to FareStdDev/
        CoefficientVariation in the metrics file, which only describe within-month dispersion.
        """
        summary = metrics.groupby('RouteAgg').apply(lambda x: pandas.Series({
            'AverageFareReal': self.weighted_average(x['WeightedAverageFareReal'], x['TotalSeats']),
            'FareRealStdDev': self.weighted_std(x['WeightedAverageFareReal'], x['TotalSeats']),
            'MinFareReal': x['WeightedAverageFareReal'].min(),
            'MaxFareReal': x['WeightedAverageFareReal'].max(),
            'MonthsAvailable': x['YearMonth'].nunique(),
            'TotalSeats': x['TotalSeats'].sum()
        })).reset_index()
        summary['CoefficientVariation'] = summary['FareRealStdDev'] / summary['AverageFareReal']

        path_to_file = os.getcwd() + "/metrics_files/" + filename
        summary.to_csv(path_to_file, index=False)
        return summary

    def save_cleaned_dataframe(self, df, filename="cleaned_airline_prices.csv"):
        """Saves the cleaned dataframe to a CSV file."""
        df.to_csv(filename, index=False)

    def process_files(self):
        df = self.read_files()
        df = self.clean_dataframe(df)
        df = self.route_agg_column(df)
        df = self.convert_fare_to_numeric(df)
        metrics = self.create_metrics_file(df)
        metrics = self.deflate_metrics(metrics)
        route_variability = self.summarize_route_variability(metrics)
        # self.save_cleaned_dataframe(df)
        return df, metrics, route_variability