from datetime import datetime, timedelta

import dash
import dash_vega_components as dvc
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from earthquake_dashboard.data_loader import (
    DEFAULT_WINDOW_DAYS,
    DT_FORMAT,
    HIDDEN_COLUMNS,
    DataLoader,
    RequestParams,
    utc_today,
)
from earthquake_dashboard.spec import CAMERA_PARAMS, refresh

dash.register_page(__name__)

# The redesign's palette, for the handful of places Dash insists on inline
# styles. Keep in step with the tokens at the top of assets/styles.css.
PANEL = '#1a1622'
FIELD = '#211b2b'
FIELD_EDGE = '#322a42'
RULE = '#241e30'
RULE_SOFT = '#201a2b'
INK_2 = '#d8cfe8'
INK_4 = '#938aa6'
MONO = "'JetBrains Mono', ui-monospace, monospace"

# The layout is assembled in one pass per page load (see the bottom of this file)
# rather than through a cascade of callbacks. The visualizer starts empty until
# the table has rows to chart.
def build_page():
    return [
        html.Div(build_loader(), id='loader', className='dashboard'),
        html.Div(build_visualizer(), id='visualizer', className='dashboard is-empty'),
    ]

def build_loader():
    return [
        html.Div(build_loader_control_panel(), id='loader_control_panel', className='control-panel',
                 **{'data-section': 'Query'}),
        html.Div(build_loader_output(), id='loader_output', className='dashboard-output',
                 **{'data-section': 'Loaded records'}),
    ]

def build_loader_output():
    loader_output = []
    loader_output.append(dash_table.DataTable(
            id = 'data_table',
            page_size=50,
            filter_action = 'native',
            sort_action = 'native',
            # These land as inline styles on the table's own elements, so they
            # beat assets/styles.css and have to carry the palette themselves.
            # Zebra striping is gone on purpose: the redesign separates rows with
            # a single hairline and leans on the hover state instead.
            style_table={
                'height': '38vh',
                'overflowY': 'auto',
            },
            style_data={
                'whiteSpace': 'normal',
                'height': 'auto',
                'backgroundColor': PANEL,
                'color': INK_2,
                'border': 'none',
                'borderBottom': f'1px solid {RULE_SOFT}',
            },
            style_cell={
                'textAlign': 'left',
                'wordBreak': 'break-word',
                'fontFamily': MONO,
                'fontSize': '12px',
                'padding': '9px 16px',
            },
            style_as_list_view=True,
            style_header={
                'backgroundColor': PANEL,
                'color': INK_4,
                'fontSize': '10px',
                'letterSpacing': '0.12em',
                'textTransform': 'uppercase',
                'fontWeight': '400',
                'border': 'none',
                'borderBottom': f'1px solid {RULE}',
            },
            style_data_conditional=[
                {'if': {'state': 'active'},
                 'backgroundColor': '#1f1929',
                 'border': f'1px solid {FIELD_EDGE}'},
            ],
            style_filter={
                'backgroundColor': FIELD,
                'color': INK_2,
                'border': 'none',
                'borderBottom': f'1px solid {RULE}',
            },
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
    # Read at render, in UTC. date.today() is the host's local day, and this
    # widget is labelled UTC; more to the point, the layout used to be built once
    # at import, so whichever day the server started on was the day the picker
    # showed until it was restarted -- on the hosted app, the deploy date.
    today = utc_today()
    widget.append(dcc.DatePickerRange(
        start_date=today - timedelta(days=DEFAULT_WINDOW_DAYS),
        # Tomorrow, not today: both dates read as 00:00 UTC, so an end date of
        # today would stop before today's events.
        end_date=today + timedelta(days=1),
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
    # The chart is a hand-written Vega-Lite template (specs/linked_views.vl.json)
    # rendered by one persistent component. Its own params -- projection, zoom,
    # rotation, magnitude bins -- are inputs that vega-embed draws into
    # #chart_controls and wires straight to the view, so moving them redraws in
    # the browser without a round trip. Dash only ever sends new rows.
    return [
        html.Div(build_visualizer_control_panel(), id='visualizer_control_panel',
                 className='control-panel', **{'data-section': 'Linked views'}),
        html.Div([
            html.Div('No rows to chart. Fetch Data, or loosen the table filter.',
                     className='chart-empty'),
            dvc.Vega(
                id='map',
                # The Dash id never reaches the DOM -- dash-vega-components renders
                # into a div with its own generated id -- so styles and figure
                # scripts find the chart by this class instead.
                className='linked-views',
                # Reported back on every change, so a data refresh -- which makes
                # dash-vega-components rebuild the view from scratch -- can reopen
                # it where the user left the camera.
                signalsToObserve=list(CAMERA_PARAMS),
                # Every slider tick otherwise reaches Dash 10 ms later, and each one
                # makes the component JSON-compare its whole spec -- megabytes at
                # the 20,000-row cap. Only the value a slider stops at matters.
                debounceWait=250,
                opt={'renderer': 'svg', 'actions': False, 'bind': '#chart_controls'},
            ),
        ], id='visualizer_output', className='dashboard-output visualization'),
        # A digest of the rows on screen, so a refresh that changes none of them
        # sends nothing. Compared on the server so the spec never travels back up.
        dcc.Store(id='chart_rows_digest'),
    ]

def build_visualizer_control_panel():
    return [
        html.Div([
            html.H5('How To Read'),
            html.Div('Drag across the map or either histogram to filter every panel.',
                     className='widget-help'),
            html.Div('Every control here redraws as you move it; new rows from the '
                     'table reset the brushes but keep the camera.',
                     className='widget-help'),
        ], id='visualizer_help', className='widget'),
        # vega-embed fills this with the template's bound params.
        html.Div(id='chart_controls', className='chart-controls'),
    ]

def table_columns(df) -> list[dict]:
    """The DataTable columns for a loaded frame."""
    return [{'name': col, 'id': col} for col in df.columns
            if col not in HIDDEN_COLUMNS]


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
        return df.to_dict('records'), table_columns(df)

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
    Output('map', 'spec'),
    Output('visualizer', 'className'),
    Output('chart_rows_digest', 'data'),
    Input('data_table', 'derived_virtual_data'),
    State('map', 'signalData'),
    State('chart_rows_digest', 'data'),
)
def update_visualizer(data, camera, last_digest):
    """Send the table's current rows to the chart, if they changed.

    derived_virtual_data is the table after its filter row and sort, so this
    fires on Fetch Data, Clear Table, and every filter or sort. Any new spec
    makes dash-vega-components rebuild the view and drop the brushes, so a sort
    -- same rows, new order -- must send nothing; see spec.refresh.
    """
    r = refresh(data, camera, last_digest)
    if r.empty:
        # dash-vega-components ignores an empty spec rather than clearing the
        # old view, so an emptied table hides the chart instead.
        return dash.no_update, 'dashboard is-empty', None
    if r.spec is None:
        return dash.no_update, 'dashboard', dash.no_update
    return r.spec, 'dashboard', r.digest


# A function, not a component. Dash Pages accepts either and calls this one on
# every page load, which is the whole point: as a module-level object it was
# evaluated once when the process started, and the date picker then showed that
# day's window for as long as the server lived. The browser still receives the
# whole control panel in the first response -- the builders all run here, not
# through a chain of callback round trips.
#
# id='layout' is load-bearing, not a leftover from the old callback chain:
# styles.css keys the page's outer header/loader/viz grid off it, along with
# the monospace font and the light text color every widget inherits.
#
# Dash passes the URL's query string as keyword arguments; this page reads none.
def layout(**_query_params):
    return html.Div(build_page(), id='layout')
