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


# Vega-Lite draws every axis label, legend entry and title in #000 unless the
# spec says otherwise, which on this app's dark canvas came out as 167 unreadable
# text nodes. The chart already knows what it is being drawn on -- create_chart
# takes the canvas colour -- so it picks its own ink from that rather than
# assuming a theme, which keeps it right in all three front-ends and for whatever
# colour someone types into the Canvas Color box.
LIGHT_INK = '#ece8f4'
MUTED_INK = '#a49ab6'   # axis and legend labels, which outnumber everything else
DARK_INK = '#1a1206'
MUTED_DARK_INK = '#4a4550'

# Enough of the CSS names to cover this app's own defaults and the obvious
# choices. Anything else falls back to light, since every front-end ships dark --
# a wrong guess there is visible and fixable, where leaving Vega's default is the
# black-on-black this exists to prevent. Parsed without matplotlib or Pillow on
# purpose: both are present here only transitively, and the Plotly Cloud bundle
# installs just the seven declared dependencies.
CSS_COLORS = {
    'black': (0, 0, 0), 'white': (255, 255, 255),
    'grey': (128, 128, 128), 'gray': (128, 128, 128),
    'darkgrey': (169, 169, 169), 'darkgray': (169, 169, 169),
    'lightgrey': (211, 211, 211), 'lightgray': (211, 211, 211),
    'dimgrey': (105, 105, 105), 'dimgray': (105, 105, 105),
    'silver': (192, 192, 192), 'gainsboro': (220, 220, 220),
    'whitesmoke': (245, 245, 245), 'ivory': (255, 255, 240),
    'darkblue': (0, 0, 139), 'navy': (0, 0, 128), 'midnightblue': (25, 25, 112),
    'darkslategrey': (47, 79, 79), 'darkslategray': (47, 79, 79),
    'darkgreen': (0, 100, 0), 'maroon': (128, 0, 0), 'indigo': (75, 0, 130),
    'steelblue': (70, 130, 180), 'lightblue': (173, 216, 230),
    'beige': (245, 245, 220), 'wheat': (245, 222, 179),
}


def _rgb(color) -> tuple[int, int, int] | None:
    """(r, g, b) for a hex, rgb()/rgba() or known-named CSS colour, else None."""
    if not isinstance(color, str):
        return None
    value = color.strip().lower()

    if value in CSS_COLORS:
        return CSS_COLORS[value]

    if value.startswith('#'):
        digits = value[1:]
        if len(digits) in (3, 4):          # #abc and #abcd
            digits = ''.join(d * 2 for d in digits[:3])
        if len(digits) in (6, 8):          # #aabbcc and #aabbccdd
            try:
                return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
        return None

    if value.startswith(('rgb(', 'rgba(')):
        parts = value[value.index('(') + 1:].rstrip(')').replace('/', ',').split(',')
        try:
            channels = [float(p.strip().rstrip('%')) for p in parts[:3]]
        except ValueError:
            return None
        if len(channels) < 3:
            return None
        return tuple(max(0, min(255, round(c))) for c in channels)

    return None


def ink_for(background) -> str:
    """The text colour to draw on `background`."""
    rgb = _rgb(background)
    if rgb is None:
        return LIGHT_INK
    r, g, b = rgb
    # Rec. 709 relative luminance, on the same 0-255 scale as the channels.
    return DARK_INK if (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140 else LIGHT_INK


DAY_MS = 24 * 60 * 60 * 1000

# Bin widths to fall back on when a day is too coarse: 1 minute through 1 day.
# A day sits at the top so the sub-day range meets the whole-day one instead of
# moving the cliff somewhere else.
SUB_DAY_STEPS = (60_000, 300_000, 900_000, 1_800_000,
                 3_600_000, 10_800_000, 21_600_000, 43_200_000, DAY_MS)


def time_bin(span: timedelta) -> tuple[int, str]:
    """Bin width in milliseconds for a time axis, and an axis format to match.

    Aims for roughly a dozen bins across `span`. The whole-day arithmetic is
    the original calculation, kept exactly so every span of twelve days or more
    bins as it always has -- the shipped 30-day default still comes out at two
    days. It is only the floor that is new: `int(n_days / 12)` reached 0 for any
    span under twelve days (#29), and Vega does not reject `"bin": {"step": 0}`.
    It ignores it, deriving bins from the data extent instead, which puts the
    edges at arbitrary times of day and -- because an extent moves when a
    selection filters the data -- makes the columns shift under a brush.
    """
    step = int(span / timedelta(days=1)) // 12 * DAY_MS
    if step == 0:
        target = span.total_seconds() * 1000 / 12
        step = min(SUB_DAY_STEPS, key=lambda candidate: abs(candidate - target))

    format = '%Y'
    if span < timedelta(days=1000):
        format = '%Y-%m'
    if span < timedelta(days=100):
        format = '%Y-%m-%d'
    if step < DAY_MS:
        format = '%m-%d %H:%M'
    return step, format


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
        time_range = self.df['time'].max() - self.df['time'].min()
        step, format = time_bin(time_range)

        if x_var == 'time':
            x = AxisSpec(x_var, alt.BinParams(step = step), alt.Axis(format = format),
                         'T', 'Date', 'Time', format)
        else:
            x = AxisSpec(x_var, alt.BinParams(), alt.Axis(),
                         'Q', x_var.capitalize(), x_var.capitalize())

        if y_var == 'time':
            # Sized from the span like the x axis, rather than a hardcoded year:
            # that put every event of a week-long query into one row.
            y = AxisSpec(y_var, alt.BinParams(step = step), alt.Axis(format = format),
                         'T', 'Date', 'Time', format)
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
                time_range = self.df['time'].max() - self.df['time'].min()
                step, format = time_bin(time_range)
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

        # The map brush cross-filters the heatmap, like every histogram brush.
        # It cannot do so the same way, though: the map's marks are placed by
        # longitude/latitude through a projection, which has no invertible scale
        # for a selection to project onto, so Vega-Lite compiles this one to
        # vlSelectionIdTest -- an identity match on Vega's internal _vgsid_
        # rather than a range test on lon/lat. Vega assigns those ids in an
        # identifier transform on one dataset, so the match holds only while the
        # heatmap's rows and the map's rows come from that same dataset. Every
        # view here is built from alt.Chart(self.df), which altair serialises to
        # a single named dataset, so they do -- see
        # test_the_heatmap_and_the_map_read_the_same_dataset, which fails if a
        # later change splits them, because the symptom is a silently empty
        # heatmap rather than a broken spec.
        heatmap = self.create_heatmap(filters = [*selectors.values(), brush],
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

        # Labels outnumber titles many times over, so they take the muted tone
        # and the titles carry the contrast. Gridlines and domains are pulled
        # most of the way back into the canvas: at Vega's default they drew a
        # white cage around every histogram.
        ink = ink_for(background)
        muted = MUTED_INK if ink == LIGHT_INK else MUTED_DARK_INK
        structure = '#2e2640' if ink == LIGHT_INK else '#d8d4dd'
        return earth.configure_axis(
            labelColor = muted,
            titleColor = ink,
            gridColor = structure,
            domainColor = structure,
            tickColor = structure,
        ).configure_legend(
            labelColor = muted,
            titleColor = ink,
        ).configure_title(
            color = ink,
        ).configure_view(
            stroke = None,
        ).configure_text(
            color = ink,
        )


