from datetime import date, datetime, timedelta

import dash
import dash_vega_components as dvc
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from earthquake_dashboard.data_loader import DT_FORMAT, DataLoader, RequestParams
from earthquake_dashboard.visualizer import DataVisualizer

dash.register_page(__name__)

# The layout is assembled once at import (see the bottom of this file) rather
# than through a cascade of callbacks. Only the three widgets whose dropdown
# options come from the loaded frame are still built by a callback.

def build_page():
    return [
        html.Div(build_loader(), id='loader', className='dashboard'),
        html.Div(build_visualizer(), id='visualizer', className='dashboard'),
    ]

def build_loader():
    return [
        html.Div(build_loader_control_panel(), id='loader_control_panel', className='control-panel'),
        html.Div(build_loader_output(), id='loader_output', className='dashboard-output'),
    ]

def build_loader_output():
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


def build_loader_control_panel():
    # Exactly eight children: .control-panel maps position to grid area through
    # :nth-child(1..8), so adding or removing one reshuffles the whole panel.
    return [
        html.Div(build_date_range(), id='date_range', className='widget date-widget'),
        html.Div(build_mag_range(), id='mag_range', className='widget slider-widget'),
        html.Div(build_sig_range(), id='sig_range', className='widget slider-widget'),
        html.Div(build_depth_range(), id='depth_range', className='widget slider-widget'),
        html.Div(build_latitude_range(), id='latitude_range', className='widget slider-widget'),
        html.Div(build_longitude_range(), id='longitude_range', className='widget slider-widget'),
        html.Div(build_loader_buttons(), id='loader_button_widget', className='widget button-widget'),
        html.Div([html.H5('Matching Events'), 'Press Preview Count'],
                 id='count_output', className='widget output-widget'),
    ]

def build_date_range():
    # h4 is the panel title, h5 a widget heading. This tile is plain block flow,
    # so it is the only loader slot that can carry the panel title without
    # adding a ninth child and shifting every grid area.
    widget = []
    widget.append(html.H4('Query USGS'))
    widget.append(html.H5('Date Range (UTC)'))
    widget.append(dcc.DatePickerRange(
        start_date=date.today()-timedelta(days=30),
        end_date=date.today()+timedelta(days=1),
        start_date_placeholder_text='From',
        end_date_placeholder_text='Up To',
        stay_open_on_select=False,
        id='date_range_picker',
        className='date_range_picker')
    )
    widget.append(html.Div(
        'Both dates read as 00:00 UTC, so the end date itself is not included.',
        className='widget-help'))
    return widget

def build_mag_range():
    widget = []
    widget.append(html.H5('Magnitude',
        title="Filters the event's preferred magnitude, usually moment magnitude."))
    widget.append(
        dcc.RangeSlider(
            min=0,
            max=10,
            step=.1,
            value=[2.0,9.1],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True, 'template': 'M {value}'},
            id='mag_range_slider',
            className='slider'
        )
    )
    return widget

def build_sig_range():
    widget = []
    widget.append(html.H5('Significance',
        title='USGS impact score combining magnitude, shaking and felt reports.'))
    widget.append(
        dcc.RangeSlider(
            min=0,
            max=3000,
            step=50,
            value=[0, 3000],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True, 'template': 'sig {value}'},
            id='sig_range_slider',
            className='slider'
        )
    )
    return widget

def build_depth_range():
    widget = []
    widget.append(html.H5('Depth',
        title='Kilometres below sea level; negative values sit above it.'))
    widget.append(
        dcc.RangeSlider(
            min=-100,
            max=1000,
            step=25,
            value=[-100, 1000],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True, 'template': '{value} km'},
            id='depth_range_slider',
            className='slider'
        )
    )
    return widget

def build_latitude_range():
    widget = []
    widget.append(html.H5('Latitude',
        title='South and north edges of the search box; pair it with Longitude.'))
    widget.append(
        dcc.RangeSlider(
            min=-90,
            max=90,
            step=1,
            value=[-90,90],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True, 'template': '{value}°'},
            id='latitude_range_slider',
            className='slider'
        )
    )
    return widget

