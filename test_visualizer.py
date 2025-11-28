import pytest
import pandas as pd
from DataVisualizer import DataVisualizer

def test_invalid_input_not_dataframe():
    with pytest.raises(AssertionError, match="Input must be a pandas DataFrame"):
        DataVisualizer("not a dataframe")

def test_empty_dataframe():
    empty_df = pd.DataFrame()
    with pytest.raises(AssertionError, match="Input DataFrame must not be empty"):
        DataVisualizer(empty_df)

def test_missing_required_columns():
    df = pd.DataFrame({
        'lat': [34.05],
        'lon': [-118.25],
        'mag': [4.5],
        # 'sig' column is missing
        'depth': [10.0],
        'time': [pd.Timestamp('2023-01-01T00:00:00Z')]
    })
    with pytest.raises(AssertionError, match="DataFrame must contain 'sig' column"):
        DataVisualizer(df)