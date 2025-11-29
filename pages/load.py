import dash
from dash import html, dcc, callback, Input, Output, State
from datetime import date, timedelta
from DataLoader import DataLoader, RequestParams

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
    html.Button('Load', id='load_button', n_clicks = 0),
    html.Div(id='output_div')
])

@callback(
    Output('output_div', 'children'),
    State('date_range', 'start_date'),
    State('date_range', 'end_date'),
    Input('load_button', 'n_clicks')
)
def update_output(start_date, end_date, n_clicks):
    return (start_date, end_date)