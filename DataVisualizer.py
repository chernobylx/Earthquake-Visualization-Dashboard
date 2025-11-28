import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data


class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        #set internal dataframe
        self.df = df
