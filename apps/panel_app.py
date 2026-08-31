"""Earthquake dashboard as a Panel app.

Same two layers as the Dash app — earthquake_dashboard.DataLoader for the USGS
query and DataVisualizer for the linked chart — with Panel widgets and pn.bind
in place of Dash callbacks.

    pixi run -e alt panel
"""

from datetime import date, datetime, timedelta

import panel as pn
import param

from earthquake_dashboard.data_loader import DT_FORMAT, DataLoader, RequestParams
from earthquake_dashboard.visualizer import DataVisualizer

pn.extension("vega", "tabulator", sizing_mode="stretch_width")

NUMERIC = ["time", "lat", "lon", "mag", "sig", "depth", "cdi"]

# --- query controls ------------------------------------------------------
start_date = pn.widgets.DatePicker(
    name="From (UTC)", value=date.today() - timedelta(days=30)
)
end_date = pn.widgets.DatePicker(name="Up to (UTC)", value=date.today() + timedelta(days=1))
magnitude = pn.widgets.RangeSlider(name="Magnitude", start=0, end=10, value=(2.0, 9.1), step=0.1)
significance = pn.widgets.IntRangeSlider(
    name="Significance", start=0, end=3000, value=(0, 3000), step=50
)
depth = pn.widgets.IntRangeSlider(name="Depth (km)", start=-100, end=1000, value=(-100, 1000), step=25)
latitude = pn.widgets.IntRangeSlider(name="Latitude", start=-90, end=90, value=(-90, 90), step=1)
longitude = pn.widgets.IntRangeSlider(name="Longitude", start=-180, end=180, value=(-180, 180), step=1)

count_button = pn.widgets.Button(name="Preview count", button_type="default")
fetch_button = pn.widgets.Button(name="Fetch data", button_type="primary")
count_text = pn.pane.Markdown("*Press **Preview count** to check the query.*")

# --- chart controls ------------------------------------------------------
projection = pn.widgets.Select(
    name="Projection",
    options={
        "Natural Earth": "naturalEarth1",
        "Azimuthal Equal-Area": "azimuthalEqualArea",
        "Mercator": "mercator",
    },
    value="naturalEarth1",
)
spin = pn.widgets.FloatSlider(name="Spin E-W", start=-179.9, end=179.9, value=0, step=1)
tilt = pn.widgets.FloatSlider(name="Tilt N-S", start=-89.9, end=89.9, value=0, step=1)
zoom = pn.widgets.IntSlider(name="Zoom", start=10, end=1000, value=100, step=10)

canvas_color = pn.widgets.TextInput(name="Canvas", value="rgb(26,26,26)")
land_color = pn.widgets.TextInput(name="Land", value="#444488")
border_color = pn.widgets.TextInput(name="Border", value="darkblue")

point_size = pn.widgets.Select(name="Point size", options=NUMERIC, value="sig")
point_color = pn.widgets.Select(name="Point color", options=NUMERIC, value="mag")
point_opacity = pn.widgets.Select(name="Point opacity", options=NUMERIC, value="mag")

heat_x = pn.widgets.Select(name="Bin across (X)", options=NUMERIC, value="time")
heat_y = pn.widgets.Select(name="Bin down (Y)", options=NUMERIC, value="depth")
heat_metric = pn.widgets.Select(
    name="Cell metric",
    options={"Max magnitude": "max(mag)", "Mean depth": "mean(depth)", "Magnitude": "mag"},
    value="max(mag)",
)
histograms = pn.widgets.MultiChoice(
    name="Histograms", options=NUMERIC, value=["time", "mag", "depth"]
)


class Store(param.Parameterized):
    """Holds the loaded frame so chart redraws never re-query the API."""

    frame = param.Parameter(default=None)


store = Store()


def _params() -> RequestParams:
    return RequestParams(
        starttime=datetime.combine(start_date.value, datetime.min.time()).strftime(DT_FORMAT),
        endtime=datetime.combine(end_date.value, datetime.min.time()).strftime(DT_FORMAT),
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


def _on_count(_):
    # Only the buttons touch the network; moving a slider never does.
    count_button.loading = True
    try:
        n = DataLoader(_params()).count()
        warn = "  \n⚠️ over the 20,000 record limit — narrow the query." if n > 20000 else ""
        count_text.object = f"**{n:,} events match.**{warn}"
    except Exception as exc:  # surface the failure instead of a blank panel
        count_text.object = f"**Query failed:** {exc}"
    finally:
        count_button.loading = False


def _on_fetch(_):
    fetch_button.loading = True
    try:
        loader = DataLoader(_params())
        loader.query()
        store.frame = loader.preprocess()
        count_text.object = f"Loaded **{len(store.frame):,}** events."
    except Exception as exc:
        count_text.object = f"**Fetch failed:** {exc}"
    finally:
        fetch_button.loading = False


count_button.on_click(_on_count)
fetch_button.on_click(_on_fetch)


def table_view(frame):
    if frame is None:
        return pn.pane.Markdown("*No data loaded yet.*")
    return pn.widgets.Tabulator(
        frame, page_size=10, pagination="remote", disabled=True, height=340
    )


def chart_view(
    frame, projection, spin, tilt, zoom, canvas, land, border,
    size_var, color_var, opacity_var, hx, hy, metric, hists,
):
    if frame is None:
        return pn.pane.Markdown("*Fetch data to draw the chart.*")
    if not hists:
        return pn.pane.Markdown("⚠️ *Pick at least one histogram variable.*")
    chart = DataVisualizer(frame).create_chart(
        width=1200, height=800,
        projection=projection, phi=spin, theta=tilt, scale=zoom,
        map_fill=land, map_stroke=border, background=canvas,
        size_var=size_var, color_var=color_var, opacity_var=opacity_var,
        heatmap_x=hx, heatmap_y=hy, heatmap_color=metric,
        filter_vars=list(hists),
    )
    # Vega-Lite v5 spec straight from DataVisualizer, rendered by Panel's Vega pane
    return pn.pane.Vega(chart, sizing_mode="stretch_width", min_height=760)


bound_table = pn.bind(table_view, frame=store.param.frame)
bound_chart = pn.bind(
    chart_view,
    frame=store.param.frame,
    projection=projection, spin=spin, tilt=tilt, zoom=zoom,
    canvas=canvas_color, land=land_color, border=border_color,
    size_var=point_size, color_var=point_color, opacity_var=point_opacity,
    hx=heat_x, hy=heat_y, metric=heat_metric, hists=histograms,
)

query_card = pn.Card(
    start_date, end_date, magnitude, significance, depth, latitude, longitude,
    pn.Row(count_button, fetch_button), count_text,
    title="Query USGS", collapsed=False,
)
chart_card = pn.Card(
    pn.pane.Markdown("**Map**"), projection, spin, tilt, zoom,
    pn.pane.Markdown("**Colors**"), canvas_color, land_color, border_color,
    pn.pane.Markdown("**Points**"), point_size, point_color, point_opacity,
    pn.pane.Markdown("**Heatmap**"), heat_x, heat_y, heat_metric, histograms,
    title="Chart settings", collapsed=False,
)

template = pn.template.FastListTemplate(
    title="Earthquake Visualization Dashboard",
    sidebar=[query_card, chart_card],
    sidebar_width=340,
    main=[
        pn.pane.Markdown(
            "Live data from the "
            "[USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/). "
            "Drag on the map or any histogram to filter every view."
        ),
        bound_table,
        bound_chart,
    ],
    theme="dark",
)

template.servable()
