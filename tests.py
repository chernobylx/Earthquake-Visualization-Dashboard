import pytest
import pandas as pd
from DataVisualizer import DataVisualizer

def test_invalid_input_not_dataframe():
    with pytest.raises(AssertionError, match="Input must be a pandas DataFrame"):
        DataVisualizer("not a dataframe")

