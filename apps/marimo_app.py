# /// script
# # Upper bound is load-bearing: uv takes the newest interpreter the range
# # allows, and on 3.14 altair 5.5 fails at import — its generated _config.py
# # builds a TypedDict with closed=True, which 3.14's typing rejects.
# requires-python = ">=3.11,<3.14"
# dependencies = [
#     "marimo",
#     "earthquake-dashboard",
# ]
#
# # molab mirrors this one file, not the repository around it, so the package
# # has to come from somewhere absolute — an earlier attempt used a "../" path
# # source and could not resolve it there (#31, reverted in #35). Installing
# # from git keeps molab on whatever main holds, with no release step. pixi
# # ignores this block; local work still uses the editable install in the alt
# # environment.
# [tool.uv.sources]
# earthquake-dashboard = { git = "https://github.com/chernobylx/Earthquake-Visualization-Dashboard", branch = "main" }
# ///
"""Earthquake dashboard as a marimo notebook.

Same two layers as the Dash app — earthquake_dashboard.DataLoader for the USGS
query and DataVisualizer for the linked chart — with marimo's reactive cells and
mo.ui widgets in place of Dash callbacks.

    pixi run -e alt marimo-app     # read-only app
    pixi run -e alt marimo-edit    # editable notebook

The script metadata above is what lets the notebook run away from this checkout:
`marimo edit --sandbox`, `uv run --script`, and molab all build an environment
from it.
"""

import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="full",
    app_title="Earthquake Dashboard",
    layout_file="layouts/marimo_app.grid.json",
)


@app.cell
def _():
    from datetime import date, timedelta

    import marimo as mo

    from earthquake_dashboard.data_loader import (
        COL_TYPES,
        DT_FORMAT,
        DataLoader,
        RequestParams,
    )
    from earthquake_dashboard.visualizer import DataVisualizer

    # The loaded frame lives in state rather than being a cell's return value.
    # mo.stop aborts the cell it is called in, so a guarded cell that returned
    # `df` un-defined it on every unrelated rerun: moving a query slider re-ran
    # the fetch cell, the button had already reset to False, and the table and
    # chart vanished with it (issue #17). State survives a stopped cell.
    get_df, set_df = mo.state(None)

    # The rendered chart lives in state for the same reason: the chart cell is
    # gated on a Render chart button, and a gated cell that returned the chart
    # would blank it on every control change (issue #18).
    get_chart, set_chart = mo.state(None)

    # Encoding options come from the column contract, not from the loaded
    # frame. Deriving them from `df` made every control cell depend on the
    # data, so fetching rebuilt all fourteen widgets at their defaults and
    # discarded the user's settings (issue #15). Fixed because
    # DataLoader.preprocess always returns exactly these columns.
    NUMERIC_COLS = [
        c for c, t in COL_TYPES.items() if t.startswith(("float", "int", "datetime"))
    ]

    # DataVisualizer asserts every one of these; mo.ui.dataframe transforms can
    # drop columns, so the chart cell checks before handing the frame over.
    REQUIRED_COLS = list(COL_TYPES)

    return (
        DT_FORMAT,
        DataLoader,
        DataVisualizer,
        NUMERIC_COLS,
        RequestParams,
        REQUIRED_COLS,
        date,
        get_chart,
        get_df,
        mo,
        set_chart,
        set_df,
        timedelta,
    )


@app.cell
def _(mo):
    mo.md("""
    # Earthquake Visualization Dashboard

    Live data from the [USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/).
    Set a query below, **Preview count** to see how many events match, then **Fetch data**.
    """)
    return


@app.cell
def _(date, mo, timedelta):
    # --- query controls -------------------------------------------------
    # Nothing here hits the network. Cells that do are gated on the buttons
    # below, so dragging a slider never fires a request.
    start_date = mo.ui.date(
        value=date.today() - timedelta(days=30), label="From (UTC)"
    )
    end_date = mo.ui.date(value=date.today() + timedelta(days=1), label="Up to (UTC)")

    magnitude = mo.ui.range_slider(
        start=0, stop=10, step=0.1, value=[2.0, 9.1], label="Magnitude", show_value=True
    )
    significance = mo.ui.range_slider(
        start=0, stop=3000, step=50, value=[0, 3000], label="Significance", show_value=True
    )
    depth = mo.ui.range_slider(
        start=-100, stop=1000, step=25, value=[-100, 1000], label="Depth (km)", show_value=True
    )
    latitude = mo.ui.range_slider(
        start=-90, stop=90, step=1, value=[-90, 90], label="Latitude", show_value=True
    )
    longitude = mo.ui.range_slider(
        start=-180, stop=180, step=1, value=[-180, 180], label="Longitude", show_value=True
    )
    return (
        depth,
        end_date,
        latitude,
        longitude,
        magnitude,
        significance,
        start_date,
    )


