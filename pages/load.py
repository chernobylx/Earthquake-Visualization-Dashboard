import dash
import dash_vega_components as dvc
from dash import html, dcc, callback, Input, Output, State, dash_table
from datetime import datetime, date, timedelta
from DataLoader import DataLoader, RequestParams, DT_FORMAT
from DataVisualizer import DataVisualizer
import pandas as pd
dash.register_page(__name__)

layout = html.Div([
    html.Div(
    [
        html.H2('Data Loader'),
        html.Div(
        [
            html.H3('Date Range'),
            dcc.DatePickerRange(
                id = 'date_range',
                min_date_allowed=date(1900,1,1),
                max_date_allowed=date.today()+timedelta(days=1),
                initial_visible_month=date.today()-timedelta(days=30),
                start_date=date.today()-timedelta(days=30),
                end_date=date.today()+timedelta(days=1)
            ),
        ], className='widget'),

        html.Div(
        [
            html.H3('Magnitude Range'),
            dcc.RangeSlider(
                min=0,
                max=10,
                step=.1,
                value=[6,9.1],
                marks = None,
                tooltip = {"placement": "bottom", "always_visible": True},
                id = 'mag_range',
                className='slider'
            )
        ],
            id = 'mag-range',
            className='widget'
        ),

        html.Div(
        [
            html.Button('Count', id='count_button', n_clicks =0),
            html.Button('Load', id='load_button', n_clicks = 0),
            html.Button('Clear', id='clear_button', n_clicks = 0)
        ],
        id = 'buttons',
        className = 'widget'
        ),

        html.Div(
        [
            'Click Count'
        ],
        id='count_div',
        )

    ],
    id = 'data-loader', className='control-pannel'),
    html.Div(
    [
        dash_table.DataTable(
            id = 'data_table',
            page_size=10,
            filter_action = 'native',
            sort_action = 'native'),
    ], id = 'data_table_div'
    ),

    html.Div(
    [
        html.H2('Visualizer'),
        #Visualizer Control Pannel
        html.Div(
        [
            #Projection Widget
            html.Div(
            [
                html.H3('Projection:'),
                dcc.Dropdown(
                    ['equalEarth', 'mercator', 'azimuthalEqualArea'], 
                    value = 'equalEarth', 
                    id = 'projection_dd'
                )
            ], id = 'projection_widget', className = 'widget'
            ),
            #Map Control Widget
            html.Div(
            [
                html.H3('Map Controls:'),
                html.Div(
                [
                    html.H4('Rotate:'),
                    html.H5('Y:'),
                    dcc.Slider(min = -179.9,
                               max = 179.9,
                               step=10,
                               value=0,
                               marks = None,
                               tooltip = {"placement": "bottom", "always_visible": True},
                               id = 'phi',
                               className='slider'),
                    html.H5('X:'),
                    dcc.Slider(min = -89.9,
                               max = 89.9,
                               step=10,
                               value=0,
                               marks = None,
                               tooltip = {"placement": "bottom", "always_visible": True},
                               id = 'theta',
                               className='slider')
                ]
                ) 
            ], id = 'map_control_widget', className = 'widget'
            ),

            html.Button('Visualize', id = 'viz_button', n_clicks = 0),
        ], id = 'viz_control_pannel', className='control-pannel'
        ),
        html.Div([],
                 id = 'visualizer_output')
    ],
    id = 'visualizer_div'
    ),

])
layout = html.Div(children=[
    html.Div(['Hidden Div'], id='hidden_div', style={'display': 'none'}),
    html.Div(children=['Page'], id='layout')
])

@callback(
        Output('layout', 'children'),
        Input('hidden_div', 'children')
)
def build_page(input):
    layout = []
    layout.append(html.Div(['Data Loader'], id = 'loader', className='dashboard'))
    return layout

@callback(
        Output('loader', 'children'),
        Input('layout', 'children')
)
def build_loader(input):
    loader = []
    loader.append(html.Div(['Control Pannel'], id = 'loader_control_pannel', className='control-pannel'))
    loader.append(html.Div(['Data Table'], id = 'data_table', className='dashboard-output data-table'))
    return loader

@callback(
        Output('loader_control_pannel', 'children'),
        Input('loader', 'children')
)
def build_loader_control_pannel(input):
    control_pannel = []
    control_pannel.append(html.Div([], id = 'data_range', className='widget date-widget'))
    control_pannel.append(html.Div([], id='mag_range', className='widget slider-widget'))
    control_pannel.append(html.Div([], id='loader_button_widget', className='widget button-widget'))

@callback(
    Output('data_table', 'data', allow_duplicate=True),
    Output('data_table', 'columns'),
    State('date_range', 'start_date'),
    State('date_range', 'end_date'),
    State('mag_range', 'value'),
    Input('load_button', 'n_clicks'),
    prevent_initial_call=True,
)
def update_output(start_date, end_date,
                  magrange,
                  n_clicks):
    format = "%Y-%m-%d"
    start_time = datetime.strptime(start_date, format)
    start_time = datetime.strftime(start_time, DT_FORMAT)
    end_time = datetime.strptime(end_date, format)
    end_time = datetime.strftime(end_time, DT_FORMAT)

    params = RequestParams(starttime=start_time, endtime=end_time, minmagnitude=magrange[0], maxmagnitude=magrange[1])
    dl = DataLoader(params)
    dl.query()
    df = dl.preprocess()
    columns = [{"name": col, "id": col} for col in df.columns]
    return df.to_dict('records'), columns

@callback(
    Output('data_table', 'data', allow_duplicate=True),
    Output('count_div', 'children', allow_duplicate=True),
    Input('clear_button', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate = True
)
def clear_output(n_clicks):
    return pd.DataFrame().to_dict('records'), 'Click Count'

@callback(
    Output('count_div', 'children', allow_duplicate=True),
    State('date_range', 'start_date'),
    State('date_range', 'end_date'),
    State('mag_range', 'value'),
    Input('count_button', 'n_clicks'),
    prevent_initial_call = True
)
def count_earthquakes(start_date, end_date,
                  magrange,
                  n_clicks):
    format = "%Y-%m-%d"
    start_time = datetime.strptime(start_date, format)
    start_time = datetime.strftime(start_time, DT_FORMAT)
    end_time = datetime.strptime(end_date, format)
    end_time = datetime.strftime(end_time, DT_FORMAT)

    params = RequestParams(starttime=start_time, endtime=end_time, minmagnitude=magrange[0], maxmagnitude=magrange[1])
    dl = DataLoader(params)
    return f'Found {dl.count()} earthquakes' 


@callback(
    Output('visualizer_output', 'children'),
    State('data_table', 'derived_virtual_data'),
    State('projection_dd', 'value'),
    Input('viz_button', 'n_clicks'),
    prevent_initial_call = True
)
def update_visualizer(data,
                      projection,
                      n_clicks):
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    dv = DataVisualizer(df)
    spec = dv.create_chart(
        projection=projection
    ).to_dict()
    return dvc.Vega(
        id='map',
        opt={"renderer": 'svg', 'actions': False},
        spec=spec
    )
