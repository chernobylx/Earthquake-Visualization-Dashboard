"""A CSV data source has no types unless the spec says so.

marimo serves the dataframe as a CSV URL rather than inlining it, and Vega
applies no type inference to a CSV without an explicit format.parse. Vega-Lite
fills the gap only for fields it encodes itself, so `time` gets parsed in the
map and histogram streams but not in the heatmap's, which converts with its own
toDate() calculate and therefore leaves Vega-Lite nothing to infer from. In the
running notebook the heatmap's rows carried
    {"mag": "5.4", "depth": "10.0", "time": "2026-09-10T18:21:18.934000+00:00"}
so brushing the time histogram compared an ISO string against the store's epoch
milliseconds, coerced to NaN, dropped every row and emptied the heatmap -- and
max(mag) was a lexicographic max over strings ("9.9" beats "10.0"). Dash never
saw either bug because it inlines the data as typed JSON.

COL_TYPES already states what each column is, so the parse map comes from there.
"""
from earthquake_dashboard.data_loader import COL_TYPES, vega_parse


def test_every_non_string_column_is_parsed():
    parse = vega_parse()
    for col, dtype in COL_TYPES.items():
        if dtype == 'object':
            assert col not in parse, f"{col} is text; Vega needs no parse for it"
        else:
            assert col in parse, f"{col} ({dtype}) would arrive as a string"


def test_parse_kinds_are_vega_kinds():
    assert vega_parse() == {
        'time': 'date',
        'lat': 'number',
        'lon': 'number',
        'mag': 'number',
        'sig': 'number',
        'depth': 'number',
        'tsunami': 'boolean',
        'cdi': 'number',
    }


def test_parse_covers_the_fields_the_heatmap_bins_and_aggregates():
    """The blank heatmap and the lexicographic colour scale, specifically."""
    parse = vega_parse()
    assert parse['time'] == 'date'      # the filter predicate that emptied it
    assert parse['mag'] == 'number'     # max(mag) as a number, not a string
    assert parse['depth'] == 'number'   # the y bin


def test_a_transformer_can_be_wrapped_through_the_public_registry():
    """The notebook wraps marimo's transformer to add the parse map.

    register() takes (name, value) and is not a decorator -- using it as one
    raised TypeError at notebook import and left every cell unrun.
    """
    import altair as alt

    alt.data_transformers.register(
        'probe_inner', lambda data, **kw: {'url': 'u', 'format': {'type': 'csv'}})
    alt.data_transformers.enable('probe_inner')
    inner = alt.data_transformers.get()
    assert callable(inner)

    def outer(data, **kwargs):
        spec = inner(data, **kwargs)
        spec.setdefault('format', {})['parse'] = vega_parse()
        return spec

    alt.data_transformers.register('probe_outer', outer)
    alt.data_transformers.enable('probe_outer')
    spec = alt.data_transformers.get()(None)
    assert spec['format']['type'] == 'csv'
    assert spec['format']['parse']['time'] == 'date'
    alt.data_transformers.enable('default')


def test_a_per_call_url_splits_the_views_and_memoising_does_not():
    """Why the notebook memoises its transformer.

    create_chart builds one alt.Chart per view. marimo's transformer mints a
    fresh virtual file every time it runs, so each view got its own URL and
    therefore its own Vega source node -- and Vega numbers rows from one global
    counter across nodes, so those nodes hold disjoint _vgsid_ ranges. The map
    brush compiles to vlSelectionIdTest (a projection has no invertible scale
    for an interval to project onto), so it matched nothing outside the map and
    dragging on the globe emptied the heatmap. Returning one URL per distinct
    frame puts every view back on one identified source.
    """
    import itertools

    import altair as alt
    import pandas as pd

    from earthquake_dashboard.visualizer import DataVisualizer

    df = pd.DataFrame({
        'place': ['a', 'b'], 'time': pd.to_datetime(['2023-01-01', '2023-06-15'], utc=True),
        'lat': [1.0, 2.0], 'lon': [3.0, 4.0], 'mag': [4.5, 5.1], 'sig': [311, 400],
        'depth': [7.0, 2.0], 'tsunami': [False, True], 'cdi': [3.4, 5.6],
        'alert': ['green', 'yellow'],
    }).astype({'sig': 'int64'})

    def urls_in(spec, path='', found=None):
        found = {} if found is None else found
        if isinstance(spec, dict):
            data = spec.get('data')
            # The map's basemap is a topojson URL from vega-datasets; only the
            # frame's own URL says whether the views share a source.
            if isinstance(data, dict) and '/@file/' in str(data.get('url', '')):
                found[path] = data['url']
            for key in ('hconcat', 'vconcat', 'layer'):
                for i, child in enumerate(spec.get(key, [])):
                    urls_in(child, f'{path}/{key}[{i}]', found)
        return found

    counter = itertools.count(1)
    alt.data_transformers.register(
        'probe_per_call', lambda data, **kw: {'url': f'/@file/{next(counter)}.csv',
                                              'format': {'type': 'csv'}})
    alt.data_transformers.enable('probe_per_call')
    split = urls_in(DataVisualizer(df).create_chart().to_dict())

    cache = {}

    def memoised(data, **kwargs):
        key = len(data), tuple(data.columns)
        cache.setdefault(key, {'url': '/@file/shared.csv', 'format': {'type': 'csv'}})
        return cache[key]

    alt.data_transformers.register('probe_memoised', memoised)
    alt.data_transformers.enable('probe_memoised')
    shared = urls_in(DataVisualizer(df).create_chart().to_dict())
    alt.data_transformers.enable('default')

    assert len(set(split.values())) > 1, (
        'expected a per-call transformer to hand each view its own URL; if it no '
        'longer does, the memo in apps/marimo_app.py may be unnecessary'
    )
    assert len(set(shared.values())) == 1, (
        f'memoising must put every view on one URL, got {sorted(set(shared.values()))}'
    )
    assert len(shared) == len(split)   # same views either way
