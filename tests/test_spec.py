"""The hand-written linked-views spec and the rows Dash feeds into it.

The chart is a Vega-Lite template (specs/linked_views.vl.json) whose camera --
projection, zoom, rotation -- is bound params, so it redraws in the browser.
Python's only job is to put the query's rows into it. These tests pin the
things that break silently when that goes wrong: a time column the template's
own expressions cannot read, a layer that reads its own copy of the data and
so drops out of the brushes, and a spec that changes when nothing did.
"""
import copy
import json

import pandas as pd
import pytest

from earthquake_dashboard.spec import (
    CAMERA_PARAMS,
    KEPT_COLUMNS,
    build_spec,
    load_template,
    refresh,
)


def make_frame() -> pd.DataFrame:
    return pd.DataFrame({
        'place': ['B place', 'A place', 'C place'],
        'time': pd.to_datetime(['2026-09-11T21:23:55.907Z',
                                '2026-09-01T03:00:00Z',
                                '2026-09-05T12:00:00Z'], utc=True, format='ISO8601'),
        'lat': [-4.98, 35.70, 61.2],
        'lon': [106.87, -117.52, -150.1],
        'mag': [6.5, 4.1, 2.3],
        'sig': [657, 271, 81],
        'depth': [372.0, 8.0, 40.5],
        'tsunami': [False, True, False],
        'cdi': [3.4, None, float('nan')],
        'alert': ['green', None, None],
        'url': ['https://earthquake.usgs.gov/a', 'https://earthquake.usgs.gov/b',
                'https://earthquake.usgs.gov/c'],
    }).astype({'sig': 'int64'})


def units(node):
    """Every leaf view (one with a mark) in a spec, however deeply composed."""
    if isinstance(node, dict):
        if 'mark' in node:
            yield node
        for key in ('hconcat', 'vconcat', 'concat', 'layer'):
            for child in node.get(key, []):
                yield from units(child)


def nodes(node):
    """Every view in a spec, composite or leaf."""
    if isinstance(node, dict):
        yield node
        for key in ('hconcat', 'vconcat', 'concat', 'layer'):
            for child in node.get(key, []):
                yield from nodes(child)


def rows_of(spec):
    return spec['datasets']['eq']


# --- the template -----------------------------------------------------------

def test_the_template_is_vega_lite_5():
    """dash-vega-components 0.11 renders with Vega-Lite 5.20, not 6."""
    assert 'vega-lite/v5' in load_template()['$schema']


def test_every_quake_layer_reads_the_one_shared_dataset():
    """The map brush matches rows by Vega's internal ids, so it filters only
    the views that read the same dataset as the map. A layer with its own copy
    -- the heatmap once fetched the GitHub test file separately -- gets a
    second id range, matches nothing, and empties on every map drag. It would
    also show that stale file instead of the query.
    """
    spec = load_template()
    assert spec['data'] == {'name': 'eq'}
    for unit in nodes(spec):
        data = unit.get('data')
        if data is None:
            continue  # inherits from its parent
        if 'sphere' in data or 'graticule' in data:
            continue
        if data.get('format', {}).get('type') == 'topojson':
            continue  # the basemap, not quakes
        assert data == {'name': 'eq'}, f"{unit.get('description')} reads {data}"


def test_the_template_fetches_no_quake_data_of_its_own():
    assert 'githubusercontent' not in json.dumps(load_template())


def test_points_link_to_usgs_in_a_new_tab():
    """Carried over from the Altair chart (#46): the point is the link."""
    spec = load_template()
    circles = [u for u in units(spec)
               if (u['mark'] if isinstance(u['mark'], str) else u['mark']['type']) == 'circle']
    assert circles, 'expected the map scatterplot'
    assert circles[0]['encoding']['href'] == {'field': 'url', 'type': 'nominal'}
    assert spec['usermeta']['embedOptions']['loader']['target'] == '_blank'


def test_the_variable_param_stays_unbound_until_something_reads_it():
    """VAR feeds only varExtent, which no encoding reads, so a bound VAR drew a
    dropdown that changed nothing. Re-bind it when an encoding uses it.
    """
    template = load_template()
    var = next(p for p in template['params'] if p['name'] == 'VAR')
    assert 'bind' not in var
    text = json.dumps({k: v for k, v in template.items() if k != 'params'})
    assert 'varExtent' not in text, 'varExtent is read now -- give VAR its bind back'


def test_every_camera_param_exists_in_the_template():
    names = {p['name'] for p in load_template()['params']}
    assert set(CAMERA_PARAMS) <= names


# --- build_spec -------------------------------------------------------------

def test_rows_go_inline_under_eq():
    spec = build_spec(make_frame())
    assert len(rows_of(spec)) == 3


def test_time_becomes_utc_epoch_milliseconds():
    """The template's timeExtent is timeOffset() over raw data('eq'), which
    does not parse dates. ISO strings came out NaN -> NaN and broke the time
    axis; epoch milliseconds are numbers it can offset.
    """
    times = [r['time'] for r in rows_of(build_spec(make_frame()))]
    assert all(isinstance(t, int) for t in times)
    assert times[0] == int(pd.Timestamp('2026-09-01T03:00:00Z').timestamp() * 1000)