@app.cell
def _(
    depth,
    end_date,
    latitude,
    longitude,
    magnitude,
    mo,
    significance,
    start_date,
):
    count_button = mo.ui.run_button(label="Preview count")
    fetch_button = mo.ui.run_button(label="Fetch data")

    query_panel = mo.vstack(
        [
            mo.md("### Query USGS"),
            mo.hstack([start_date, end_date], justify="start", gap=1),
            magnitude,
            significance,
            depth,
            latitude,
            longitude,
            mo.hstack([count_button, fetch_button], justify="start", gap=1),
        ]
    )
    query_panel
    return count_button, fetch_button


@app.cell
def _(
    DT_FORMAT,
    RequestParams,
    depth,
    end_date,
    latitude,
    longitude,
    magnitude,
    significance,
    start_date,
):
    from datetime import datetime as _dt

    def current_params():
        """The widget values as a validated RequestParams."""
        return RequestParams(
            starttime=_dt.combine(start_date.value, _dt.min.time()).strftime(DT_FORMAT),
            endtime=_dt.combine(end_date.value, _dt.min.time()).strftime(DT_FORMAT),
            minmagnitude=magnitude.value[0],
            maxmagnitude=magnitude.value[1],
            minsig=significance.value[0],
            maxsig=significance.value[1],
            mindepth=depth.value[0],
            maxdepth=depth.value[1],
            minlatitude=latitude.value[0],
            maxlatitude=latitude.value[1],
            minlongitude=longitude.value[0],
            maxlongitude=longitude.value[1],
        )

    return (current_params,)


@app.cell
def _(DataLoader, count_button, current_params, mo):
    # Gated on the button: marimo re-runs this cell whenever any input changes,
    # so without the guard every slider drag would query the API.
    mo.stop(not count_button.value, mo.md("*Press **Preview count** to check the query.*"))

    _n = DataLoader(current_params()).count()
    mo.md(
        f"**{_n:,} events match.**"
        + ("  \n:warning: over the 20,000 record limit — narrow the query." if _n > 20000 else "")
    )
    return


@app.cell
def _(DataLoader, current_params, fetch_button, mo, set_df):
    # This cell reruns whenever a query widget moves, because current_params
    # references them all. The stop below is what keeps a slider drag from
    # hitting the API — and because the frame goes to state rather than being
    # returned, stopping no longer destroys it.
    mo.stop(not fetch_button.value, mo.md("*Press **Fetch data** to download.*"))

    _loader = DataLoader(current_params())
    _loader.query()
    _frame = _loader.preprocess()
    set_df(_frame)
    mo.md(f"Loaded **{len(_frame):,}** events.")
    return


@app.cell
def _(get_df, mo):
    _frame = get_df()
    if _frame is None:
        _out = mo.md("*No data loaded yet.*")
    else:
        # marimo 0.24 parses a filter value with a naive datetime.fromisoformat
        # and compares it straight against the column, so filtering a tz-aware
        # column raises "Invalid comparison between dtype=datetime64[ns, UTC]
        # and Timestamp" (issue #12) — and `time` is the first column anyone
        # filters here. Hand the table a tz-naive copy; times are UTC either
        # way. The frame the chart uses keeps its tz, which COL_TYPES requires
        # and DataVisualizer asserts.
        _out = mo.ui.table(
            _frame.assign(time=_frame["time"].dt.tz_localize(None)),
            page_size=10,
            selection=None,
        )
    _out
    return


@app.cell
def _(get_df, mo):
    # The table above is for browsing; this is what the chart reads. Filtering
    # or transforming here flows straight through to the map, histograms and
    # heatmap (issues #14 and #16).
    #
    # tz-naive for the same reason as the table — marimo compares filter values
    # as naive Timestamps. It matters more here: mo.ui.dataframe wraps its
    # filtering in `except Exception`, so on a tz-aware column it would swallow
    # the TypeError and hand back the UNFILTERED frame with no visible error.
    _frame = get_df()
    if _frame is None:
        chart_source = None
        _out = mo.md("*Fetch data to enable filtering.*")
    else:
        chart_source = mo.ui.dataframe(
            _frame.assign(time=_frame["time"].dt.tz_localize(None))
        )
        _out = chart_source
    _out
    return (chart_source,)


