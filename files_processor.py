##################################################################
# objetivo: limpar e ajustar os arquivos necessários para análise
##################################################################

import glob
import os
# import numpy 
import pandas

# def weighted_avg_and_std(values, weights):
#     import math
#     """
#     Return the weighted average and standard deviation.

#     They weights are in effect first normalized so that they 
#     sum to 1 (and so they must not all be 0).

#     values, weights -- NumPy ndarrays with the same shape.
#     """
#     average = numpy.average(values, weights=weights)
#     # Fast and numerically precise:
#     variance = numpy.average((values-average)**2, weights=weights)
#     return (average, math.sqrt(variance))

class FilesProcessor:
    def __init__(self):
        import json
        self.path = os.getcwd() + "/csv_files_from_anac/"
        self.dict_airports = json.load(open("airports.json", encoding='utf-8'))
        self.dict_airports = pandas.DataFrame(self.dict_airports)

    def read_files(self):
        df = pandas.concat((pandas.read_csv(f, delimiter=';', encoding='latin-1') for f in glob.glob(self.path + "*.CSV")), ignore_index=True)
        return df
        
    def clean_dataframe(self, df):
        """Cleans the dataframe by renaming columns and creating a YearMonth column."""
        # rename columns for better readability
        df.columns = ["Year", "Month", "Airline", "OriginICAO", "DestinationICAO", "Fare", "Seats"]
        # create a YearMonth column for easier time series analysis
        df["YearMonth"] = df["Year"].astype(str) + "-" + df["Month"].astype(str).str.zfill(2)
        # merge with airports data to get city names
        df = df.merge(self.dict_airports[['ICAO', 'Nome do Aeroporto', "IATA"]], left_on='OriginICAO', right_on='ICAO', how='left')
        df = df.rename(columns={'Nome do Aeroporto': 'OriginCity', "IATA": "Origin"})
        df = df.merge(self.dict_airports[['ICAO', 'Nome do Aeroporto', "IATA"]], left_on='DestinationICAO', right_on='ICAO', how='left')
        df = df.rename(columns={'Nome do Aeroporto': 'DestinationCity', "IATA": "Destination"})
        df = df.drop(columns=['ICAO_x', 'ICAO_y'])
        # create Route column for better analysis
        df["Route"] = df["Origin"] + " >> " + df["Destination"]
        # make sure Route is string for better analysis
        df["Route"] = df["Route"].astype(str)
        # order dataframe by Year and Month
        df = df.sort_values(by=["Year", "Month"]).reset_index(drop=True)
        return df
    
    def route_agg_column(self, df):
        """Creates a RouteAgg column that aggregates routes in both directions."""
        routes = df["Route"].unique()
        dict_RouteAgg = []
        RouteAgg = []
        for route in routes:
            x = str(route).split(" >> ")
            if x != ['nan', 'nan'] and x != ['nan']:
                route_invert =  f"{x[1]} >> {x[0]}"
                route_complete = [route, route_invert]
                RouteAgg.append(route_complete)
                dict_RouteAgg.append({"Route": route, "RouteAgg": route_complete})
        df_RouteAgg = pandas.DataFrame(dict_RouteAgg)
        df = df.merge(df_RouteAgg, left_on='Route', right_on='Route', how='left')
        return df

    def convert_fare_to_numeric(self, df):
        """Converts the Fare column to numeric, handling commas as decimal separators."""
        df["Fare"] = df["Fare"].str.replace(",", ".")  # Replace comma with dot for decimal
        df["Fare"] = pandas.to_numeric(df["Fare"], errors='coerce')
        return df
    
    def create_metrics_file(self, df):
        """
        Calculates the weighted average fare, weighted standard deviation and total seats for each route and month
        considering seats as weights for the average fare and standard deviation.
        """
        # transform the RouteAgg column to string to avoid issues with list comparison during groupby
        df["RouteAgg"] = df["RouteAgg"].apply(lambda x: ' >> '.join(x) if isinstance(x, list) else x)
        # TODO: review std dev weighted calculation
        metrics = df.groupby(['RouteAgg', 'Route', 'YearMonth']).apply(lambda x: pandas.Series({
            'WeightedAverageFare': (x['Fare'] * x['Seats']).sum() / x['Seats'].sum(),
            'FareStdDev': x['Fare'].std(),
            'TotalSeats': x['Seats'].sum()
        })).reset_index()

        # metrics.to_csv("airline_metrics.csv", index=False)

    def save_cleaned_dataframe(self, df, filename="cleaned_airline_prices.csv"):
        """Saves the cleaned dataframe to a CSV file."""
        df.to_csv(filename, index=False)

    def process_files(self):
        df = self.read_files()
        df = self.clean_dataframe(df)
        df = self.route_agg_column(df)
        df = self.convert_fare_to_numeric(df)
        # self.create_metrics_file(df)
        # self.save_cleaned_dataframe(df)
        return df
    

# class WeightedStatistics:
#     def __init__(self):
#         import pandas
#         import numpy
#         from scipy.stats.mstats import weightedquantile  # For weighted quantiles  


    
# # https://www.ancisoft.com/blog/using-describe-with-weighted-data-mean-standard-deviation-median-quantiles/