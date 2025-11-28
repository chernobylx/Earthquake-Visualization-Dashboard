import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data


class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input must be a pandas DataFrame"
        assert not df.empty, "Input DataFrame must not be empty"
        for col in ['lat', 'lon', 'mag', 'sig', 'depth', 'time']:
            assert col in df.columns, f"DataFrame must contain '{col}' column"
        
        col_types = {
            'lat': 'float64',
            'lon': 'float64',
            'mag': 'float64',
            'sig': 'int64',
            'depth': 'float64',
            'time': 'datetime64[ns, UTC]'
        }
        for col, expected_type in col_types.items():
            assert df[col].dtype == expected_type, f"Column '{col}' must be of type {expected_type}"
        #set internal dataframe
        self.df = df
