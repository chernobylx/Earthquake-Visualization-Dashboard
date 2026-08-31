# Earthquake Visualization Dashboard

[![CI](https://github.com/chernobylx/Earthquake-Visualization-Dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/chernobylx/Earthquake-Visualization-Dashboard/actions/workflows/ci.yml)

An interactive dashboard for exploring earthquake data from the
[USGS Earthquake Catalog API](https://earthquake.usgs.gov/fdsnws/event/1/), built with
[Dash](https://dash.plotly.com/) and [Altair](https://altair-viz.github.io/)/Vega-Lite.

Query the live USGS catalog by date, magnitude, significance, depth, and geographic
bounds, then explore what comes back through a linked set of views — a world map, a
stack of brushable histograms, and a time–depth heatmap. Every view shares the same
Vega-Lite selections, so a brush drawn in any one of them filters all the others.

**[Try the live dashboard](https://0be82526-8d32-4767-bbed-2b63946ff944.plotly.app/dashboard)** — hosted on Plotly Cloud, querying the USGS catalog in real time.

![Linked views over 2,251 M2.5+ earthquakes from the past 30 days: a world map colored by magnitude tracing the Pacific Ring of Fire, brushable time, magnitude and depth histograms, and a time-depth heatmap](docs/figures/dashboard.png)

## Features

- **Live data loading** — query the USGS FDSN event API through a validated parameter
  object, preview the match count before committing to a download, and browse the raw
  records in a sortable, filterable table.
- **Cross-filtered views** — the map, histograms, and heatmap share interval
  selections. Brush a histogram or drag across the map and every other view responds.
- **Configurable map** — three projections (Natural Earth, azimuthal equal-area,
  Mercator), rotation and scale sliders, and free-text fill, stroke, and background
  colors.
- **Flexible encodings** — choose which variables drive point size, color, and opacity
  on the map, which pair the heatmap aggregates over, and which columns become filter
  histograms.
- **Time axes that follow the window** — the heatmap and time histogram switch between
  yearly, monthly, and daily tick formats based on the span of the loaded data, so a
  one-month query doesn't render every tick as the same month.

![The data loader and visualizer control panels, with 2,251 records loaded into the sortable data table](docs/figures/app-ui.png)

## Quick start

### With pixi (recommended)

Install [pixi](https://pixi.sh), then from the repository root:

```bash
pixi install
```

```bash
pixi run app
```

### With pip

Requires Python 3.11 or newer.

```bash
pip install -e ".[dev]"
```

```bash
python -m earthquake_dashboard.app
```

### Using the app

Open <http://127.0.0.1:8050>. The landing page carries a quick-start guide; click
**Launch Dashboard** — or go straight to `/dashboard` — to reach the app itself. There:

1. Set your query with the date, magnitude, significance, depth, latitude, and
   longitude controls.
2. Click **Preview Count** to see how many events match, without downloading them.
3. Click **Fetch Data** to fetch the records into the table.
4. Click **Render Chart** to build the linked charts.

**Clear Table** empties the table and resets the count. Set `DASH_DEBUG=1` to start the app
with Dash's debug tooling enabled.

## The data

Records come from the USGS FDSN event API on demand and are never committed; anything
written under `data/` is gitignored. Each loaded event carries these fields, and the
loader enforces their types before the visualizer will accept a frame:

| Field | Type | Meaning |
|---|---|---|
| `place` | string | Human-readable location description |
| `time` | datetime (UTC) | When the event occurred |
| `lat` / `lon` | float | Geographic coordinates |
| `depth` | float | Depth below the surface, in km |
| `mag` | float | Magnitude |
| `sig` | int | USGS significance score |
| `tsunami` | bool | Whether a tsunami was generated |
| `cdi` | float | Community Decimal Intensity (reported shaking) |
| `alert` | string | PAGER alert level: green, yellow, orange, or red |

A single request is capped at 20,000 records by the API.

## Known limitations

**A map brush goes stale when a histogram filter widens.** With interval brushes active
on *both* the map and a histogram, widening the histogram brush brings the newly matching
earthquakes onto the map greyed out and leaves them out of the heatmap. Repositioning the
map brush forces a re-evaluation and they appear. This predates the package restructure —
it is present in the original build and on the deployed app.

The likely cause is that the map's brush has no data fields to project onto. A Vega-Lite
interval selection projects onto its view's `x` and `y` channels, but the earthquake layer
positions its marks with `longitude`/`latitude` through a projection, so there are no
invertible scales; the selection compiles with neither `encodings` nor `fields`, and so
cannot act as a data predicate the way the histogram brushes can.

Cross-filtering itself is unaffected — brushing a histogram does filter both the map and
the heatmap.

## Architecture

The code is a small installable package under `src/earthquake_dashboard/`, in three
layers:

| Module | Responsibility |
|---|---|
| `data_loader.py` | `RequestParams`, a validated dataclass mirroring the USGS query parameters, and `DataLoader`, which counts, queries, and preprocesses against the live API and returns a typed GeoDataFrame |
| `visualizer.py` | `DataVisualizer` checks the input frame's columns and dtypes, then composes the Altair chart: world map plus earthquake layer, per-variable histogram selectors, and a heatmap, all wired through shared selections |
| `app.py` + `pages/` | The multi-page Dash app — layout, widgets, and the callbacks connecting user input to the two classes above |

Keeping the API client and the chart factory out of the Dash layer means both can be
exercised directly by the test suite, without standing up a server.

## Project structure

| Path | Purpose |
|---|---|
| `src/earthquake_dashboard/` | Installable package: API client, chart factory, Dash app |
| `src/earthquake_dashboard/pages/` | `index.py` (landing page and quick-start guide, at `/`) and `dashboard.py` (the loader and visualizer, at `/dashboard`) |
| `src/earthquake_dashboard/assets/` | Stylesheet driving the dashboard's grid layout |
| `tests/` | pytest suite |
| `notebooks/` | `eq-dashboard.ipynb`, the self-contained ipywidgets prototype this dashboard grew out of |
| `docs/figures/` | Images used in this README |
| `docs/make_figures.mjs` | Regenerates those images by driving the running app with headless Chrome |
| `pixi.toml` / `pyproject.toml` | Environment, packaging, and tool configuration |

## Development

```bash
pixi run check
```

That runs lint and tests together; `pixi run lint`, `pixi run format`, and
`pixi run test` run [ruff](https://docs.astral.sh/ruff/) check, ruff format, and pytest
individually.

The suite covers request-parameter validation, the DataFrame contract `DataVisualizer`
enforces, and live count/query/preprocess round trips against the real API. The live
tests skip themselves when USGS is unreachable, and assert relationships rather than
fixed record counts — the catalog is revised over time, so pinning an exact number for
a historical window makes the suite fail for reasons that have nothing to do with the
code.

CI runs the same lint and tests on Python 3.11 and 3.12.

### Regenerating the README figures

The figures under `docs/figures/` are captured from the real app rather than hand-cropped.
Start the app, then drive it with headless Chrome:

```bash
CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe" node docs/make_figures.mjs
```

It loads a query, sets the map to colour by magnitude, clicks through Preview Count /
Render Chart, and writes both PNGs. `MIN_MAG`, `COLOR_VAR`, `BASE`, and `OUTDIR` override the
defaults. Node 22+ only — no npm install, it uses the built-in WebSocket to speak CDP.

## Deployment

The dashboard is hosted on [Plotly Cloud](https://plotly.com/) at
<https://0be82526-8d32-4767-bbed-2b63946ff944.plotly.app/>, running Altair 5.5 on
Python 3.13. That version matters: `altair` is pinned to `>=5,<6` here because Altair 6
emits Vega-Lite v6 specs, while the renderer bundled with `dash-vega-components` speaks
Vega-Lite v5. Unpinned, the chart still renders but the browser warns about the
mismatch and falls back to best-effort handling of anything v6-specific.

The deployed copy is the same code as `src/earthquake_dashboard/`, flattened
(`app2.py`, `DataLoader.py`, `DataVisualizer.py`, `pages/`) to suit the platform, with
its conda environment captured in a `Viz.yaml` export.