@app.cell
def _(NUMERIC_COLS, mo):
    # --- chart controls -------------------------------------------------
    # Deliberately does NOT reference the loaded frame. Taking df as an input
    # made marimo rerun this cell on every fetch, rebuilding all fourteen
    # widgets at their defaults and throwing away the user's settings
    # (issue #15). The option set is fixed by the column contract anyway.
    _numeric = NUMERIC_COLS

    projection = mo.ui.dropdown(
        options={
            "Natural Earth": "naturalEarth1",
            "Azimuthal Equal-Area": "azimuthalEqualArea",
            "Mercator": "mercator",
        },
        value="Natural Earth",
        label="Projection",
    )
    spin = mo.ui.slider(-179.9, 179.9, 1, value=0, label="Spin E-W", show_value=True)
    tilt = mo.ui.slider(-89.9, 89.9, 1, value=0, label="Tilt N-S", show_value=True)
    zoom = mo.ui.slider(10, 1000, 10, value=100, label="Zoom", show_value=True)

    canvas_color = mo.ui.text(value="rgb(26,26,26)", label="Canvas")
    land_color = mo.ui.text(value="#444488", label="Land")
    border_color = mo.ui.text(value="darkblue", label="Border")

    point_size = mo.ui.dropdown(_numeric, value="sig", label="Point size")
    point_color = mo.ui.dropdown(_numeric, value="mag", label="Point color")
    point_opacity = mo.ui.dropdown(_numeric, value="mag", label="Point opacity")

    heat_x = mo.ui.dropdown(_numeric, value="time", label="Bin across (X)")
    heat_y = mo.ui.dropdown(_numeric, value="depth", label="Bin down (Y)")
    heat_metric = mo.ui.dropdown(
        {"Max magnitude": "max(mag)", "Mean depth": "mean(depth)", "Magnitude": "mag"},
        value="Max magnitude",
        label="Cell metric",
    )
    histograms = mo.ui.multiselect(
        _numeric, value=[c for c in ("time", "mag", "depth") if c in _numeric],
        label="Histograms",
    )

    # Lives in this cell, not one of its own: a cell defining only the button
    # would need its own grid slot, and this cell is the one that never reruns
    # on a widget move, so the button survives alongside the settings.
    render_button = mo.ui.run_button(label="Render chart")

    mo.hstack(
        [
            mo.vstack([mo.md("**Map**"), projection, spin, tilt, zoom]),
            mo.vstack([mo.md("**Colors**"), canvas_color, land_color, border_color]),
            mo.vstack([mo.md("**Points**"), point_size, point_color, point_opacity]),
            mo.vstack([mo.md("**Heatmap**"), heat_x, heat_y, heat_metric, histograms]),
            mo.vstack([mo.md("**Draw**"), render_button]),
        ],
        justify="start",
        gap=2,
        widths="equal",
    )
    return (
        border_color,
        canvas_color,
        heat_metric,
        heat_x,
        heat_y,
        histograms,
        land_color,
        point_color,
        point_opacity,
        point_size,
        projection,
        render_button,
        spin,
        tilt,
        zoom,
    )


@app.cell
def _(
    DataVisualizer,
    border_color,
    canvas_color,
    chart_source,
    heat_metric,
    heat_x,
    heat_y,
    histograms,
    REQUIRED_COLS,
    land_color,
    mo,
    point_color,
    point_opacity,
    point_size,
    projection,
    render_button,
    set_chart,
    spin,
    tilt,
    zoom,
):
    # This cell references every chart control, so marimo reruns it on each
    # tweak — dragging Zoom re-encoded thousands of rows per intermediate value
    # (issue #18). The button is the gate; the stop below leaves whatever was
    # rendered last on screen, because the result goes to state instead of
    # being this cell's output. The cell shows nothing itself.
    mo.stop(not render_button.value)

    # Past this point the press was deliberate, so a problem is reported rather
    # than silently held: each branch replaces the chart with the reason.
    if chart_source is None:
        set_chart(mo.md("*Fetch data to draw the chart.*"))
    elif not histograms.value:
        set_chart(mo.md(":warning: Pick at least one histogram variable."))
    else:
        # Whatever survives the filters above, not the whole download.
        _frame = chart_source.value

        # A transform can drop a column, and DataVisualizer asserts on all of
        # them — say so plainly rather than surfacing an AssertionError.
        _missing = [c for c in REQUIRED_COLS if c not in _frame.columns]
        if _missing:
            set_chart(mo.md(
                f":warning: The chart needs `{'`, `'.join(_missing)}` — a transform removed it."
            ))
        elif _frame.empty:
            set_chart(mo.md(":warning: The filters match no events."))
        else:
            # The filtering widget was handed a tz-naive copy (see the cell
            # above); put the timezone back, because COL_TYPES demands
            # datetime64[ns, UTC].
            _frame = _frame.assign(time=_frame["time"].dt.tz_localize("UTC"))

            set_chart(DataVisualizer(_frame).create_chart(
                width=1200,
                height=800,
                projection=projection.value,
                phi=spin.value,
                theta=tilt.value,
                scale=zoom.value,
                map_fill=land_color.value,
                map_stroke=border_color.value,
                background=canvas_color.value,
                size_var=point_size.value,
                color_var=point_color.value,
                opacity_var=point_opacity.value,
                heatmap_x=heat_x.value,
                heatmap_y=heat_y.value,
                heatmap_color=heat_metric.value,
                filter_vars=histograms.value,
            ))
    return


@app.cell
def _(get_chart, mo):
    # Reads the state and nothing else, so it reruns only when a render
    # actually stored something new. Never calls set_chart: a cell that both
    # read the getter and called the setter would rerun itself.
    _chart = get_chart()
    _chart if _chart is not None else mo.md("*Press **Render chart** to draw.*")
    return


if __name__ == "__main__":
    app.run()
