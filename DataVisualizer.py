import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data


class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input must be a pandas DataFrame"
        assert not df.empty, "Input DataFrame must not be empty"
        #set internal dataframe
        self.df = df