def test_iso_string_times_from_the_table_work_too():
    """derived_virtual_data hands the times back as strings."""
    df = make_frame()
    df['time'] = df['time'].map(lambda t: t.isoformat())
    assert rows_of(build_spec(df)) == rows_of(build_spec(make_frame()))


def test_missing_values_become_null_and_the_spec_is_plain_json():
    df = make_frame()
    df.loc[1, 'depth'] = float('nan')
    spec = build_spec(df)
    json.dumps(spec, allow_nan=False)  # raises on NaN
    assert None in [r['depth'] for r in rows_of(spec)]


def test_a_missing_time_is_null_not_the_int64_minimum():
    """NaT cast straight to int64 is -9223372036854775808: a date 292 million
    years ago that drags the time domain with it, silently.
    """
    df = make_frame()
    df.loc[0, 'time'] = pd.NaT
    times = [r['time'] for r in rows_of(build_spec(df))]
    assert None in times
    assert all(t is None or t > 0 for t in times)


def test_only_the_columns_the_template_reads_are_sent():
    """Every filter re-sends the rows; at the 20,000-row cap the unused ones
    were about a fifth of the payload.
    """
    keys = set(rows_of(build_spec(make_frame()))[0])
    assert keys == set(KEPT_COLUMNS)


def test_a_non_dict_camera_is_ignored():
    assert build_spec(make_frame(), camera=['zoom', 3]) == build_spec(make_frame())


def test_row_order_does_not_change_the_spec():
    """A table sort must not look like new data: dash-vega-components tears the
    view down whenever the spec differs at all.
    """
    df = make_frame()
    assert build_spec(df) == build_spec(df.iloc[::-1].reset_index(drop=True))


def test_the_camera_carries_over():
    camera = {'PROJECTION': 'orthographic', 'zoom': 340, 'rotate0': -75}
    params = {p['name']: p for p in build_spec(make_frame(), camera=camera)['params']}
    assert params['PROJECTION']['value'] == 'orthographic'
    assert params['zoom']['value'] == 340
    assert params['rotate0']['value'] == -75


def test_unknown_and_missing_camera_values_are_ignored():
    default = build_spec(make_frame())
    spec = build_spec(make_frame(), camera={'zoom': None, 'BRUSH_MAP': {'x': 1}, 'nope': 3})
    assert spec == default


def test_the_template_itself_is_never_modified():
    before = copy.deepcopy(load_template())
    build_spec(make_frame(), camera={'zoom': 999})
    assert load_template() == before


@pytest.mark.parametrize('empty', [pd.DataFrame(), None])
def test_no_rows_means_no_spec(empty):
    assert build_spec(empty) is None


# --- refresh: what the chart callback sends ---------------------------------

def records(df):
    """The table hands rows over the way derived_virtual_data does."""
    out = df.copy()
    out['time'] = out['time'].map(lambda t: t.isoformat())
    return out.to_dict('records')


def test_new_rows_send_a_spec_and_a_digest():
    r = refresh(records(make_frame()), camera=None, last_digest=None)
    assert r.spec is not None and r.digest and not r.empty


def test_a_sort_after_moving_the_camera_sends_nothing():
    """The rebuild would otherwise wipe the brushes: the camera the user just
    moved makes the new spec differ from the one on screen, even though not
    one row changed.
    """
    first = refresh(records(make_frame()), camera=None, last_digest=None)
    sorted_rows = records(make_frame().iloc[::-1].reset_index(drop=True))
    again = refresh(sorted_rows, camera={'rotate0': -75}, last_digest=first.digest)
    assert again.spec is None and not again.empty
    assert again.digest == first.digest


def test_different_rows_rebuild_and_carry_the_camera():
    first = refresh(records(make_frame()), camera=None, last_digest=None)
    fewer = records(make_frame().iloc[:2])
    r = refresh(fewer, camera={'rotate0': -75}, last_digest=first.digest)
    assert r.spec is not None and r.digest != first.digest
    assert {p['name']: p for p in r.spec['params']}['rotate0']['value'] == -75


@pytest.mark.parametrize('data', [None, []])
def test_no_rows_is_empty(data):
    r = refresh(data, camera=None, last_digest='abc')
    assert r.empty and r.spec is None and r.digest is None


MAGMA = {'name': 'magma', 'extent': [0.2, 1]}


def test_every_significance_colour_uses_trimmed_magma():
    """One shared colour scale, one scheme.

    The layers that colour by significance share a scale and a single legend,
    so they have to agree. Magma's darkest fifth is dropped because it is close
    to the chart's #0e0435 background, and most quakes have low significance:
    they would all but vanish at the black end.
    """
    colours = []
    for node in nodes(load_template()):
        colour = node.get('encoding', {}).get('color')
        if not colour:
            continue
        for definition in (colour, colour.get('condition', {})):
            if 'field' in definition:
                colours.append((node.get('description'), definition))
    assert len(colours) == 4, [d for d, _ in colours]
    for description, definition in colours:
        assert definition.get('scale', {}).get('scheme') == MAGMA, description
