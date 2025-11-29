import dash
from dash import html, dcc, callback, Input, Output
from datetime import date, timedelta

dash.register_page(__name__)

layout = html.Div([
    html.H1('Data Loader'),
    dcc.DatePickerRange(
        id = 'date_range',
        min_date_allowed=date(1900,1,1),
        max_date_allowed=date.today()+timedelta(days=1),
        initial_visible_month=date.today()-timedelta(days=30),
        end_date=date.today()+timedelta(days=1)
    )  
])