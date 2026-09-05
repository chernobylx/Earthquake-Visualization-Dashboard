import re
from datetime import timedelta
from typing import NamedTuple

import altair as alt
import pandas as pd
from pandas.api import types as pdtypes
from vega_datasets import data

from earthquake_dashboard.data_loader import COL_TYPES

alt.data_transformers.disable_max_rows()

# What each COL_TYPES entry means, rather than how it happens to be spelled.
# Comparing dtypes by string equality rejects frames holding exactly the right
# values in a different container: pandas' own `string` dtype, an arrow-backed
# `string[pyarrow]`, or pandas 3's `str`. marimo's dataframe widget hands one of
# those back on molab, and `'string' != 'object'` cost the notebook its chart
# with "Column 'place' must be of type object" (#42). Unknown spellings fall
# back to equality, so adding a column to COL_TYPES cannot silently pass.
DTYPE_HOLDS = {
    # is_string_dtype alone is not enough: on an object column pandas infers the
    # contents, and USGS leaves `alert` mostly null, so a real frame reads
    # is_string=False and got rejected with "must be of type object, got
    # object". Accept object as it always was, and string dtypes as well.
    'object': lambda s: pdtypes.is_object_dtype(s) or pdtypes.is_string_dtype(s),
    'float64': pdtypes.is_float_dtype,
    'int64': pdtypes.is_integer_dtype,
    'bool': pdtypes.is_bool_dtype,
    # Any timezone, not only UTC: the loader produces UTC and the front-ends
    # re-localise to it, but a chart does not care which zone it is given.
    'datetime64[ns, UTC]': lambda s: pdtypes.is_datetime64_any_dtype(s)
    and getattr(s.dtype, 'tz', None) is not None,
}


# A heatmap coloured by max(mag) or min(depth) reduces each cell to one record,
# so the cell can name it. Matches those shorthands and nothing else: mean(depth)
# has no owning record to point at.
EXTREMUM = re.compile(r'^(max|min)\((\w+)\)$')


class AxisSpec(NamedTuple):
    """How one heatmap axis is binned, scaled and labelled.

    Built once and used by both heatmap builders, which differ only in whether
    they bin in the encoding or in a transform.
    """
    var: str
    bin: alt.BinParams
    axis: alt.Axis
    type: str          # 'T' or 'Q', the Vega-Lite type shorthand
    title: str         # axis title
    tip_title: str     # tooltip row label
    tip_format: object = alt.Undefined
    scale: object = alt.Undefined



