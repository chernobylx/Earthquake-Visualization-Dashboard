import pandas as pd
import altair as alt
import dash_vega_components as dvc
from dash import Dash, Input, Output, callback, dcc, html
from DataVisualizer import DataVisualizer

alt.data_transformers.disable_max_rows()


df = pd.read_csv('data/test.csv')

def preprocess(df):
    df.set_index('id', inplace=True)
    df['time'] = pd.to_datetime(df['time'], format = 'ISO8601')
    df = df.sample(5000, random_state=42)
    return df

df = preprocess(df)
visualizer = DataVisualizer(df)

app = Dash()
app.layout = html.Div([
    html.H1('Title'),
    html.Div(
        ['Projection:',
         dcc.Dropdown(['equalEarth', 'mercator', 'azimuthalEqualArea'], 'equalEarth', id='proj_dd')]
    ),
    html.Div(
        ['Rotate:',
        dcc.Slider(-179.9,179.9,step=10,value=0,id = 'phi'),
        dcc.Slider(-89.9,89.9,step=10,value=0,id = 'theta')]
    ),
    html.Div(
        ['Scale:', dcc.Slider(10,1000,step=10,value=120,id = 'scale')]
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
                value = 'magnitude',
                id = 'color_var'
            )
        ]
    ),
    html.Div(
        [
            'Opacity Variable:',
            dcc.Dropdown(
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = 'significance',
                id = 'opacity_var'
            )
        ]
    ),
    html.Div(
        [
            'Filters:',
            dcc.Dropdown(
                multi=True,
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = ['time', 'magnitude', 'significance'],
                id = 'filter_vars'
            )
        ]
    ),
    html.Div(
        [
            'Heatmap X:',
            dcc.Dropdown(
                multi=False,
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = 'time',
                id = 'heatmap_x'
            )
        ]
    ),
    html.Div(
        [
            'Heatmap Y:',
            dcc.Dropdown(
                multi=False,
                options = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist(),
                value = 'depth',
                id = 'heatmap_y'
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
    Input('opacity_var', 'value'),
    Input('filter_vars', 'value'),
    Input('heatmap_x', 'value'),
    Input('heatmap_y', 'value'),
)
def update_output(proj_dd, phi, theta, scale, map_fill, map_stroke, background,
                  size_var, color_var, opacity_var,
                  filter_vars,
                  heatmap_x, heatmap_y):
    chart_spec = visualizer.create_chart(
        projection=proj_dd,
        phi=phi, theta=theta,
        scale = scale,
        map_fill=map_fill,
        map_stroke = map_stroke,
        size_var=size_var,
        color_var=color_var,
        opacity_var=opacity_var,
        filter_vars=filter_vars,
        heatmap_x=heatmap_x,
        heatmap_y=heatmap_y,
        width = 1200,
        height = 500,
    ).properties(
        background = background).to_dict()
    return dvc.Vega(
        id='map',
        signalsToObserve=['brush'],
        opt={"renderer": 'svg', 'actions': False},
        spec=chart_spec
    )

app.run(debug = True)
