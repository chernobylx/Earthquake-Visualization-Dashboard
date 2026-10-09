"""The linked-views chart: a hand-written Vega-Lite template, fed by Dash.

The chart lives in specs/linked_views.vl.json, not in Python. Its camera --
projection, zoom, rotation -- is a set of bound params, so dragging those
sliders redraws the map in the browser with no round trip to the server. The
one thing Python still has to do is put the query's rows into it.

Dash sends the result to dash-vega-components, which tears the whole view
down and builds a new one whenever its spec differs at all. A new spec is
therefore expensive -- it clears every brush -- so refresh() sends one only
when the *rows* change. Comparing specs would not do: the camera the user has
just moved is written into each new spec, so two specs over identical rows
differ the moment a slider has been touched, and a table sort would rebuild.
"""
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import pandas as pd

# Next to this module, so the path holds both in the installed package and in
# the flattened Plotly Cloud bundle, where this file sits at the bundle root.
TEMPLATE_PATH = Path(__file__).parent / 'specs' / 'linked_views.vl.json'

# Bound params whose current value survives a data refresh. dash-vega-components
# reports them back through signalData when they are listed in signalsToObserve.
CAMERA_PARAMS = ('PROJECTION', 'zoom', 'rotate0', 'rotate1', 'rotate2', 'mag_bins', 'VAR')

# The columns the template reads. Every table filter re-sends the rows, so the
# rest -- tsunami, cdi, alert -- would only be payload.
KEPT_COLUMNS = ('time', 'place', 'lat', 'lon', 'mag', 'depth', 'sig', 'url')


@lru_cache(maxsize=1)
def _template_text() -> str:
    return TEMPLATE_PATH.read_text(encoding='utf-8')


def load_template() -> dict:
    """A fresh copy of the template, safe to modify."""
    return json.loads(_template_text())


def chart_rows(df: pd.DataFrame | None) -> list[dict] | None:
    """`df` as the template's `eq` rows, or None when there are none."""
    if df is None or df.empty:
        return None

    df = df[[c for c in KEPT_COLUMNS if c in df.columns]].copy()
    # The table hands times back as ISO strings; a fresh query has datetimes.
    df['time'] = pd.to_datetime(df['time'], utc=True, format='ISO8601')

    # Sorted on everything sent, so the same rows in any order are the same
    # rows here. Done while time is still a datetime, so a missing one sorts
    # last instead of failing to compare with the integers below.
    df = df.sort_values(list(df.columns), kind='mergesort').reset_index(drop=True)

    # Epoch milliseconds, not strings: the template computes its time domain
    # with offsets over data('eq') directly, which never parses dates, so ISO
    # strings made that domain NaN -> NaN. Missing times become null by hand:
    # NaT cast to int64 is the int64 minimum, a date 292 million years ago.
    missing = df['time'].isna()
    ms = df['time'].dt.as_unit('ms').astype('int64')
    df['time'] = [None if gone else int(v) for v, gone in zip(ms, missing, strict=True)]

    # NaN is not JSON; Vega reads null as missing.
    df = df.astype(object).where(df.notna(), None)
    return df.to_dict('records')


def spec_from_rows(rows: list[dict], camera: dict | None = None) -> dict:
    """The template with `rows` inlined as the `eq` dataset.

    `camera` is dash-vega-components' signalData: any CAMERA_PARAMS value in it
    becomes that param's starting value, so a rebuilt view opens where the old
    one was left.
    """
    spec = load_template()
    spec['datasets'] = {'eq': rows}
    camera = camera if isinstance(camera, dict) else {}
    for param in spec['params']:
        value = camera.get(param['name'])
        if param['name'] in CAMERA_PARAMS and value is not None:
            param['value'] = copy.deepcopy(value)
    return spec


def build_spec(df: pd.DataFrame | None, camera: dict | None = None) -> dict | None:
    """The template filled with `df`'s rows, or None when there are none."""
    rows = chart_rows(df)
    return None if rows is None else spec_from_rows(rows, camera)


def rows_digest(rows: list[dict]) -> str:
    return hashlib.sha1(json.dumps(rows, sort_keys=True).encode()).hexdigest()


class Refresh(NamedTuple):
    spec: dict | None   # None: send nothing new
    digest: str | None  # the rows the chart now shows
    empty: bool         # no rows: hide the chart


def refresh(data: list[dict] | None, camera: dict | None,
            last_digest: str | None) -> Refresh:
    """What the chart callback should send for the table's current rows.

    The digest is of the rows alone, so a sort -- or any other update that
    leaves the rows as they were -- sends nothing, however far the camera has
    moved since the last spec.
    """
    rows = chart_rows(pd.DataFrame(data or []))
    if rows is None:
        return Refresh(None, None, True)
    digest = rows_digest(rows)
    if digest == last_digest:
        return Refresh(None, digest, False)
    return Refresh(spec_from_rows(rows, camera), digest, False)
