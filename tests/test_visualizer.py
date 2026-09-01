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


def heatmap_spec(color_var: str) -> dict:
    """The heatmap's compiled spec for a given cell metric."""
    dv = DataVisualizer(make_valid_df())
    heatmap = dv.create_heatmap(filters=[alt.selection_interval(name='test_brush')],
                                width=100, height=100, color_var=color_var)
    return heatmap.to_dict()


def heatmap_tooltip(color_var: str) -> list[dict]:
    """The heatmap's tooltip entries for a given cell metric."""
    return heatmap_spec(color_var)['encoding']['tooltip']


def location_row(color_var: str) -> list[dict]:
    return [t for t in heatmap_tooltip(color_var) if t.get('title') == 'Location']


def test_heatmap_names_the_strongest_quake_in_the_cell():
    spec = heatmap_spec('max(mag)')
    ops = [a for t in spec['transform'] if 'aggregate' in t for a in t['aggregate']]
    assert {'op': 'argmax', 'field': 'mag', 'as': '_winner'} in ops
    # The tooltip reads a field the aggregated rows actually carry.
    assert [t['field'] for t in location_row('max(mag)')] == ['location']
    assert {'calculate': 'datum._winner.place', 'as': 'location'} in spec['transform']


def test_heatmap_names_the_shallowest_quake_in_the_cell():
    ops = [a for t in heatmap_spec('min(depth)')['transform'] if 'aggregate' in t
           for a in t['aggregate']]
    assert {'op': 'argmin', 'field': 'depth', 'as': '_winner'} in ops
    assert location_row('min(depth)')


def test_heatmap_omits_location_for_a_mean():
    # No single record owns a mean, so there is nothing honest to point at.
    assert not location_row('mean(depth)')


def test_heatmap_omits_location_for_an_unaggregated_metric():
    assert not location_row('mag')


def test_heatmap_never_puts_an_argmax_in_an_encoding():
    """The form that renders "undefined" under Vega-Lite 6 (issue #27).

    Vega-Lite 5 compiles a tooltip {"aggregate": {"argmax": "mag"}, "field":
    "place"} to datum["argmax_mag"]["place"], but Vega-Lite 6 emits
    datum["place"] -- a field the aggregated rows do not have. Both front-ends
    render the same spec with different Vega majors, so the encoding-level form
    is simply not safe to use; the aggregation is spelled out in transforms
    instead. This guards the spec shape, not the pixels: only a browser can
    prove the tooltip reads right, so see docs/check_heatmap_tooltip.mjs.
    """
    for metric in ('max(mag)', 'min(depth)', 'mean(depth)', 'mag'):
        for entry in heatmap_tooltip(metric):
            assert not isinstance(entry.get('aggregate'), dict), \
                f'{metric} still uses an encoding-level argmin/argmax'


def test_heatmap_tooltips_report_the_bin_not_the_row():
    # A tooltip on a raw field lands in the aggregate's groupby, splitting each
    # cell by exact time and depth — the colour then is not the bin's extremum.
    for metric in ('mean(depth)', 'mag'):
        tooltips = heatmap_tooltip(metric)
        # `any`, not a lookup by field: with mean(depth) the metric tooltip is
        # on depth too, and only the axis one carries the bin.
        for axis_field in ('time', 'depth'):
            assert any(t.get('field') == axis_field and 'bin' in t for t in tooltips), \
                f'{metric} has no binned tooltip for {axis_field}'
    # The extremum path bins in transforms, so its tooltips read pre-binned
    # fields: the time bin's start, and a label spanning the quantitative bin.
    fields = [t.get('field') for t in heatmap_tooltip('max(mag)')]
    assert fields == ['location', 'x_date', '_y_label', 'metric']
