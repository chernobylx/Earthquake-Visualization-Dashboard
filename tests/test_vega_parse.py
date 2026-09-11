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
