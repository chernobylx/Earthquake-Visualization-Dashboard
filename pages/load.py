import dash
from dash import html, dcc, callback, Input, Output, State
from datetime import datetime, date, timedelta
from DataLoader import DataLoader, RequestParams, DT_FORMAT

dash.register_page(__name__)

layout = html.Div([
    html.H1('Data Loader'),
    dcc.DatePickerRange(
        id = 'date_range',
        min_date_allowed=date(1900,1,1),
        max_date_allowed=date.today()+timedelta(days=1),
        initial_visible_month=date.today()-timedelta(days=30),
        end_date=date.today()+timedelta(days=1)
    ),
    html.Div(
        [dcc.RangeSlider(
            min=0,
            max=10,
            step=.1,
            value=[6,9.1],
            marks = None,
            tooltip = {"placement": "bottom", "always_visible": True},
            id = 'mag_range',
        )],
        style = {'width': '200px'},
    ),

    html.Button('Load', id='load_button', n_clicks = 0),

    html.Div(id='output_div')
])

@callback(
    Output('output_div', 'children'),
    State('date_range', 'start_date'),
    State('date_range', 'end_date'),
    State('mag_range', 'value'),
    Input('load_button', 'n_clicks'),
    prevent_initial_call=True
)
def update_output(start_date, end_date, 
                  magrange,
                  n_clicks):
    format = "%Y-%m-%d"
    start_time = datetime.strptime(start_date, format)
    start_time = datetime.strftime(start_time, DT_FORMAT)
    end_time = datetime.strptime(end_date, format)
    end_time = datetime.strftime(end_time, DT_FORMAT)

    params = RequestParams(starttime=start_time, endtime=end_time, minmagnitude=5)
    dl = DataLoader(params)
    return dl.count()