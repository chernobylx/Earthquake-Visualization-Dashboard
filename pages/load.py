import dash
import dash_vega_components as dvc
from dash import html, dcc, callback, Input, Output, State, dash_table
from dash.exceptions import PreventUpdate
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
    layout.append(html.Div(['Visualizer'], id='visualizer', className='dashboard'))
    return layout

@callback(
        Output('loader', 'children'),
        Input('layout', 'children')
)
def build_loader(input):
    loader = []
    loader.append(html.Div(['Control Pannel'], id = 'loader_control_pannel', className='control-pannel'))
    loader.append(html.Div(['Data Table'], id = 'loader_output', className='dashboard-output'))
    return loader

@callback(
        Output('loader_output', 'children'),
        Input('loader', 'children')
)
def build_loader_output(input):
    loader_output = []
    loader_output.append(dash_table.DataTable(
            id = 'data_table',
            page_size=50,
            filter_action = 'native',
            sort_action = 'native',
            style_table={
                'height': '38vh',
                'width': '44vw',
                'overflowY': 'auto'
            },
            style_data={
                'whiteSpace': 'normal',
                'height': 'auto',
            },
            style_cell={'textAlign': 'left',
                        'wordBreak': 'break-all',
            },
            style_as_list_view=True,
            style_header={'backgroundColor': 'darkblue'},
            style_data_conditional=[
                {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(0,70,139)',
                },
                {
                'if': {'row_index': 'even'},
                'backgroundColor': 'rgb(70,0,139)',
                },
            ],
            style_filter={'backgroundColor': 'rgb(0,0,165)',
                          'color': 'rgb(0,0,165)'}   
        )
    )
    return loader_output


@callback(
        Output('loader_control_pannel', 'children'),
        Input('loader', 'children')
)
def build_loader_control_pannel(input):
    control_pannel = []
    control_pannel.append(html.Div(['Date'], id = 'date_range', className='widget date-widget'))
    control_pannel.append(html.Div(['Magnitude'], id='mag_range', className='widget slider-widget'))
    control_pannel.append(html.Div(['Significance'], id='sig_range', className='widget slider-widget'))
    control_pannel.append(html.Div(['Depth'], id='depth_range', className='widget slider-widget'))
    control_pannel.append(html.Div(['Latitude'], id='latitude_range', className='widget slider-widget'))
    control_pannel.append(html.Div(['Longitude'], id='longitude_range', className='widget slider-widget'))
    control_pannel.append(html.Div(['Buttons'], id='loader_button_widget', className='widget button-widget'))
    control_pannel.append(html.Div(['EQ Count'], id='count_output', className='widget output-widget'))
    return control_pannel

