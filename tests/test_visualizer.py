import json
import re
from datetime import timedelta

import altair as alt
import pandas as pd
import pytest

from earthquake_dashboard.data_loader import COL_TYPES
from earthquake_dashboard.visualizer import (
    DARK_INK,
    LIGHT_INK,
    MUTED_INK,
    OPACITY_FLOOR,
    DataVisualizer,
    ink_for,
    time_bin,
)


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
        'url': ['https://earthquake.usgs.gov/earthquakes/eventpage/ok2023a',
                'https://earthquake.usgs.gov/earthquakes/eventpage/ci2023b'],
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


def test_string_dtype_columns_accepted():
    """The molab failure: a widget hands back `string`, not `object` (#42).

    marimo's dataframe widget returns the text columns in pandas' string dtype
    rather than object, and the old check compared dtypes by string equality, so
    `'string' != 'object'` rejected a frame holding exactly the right values —
    "Column 'place' must be of type object" — and the chart never drew.
    """
    df = make_valid_df().astype({'place': 'string', 'alert': 'string'})
    assert str(df['place'].dtype) == 'string'      # not 'object'
    dv = DataVisualizer(df)                        # must not raise
    assert list(dv.df.columns) == list(COL_TYPES.keys())


def test_mostly_null_object_column_accepted():
    """USGS leaves `alert` null for most events, and that must stay valid.

    A first cut at the tolerant check used `is_string_dtype` alone, which infers
    an object column's contents — an all-null `alert` reads False, so a real
    frame was rejected with the self-contradicting "must be of type object, got
    object". Synthetic all-string test data never showed it; the live app did.
    """
    df = make_valid_df()
    df['alert'] = [None, None]
    assert str(df['alert'].dtype) == 'object'
    DataVisualizer(df)                             # must not raise


def test_dtype_check_still_rejects_a_wrong_kind():
    """Tolerating string dtypes must not tolerate everything."""
    df = make_valid_df()
    df['mag'] = df['mag'].astype(str)              # floats as text
    with pytest.raises(AssertionError, match="Column 'mag' must be of type float64"):
        DataVisualizer(df)


def test_naive_time_rejected():
    """`time` still has to carry a timezone; the front-ends re-localise for this."""
    df = make_valid_df()
    df['time'] = df['time'].dt.tz_localize(None)
    with pytest.raises(AssertionError, match="Column 'time' must be of type"):
        DataVisualizer(df)


def test_incorrect_column_types():
    df = make_valid_df()
    df['sig'] = ['high', 'low']  # should be int64
    with pytest.raises(AssertionError, match="Column 'sig' must be of type int64"):
        DataVisualizer(df)


def test_map_brush_cross_filters_the_heatmap():
    """Dragging on the globe must narrow the heatmap, like the histograms do.

    The map's marks are placed by longitude/latitude through a projection, so
    the selection has no invertible scale to project onto and Vega-Lite compiles
    it to vlSelectionIdTest -- an identity match on Vega's internal _vgsid_
    rather than a range test on a field. That works only while the heatmap's
    rows carry the same ids as the map's, which the next test pins down.
    """
    spec = DataVisualizer(make_valid_df()).create_chart(filter_vars=['mag', 'depth'])
    heatmap = [v for v in spec.to_dict()['hconcat'] if 'transform' in v]
    predicates = json.dumps([v['transform'] for v in heatmap])
    assert 'mag_brush' in predicates      # the histogram brushes cross-filter
    assert '"brush"' in predicates        # and so does the map brush


