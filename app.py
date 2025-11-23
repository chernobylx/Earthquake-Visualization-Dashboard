#import requests
import pandas as pd
#from io import StringIO
#import ipywidgets as widgets
#from IPython.display import display, clear_output
#from datetime import datetime, timedelta
import altair as alt
from vega_datasets import data
#from ipywidgets import interact, interactive, fixed, interact_manual, IntSlider, FloatSlider, DatePicker
#import geopandas as gpd
#import json
import dash_vega_components as dvc
from dash import Dash, Input, Output, callback, dcc, html
alt.data_transformers.disable_max_rows()
import dash_daq

df = pd.read_csv('test.csv')
df.set_index('id', inplace=True)
df['time'] = pd.to_datetime(df['time'], format = 'ISO8601')
eq = df.sample(5000, random_state=42)

def create_chart(df, width=800, height=600, 
                 projection ='equalEarth', phi = 0, theta = 0, scale = 100,
                 map_fill = 'darkgrey', map_stroke = 'lightgrey',
                 color_var = 'significance', color_scheme = 'magma',
                 opacity_var = 'magnitude',
                 size_var = 'magnitude', size_range = [10, 200],
                 filter_vars = ['time', 'magnitude', 'significance', 'depth', 'longitude', 'latitude']):
    
    rotation = [phi, theta, 0]
    Projection = alt.Projection(type = projection, rotate=rotation, scale = scale, translate = [width/2, height/2])

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

    ColorScale = alt.Scale(scheme = color_scheme, domain = [df[color_var[:-2]].min(), df[color_var[:-2]].max()])
    ColorLegend = alt.Legend(title = color_var)
    Color = alt.Color(color_var, scale = ColorScale, legend=ColorLegend)
    #Color = alt.Color('magnitude:Q', scale = alt.Scale(scheme = 'magma', domain = [df['magnitude'].min(), df['magnitude'].max()]))
    SizeScale = alt.Scale(range=size_range)
    SizeLegend = alt.Legend(title = size_var)
    Size = alt.Size(size_var, scale=SizeScale, legend=SizeLegend)

    OpacityScale = alt.Scale(range = [0.1, 1])
    OpacityLegend = alt.Legend(title = opacity_var)
    Opacity = alt.Opacity(opacity_var, scale=OpacityScale, legend=OpacityLegend)


    hists = {}
    selectors = {}
    for var in filter_vars:
                    
        selectors[var] = alt.selection_interval(name = var + '_brush')
        if var == 'time':
            type = ':T'
        else:
            type = ':Q'

        hists[var] = alt.Chart(df).mark_bar().encode(
            x = alt.X(var + type, bin= alt.Bin(maxbins=30)),
            y = alt.Y('count()', 
                      scale = alt.Scale(type = 'symlog'), 
                      axis = alt.Axis(values = [10,100,1000])),
            color = alt.condition(selectors[var],
                                 alt.Color('magnitude:Q',
                                           scale = alt.Scale(scheme = 'magma',
                                                             domain = [df['magnitude'].min(), df['magnitude'].max()])),
                                 alt.value('lightgrey')),
            order = alt.Order(var + type, sort = 'ascending')
        ).properties(
            width = 600,
            height = 25
        ).add_params(
            selectors[var]
        )

    topo = alt.topo_feature(data.world_110m.url, 'countries')
    earth = alt.Chart(topo).mark_geoshape(
        fill = map_fill,
        stroke = map_stroke
    ).properties(
        width = width,
        height = height,
        projection = Projection
    )

    graticule = alt.Chart(alt.graticule()).mark_geoshape().properties(projection = Projection)

    earth += graticule


    brush = alt.selection_interval(name = "brush")

    quakes = alt.Chart(df).mark_circle().encode(
        longitude = 'longitude:Q',
        latitude = 'latitude:Q',
        size = Size,
        opacity= Opacity,
        color = alt.condition(brush,
                            Color,
                            alt.value('lightgrey')),
        tooltip = [
            alt.Tooltip('location:N', title='Location'),
            alt.Tooltip('magnitude:Q', title='Magnitude'),
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

    earth+=quakes

    for hist in hists.values():
        earth &= hist
    return earth
#
app = Dash()
app.layout = html.Div([
    html.H1('Title'),
    html.Div(
        ['Projection:',
         dcc.Dropdown(['equalEarth', 'mercator', 'azimuthalEqualArea'], 'mercator', id='proj_dd')]
    ),
    html.Div(
        ['Rotate:',
        dcc.Slider(-179.9,179.9,step=10,value=0,id = 'phi'),
        dcc.Slider(-89.9,89.9,step=10,value=0,id = 'theta')]
    ),
    html.Div(
        ['Scale:', dcc.Slider(100,1000,step=50,value=100,id = 'scale')]
    ),
    html.Div(
        [
            'Map Fill Color:',
            dcc.Input(value = '#4287f5', id='map_fill')
        ]
    ),
    html.Div(
        [
            'Map Stroke Color:',
            dcc.Input(value = 'lightgrey', id='map_stroke')
        ]
    ),
    html.Div(
        [
            'Background Color:',
            dcc.Input(value = '#444444', id='background')
        ]
    ),
    html.Div(
        [
            'Size Variable:',
            dcc.Dropdown(
                options = df.select_dtypes(include=['number']).columns.tolist(),
                value = 'magnitude',
                id='size_var'
            )
        ]
    ),
    html.Div(
        [
            'Color Variable:',
            dcc.Dropdown(
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = 'significance',
                id = 'color_var'
            )
        ]
    ),
     html.Div(
        [
            'Opacity Variable:',
            dcc.Dropdown(
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = 'time',
                id = 'opacity_var'
            )
        ]
    ),

    html.Div(id='output_div'),

])

@callback(
    Output('output_div', 'children'),
    Input('proj_dd', 'value'),
    Input('phi', 'value'),
    Input('theta', 'value'),
    Input('scale', 'value'),
    Input('map_fill', 'value'),
    Input('map_stroke', 'value'),
    Input('background', 'value'),
    Input('size_var', 'value'),
    Input('color_var', 'value'),
    Input('opacity_var', 'value')
)
def update_output(proj_dd, phi, theta, scale, map_fill, map_stroke, background, size_var, color_var, opacity_var):
    chart_spec = create_chart(df, 
                              projection=proj_dd, 
                              phi=phi, theta=theta, 
                              scale = scale, 
                              map_fill=map_fill, 
                              map_stroke = map_stroke,
                              size_var=size_var,
                              color_var=color_var,
                              opacity_var=opacity_var
                              ).properties(
                                  background = background).to_dict()
    return dvc.Vega(
        id='map',
        signalsToObserve=['brush'],
        opt={"renderer": 'svg', 'actions': False},
        spec=chart_spec
    )
app.run(debug = True)