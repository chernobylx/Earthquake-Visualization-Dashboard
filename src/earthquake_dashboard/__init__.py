"""Interactive dashboard for exploring the USGS Earthquake Catalog.

The package is organised in three layers:

- :mod:`earthquake_dashboard.data_loader` -- typed request parameters and a
  client for the USGS FDSN event API.
- :mod:`earthquake_dashboard.visualizer` -- composable Altair charts (map,
  linked histograms, heatmap) built from a validated DataFrame.
- :mod:`earthquake_dashboard.app` -- the multi-page Dash application that
  wires the two together.
"""

__version__ = "1.0.0"