def build_longitude_range():
    widget = []
    widget.append(html.H5('Longitude',
        title='West and east edges of the box; it cannot cross the date line.'))
    widget.append(
        dcc.RangeSlider(
            min=-180,
            max=180,
            step=1,
            value=[-180,180],
            marks=None,
            tooltip={'placement': 'bottom', 'always_visible': True, 'template': '{value}°'},
            id='longitude_range_slider',
            className='slider'
        )
    )
    return widget




def build_loader_buttons():
    widget = []
    # No heading here: .button-widget is a three-row grid holding exactly these
    # three buttons, so a fourth child would spill into an implicit row.
    widget.append(html.Button('Preview Count', id='count_button', className='button', n_clicks=0,
        title='Asks USGS how many events match. Downloads nothing.'))
    widget.append(html.Button('Fetch Data', id='load_button', className='button', n_clicks=0,
        title='Downloads the matching events, up to the 20,000 record limit.'))
    widget.append(html.Button('Clear Table', id='clear_button', className='button', n_clicks=0,
        title='Empties the table and resets the count.'))

    return widget

def build_visualizer():
    return [
        html.Div(build_visualizer_control_panel(), id='visualizer_control_panel',
                 className='control-panel'),
        html.Div(['Visualization'], id='visualizer_output',
                 className='dashboard-output visualization'),
        dcc.Store(id='visualizer_dimensions', data={'width': None, 'height': None}),
    ]

def build_visualizer_control_panel():
    # Exactly eight children, as in the loader panel. Slots 4, 5 and 6 start
    # empty: their dropdown options are derived from the loaded frame, so they
    # are the only tiles still filled in by a callback.
    return [
        html.Div(build_projection_widget(), id='projection_widget',
                 className='widget dropdown-widget'),
        html.Div(build_map_tools_widget(), id='map_tools_widget',
                 className='widget slider-widget'),
        html.Div(build_map_colors_widget(), id='map_colors_widget',
                 className='widget text-widget'),
        html.Div(id='map_aesthetics_widget', className='widget dropdown-widget'),
        html.Div(id='heatmap_aesthetics_widget', className='widget dropdown-widget'),
        html.Div(id='filter_widget', className='widget dropdown-widget'),
        # This tile exists to hold grid slot w7: without it the Render Chart
        # button shifts into w7. It carries the two behaviours nothing else
        # explains.
        html.Div([
            html.H5('How To Read'),
            html.Div('Drag across the map or any histogram to filter every panel.',
                     className='widget-help'),
            html.Div('Nothing redraws until you press Render Chart.',
                     className='widget-help'),
        ], id='visualizer_widget7', className='widget'),
        html.Div(build_viz_button_widget(), id='viz_button_widget',
                 className='widget button-widget'),
    ]

def build_projection_widget():
    widget = []
    # #projection_widget is overridden to a single column, so an extra child
    # cannot scramble label/control pairing — the panel title goes here.
    widget.append(html.H4('Chart Loaded Data'))
    widget.append(html.H5('Map Projection',
        title='Mercator clips near the poles and skews when the globe is tilted.'))
    widget.append(
        dcc.Dropdown(
            options = [{'label': 'Natural Earth', 'value': 'naturalEarth1'},
                       {'label': 'Azimuthal Equal-Area', 'value': 'azimuthalEqualArea'},
                       {'label': 'Mercator', 'value': 'mercator'}],
            value = 'naturalEarth1',
            id = 'projection_dropdown',
            className = 'dropdown'
        )
    )

    return widget