class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input must be a pandas DataFrame"
        assert not df.empty, "Input DataFrame must not be empty"
        for col in COL_TYPES.keys():
            assert col in df.columns, f"DataFrame must contain '{col}' column"


        for col, expected_type in COL_TYPES.items():
            holds = DTYPE_HOLDS.get(expected_type)
            ok = holds(df[col]) if holds else df[col].dtype == expected_type
            assert ok, (
                f"Column '{col}' must be of type {expected_type}, got {df[col].dtype}"
            )
        #set internal dataframe
        self.df = df

    def create_heatmap(self, filters, width, height, x_var='time', y_var='depth', color_var='max(mag)'):
        day = 24*60*60*1000
        time_range = self.df['time'].max() - self.df['time'].min()
        format = '%Y'
        if time_range < timedelta(days = 1000):
            format = '%Y-%m'
        if time_range < timedelta(days = 100):
            format = '%Y-%m-%d'

        n_days = int(time_range / timedelta(days=1))
        step = int(n_days/12) * day

        if x_var == 'time':
            x = AxisSpec(x_var, alt.BinParams(step = step), alt.Axis(format = format),
                         'T', 'Date', 'Time', format)
        else:
            x = AxisSpec(x_var, alt.BinParams(), alt.Axis(),
                         'Q', x_var.capitalize(), x_var.capitalize())

        if y_var == 'time':
            y = AxisSpec(y_var, alt.BinParams(step = 365 * day), alt.Axis(format = '%Y'),
                         'T', 'Date', 'Time', '%Y')
        else:
            y = AxisSpec(y_var, alt.BinParams(), alt.Axis(),
                         'Q', y_var.capitalize(), y_var.capitalize(),
                         scale = alt.Scale(reverse = (y_var == 'depth')))

        extremum = EXTREMUM.match(color_var)
        if extremum:
            return self._extremum_heatmap(filters, width, height,
                                          *extremum.groups(), color_var, x, y)

        # Every tooltip below repeats its channel's bin. A tooltip on the raw
        # field instead adds that field to the aggregate's groupby, which splits
        # each cell by exact time or depth: the rects overplot and the colour
        # stops being the bin's true extremum.
        X = alt.X(f'{x.var}:{x.type}', axis = x.axis, bin = x.bin, title = x.title)
        X_tooltip = alt.Tooltip(f'{x.var}:{x.type}', bin = x.bin,
                                format = x.tip_format, title = x.tip_title)
        Y = alt.Y(f'{y.var}:{y.type}', axis = y.axis, bin = y.bin,
                  scale = y.scale, title = y.title)
        Y_tooltip = alt.Tooltip(f'{y.var}:{y.type}', bin = y.bin,
                                format = y.tip_format, title = y.tip_title)

        chart = alt.Chart(self.df).mark_rect().encode(
            x = X,
            y = Y,
            color = alt.Color(color_var, scale = alt.Scale(scheme = 'magma')),
            tooltip = [X_tooltip,
                       Y_tooltip,
                       alt.Tooltip(color_var, title = color_var.capitalize())]
        ).transform_filter(
            *filters
        ).properties(
            width=width,
            height=height,
        )
        return chart

    def _extremum_heatmap(self, filters, width, height, op, field, color_var,
                          x: AxisSpec, y: AxisSpec):
        """A heatmap whose cells name the earthquake holding the extremum.

        max(mag) or min(depth) reduces each cell to a single record, so the cell
        can say which one it was. The binning and aggregation are spelled out as
        transforms rather than left to the encodings, because the encoding form
        -- tooltip {"aggregate": {"argmax": "mag"}, "field": "place"} -- is
        miscompiled by Vega-Lite 6: it emits datum["place"], dropping the
        argmax_mag wrapper the aggregate actually writes, and the tooltip reads
        "undefined" (issue #27). Vega-Lite 5 emits the nested access correctly,
        so the bug only showed in the marimo front-end, which bundles Vega 6,
        and not in Dash, which is on Vega 5. Aggregating explicitly and pulling
        the field out with our own calculate is right on both.
        """
        # bin='binned' below puts the axis on a linear scale over epoch
        # milliseconds, so a time format string would reach d3-format and throw
        # "invalid format: %Y-%m-%d". Saying which kind of format it is fixes it.
        x_axis = alt.Axis(format = x.tip_format, formatType = 'time') if x.type == 'T' else x.axis
        y_axis = alt.Axis(format = y.tip_format, formatType = 'time') if y.type == 'T' else y.axis

        chart = alt.Chart(self.df).transform_filter(*filters)

        # Binning in a transform rather than an encoding means Vega-Lite never
        # infers a date parse for a time axis, and binning the raw ISO strings
        # yields NaN -- every row is then dropped by its own invalid-value
        # filter. Converting first is what keeps the cells on screen.
        x_source, y_source = x.var, y.var
        if x.var == 'time':
            chart = chart.transform_calculate(_x_time = 'toDate(datum.time)')
            x_source = '_x_time'
        if y.var == 'time':
            chart = chart.transform_calculate(_y_time = 'toDate(datum.time)')
            y_source = '_y_time'

        chart = chart.transform_bin(['x0', 'x0_end'], field = x_source, bin = x.bin)
        chart = chart.transform_bin(['y0', 'y0_end'], field = y_source, bin = y.bin)
        chart = chart.transform_aggregate(
            [alt.AggregatedFieldDef(op = op, field = field, **{'as': 'metric'}),
             alt.AggregatedFieldDef(op = 'arg' + op, field = field, **{'as': '_winner'})],
            groupby = ['x0', 'x0_end', 'y0', 'y0_end'],
        ).transform_calculate(
            location = 'datum._winner.place'
        )

        # The bin transform emits epoch milliseconds. Encoding those as temporal
        # leaves Vega-Lite in two minds about the field -- it parses it as a
        # number, then generates the mark's aria description with the numeric
        # format(), which throws "invalid format: %Y-%m-%d" at runtime. Handing
        # it real dates keeps one consistent view of the field.
        x_field, y_field = 'x0', 'y0'
        if x.type == 'T':
            chart = chart.transform_calculate(x_date = 'toDate(datum.x0)',
                                              x_date_end = 'toDate(datum.x0_end)')
            x_field = 'x_date'
        if y.type == 'T':
            chart = chart.transform_calculate(y_date = 'toDate(datum.y0)',
                                              y_date_end = 'toDate(datum.y0_end)')
            y_field = 'y_date'

        # Vega-Lite renders a binned quantitative tooltip as a range ("0 - 100").
        # These cells are already binned, so it has nothing to widen and would
        # show the bin's start alone; build the same label from both edges.
        labels = {}
        if x.type == 'T':
            x_tip = alt.Tooltip(f'{x_field}:T', format = x.tip_format, title = x.tip_title)
        else:
            labels['_x_label'] = "format(datum.x0, '') + ' \u2013 ' + format(datum.x0_end, '')"
            x_tip = alt.Tooltip('_x_label:N', title = x.tip_title)
        if y.type == 'T':
            y_tip = alt.Tooltip(f'{y_field}:T', format = y.tip_format, title = y.tip_title)
        else:
            labels['_y_label'] = "format(datum.y0, '') + ' \u2013 ' + format(datum.y0_end, '')"
            y_tip = alt.Tooltip('_y_label:N', title = y.tip_title)
        if labels:
            chart = chart.transform_calculate(**labels)

        return chart.mark_rect().encode(
            x = alt.X(f'{x_field}:{x.type}', bin = 'binned', axis = x_axis, title = x.title),
            x2 = alt.X2(f'{x_field}_end'),
            y = alt.Y(f'{y_field}:{y.type}', bin = 'binned', axis = y_axis,
                      scale = y.scale, title = y.title),
            y2 = alt.Y2(f'{y_field}_end'),
            color = alt.Color('metric:Q', scale = alt.Scale(scheme = 'magma'),
                              title = color_var.capitalize()),
            # Vega-Lite builds a screen-reader description from every channel,
            # and for a bin='binned' channel it formats with the numeric
            # format() even when the axis format is a time format -- which
            # throws "invalid format: %Y-%m-%d" at runtime. Naming the cell
            # ourselves replaces that description, and says more anyway.
            description = alt.Description('location:N'),
            # Location leads, as it does in the map's point tooltip.
            tooltip = [alt.Tooltip('location:N', title = 'Location'),
                       x_tip,
                       y_tip,
                       alt.Tooltip('metric:Q', title = color_var.capitalize())],
        ).properties(
            width = width,
            height = height,
        )

    def create_hists_selectors(self, filter_vars, filter_width, filter_height, color_scheme='magma'):
        hists = {}
        selectors = {}
        for var in filter_vars:

            selectors[var] = alt.selection_interval(name = var + '_brush')
            if var == 'time':
                day = 24*60*60*1000
                time_range = self.df['time'].max() - self.df['time'].min()
                format = '%Y'
                if time_range < timedelta(days = 1000):
                    format = '%Y-%m'
                if time_range < timedelta(days = 100):
                    format = '%Y-%m-%d'

                n_days = int(time_range / timedelta(days=1))
                step = int(n_days/12) * day
                x = alt.X('time:T',
                        axis = alt.Axis(format = format),
                        bin = alt.BinParams(step = step),
                        title = 'Date')
                    
                type = ':T'
            elif var == 'depth':
                type = ':Q'
                x = alt.X(var+type, bin = alt.Bin(step=12.5), title = None)
            else:
                type = ':Q'
                x = alt.X(var + type, bin=alt.Bin(maxbins=30), title = None)

            hists[var] = alt.Chart(self.df).mark_bar().encode(
                x = x,
                y = alt.Y('count()', title = var[:4]),
                color = alt.condition(selectors[var],
                                    alt.Color('mag:Q',
                                            scale = alt.Scale(scheme = color_scheme)),
                                    alt.value('lightgrey')),
                order = alt.Order(var+type, sort='ascending')
                ).properties(
                    width = filter_width,
                    height = filter_height,
                ).add_params(
                    selectors[var]
                )
        return hists, selectors

    def create_map(self,
                   map_fill: str = 'red',
                   map_stroke: str = 'blue',
                   map_width: int = 800,
                   map_height: int = 600,
                   Projection = None):
        if Projection is None:
            Projection = alt.Projection(type = 'equalEarth')
        topo = alt.topo_feature(data.world_110m.url, 'countries')
        earth = alt.Chart(topo).mark_geoshape(
            fill = map_fill,
            stroke = map_stroke
        ).properties(
            width = map_width,
            height = map_height,
            projection = Projection
            
        )

        graticule = alt.Chart(alt.graticule()).mark_geoshape().properties(projection = Projection)

        earth += graticule
        return earth

    def create_chart(self, width=1200, height=800,
                     projection ='equalEarth', phi = 0, theta = 0, scale = 100,
                     map_fill = 'darkgrey', map_stroke = 'lightgrey', background = 'darkgrey',
                     color_var = 'sig', color_scheme = 'magma',
                     opacity_var = 'mag',
                     size_var = 'mag', size_range = (10, 200),
                     filter_vars = ('time', 'mag', 'sig', 'depth', 'lon', 'lat'),
                     heatmap_x = 'time', heatmap_y = 'depth', heatmap_color = 'max(mag)'):
        size_range = list(size_range)
        filter_vars = list(filter_vars)
        width *= .75
        height *= .8
        map_width = int(.6 * width)
        map_height = int(.8 * height)

        filter_width = map_width
        # Plot-area height per histogram. Each row also renders roughly 20px of
        # x-axis and 20px of vconcat spacing outside this value, so the composed
        # chart grows about 40px per histogram whatever we do here. Clamp so the
        # bars stay readable rather than collapsing to 12px at ten histograms —
        # the front-end slots scroll.
        filter_height = max(24, int((height - map_height) / len(filter_vars)))

        heatmap_width = width - map_width
        heatmap_height = height

        rotation = [phi, theta, 0]
        Projection = alt.Projection(type = projection,
                                    rotate=rotation,
                                    scale = scale,
                                    translate = [map_width/2, map_height/2])

        if color_var == 'time':
            color_var += ':T'
        else:
            color_var += ':Q'

        if size_var == 'time':
            size_var += ':T'
        else:
            size_var += ':Q'

        if opacity_var == 'time':
            opacity_var += ':T'
        else:
            opacity_var += ':Q'

        ColorScale = alt.Scale(scheme = color_scheme, domain = [self.df[color_var[:-2]].min(), self.df[color_var[:-2]].max()])
        ColorLegend = alt.Legend(title = color_var)
        Color = alt.Color(color_var, scale = ColorScale, legend=ColorLegend)

        SizeScale = alt.Scale(range=size_range, domain = [self.df[size_var[:-2]].min(), self.df[size_var[:-2]].max()])
        SizeLegend = alt.Legend(title = size_var)
        Size = alt.Size(size_var, scale=SizeScale, legend=SizeLegend)

        OpacityScale = alt.Scale(range = [0.1, 1], domain = [self.df[opacity_var[:-2]].min(), self.df[opacity_var[:-2]].max()])
        OpacityLegend = alt.Legend(title = opacity_var)
        Opacity = alt.Opacity(opacity_var, scale=OpacityScale, legend=OpacityLegend)

        hists, selectors = self.create_hists_selectors(filter_vars, filter_width, filter_height, color_scheme=color_scheme)

        earth = self.create_map(map_fill, map_stroke, map_width, map_height, Projection)

        brush = alt.selection_interval(name = "brush")
        quakes = alt.Chart(self.df).mark_circle().encode(
            longitude = 'lon:Q',
            latitude = 'lat:Q',
            size = Size,
            opacity= Opacity,
            color = alt.condition(brush,
                                Color,
                                alt.value('lightgrey')),
            order = alt.Order('time:T', sort='ascending'),
            tooltip = [
                alt.Tooltip('place:N', title='Location'),
                alt.Tooltip('mag:Q', title='Magnitude'),
                alt.Tooltip('depth:Q', title='Depth (km)'),
                alt.Tooltip('time:T', title='Time')
            ]
        ).properties(
            projection = Projection
        ).add_params(
            brush
        ).transform_filter(
            *selectors.values()
        )

        # The map brush deliberately does NOT filter the heatmap. Its marks are
        # placed by longitude/latitude through a projection, so the selection has
        # no invertible scale to project onto and Vega-Lite compiles it to
        # vlSelectionIdTest -- an identity match on Vega's internal _vgsid_.
        # Those ids belong to the map's own data stream, so nothing in the
        # heatmap's stream ever matches and the whole heatmap emptied the moment
        # you dragged on the globe: measured at a 93% drop in drawn pixels.
        # It still colours the map through alt.condition above, which is the
        # part that works.
        heatmap = self.create_heatmap(filters = list(selectors.values()),
                                 x_var = heatmap_x,
                                 y_var = heatmap_y,
                                 width = heatmap_width,
                                 height = heatmap_height,
                                 color_var = heatmap_color)

        earth+=quakes

        for hist in hists.values():
            earth &= hist

        earth |= heatmap
        earth = earth.resolve_scale(color='independent')
        earth = earth.properties(background = background)
        return earth