def test_the_heatmap_and_the_map_read_the_same_dataset():
    """The precondition for the map brush's id match.

    vlSelectionIdTest compares datum._vgsid_ against the ids Vega stored for the
    marks inside the box, and Vega assigns those ids in an `identifier`
    transform on one dataset. The match therefore holds only while the heatmap's
    rows and the map's rows descend from that same dataset. They do today --
    every view is built from `alt.Chart(self.df)`, which altair serialises to a
    single named dataset -- but nothing in the spec enforces it, and giving
    either stream its own copy would empty the heatmap on every map drag while
    still compiling cleanly.
    """
    spec = DataVisualizer(make_valid_df()).create_chart(filter_vars=['mag', 'depth']).to_dict()

    def data_names(node, path=''):
        found = {}
        if isinstance(node, dict):
            data = node.get('data')
            if isinstance(data, dict) and 'name' in data:
                found[path] = data['name']
            for key in ('hconcat', 'vconcat', 'layer'):
                for i, child in enumerate(node.get(key, [])):
                    found.update(data_names(child, f'{path}/{key}[{i}]'))
        return found

    names = data_names(spec)
    heatmap = [n for path, n in names.items() if path.startswith('/hconcat[1]')]
    quakes = [n for path, n in names.items() if path.startswith('/hconcat[0]/vconcat[0]')]
    assert heatmap and quakes, f'expected both views to name a dataset, got {names}'
    assert set(heatmap) == set(quakes), (
        f'heatmap reads {heatmap} but the map reads {quakes}; _vgsid_ would not '
        'line up and the map brush would empty the heatmap'
    )


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


# --- #29: the time bin step must never floor to zero -------------------------

DAY_MS = 24 * 60 * 60 * 1000


def frame_spanning(days: float, rows: int = 40) -> pd.DataFrame:
    """A valid frame whose `time` column spans exactly `days`."""
    start = pd.Timestamp('2026-09-01T00:00:00Z')
    times = [start + timedelta(seconds=days * 86400 * i / max(rows - 1, 1))
             for i in range(rows)]
    df = pd.DataFrame({
        'place': [f'{i} km N of Somewhere' for i in range(rows)],
        'time': pd.to_datetime(times, utc=True),
        'lat': [1.0 * i for i in range(rows)],
        'lon': [-1.0 * i for i in range(rows)],
        'mag': [1.0 + (i % 7) for i in range(rows)],
        'sig': [10 * i for i in range(rows)],
        'depth': [1.0 * (i % 600) for i in range(rows)],
        'tsunami': [i % 2 == 0 for i in range(rows)],
        'cdi': [1.0 * (i % 9) for i in range(rows)],
        'alert': ['green' if i % 2 else None for i in range(rows)],
        'url': [f'https://earthquake.usgs.gov/earthquakes/eventpage/e{i}'
                for i in range(rows)],
    })
    return df.astype({'sig': 'int64'})


def bin_steps(spec: dict) -> list[int]:
    """Every bin step in a compiled chart spec, however it is spelled."""
    return [int(s) for s in re.findall(r'"step":\s*(\d+)', json.dumps(spec))]


@pytest.mark.parametrize('days', [30, 45, 100, 365])
def test_long_spans_keep_exactly_the_step_they_had(days):
    """The fix is a floor, not a re-binning.

    Anything twelve days or wider must come out byte-identical to the original
    `int(n_days / 12) * day`, so the shipped 30-day default still bins at two
    days. A difference here is a deliberate change to existing charts, not a
    bug fix, and belongs in the issue before it belongs in the code.
    """
    step, _ = time_bin(timedelta(days=days))
    assert step == int(days / 12) * DAY_MS


def test_the_shipped_default_still_bins_at_two_days():
    step, _ = time_bin(timedelta(days=30))
    assert step == 172_800_000


@pytest.mark.parametrize('days', [0, 0.5, 3, 7, 11.9])
def test_short_spans_never_emit_a_zero_step(days):
    """`"bin": {"step": 0}` compiles cleanly and Vega then ignores it.

    It does not error and it does not draw nothing -- it derives bins from the
    data extent instead, which puts the edges at arbitrary times of day and
    makes them move again whenever a brush narrows the data (#29).
    """
    spec = DataVisualizer(frame_spanning(days)).create_chart(
        filter_vars=['time', 'mag']).to_dict()
    steps = bin_steps(spec)
    assert steps, 'expected the chart to declare at least one bin step'
    assert 0 not in steps, f'span of {days} days still emits a zero step: {steps}'


