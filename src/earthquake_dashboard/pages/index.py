"""Quick start — implements the guide route of the redesign.

The content is the same ground the old page covered; what changed is the shape.
The redesign turns six numbered steps into a ruled grid and the reference
material into four short key/value groups, so the page reads as a card you scan
rather than a page you read top to bottom.
"""

import dash
from dash import dcc, html

dash.register_page(__name__, path='/', name='Quick start')

STEPS = [
    ('01', 'Set the query',
     'Date, magnitude, significance, depth and a lat/lon box. Defaults cover the past 30 days.'),
    ('02', 'Preview count',
     'Asks USGS how many events match and downloads nothing.'),
    ('03', 'Fetch data',
     'Pulls the matching records into the table, up to 20,000 per request, and draws '
     'the linked views from them.'),
    ('04', 'Filter the table',
     'Type into the table’s filter row and the chart redraws from the narrowed rows, '
     'not the full download.'),
    ('05', 'Move the map',
     'Projection, zoom, spin, tilt and roll redraw the map as you move them, without '
     'waiting on the server.'),
    ('06', 'Brush the views',
     'Drag across the map or either histogram — every other view narrows to the same '
     'selection.'),
]

GROUPS = [
    ('Map controls', [
        ('Projection', 'Fifteen, from gnomonic and orthographic to Mercator'),
        ('Spin / Tilt / Roll', 'Rotate the globe about each of its three axes'),
        ('Zoom', 'Scales the geography from 10 to 1000'),
    ]),
    ('The views', [
        ('Map', 'Points sized by magnitude, coloured by significance'),
        ('Histograms', 'Events per UTC day and per magnitude bin; grey bars are '
                       'the totals'),
        ('Heatmap', 'Day by depth, shaded by mean significance'),
    ]),
    ('Filtering', [
        ('Brush', 'Drag either histogram to filter every other view'),
        ('Map select', 'Drag across the globe to filter by location'),
        ('Clear', 'Click outside a brushed area to release it'),
    ]),
    ('Fields', [
        ('mag / sig', 'Magnitude and USGS significance score'),
        ('depth', 'Kilometres below sea level; negatives sit above'),
        ('cdi / alert', 'Reported shaking and PAGER alert level'),
    ]),
]

layout = html.Div([
    html.P('Quick start', className='guide-eyebrow'),
    html.H1('Query the USGS catalog, then brush it from any angle.'),
    html.P('Every view shares one set of Vega-Lite selections, so a brush drawn on the map '
           'or either histogram filters all the others. Capped at 20,000 records per '
           'request.', className='guide-lede'),

    html.Div([
        html.Div([
            html.Div(n, className='step-n'),
            html.Div(title, className='step-title'),
            html.Div(body, className='step-body'),
        ], className='step') for n, title, body in STEPS
    ], className='steps'),

    html.Div([
        html.Div([
            html.H3(title),
            *[html.Div([
                html.Span(k, className='guide-k'),
                html.Span(v, className='guide-v'),
            ], className='guide-row') for k, v in items],
        ]) for title, items in GROUPS
    ], className='guide-groups'),

    html.Div([
        dcc.Link(html.Button('Launch dashboard →', className='cta'), href='/dashboard'),
        html.Span(['data source · ',
                   html.A('USGS FDSN event API',
                          href='https://earthquake.usgs.gov/fdsnws/event/1/',
                          target='_blank')], className='guide-source'),
    ], className='guide-foot'),
], className='guide')
