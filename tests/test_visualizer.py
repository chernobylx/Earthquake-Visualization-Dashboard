import altair as alt
import pandas as pd
import pytest

from earthquake_dashboard.data_loader import COL_TYPES
from earthquake_dashboard.visualizer import DataVisualizer


def make_valid_df() -> pd.DataFrame:
    """Build a minimal DataFrame with every column and dtype the visualizer requires."""
    df = pd.DataFrame({
        'place': ['3 km SE of Perry, Oklahoma', '13 km WSW of Searles Valley, CA'],
        'time': pd.to_datetime(['2023-01-01T00:00:00Z', '2023-06-15T12:30:00Z'], utc=True),
        'lat': [36.2709, 35.7045],
        'lon': [-97.2576, -117.524],
        'mag': [4.5, 5.1],
        'sig': [311, 400],
        'depth': [7.28, 2.75],
        'tsunami': [False, True],
        'cdi': [3.4, 5.6],
        'alert': ['green', 'yellow'],
    })
    return df.astype({'sig': 'int64'})


def test_valid_dataframe_accepted():
    dv = DataVisualizer(make_valid_df())
    assert list(dv.df.columns) == list(COL_TYPES.keys())


def test_invalid_input_not_dataframe():
    with pytest.raises(AssertionError, match="Input must be a pandas DataFrame"):
        DataVisualizer("not a dataframe")


def test_empty_dataframe():
    empty_df = pd.DataFrame()
    with pytest.raises(AssertionError, match="Input DataFrame must not be empty"):
        DataVisualizer(empty_df)


def test_missing_required_columns():
    df = make_valid_df().drop(columns=['sig'])
    with pytest.raises(AssertionError, match="DataFrame must contain 'sig' column"):
        DataVisualizer(df)


def test_incorrect_column_types():
    df = make_valid_df()
    df['sig'] = ['high', 'low']  # should be int64
    with pytest.raises(AssertionError, match="Column 'sig' must be of type int64"):
        DataVisualizer(df)


def test_create_chart_returns_spec():
    dv = DataVisualizer(make_valid_df())
    chart = dv.create_chart(filter_vars=['mag', 'depth'])
    spec = chart.to_dict()
    assert 'hconcat' in spec or 'vconcat' in spec


def heatmap_tooltip(color_var: str) -> list[dict]:
    """The heatmap's tooltip entries for a given cell metric."""
    dv = DataVisualizer(make_valid_df())
    heatmap = dv.create_heatmap(filters=[alt.selection_interval(name='test_brush')],
                                width=100, height=100, color_var=color_var)
    return heatmap.to_dict()['encoding']['tooltip']


def test_heatmap_names_the_strongest_quake_in_the_cell():
    place = [t for t in heatmap_tooltip('max(mag)') if t['field'] == 'place']
    assert place == [{'aggregate': {'argmax': 'mag'},
                      'field': 'place',
                      'title': 'Location',
                      'type': 'nominal'}]


def test_heatmap_names_the_shallowest_quake_in_the_cell():
    place = [t for t in heatmap_tooltip('min(depth)') if t['field'] == 'place']
    assert place[0]['aggregate'] == {'argmin': 'depth'}


def test_heatmap_omits_location_for_a_mean():
    # No single record owns a mean, so there is nothing honest to point at.
    assert not [t for t in heatmap_tooltip('mean(depth)') if t['field'] == 'place']


def test_heatmap_omits_location_for_an_unaggregated_metric():
    assert not [t for t in heatmap_tooltip('mag') if t['field'] == 'place']


def test_heatmap_tooltips_repeat_the_bins():
    # A tooltip on a raw field lands in the aggregate's groupby, splitting each
    # cell by exact time and depth — the colour then is not the bin's extremum.
    binned = {t.get('field'): t for t in heatmap_tooltip('max(mag)')
              if t.get('field') in ('time', 'depth')}
    assert 'bin' in binned['time']
    assert 'bin' in binned['depth']