def build_map_tools_widget():
    widget = []
    widget.append(html.H5('Spin East-West:',
        title='Drag right and the map centre moves west.'))
    widget.append(dcc.Slider(
        min=-179.9,
        max=179.9,
        step = 1,
        value = 0,
        marks = None,
        tooltip={'placement': 'bottom', 'always_visible': True, 'template': '{value}°'},
        id='phi_slider',
        className='slider'
    ))
    widget.append(html.H5('Tilt North-South:',
        title='Drag right and the map centre moves south.'))
    widget.append(dcc.Slider(
        min=-89.9,
        max=89.9,
        step = 1,
        value = 0,
        marks = None,
        tooltip={'placement': 'bottom', 'always_visible': True, 'template': '{value}°'},
        id='theta_slider',
        className='slider'
    ))
    widget.append(html.H5('Zoom:',
        title='Zooms the geography; the panel keeps its size.'))
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

def build_map_colors_widget():
    widgets = []
    widgets.append(html.H5('Canvas Color:',
        title='Any CSS color; tints the whole figure, not just the globe.'))
    widgets.append(dcc.Input(
        value='rgb(26,26,26)',
        id='map_background',
        className='text_input'
    ))
    widgets.append(html.H5('Land Color:'))
    widgets.append(dcc.Input(
        value='#444488',
        id='map_fill',
        className='text_input'
    ))
    widgets.append(html.H5('Border Color:',
        title='Country outlines only; the lat/lon grid keeps its default color.'))
    widgets.append(dcc.Input(
        value='darkblue',
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
    widget.append(html.H5('Point Size:',
        title='Scales each dot by area, 10 to 200 px.'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'sig',
        id='size_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Point Color:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'mag',
        id='color_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Point Opacity:'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'mag',
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
    widget.append(html.H5('Bin Across (X):'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'time',
        id='x_dropdown',
        className='dropdown'
    ))
    widget.append(html.H5('Bin Down (Y):',
        title='Depth flips the axis; time always bins by whole years.'))
    widget.append(dcc.Dropdown(
        options=cols,
        value = 'depth',
        id='y_dropdown',
        className='dropdown'
    ))
    # 'Cell Metric' rather than a second 'Color:' — this picks the statistic the
    # cell color reports, not a column like the map's Point Color.
    widget.append(html.H5('Cell Metric:',
        title='The statistic each cell color reports for the quakes inside it.'))
    widget.append(dcc.Dropdown(
        options=[{'label': 'Max magnitude', 'value': 'max(mag)'},
                 {'label': 'Mean depth', 'value': 'mean(depth)'},
                 {'label': 'Magnitude (unaggregated)', 'value': 'mag'}],
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
    widget.append(html.H5('Histograms:',
        title='Each variable you pick gets a histogram you can drag to filter.'))
    widget.append(dcc.Dropdown(
        multi=True,
        options=cols,
        value=['time', 'mag', 'depth'],
        placeholder='Pick variables to brush',
        id='filter_dropdown',
        className='dropdown multi-dropdown'
    ))

    return widget
def build_viz_button_widget():
    widget = []
    widget.append(html.H5('Apply Settings',
        title='Every control above is read fresh at the moment you click.'))
    widget.append(html.Button('Render Chart', id='viz_button', className='button'))
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
        return (pd.DataFrame().to_dict('records'),
                [html.H5('Matching Events'), 'Press Preview Count'])

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
        n = dl.count()
        msg = f'{n:,} events match'
        if n > 20000:
            msg = f'{n:,} events match - over the 20,000 limit, narrow your filters'
        return [html.H5('Matching Events'), msg] 


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

    # This callback also fires when the Store is first created, before any data is loaded.
    if not data:
        raise PreventUpdate

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


# Built once at import. Dash reads this after every builder above is defined,
# so the browser receives the whole control panel in the first response instead
# of assembling it through a chain of callback round trips.
#
# id='layout' is load-bearing, not a leftover from the old callback chain:
# styles.css keys the page's outer header/loader/viz grid off it, along with
# the monospace font and the light text color every widget inherits.
layout = html.Div(build_page(), id='layout')
