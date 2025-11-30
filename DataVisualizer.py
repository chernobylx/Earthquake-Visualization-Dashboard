import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data
from DataLoader import COL_TYPES


class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input must be a pandas DataFrame"
        assert not df.empty, "Input DataFrame must not be empty"
        for col in COL_TYPES.keys():
            assert col in df.columns, f"DataFrame must contain '{col}' column"
        
        
        for col, expected_type in COL_TYPES.items():
            assert df[col].dtype == expected_type, f"Column '{col}' must be of type {expected_type}"
        #set internal dataframe
        self.df = df
