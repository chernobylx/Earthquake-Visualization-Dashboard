import pandas as pd
import geopandas as gpd
import altair as alt
from vega_datasets import data
from DataLoader import COL_TYPES

alt.data_transformers.disable_max_rows()
class DataVisualizer:
    def __init__(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input must be a pandas DataFrame"
        assert not df.empty, "Input DataFrame must not be empty"
        for col in COL_TYPES.keys():
            assert col in df.columns, f"DataFrame must contain '{col}' column"


        for col, expected_type in COL_TYPES.items():
            assert df[col].dtype == expected_type, f"Column '{col}' must be of type {expected_type}"
        #set internal dataframe
        self.df = df

    def create_heatmap(self, filters, width, height, x_var='time', y_var='depth', color_var='max(mag)'):
        day = 24*60*60*1000

        if x_var == 'time':
            X = alt.X('time:T',
                      axis = alt.Axis(format = '%Y'),
                      bin = alt.BinParams(step = 365 * day),
                      title = 'Date')
            X_tooltip = alt.Tooltip('year(time):T', title='Time')
        else:
            X = alt.X(x_var+':Q',
                      axis = alt.Axis(),
                      bin = alt.BinParams(),
                      title = x_var.capitalize())
            X_tooltip = alt.Tooltip(x_var+':Q', title=x_var.capitalize())

        reversed_y = (y_var == 'depth')
        if y_var == 'time':
            Y = alt.Y('time:T',
                      axis = alt.Axis(format = '%Y'),
                      bin = alt.BinParams(step = 365 * day),
                      title = 'Date')
            Y_tooltip = alt.Tooltip('year(time):T', title='Time')
        else:
            Y = alt.Y(y_var+':Q',
                      axis = alt.Axis(),
                      scale = alt.Scale(reverse = reversed_y),
                      bin = alt.BinParams(),
                      title = y_var.capitalize())
            Y_tooltip = alt.Tooltip(y_var+':Q', title=y_var.capitalize())

        Color = alt.Color(color_var,
                          scale = alt.Scale(scheme = 'magma'))


        chart = alt.Chart(self.df).mark_rect().encode(
            x = X,
            y = Y,
            color = Color,
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

    def create_hists_selectors(self, filter_vars, filter_width, filter_height, color_scheme='magma'):
        hists = {}
        selectors = {}
        for var in filter_vars:

            selectors[var] = alt.selection_interval(name = var + '_brush')
            if var == 'time':
                x = alt.X('time:T',
                        timeUnit = 'year',
                        axis = alt.Axis(format = '%Y'),
                        title = None)
                type = ':T'

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
                   Projection = alt.Projection(type = 'equalEarth')):
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
                     size_var = 'mag', size_range = [10, 200],
                     filter_vars = ['time', 'mag', 'sig', 'depth', 'lon', 'lat'],
                     heatmap_x = 'time', heatmap_y = 'depth', heatmap_color = 'max(mag)'):
        map_width = int(.6 * width)
        map_height = int(.8 * height)

        filter_width = map_width
        filter_height = int((height - map_height) / len(filter_vars))

        heatmap_width = width - map_width
        heatmap_height = map_height

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

        filters = [selector for selector in selectors.values()]
        filters.append(brush)
        heatmap = self.create_heatmap(filters = filters,
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