def test_the_heatmap_and_the_time_histogram_agree_on_the_step():
    """Both axes sized the same span the same way, from one helper.

    They used to hold a verbatim copy of the calculation each, which is how the
    two could disagree about where a day starts.
    """
    dv = DataVisualizer(frame_spanning(7))
    heatmap = dv.create_heatmap(filters=[alt.selection_interval(name='b')],
                                width=100, height=100)
    hists, _ = dv.create_hists_selectors(['time'], 100, 40)
    assert set(bin_steps(heatmap.to_dict())) & set(bin_steps(hists['time'].to_dict()))


def test_a_zero_span_frame_bins_at_the_floor():
    """Every row sharing a timestamp must not divide its way to nothing."""
    df = frame_spanning(0)
    assert df['time'].max() == df['time'].min()
    step, _ = time_bin(timedelta(0))
    assert step == 60_000


@pytest.mark.parametrize(('days', 'wants_hours'), [(0.5, True), (7, True), (30, False), (365, False)])
def test_the_axis_format_shows_hours_exactly_when_the_step_is_sub_day(days, wants_hours):
    step, fmt = time_bin(timedelta(days=days))
    assert ('%H' in fmt) is wants_hours
    assert (step < DAY_MS) is wants_hours


# --- chart text must be readable on the chart's own background ---------------

def test_ink_for_reads_hex_rgb_and_names():
    """The canvas colour is whatever the user typed into the front-end's box."""
    for dark in ['#16121d', '#000', 'rgb(26,26,26)', 'rgba(19,16,25,0.9)', 'black', 'darkblue']:
        assert ink_for(dark) == LIGHT_INK, f'{dark} should take light text'
    for light in ['#ffffff', '#eee', 'rgb(240,240,240)', 'white', 'lightgrey']:
        assert ink_for(light) == DARK_INK, f'{light} should take dark text'


def test_ink_for_falls_back_to_light_on_an_unparseable_colour():
    """Every front-end here ships dark, so light is the safer guess.

    Stated as a test because the alternative -- leaving Vega's default -- is
    black text, which is the bug this whole thing exists to fix.
    """
    assert ink_for('rebeccapurple-ish nonsense') == LIGHT_INK
    assert ink_for(None) == LIGHT_INK


def test_the_chart_never_leaves_its_text_at_vegas_black_default():
    """167 text nodes rendered #000 on a #16121d canvas before this existed."""
    spec = DataVisualizer(make_valid_df()).create_chart(
        filter_vars=['mag'], background='#16121d').to_dict()
    config = spec.get('config', {})
    assert config['axis']['labelColor'] == MUTED_INK
    assert config['axis']['titleColor'] == LIGHT_INK
    assert config['legend']['labelColor'] == MUTED_INK
    assert config['title']['color'] == LIGHT_INK
    assert '#000' not in json.dumps(config)


def test_a_light_canvas_gets_dark_chart_text():
    spec = DataVisualizer(make_valid_df()).create_chart(
        filter_vars=['mag'], background='white').to_dict()
    assert spec['config']['axis']['titleColor'] == DARK_INK


def layers(node):
    """Every view in a composed spec, including the layers inside a map."""
    if isinstance(node, dict):
        yield node
        for key in ('hconcat', 'vconcat', 'layer'):
            for child in node.get(key, []):
                yield from layers(child)


def point_spec(**kwargs) -> dict:
    """The compiled spec for the map's earthquake points.

    Found by its mark rather than by its position in the concatenation, so
    rearranging the views does not silently start testing the basemap.
    """
    spec = DataVisualizer(make_valid_df()).create_chart(
        filter_vars=['mag'], **kwargs).to_dict()
    points = [v for v in layers(spec)
              if (v.get('mark') if isinstance(v.get('mark'), str)
                  else (v.get('mark') or {}).get('type')) == 'circle']
    assert len(points) == 1, f'expected one circle layer, found {len(points)}'
    return points[0]