@callback(
    Output('date_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_date_range(input):
    widget = []
    widget.append(html.H4('Date Range'))
    widget.append(dcc.DatePickerRange(
        start_date=date.today()-timedelta(days=30),
        end_date=date.today()+timedelta(days=1),
        stay_open_on_select=False,
        id='date_range_picker',
        className='date_range_picker')
    )
    return widget

@callback(
    Output('mag_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_mag_range(input):
    widget = []
    widget.append(html.H5('mag:'))
    widget.append(
        dcc.RangeSlider(
            min=0,
            max=10,
            step=.1,
            value=[6,9.1],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True},
            id='mag_range_slider',
            className='slider'
        )
    )
    return widget

@callback(
    Output('sig_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_sig_range(input):
    widget = []
    widget.append(html.H5('sig:'))
    widget.append(
        dcc.RangeSlider(
            min=0,
            max=3000,
            step=50,
            value=[0, 3000],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True},
            id='sig_range_slider',
            className='slider'
        )
    )
    return widget

@callback(
    Output('depth_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_depth_range(input):
    widget = []
    widget.append(html.H5('depth:'))
    widget.append(
        dcc.RangeSlider(
            min=-100,
            max=1000,
            step=25,
            value=[-100, 1000],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True},
            id='depth_range_slider',
            className='slider'
        )
    )
    return widget

@callback(
    Output('latitude_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_latitude_range(input):
    widget = []
    widget.append(html.H5('lat:'))
    widget.append(
        dcc.RangeSlider(
            min=-90,
            max=90,
            step=1,
            value=[-90,90],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True},
            id='latitude_range_slider',
            className='slider'
        )
    )
    return widget

@callback(
    Output('longitude_range', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_longitude_range(input):
    widget = []
    widget.append(html.H5('lon:'))
    widget.append(
        dcc.RangeSlider(
            min=-180,
            max=180,
            step=1,
            value=[-180,180],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True},
            id='longitude_range_slider',
            className='slider'
        )
    )
    return widget




@callback(
    Output('loader_button_widget', 'children'),
    Input('loader_control_pannel', 'children')
)
def build_loader_buttons(input):
    widget = []
    widget.append(html.Button('Count', id='count_button', className='button', n_clicks=0))
    widget.append(html.Button('Load', id='load_button', className='button', n_clicks=0))
    widget.append(html.Button('Clear', id='clear_button', className='button', n_clicks=0))

    return widget

@callback(
        Output('visualizer', 'children'),
        Input('layout', 'children')
)
def build_visualizer(input):
    visualizer = []
    visualizer.append(html.Div(['Control Pannel'], id = 'visualizer_control_pannel', className='control-pannel'))
    visualizer.append(html.Div(['Visualization'], id = 'visualizer_output', className='dashboard-output visualization'))
    visualizer.append(dcc.Store(id='visualizer_dimensions', data={'width': None, 'height': None}))
    return visualizer

@callback(
        Output('visualizer_control_pannel', 'children'),
        Input('visualizer', 'children')
)
def build_visualizer_control_pannel(input):
    control_pannel = []
    control_pannel.append(html.Div(['Projection'], id='projection_widget', className='widget dropdown-widget'))
    control_pannel.append(html.Div(['Map Tools'], id='map_tools_widget', className='widget slider-widget'))
    control_pannel.append(html.Div(['Map Colors'], id='map_colors_widget', className='widget text-widget'))
    control_pannel.append(html.Div(['Map Aesthetics'], id='map_aesthetics_widget', className='widget dropdown-widget'))
    control_pannel.append(html.Div(['Heatmap Aesthetics'], id='heatmap_aesthetics_widget', className='widget dropdown-widget'))
    control_pannel.append(html.Div(['Filters'], id='filter_widget', className='widget dropdown-widget'))
    for i in range(7,8):
        control_pannel.append(html.Div([f'Widget{i}'], id=f'visualizer_widget{i}', className='widget'))

    control_pannel.append(html.Div(['Viz Buttons'], id='viz_button_widget', className='widget button-widget'))
    return control_pannel

@callback(
        Output('projection_widget', 'children'),
        Input('visualizer_control_pannel', 'children')
)
def build_projection_widget(input):
    widget = []
    widget.append(html.H4('Map Projection'))
    widget.append(
        dcc.Dropdown(
            options = ['naturalEarth1', 'azimuthalEqualArea', 'mercator'],
            value = 'naturalEarth1',
            id = 'projection_dropdown',
            className = 'widget dropdown-widget'
        )
    )

    return widget

@callback(
        Output('map_tools_widget', 'children'),
        Input('visualizer_control_pannel', 'children')
)
def build_map_tools_widget(input):
    widget = []
    widget.append(html.H5('Rotate Y:'))
    widget.append(dcc.Slider(
        min=-179.9,
        max=179.9,
        step = 1,
        value = 0,
        marks = None,
        tooltip={'placement': 'bottom', 'always_visible': True},
        id='phi_slider',
        className='slider'
    ))
    widget.append(html.H5('Rotate X:'))
    widget.append(dcc.Slider(
        min=-89.9,
        max=89.9,
        step = 1,
        value = 0,
        marks = None,
        tooltip={'placement': 'bottom', 'always_visible': True},
        id='theta_slider',
        className='slider'
    ))
    widget.append(html.H5('scale'))
    widget.append(dcc.Slider(
        min=10,
        max=1000,
        step = 10,
        value = 100,
        marks = None,
        tooltip={'placement': 'bottom', 'always_visible': True},
        id='scale_slider',
        className='slider'
    ))

    return widget

@callback(
        Output('map_colors_widget', 'children'),
        Input('visualizer_control_pannel', 'children')
)
def build_map_colors_widget(input):
    widgets = []
    widgets.append(html.H5('Background:'))
    widgets.append(dcc.Input(
        value='darkgrey',
        id='map_background',
        className='text_input'
    ))
    widgets.append(html.H5('Fill:'))
    widgets.append(dcc.Input(
        value='#00008d',
        id='map_fill',
        className='text_input'
    ))
    widgets.append(html.H5('Stroke:'))
    widgets.append(dcc.Input(
        value='lightgrey',
        id='map_stroke',
        className='text_input'
    )) 
    return widgets

@callback(
        Output('map_aesthetics_widget', 'children'),
        Input('data_table', 'data'),
        prevent_initial_callback = True
)
def build_map_aesthetics_widget(data):
    df = pd.DataFrame(data)
    cols = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist()
    widget = []
    widget.append(html.H5('Size:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'mag',
        id='size_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Color:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'depth',
        id='color_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Alpha:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'sig',
        id='alpha_dropdown',
        className='dropdown'
    ))

    return widget   

@callback(
        Output('heatmap_aesthetics_widget', 'children'),
        Input('data_table', 'data'),
        prevent_initial_callback = True
)
def build_heatmap_aesthetics_widget(data):
    df = pd.DataFrame(data)
    if len(df):
        df['time'] = pd.to_datetime(df['time'], utc=True, format='ISO8601')
    cols = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist()
    widget = []
    widget.append(html.H5('X:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'time',
        id='x_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Y:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'depth',
        id='y_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Color:'))
    widget.append(dcc.Dropdown(
        options=['max(mag)', 'mag', 'mean(depth)'],
        value = 'max(mag)',
        id='heatmap_color_dropdown',
        className='dropdown'
    ))

    return widget   

@callback(
        Output('filter_widget', 'children'),
        Input('data_table', 'data'),
        prevent_initial_callback=True
)
def build_filter_widget(data):
    df = pd.DataFrame(data)
    if len(df):
        df['time'] = pd.to_datetime(df['time'], utc=True, format='ISO8601')
    cols = df.select_dtypes(include=['number', 'datetime64[ns, UTC]']).columns.tolist()
    widget = []
    widget.append(html.H5('Filters:'))
    widget.append(dcc.Dropdown(
        multi=True,
        options=cols,
        value=['time', 'mag', 'depth'],
        id='filter_dropdown',
        className='dropdown multi-dropdown'
    ))

    return widget
@callback(
    Output('viz_button_widget', 'children'),
    Input('visualizer_control_pannel', 'children')
)
def build_viz_button_widget(input):
    widget = []
    widget.append(html.Button('Visualize', id='viz_button', className='button'))
    return widget

@callback(
    Output('data_table', 'data', allow_duplicate=True),
    Output('data_table', 'columns'),
    State('date_range_picker', 'start_date'),
    State('date_range_picker', 'end_date'),
    State('mag_range_slider', 'value'),
    State('sig_range_slider', 'value'),
    State('depth_range_slider', 'value'),
    State('latitude_range_slider', 'value'),
    State('longitude_range_slider', 'value'),
    Input('load_button', 'n_clicks'),
    prevent_initial_call=True,
)
def update_data_table(start_date, 
                        end_date,
                        magrange,
                        sigrange,
                        depthrange,
                        latrange,
                        lonrange,
                        n_clicks):
    if not n_clicks or n_clicks == 0:
        raise PreventUpdate
    else:
        format = "%Y-%m-%d"
        start_time = datetime.strptime(start_date, format)
        start_time = datetime.strftime(start_time, DT_FORMAT)
        end_time = datetime.strptime(end_date, format)
        end_time = datetime.strftime(end_time, DT_FORMAT)

        params = RequestParams(starttime=start_time, 
                               endtime=end_time, 
                               minmagnitude=magrange[0], 
                               maxmagnitude=magrange[1],
                               minsig=sigrange[0],
                               maxsig=sigrange[1],
                               mindepth=depthrange[0],
                               maxdepth=depthrange[1],
                               minlatitude=latrange[0],
                               maxlatitude=latrange[1],
                               minlongitude=lonrange[0],
                               maxlongitude=lonrange[1])
        dl = DataLoader(params)
        dl.query()
        df = dl.preprocess()
        columns = [{"name": col, "id": col} for col in df.columns]
        return df.to_dict('records'), columns

@callback(
    Output('data_table', 'data', allow_duplicate=True),
    Output('count_output', 'children', allow_duplicate=True),
    Input('clear_button', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate = True
)
def clear_output(n_clicks):
    if not n_clicks or n_clicks ==0:
        raise PreventUpdate
    else:
        return pd.DataFrame().to_dict('records'), 'Click Count'

@callback(
    Output('count_output', 'children', allow_duplicate=True),
    State('date_range_picker', 'start_date'),
    State('date_range_picker', 'end_date'),
    State('mag_range_slider', 'value'),
    State('sig_range_slider', 'value'),
    State('depth_range_slider', 'value'),
    State('latitude_range_slider', 'value'),
    State('longitude_range_slider', 'value'),
    Input('count_button', 'n_clicks'),
    prevent_initial_call = True
)
def count_earthquakes(start_date, 
                        end_date,
                        magrange,
                        sigrange,
                        depthrange,
                        latrange,
                        lonrange,
                        n_clicks):
    if not n_clicks or n_clicks==0:
        raise PreventUpdate
    else:
        format = "%Y-%m-%d"
        start_time = datetime.strptime(start_date, format)
        start_time = datetime.strftime(start_time, DT_FORMAT)
        end_time = datetime.strptime(end_date, format)
        end_time = datetime.strftime(end_time, DT_FORMAT)

        params = RequestParams(starttime=start_time, 
                               endtime=end_time, 
                               minmagnitude=magrange[0], 
                               maxmagnitude=magrange[1],
                               minsig=sigrange[0],
                               maxsig=sigrange[1],
                               mindepth=depthrange[0],
                               maxdepth=depthrange[1],
                               minlatitude=latrange[0],
                               maxlatitude=latrange[1],
                               minlongitude=lonrange[0],
                               maxlongitude=lonrange[1])
        dl = DataLoader(params)
        return f'Found {dl.count()} earthquakes' 


@callback(
    Output('visualizer_output', 'children'),
    State('data_table', 'derived_virtual_data'),
    State('projection_dropdown', 'value'),
    State('phi_slider','value'),
    State('theta_slider', 'value'),
    State('scale_slider', 'value'),
    State('map_fill', 'value'),
    State('map_stroke', 'value'),
    State('map_background', 'value'),
    State('size_dropdown', 'value'),
    State('color_dropdown', 'value'),
    State('alpha_dropdown', 'value'),
    State('x_dropdown', 'value'),
    State('y_dropdown', 'value'),
    State('heatmap_color_dropdown', 'value'),
    State('filter_dropdown', 'value'),
    Input('visualizer_dimensions', 'data'),
    Input('viz_button', 'n_clicks'),
    prevent_initial_call = True
)
def update_visualizer(data,
                      projection,
                      phi,
                      theta,
                      scale,
                      map_fill,
                      map_stroke,
                      map_background,
                      size_var,
                      color_var,
                      alpha_var,
                      x_var,
                      y_var,
                      heatmap_color,
                      filter_vars,
                      dimensions,
                      n_clicks):
    # Extract dimensions with fallbacks
    if dimensions and isinstance(dimensions, dict):
        width = dimensions.get('width')
        height = dimensions.get('height')
    else:
        width = None
        height = None

    # Use fallback dimensions if capture failed
    if width is None or width <= 0:
        width = 400  # Fallback width
    if height is None or height <= 0:
        height = 200  # Fallback height

    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'], utc=True,format='ISO8601')
    dv = DataVisualizer(df)
    spec = dv.create_chart(
        width=width,
        height=height,
        projection=projection,
        phi=phi,
        theta=theta,
        scale = scale,
        map_fill=map_fill,
        map_stroke=map_stroke,
        size_var=size_var,
        color_var=color_var,
        opacity_var=alpha_var,
        heatmap_x=x_var,
        heatmap_y=y_var,
        heatmap_color=heatmap_color,
        filter_vars=filter_vars,
        background = map_background,
    ).to_dict()
    return dvc.Vega(
        id='map',
        opt={"renderer": 'svg', 'actions': False},
        spec=spec
    )