def point_tooltip() -> dict:
    """The point tooltip, keyed by the label each row shows."""
    return {row['title']: row for row in point_spec()['encoding']['tooltip']}


def test_the_point_tooltip_gives_the_time_to_the_second_in_utc():
    """A bare temporal tooltip reads "Jan 1, 2023" in the browser's own zone.

    Every date in this app is UTC -- the pickers say so -- and an event's
    identity is its moment, not its day, so the tooltip formats the instant
    itself with utcFormat rather than letting Vega render it locally.
    """
    assert utc_time_calculation()['calculate'].count('%H:%M:%S') == 1
    assert point_tooltip()['Time (UTC)']['type'] == 'nominal', \
        'a temporal field would render in the browser\'s zone, and to the day'


def utc_time_calculation() -> dict:
    """The transform that builds the field the Time (UTC) tooltip row reads.

    Found by following the tooltip's own field rather than by scanning for
    `utcFormat` anywhere on the layer. Checking the two halves separately let a
    rename on one side alone pass: altair does not verify that an explicitly
    typed field exists, so the tooltip would point at a field no transform
    produces and the row would render empty while the suite stayed green.
    """
    spec = point_spec()
    field = point_tooltip()['Time (UTC)']['field']
    written = [t for t in spec['transform'] if t.get('as') == field and 'calculate' in t]
    assert len(written) == 1, (
        f'the Time (UTC) tooltip reads {field!r}, which no transform on this '
        f"layer creates: {[t.get('as') for t in spec['transform']]}"
    )
    assert 'utcFormat' in written[0]['calculate'], (
        f"{field} is not built with utcFormat: {written[0]['calculate']}"
    )
    return written[0]


def test_the_utc_time_calculation_survives_a_csv_source():
    """marimo serves the frame as a CSV, where `time` arrives as a string.

    utcFormat over a string returns nothing useful, so the calculation converts
    first. Dash inlines typed JSON and would not have shown this.
    """
    assert 'toDate(' in utc_time_calculation()['calculate']


def test_the_point_tooltip_gives_coordinates_to_four_decimals():
    tooltip = point_tooltip()
    assert tooltip['Latitude']['field'] == 'lat'
    assert tooltip['Longitude']['field'] == 'lon'
    # Four decimals is about eleven metres, and what USGS itself reports.
    assert tooltip['Latitude']['format'] == '.4f'
    assert tooltip['Longitude']['format'] == '.4f'


def test_the_point_tooltip_carries_the_usgs_url():
    assert point_tooltip()['USGS']['field'] == 'url'


def test_clicking_a_point_opens_its_usgs_event_page():
    """A Vega tooltip is plain text, so the URL in it cannot be clicked.

    The href channel is what makes the mark itself a link, which is the only
    way a Vega-Lite spec can offer one.
    """
    assert point_spec()['encoding']['href']['field'] == 'url'


def test_the_faintest_earthquake_is_still_visible():
    """0.1 is a floor in name only: on this canvas the point disappears."""
    low, high = point_spec()['encoding']['opacity']['scale']['range']
    assert low == OPACITY_FLOOR
    assert low >= 0.35
    assert high == 1


def test_the_opacity_floor_can_be_raised_by_a_caller():
    low, high = point_spec(opacity_range=(0.6, 0.9))['encoding']['opacity']['scale']['range']
    assert (low, high) == (0.6, 0.9)


def test_a_point_link_opens_beside_the_dashboard():
    """Navigating this tab to USGS would throw the session away.

    The loaded records, every histogram brush and the rendered chart all live in
    the page, so a link that replaces it costs the user their whole query. Vega
    resolves an href through its loader, and the loader's target defaults to the
    current tab, so the spec has to say otherwise. It says so in usermeta, which
    vega-embed reads -- that reaches Dash and marimo alike, where a front-end's
    own embed options would only ever fix one of them.
    """
    spec = DataVisualizer(make_valid_df()).create_chart(filter_vars=['mag']).to_dict()
    assert spec['usermeta']['embedOptions']['loader']['target'] == '_blank'
